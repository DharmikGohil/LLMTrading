"""The trading loop: analyse -> plan -> risk-check -> execute -> monitor.

The bot only manages quantity it bought itself (tracked in
<data_dir>/bot_state.json), so manual holdings in the same demat account are
never sold by it.
"""

from __future__ import annotations

import csv
import json
import logging
import time
from datetime import date, datetime

from indtrader import data as market_data
from indtrader.brokers import Broker, Order, OrderResult
from indtrader.config import Settings
from indtrader.market import IST, previous_trading_day, round_to_tick
from indtrader.notify import notify
from indtrader.risk import AccountView, check_buy, check_sell
from indtrader.signals.llm_agent import SignalStore, TradingAgentsAnalyzer
from indtrader.signals.technical import snapshot
from indtrader.strategy import plan_target, protective_levels

log = logging.getLogger(__name__)


class BotState:
    def __init__(self, path):
        self.path = path
        self.data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        self.data.setdefault("positions", {})   # symbol -> {qty, avg, stop, target, opened}
        self.data.setdefault("pending", [])     # open live orders awaiting fills
        self.data.setdefault("day", {})
        self.data.setdefault("stopped_out", {})  # symbol -> date of last stop-loss exit

    def save(self) -> None:
        self.path.write_text(json.dumps(self.data, indent=2), encoding="utf-8")

    @property
    def positions(self) -> dict:
        return self.data["positions"]

    def qty(self, symbol: str) -> int:
        return int(self.positions.get(symbol, {}).get("qty", 0))

    def apply_fill(self, symbol: str, side: str, qty: int, price: float, stop=None, target=None) -> None:
        pos = self.positions.setdefault(symbol, {"qty": 0, "avg": 0.0, "stop": None, "target": None,
                                                 "opened": datetime.now(IST).date().isoformat()})
        if side == "BUY":
            total = pos["qty"] + qty
            pos["avg"] = round((pos["qty"] * pos["avg"] + qty * price) / total, 2)
            pos["qty"] = total
            pos["stop"] = stop if stop is not None else pos["stop"]
            pos["target"] = target if target is not None else pos["target"]
        else:
            pos["qty"] = max(0, pos["qty"] - qty)
            if pos["qty"] == 0:
                del self.positions[symbol]


class Engine:
    def __init__(self, settings: Settings, broker: Broker, analyzer: TradingAgentsAnalyzer | None = None):
        self.s = settings
        self.broker = broker
        self.analyzer = analyzer
        self.store = SignalStore(settings.path("signals", "_").parent)
        self.state = BotState(settings.path("bot_state.json"))
        self.journal = settings.path("trades.csv")

    # ---------------------------------------------------------------- analysis
    def analyze_universe(self, today: date, force: bool = False) -> dict:
        """Run TradingAgents for every symbol on data up to the previous close."""
        as_of = previous_trading_day(today, self.s.holidays)
        analyzer = self.analyzer or TradingAgentsAnalyzer(self.s)
        portfolio = self._portfolio_context()
        out = {}
        for sym in self.s.universe:
            try:
                out[sym] = analyzer.analyze(sym, as_of, portfolio=portfolio, force=force)
            except Exception as exc:
                log.exception("analysis failed for %s", sym)
                notify(f"[indtrader] analysis failed for {sym}: {exc}")
        notify("[indtrader] analysis " + as_of.isoformat() + ": "
               + ", ".join(f"{k}={v.rating}" for k, v in out.items()))
        return out

    def _portfolio_context(self) -> dict:
        return {
            "cash": self.broker.funds(),
            "currency": "INR",
            "positions": [{"ticker": f"{s}.NS" if self.s.exchange == "NSE" else f"{s}.BO",
                           "quantity": p["qty"], "average_price": p["avg"]}
                          for s, p in self.state.positions.items()],
        }

    # ---------------------------------------------------------------- execution
    def _account(self, prices: dict[str, float]) -> AccountView:
        exposure = sum(p["qty"] * prices.get(s, p["avg"]) for s, p in self.state.positions.items())
        # the bot may only use `capital`, even if the account holds more
        cash = min(self.broker.funds(), max(self.s.risk.capital - exposure, 0.0))
        today = datetime.now(IST).date().isoformat()
        day = self.state.data["day"]
        if day.get("date") != today:
            day.clear()
            day.update({"date": today, "start_equity": cash + exposure, "orders": 0})
            self.state.save()
        return AccountView(cash, cash + exposure, day["start_equity"], exposure,
                           sum(1 for p in self.state.positions.values() if p["qty"]), day["orders"])

    def _limit_price(self, side: str, ltp: float) -> float:
        buf = self.s.risk.limit_buffer_pct
        return round_to_tick(ltp * (1 + buf) if side == "BUY" else ltp * (1 - buf), side=side)

    def _send(self, symbol: str, side: str, qty: int, ltp: float, reason: str, stop=None, target=None) -> OrderResult:
        order = Order(symbol=symbol, side=side, quantity=qty, order_type="LIMIT",
                      price=self._limit_price(side, ltp), product=self.s.broker.product,
                      exchange=self.s.exchange, reason=reason, tag=self.s.broker.strategy_tag)
        if self.s.dry_run:
            result = OrderResult("DRY", "DRY_RUN", message="dry run")
        else:
            result = self.broker.place_order(order)
            self.state.data["day"]["orders"] = self.state.data["day"].get("orders", 0) + 1
            if result.status == "OPEN":
                result = self._await_fill(result)
            if result.status == "COMPLETE":
                self.state.apply_fill(symbol, side, result.filled_qty, result.avg_price or order.price, stop, target)
            elif result.status == "OPEN":
                self.state.data["pending"].append({"order_id": result.order_id, "symbol": symbol, "side": side,
                                                   "stop": stop, "target": target})
        self.state.save()
        self._log_trade(order, result)
        notify(f"[indtrader] {side} {qty} {symbol} @ ~{order.price} -> {result.status} {result.message} ({reason})")
        return result

    def _await_fill(self, result: OrderResult, timeout_s: float = 30, poll_s: float = 2) -> OrderResult:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            st = self.broker.order_status(result.order_id)
            if st and st.status in ("COMPLETE", "REJECTED"):
                return st
            time.sleep(poll_s)
        return result

    def reconcile_pending(self) -> None:
        """Apply fills of live orders that completed after we stopped waiting."""
        still = []
        for p in self.state.data["pending"]:
            st = self.broker.order_status(p["order_id"])
            if st and st.status == "COMPLETE":
                self.state.apply_fill(p["symbol"], p["side"], st.filled_qty, st.avg_price or 0.0, p["stop"], p["target"])
            elif not st or st.status == "OPEN":
                still.append(p)
        self.state.data["pending"] = still
        # never believe we hold more than the broker says
        broker_pos = self.broker.positions()
        for sym in list(self.state.positions):
            have = broker_pos.get(sym).quantity if sym in broker_pos else 0
            if have < self.state.qty(sym):
                log.warning("%s: bot thinks %d, broker has %d; adjusting", sym, self.state.qty(sym), have)
                self.state.apply_fill(sym, "SELL", self.state.qty(sym) - have, 0.0)
        self.state.save()

    def _log_trade(self, order: Order, result: OrderResult) -> None:
        new = not self.journal.exists()
        with self.journal.open("a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if new:
                w.writerow(["time", "symbol", "side", "qty", "limit", "status", "fill_qty", "fill_price", "order_id", "reason", "message"])
            w.writerow([datetime.now(IST).isoformat(timespec="seconds"), order.symbol, order.side, order.quantity,
                        order.price, result.status, result.filled_qty, result.avg_price, result.order_id,
                        order.reason, result.message])

    def rebalance(self, today: date) -> list[dict]:
        """Turn the latest signals into orders. Sells first, then buys."""
        self.reconcile_pending()
        as_of = previous_trading_day(today, self.s.holidays)
        symbols = sorted(set(self.s.universe) | set(self.state.positions))
        prices = self.broker.ltp(symbols, self.s.exchange)
        acct = self._account(prices)
        capital = min(self.s.risk.capital, acct.equity)
        plans = []
        for sym in symbols:
            sig = self.store.latest(sym, as_of.isoformat())
            if sig and (as_of - date.fromisoformat(sig.as_of)).days > self.s.strategy.max_signal_age_days:
                sig = None
            try:
                hist = market_data.recent_history(sym, as_of, exchange=self.s.exchange)
                tech = snapshot(hist, self.s.strategy.trend_ema, self.s.strategy.atr_period)
            except Exception as exc:
                log.warning("%s: no technicals (%s); skipping", sym, exc)
                continue
            if sym not in prices:
                continue
            plan = plan_target(sym, sig.rating if sig else None, prices[sym], tech, self.state.qty(sym), capital,
                               self.s.strategy, self.s.risk,
                               sig.stop_loss if sig else None, sig.price_target if sig else None)
            # trail the stop of an existing position (never lower it)
            pos = self.state.positions.get(sym)
            if pos and pos.get("stop"):
                trail, _ = protective_levels(prices[sym], tech, self.s.strategy)
                pos["stop"] = max(pos["stop"], trail)
            plans.append((plan, tech, prices[sym]))
        self.state.save()

        executed = []
        for plan, tech, ltp in sorted(plans, key=lambda x: x[0].target_qty - self.state.qty(x[0].symbol)):
            held = self.state.qty(plan.symbol)
            delta = plan.target_qty - held
            log.info("%s: %s", plan.symbol, "; ".join(plan.notes))
            if delta < 0:
                d = check_sell(-delta, held)
                if d.allowed:
                    self._send(plan.symbol, "SELL", d.quantity, ltp, "; ".join(plan.notes))
                    executed.append({"symbol": plan.symbol, "side": "SELL", "qty": d.quantity})
            elif delta > 0:
                last_stop = self.state.data["stopped_out"].get(plan.symbol)
                if last_stop and (today - date.fromisoformat(last_stop)).days < self.s.strategy.reentry_cooldown_days:
                    log.info("%s: buy skipped, stopped out on %s (cooldown)", plan.symbol, last_stop)
                    continue
                acct = self._account(prices)
                d = check_buy(plan.symbol, delta, ltp, held, acct, self.s.risk, analysed_close=tech.close)
                if d.allowed:
                    self._send(plan.symbol, "BUY", d.quantity, ltp, "; ".join(plan.notes), plan.stop, plan.take_profit)
                    executed.append({"symbol": plan.symbol, "side": "BUY", "qty": d.quantity})
                else:
                    log.info("%s: buy blocked: %s", plan.symbol, d.reason)
        return executed

    def monitor(self) -> list[dict]:
        """Exit positions that hit their stop-loss or take-profit."""
        self.reconcile_pending()
        if not self.state.positions:
            return []
        prices = self.broker.ltp(list(self.state.positions), self.s.exchange)
        exits = []
        for sym, pos in list(self.state.positions.items()):
            ltp = prices.get(sym)
            if ltp is None:
                continue
            if pos.get("stop") and ltp <= pos["stop"]:
                reason = f"stop-loss hit ({ltp:.2f} <= {pos['stop']})"
            elif pos.get("target") and ltp >= pos["target"]:
                reason = f"target hit ({ltp:.2f} >= {pos['target']})"
            else:
                continue
            result = self._send(sym, "SELL", pos["qty"], ltp, reason)
            if reason.startswith("stop") and result.status in ("COMPLETE", "OPEN"):
                self.state.data["stopped_out"][sym] = datetime.now(IST).date().isoformat()
                self.state.save()
            exits.append({"symbol": sym, "reason": reason})
        return exits

    def square_off_intraday(self) -> None:
        """MIS positions must be closed before the broker's auto square-off (~15:20)."""
        if self.s.broker.product != "MIS":
            return
        prices = self.broker.ltp(list(self.state.positions), self.s.exchange) if self.state.positions else {}
        for sym, pos in list(self.state.positions.items()):
            self._send(sym, "SELL", pos["qty"], prices.get(sym, pos["avg"]), "intraday square-off")

    def status(self) -> dict:
        symbols = list(self.state.positions)
        prices = self.broker.ltp(symbols, self.s.exchange) if symbols else {}
        rows = []
        for s, p in self.state.positions.items():
            ltp = prices.get(s, p["avg"])
            rows.append({**p, "symbol": s, "ltp": ltp, "unrealized": round((ltp - p["avg"]) * p["qty"], 2)})
        return {"broker": self.broker.name, "funds": self.broker.funds(), "positions": rows,
                "pending": self.state.data["pending"], "day": self.state.data["day"]}

