"""The trading loop: analyse -> plan -> risk-check -> execute -> monitor.

The bot only manages quantity it bought itself (tracked in
<data_dir>/bot_state.json), so manual holdings in the same demat account are
never sold by it. It also keeps its own cash ledger (capital + realised P&L -
cost of open positions - charges), so it never spends more than `risk.capital`
plus what it has made, and the daily-loss kill switch sees its real P&L even
when the broker account holds more money.
"""

from __future__ import annotations

import csv
import json
import logging
import math
import time
from datetime import date, datetime

from indtrader import data as market_data
from indtrader.brokers import Broker, Order, OrderResult
from indtrader.brokers.base import TERMINAL
from indtrader.config import SecondOpinionSettings, Settings
from indtrader.market import now_ist, previous_trading_day, round_to_tick
from indtrader.notify import notify
from indtrader.risk import AccountView, check_buy, check_sell
from indtrader.signals.llm_agent import SignalStore, TradingAgentsAnalyzer
from indtrader.signals.technical import is_bear_market, snapshot
from indtrader.strategy import BULLISH, combine_opinions, plan_target, protective_levels, vol_scale

log = logging.getLogger(__name__)


def _valid_price(p) -> bool:
    return isinstance(p, int | float) and math.isfinite(p) and p > 0


class BotState:
    def __init__(self, path, capital: float):
        self.path = path
        self.data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        self.data.setdefault("positions", {})    # symbol -> {qty, avg, stop, target, opened}
        self.data.setdefault("pending", [])      # live orders not yet final
        self.data.setdefault("day", {})
        self.data.setdefault("stopped_out", {})  # symbol -> date of last stop-loss exit
        self.data.setdefault("realized_pnl", 0.0)
        if "cash" not in self.data:
            invested = sum(p["qty"] * p["avg"] for p in self.positions.values())
            self.data["cash"] = capital - invested
            self.data["capital"] = capital
        if self.data.get("capital") != capital:   # capital changed in config: move the difference in/out
            self.data["cash"] += capital - self.data.get("capital", capital)
            self.data["capital"] = capital

    def save(self) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=2), encoding="utf-8")
        tmp.replace(self.path)                     # atomic: a crash never leaves half a file

    @property
    def positions(self) -> dict:
        return self.data["positions"]

    @property
    def cash(self) -> float:
        return float(self.data["cash"])

    def qty(self, symbol: str) -> int:
        return int(self.positions.get(symbol, {}).get("qty", 0))

    def pending_for(self, symbol: str, side: str | None = None) -> list[dict]:
        return [p for p in self.data["pending"] if p["symbol"] == symbol and (side is None or p["side"] == side)]

    def apply_fill(self, symbol: str, side: str, qty: int, price: float, charges: float = 0.0,
                   stop=None, target=None) -> None:
        if qty <= 0:
            return
        if side == "BUY":
            pos = self.positions.setdefault(symbol, {"qty": 0, "avg": 0.0, "stop": None, "target": None,
                                                     "opened": now_ist().date().isoformat()})
            total = pos["qty"] + qty
            pos["avg"] = round((pos["qty"] * pos["avg"] + qty * price) / total, 2)
            pos["qty"] = total
            if stop is not None:   # adding must never loosen a trailed stop
                pos["stop"] = max(pos["stop"], stop) if pos.get("stop") else stop
            if target is not None:
                pos["target"] = target
            pos["buy_charges"] = pos.get("buy_charges", 0.0) + charges   # realised when sold
            self.data["cash"] -= qty * price + charges
        else:
            pos = self.positions.get(symbol)
            if not pos:
                return
            qty = min(qty, pos["qty"])
            buy_charges = pos.get("buy_charges", 0.0) * qty / pos["qty"]
            pos["buy_charges"] = pos.get("buy_charges", 0.0) - buy_charges
            self.data["realized_pnl"] += qty * (price - pos["avg"]) - charges - buy_charges
            self.data["cash"] += qty * price - charges
            pos["qty"] -= qty
            if pos["qty"] == 0:
                del self.positions[symbol]


class Engine:
    def __init__(self, settings: Settings, broker: Broker, analyzer: TradingAgentsAnalyzer | None = None):
        self.s = settings
        self.broker = broker
        self.analyzer = analyzer
        self.store = SignalStore(settings.signals_root)
        self.vibe_store = SignalStore(settings.path("signals_vibe", "_").parent)
        self.vibe = None  # VibeTradingAnalyzer, created lazily
        self.state = BotState(settings.path("bot_state.json"), settings.risk.capital)
        self.journal = settings.path("trades.csv")
        self.fill_timeout_s = 30.0   # how long _send waits for a live order to fill before tracking it as pending
        self._screen_cache: dict[str, object] = {}
        self._nse = None

    # ---------------------------------------------------------------- india data
    @property
    def nse(self):
        if self._nse is None:
            from indtrader.nse import NSEData, NullNSE

            self._nse = (NSEData(self.s.path("nse", "_").parent, now_ist().date())
                         if self.s.nse_checks else NullNSE())
        return self._nse

    def screen_table(self, as_of: date):
        """Full momentum ranking of the configured index on data up to `as_of` (cached per day)."""
        import pandas as pd

        key = as_of.isoformat()
        if key in self._screen_cache:
            return self._screen_cache[key]
        f = self.s.path("screen", f"{key}.json")
        if f.exists():
            table = pd.read_json(f)
        else:
            from datetime import timedelta

            from indtrader.screen import download_closes, index_members, score_universe

            sc = self.s.screen
            members = index_members(sc.index, self.s.path("universe", "_").parent)
            table = score_universe(download_closes(members, as_of - timedelta(days=420), as_of), as_of,
                                   min_traded_value_cr=sc.min_traded_value_cr,
                           vol_exclude_pct=sc.vol_exclude_pct, trend_template_required=sc.trend_template)
            table.to_json(f)
        self._screen_cache[key] = table
        return table

    def _entry_blockers(self, symbol: str, today: date) -> str | None:
        """Hard reasons not to open/add a position (never blocks sells)."""
        st = self.s.strategy
        if st.avoid_surveillance:
            if reason := self.nse.surveillance().get(symbol):
                return f"under surveillance: {reason}"
            series = self.nse.series().get(symbol)
            if series and series[0] != "EQ":
                return f"series {series[0]} (trade-for-trade)"
        if sectors := self._sectors():
            sector = sectors.get(symbol)
            same = [s for s in self.state.positions if s != symbol and sectors.get(s) == sector]
            if sector and symbol not in self.state.positions and len(same) >= self.s.risk.max_per_sector:
                return f"sector cap: already {len(same)} in {sector} ({', '.join(same)})"
        if st.results_blackout_days > 0:
            lookup = getattr(self.nse, "results_dates_for", None)
            for d in (lookup(symbol) if lookup else self.nse.results_dates().get(symbol, [])):
                if 0 <= (d - today).days <= st.results_blackout_days:
                    return f"results board meeting on {d} (blackout {st.results_blackout_days}d)"
        return None

    def _sectors(self) -> dict[str, str]:
        from indtrader.screen import industries

        try:
            return industries(self.s.screen.index, self.s.path("universe", "_").parent)
        except Exception as exc:
            log.warning("sector map unavailable: %s", exc)
            return {}

    def apply_corporate_actions(self, today: date) -> None:
        """Rescale held quantity and prices on split/bonus ex-dates, so a split never fires a false stop."""
        from indtrader.nse import adjustment_factor

        if not self.state.positions:
            return
        done = self.state.data.setdefault("ca_applied", [])
        for ca in self.nse.corporate_actions(today, today):
            sym, ex = ca.get("symbol"), ca.get("exDate")
            key = f"{sym}:{ex}"
            if sym not in self.state.positions or key in done:
                continue
            try:
                if datetime.strptime(ex, "%d-%b-%Y").date() != today:
                    continue
            except (TypeError, ValueError):
                continue
            factor = adjustment_factor(ca.get("subject", ""))
            if not factor:
                continue
            pos = self.state.positions[sym]
            pos["qty"] = int(round(pos["qty"] * factor))
            for k in ("avg", "stop", "target"):
                if pos.get(k):
                    pos[k] = round(pos[k] / factor, 2)
            done.append(key)
            notify(f"[indtrader] {sym}: {ca.get('subject')} -> qty x{factor:g}, prices /{factor:g}")
        self.state.save()

    # ---------------------------------------------------------------- analysis
    def analyze_universe(self, today: date, force: bool = False) -> dict:
        """Run TradingAgents for every symbol on data up to the previous close
        (or, with llm.signal_source=external, just report the signals delivered)."""
        as_of = previous_trading_day(today, self.s.holidays)
        if self.s.llm.signal_source == "external":
            self.sync_signals()
            wanted = self.analysis_symbols(as_of)
            found = {sym: sig for sym in wanted if (sig := self.store.get(sym, as_of.isoformat()))}
            missing = [sym for sym in wanted if sym not in found]
            notify(f"[indtrader] external signals {as_of}: "
                   + (", ".join(f"{k}={v.rating}({v.confidence})" for k, v in found.items()) or "none")
                   + (f"; missing: {', '.join(missing)}" if missing else ""))
            if self.s.second_opinion.enabled:
                self._second_opinions(found, as_of)
            return found
        analyzer = self.analyzer or TradingAgentsAnalyzer(self.s)
        portfolio = self._portfolio_context()
        out = {}
        for sym in self.analysis_symbols(as_of):
            try:
                out[sym] = analyzer.analyze(sym, as_of, portfolio=portfolio, force=force)
            except Exception as exc:
                log.exception("analysis failed for %s", sym)
                notify(f"[indtrader] analysis failed for {sym}: {exc}")
        if self.s.second_opinion.enabled:
            self._second_opinions(out, as_of)
        notify("[indtrader] analysis " + as_of.isoformat() + ": "
               + ", ".join(f"{k}={v.rating}" for k, v in out.items()))
        return out

    def analysis_symbols(self, as_of: date) -> list[str]:
        """What the LLM should review: the fixed universe (llm mode) or the screen's top N plus holdings."""
        mode = self.s.strategy.signal_mode
        if mode == "llm":
            return list(self.s.universe)
        held = list(self.state.positions)
        if mode == "factor":
            return held
        table = self.screen_table(as_of)
        top = list(table[table["eligible"]].head(self.s.screen.top_n)["symbol"])
        return list(dict.fromkeys(top + held))

    def sync_signals(self) -> None:
        """Pull signals committed by the external analyst (signal_sync: git)."""
        if self.s.signal_sync != "git":
            return
        import subprocess

        proc = subprocess.run(["git", "pull", "--ff-only", "--quiet"], capture_output=True, text=True, timeout=120)
        if proc.returncode != 0:
            log.warning("git pull failed: %s", proc.stderr.strip())
            notify(f"[indtrader] WARNING: could not pull signals: {proc.stderr.strip()[:300]}")

    def _second_opinions(self, primary: dict, as_of: date) -> None:
        from indtrader.signals.vibe_opinion import VibeTradingAnalyzer

        self.vibe = self.vibe or VibeTradingAnalyzer(self.s)
        for sym, sig in primary.items():
            if self.s.second_opinion.only_when_bullish and sig.rating not in BULLISH:
                continue
            try:
                second = self.vibe.analyze(sym, as_of)
                notify(f"[indtrader] {sym}: TradingAgents={sig.rating}, Vibe-Trading={second.rating} ({second.confidence})")
            except Exception as exc:
                log.exception("second opinion failed for %s", sym)
                notify(f"[indtrader] second opinion failed for {sym}: {exc}")

    def _portfolio_context(self) -> dict:
        return {
            "cash": max(min(self.broker.funds(), self.state.cash), 0.0),
            "currency": "INR",
            "positions": [{"ticker": f"{s}.NS" if self.s.exchange == "NSE" else f"{s}.BO",
                           "quantity": p["qty"], "average_price": p["avg"]}
                          for s, p in self.state.positions.items()],
        }

    # ---------------------------------------------------------------- accounting
    def _prices(self, symbols) -> dict[str, float]:
        if not symbols:
            return {}
        try:
            raw = self.broker.ltp(sorted(symbols), self.s.exchange)
        except Exception as exc:
            log.warning("bulk quote failed (%s); fetching one by one", exc)
            raw = {}
            for sym in symbols:
                try:
                    raw.update(self.broker.ltp([sym], self.s.exchange))
                except Exception as exc2:
                    log.warning("%s: no quote (%s)", sym, exc2)
        return {s: float(p) for s, p in raw.items() if _valid_price(p)}

    def _account(self, prices: dict[str, float]) -> AccountView:
        """Bot account view; also rolls the daily counters over on the first call of a day."""
        exposure = sum(p["qty"] * prices.get(s, p["avg"]) for s, p in self.state.positions.items())
        pending_buys = sum(p.get("qty", 0) * p.get("price", 0) for p in self.state.data["pending"] if p["side"] == "BUY")
        ledger = self.state.cash
        equity = ledger + exposure
        today = now_ist().date().isoformat()
        day = self.state.data["day"]
        if day.get("date") != today:
            day.clear()
            day.update({"date": today, "start_equity": round(equity, 2), "orders": 0})
            self.state.save()
        # spendable = what the bot's ledger allows AND what the broker actually has
        cash = max(min(self.broker.funds(), ledger - pending_buys), 0.0)
        return AccountView(cash, equity, day["start_equity"], exposure + pending_buys,
                           len({s for s, p in self.state.positions.items() if p["qty"]}
                               | {p["symbol"] for p in self.state.data["pending"] if p["side"] == "BUY"}),
                           day["orders"])

    def _limit_price(self, side: str, ltp: float) -> float:
        buf = self.s.risk.limit_buffer_pct
        return round_to_tick(ltp * (1 + buf) if side == "BUY" else ltp * (1 - buf), side=side)

    # ---------------------------------------------------------------- orders
    @property
    def halted(self) -> bool:
        """Kill switch: while <data_dir>/HALT exists no order of any kind is sent."""
        return self.s.path("HALT").exists()

    def _charges(self, side: str, qty: int, price: float) -> float:
        return self.s.cost_model.charges(side, qty, price, self.s.broker.product)

    def _apply_result(self, symbol: str, side: str, result: OrderResult, fallback_price: float, stop, target) -> None:
        if result.filled_qty > 0:   # complete, or partially filled then cancelled/rejected
            px = result.avg_price or fallback_price
            self.state.apply_fill(symbol, side, result.filled_qty, px, self._charges(side, result.filled_qty, px),
                                  stop, target)

    def _send(self, symbol: str, side: str, qty: int, ltp: float, reason: str, stop=None, target=None) -> OrderResult:
        if self.halted:
            log.warning("HALT file present: not sending %s %d %s", side, qty, symbol)
            return OrderResult("", "REJECTED", message="halted")
        order = Order(symbol=symbol, side=side, quantity=qty, order_type="LIMIT",
                      price=self._limit_price(side, ltp), product=self.s.broker.product,
                      exchange=self.s.exchange, reason=reason, tag=self.s.broker.strategy_tag)
        if self.s.dry_run:
            result = OrderResult("DRY", "DRY_RUN", message="dry run")
        else:
            self.state.data["day"]["orders"] = self.state.data["day"].get("orders", 0) + 1
            result = self.broker.place_order(order)
            if result.status == "UNKNOWN":
                found = self.broker.find_order(symbol, side, order.tag)
                result = found or result
            if result.status == "OPEN":
                result = self._await_fill(result, self.fill_timeout_s)
            if result.status in TERMINAL:
                self._apply_result(symbol, side, result, order.price, stop, target)
            elif result.status in ("OPEN", "UNKNOWN"):
                self.state.data["pending"].append({
                    "order_id": result.order_id or None, "symbol": symbol, "side": side, "qty": qty,
                    "price": order.price, "stop": stop, "target": target, "tag": order.tag,
                    "placed": now_ist().date().isoformat()})
                if result.status == "UNKNOWN":
                    notify(f"[indtrader] WARNING: {side} {qty} {symbol} status unknown ({result.message}); "
                           "check the broker order book. No new orders for this stock until it is resolved.")
        self.state.save()
        self._log_trade(order, result)
        notify(f"[indtrader] {side} {qty} {symbol} @ ~{order.price} -> {result.status} {result.message} ({reason})")
        return result

    def _await_fill(self, result: OrderResult, timeout_s: float = 30, poll_s: float = 2) -> OrderResult:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            try:
                st = self.broker.order_status(result.order_id)
            except Exception as exc:
                log.warning("order status failed (%s)", exc)
                st = None
            if st and st.status in TERMINAL:
                return st
            time.sleep(poll_s)
        return result

    def reconcile_pending(self) -> None:
        """Apply fills of orders that finished after we stopped waiting, then
        make sure the bot never believes it holds more than the broker does."""
        still = []
        today = now_ist().date().isoformat()
        for p in self.state.data["pending"]:
            try:
                if not p.get("order_id"):
                    st = self.broker.find_order(p["symbol"], p["side"], p.get("tag", self.s.broker.strategy_tag))
                    if st is None:
                        if p.get("placed", today) < today:
                            notify(f"[indtrader] dropping unresolved {p['side']} {p['symbol']} from {p.get('placed')}")
                            continue
                        still.append(p)
                        continue
                    p["order_id"] = st.order_id
                    if st.status not in TERMINAL:
                        st = self.broker.order_status(st.order_id) or st
                else:
                    st = self.broker.order_status(p["order_id"])
            except Exception as exc:
                log.warning("could not check order %s (%s)", p.get("order_id"), exc)
                still.append(p)
                continue
            if st and st.status in TERMINAL:
                self._apply_result(p["symbol"], p["side"], st, p.get("price") or 0.0, p.get("stop"), p.get("target"))
            else:
                still.append(p)
        self.state.data["pending"] = still

        try:
            broker_pos = self.broker.positions()
        except Exception as exc:
            log.warning("could not read broker positions (%s); skipping position check", exc)
            self.state.save()
            return
        for sym in list(self.state.positions):
            have = broker_pos[sym].quantity if sym in broker_pos else 0
            mine = self.state.qty(sym)
            if have < mine:
                log.warning("%s: bot thinks %d, broker has %d; adjusting", sym, mine, have)
                notify(f"[indtrader] {sym}: broker holds {have} < bot's {mine}; reducing (sold outside the bot?)")
                pos = self.state.positions[sym]
                self.state.apply_fill(sym, "SELL", mine - have, pos["avg"])   # at cost: no P&L invented
        self.state.save()

    def _log_trade(self, order: Order, result: OrderResult) -> None:
        new = not self.journal.exists()
        with self.journal.open("a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if new:
                w.writerow(["time", "symbol", "side", "qty", "limit", "status", "fill_qty", "fill_price", "order_id", "reason", "message"])
            w.writerow([now_ist().isoformat(timespec="seconds"), order.symbol, order.side, order.quantity,
                        order.price, result.status, result.filled_qty, result.avg_price, result.order_id,
                        order.reason, result.message])

    # ---------------------------------------------------------------- decisions
    def _bear_market(self, as_of: date) -> bool:
        st = self.s.strategy
        if not st.regime_filter:
            return False
        try:
            idx = market_data.recent_history(st.regime_index, as_of, lookback_days=int(st.regime_sma * 1.6) + 30)
        except Exception as exc:
            log.warning("regime index %s unavailable (%s); assuming normal regime", st.regime_index, exc)
            return False
        bear = is_bear_market(idx["Close"], st.regime_sma)
        if bear:
            log.info("%s below its %d-day average: bear regime, new buys scaled by %s",
                     st.regime_index, st.regime_sma, st.bear_market_scale)
        return bear

    def _fresh_second(self, symbol: str, primary):
        """The Vibe-Trading verdict for the same analysis date as the primary signal."""
        if primary is None or not self.s.second_opinion.enabled:
            return None
        return self.vibe_store.get(symbol, primary.as_of)

    def _rating(self, sym: str, sig, as_of: date) -> tuple[str | None, str]:
        """The rating to trade, per strategy.signal_mode (see config.StrategySettings)."""
        mode = self.s.strategy.signal_mode
        if mode == "llm":
            return combine_opinions(sig.rating if sig else None, self._fresh_second(sym, sig), self.s.second_opinion)
        from indtrader.screen import momentum_rating

        factor = momentum_rating(self.screen_table(as_of), sym, self.s.screen.top_n)
        if mode == "factor":
            return factor, f"momentum: {factor}"
        # hybrid: the LLM review can only veto or shrink what the screen proposes
        veto = SecondOpinionSettings(enabled=True, mode="veto", min_confidence=self.s.strategy.llm_veto_min_confidence,
                                     on_missing=self.s.strategy.llm_missing)
        rating, note = combine_opinions(factor, sig, veto)
        note = f"momentum {factor}" + (f"; LLM: {note}" if note else "")
        if self.s.second_opinion.enabled and rating in BULLISH:
            rating, note2 = combine_opinions(rating, self.vibe_store.get(sym, sig.as_of) if sig else None,
                                             self.s.second_opinion)
            note += f"; {note2}" if note2 else ""
        return rating, note

    def _exposure_scale(self, as_of: date, equity: float) -> float:
        """Drawdown circuit breaker (risk.max_drawdown_pct) and volatility target (strategy.vol_target)."""
        peak = max(self.state.data.get("peak_equity", self.s.risk.capital), equity)
        self.state.data["peak_equity"] = round(peak, 2)
        dd = self.s.risk.max_drawdown_pct
        if dd and equity < peak * (1 - dd):
            log.warning("equity %.2f is %.1f%% below its peak %.2f: circuit breaker, no new buys",
                        equity, 100 * (1 - equity / peak), peak)
            return 0.0
        st = self.s.strategy
        if not st.vol_target:
            return 1.0
        try:
            idx = market_data.recent_history(st.regime_index, as_of, lookback_days=int(st.vol_lookback * 1.6) + 10)
        except Exception as exc:
            log.warning("index %s unavailable for the volatility target (%s); no scaling", st.regime_index, exc)
            return 1.0
        return vol_scale(idx["Close"], st)

    def _plan(self, sym: str, today: date, as_of: date, price: float, capital: float, bear: bool,
              scale: float = 1.0):
        sig = self.store.latest(sym, as_of.isoformat())
        if sig and (as_of - date.fromisoformat(sig.as_of)).days > self.s.strategy.max_signal_age_days:
            sig = None
        rating, opinion_note = self._rating(sym, sig, as_of)
        hist = market_data.recent_history(sym, as_of, exchange=self.s.exchange)
        tech = snapshot(hist, self.s.strategy.trend_ema, self.s.strategy.atr_period)
        pos = self.state.positions.get(sym)
        held_days = (today - date.fromisoformat(pos["opened"])).days if pos and pos.get("opened") else None
        plan = plan_target(sym, rating, price, tech, self.state.qty(sym), capital,
                           self.s.strategy, self.s.risk,
                           sig.stop_loss if sig else None, sig.price_target if sig else None,
                           bear_market=bear, held_days=held_days, exposure_scale=scale)
        if opinion_note:
            plan.notes.insert(0, opinion_note)
        if pos and pos.get("stop"):   # trail the stop of an existing position (never lower it)
            trail, _ = protective_levels(price, tech, self.s.strategy)
            pos["stop"] = max(pos["stop"], trail)
        return plan, tech

    def rebalance(self, today: date) -> list[dict]:
        """Turn the latest signals into orders. Sells first, then buys."""
        if self.s.llm.signal_source == "external":
            self.sync_signals()
        self.reconcile_pending()
        self.apply_corporate_actions(today)
        as_of = previous_trading_day(today, self.s.holidays)
        # the configured universe, anything held, and anything the analyst rated today (screen picks)
        symbols = set(self.state.positions) | set(self.store.symbols_on(as_of.isoformat()))
        if self.s.strategy.signal_mode == "llm":
            symbols |= set(self.s.universe)
        else:   # the screen's candidates (top 2N keeps hysteresis room)
            table = self.screen_table(as_of)
            symbols |= set(table[table["eligible"]].head(2 * self.s.screen.top_n)["symbol"])
        symbols = sorted(symbols)
        prices = self._prices(symbols)
        acct = self._account(prices)
        capital = min(self.s.risk.capital, acct.equity)
        bear = self._bear_market(as_of)
        scale = self._exposure_scale(as_of, acct.equity)
        plans = []
        for sym in symbols:
            if self.state.pending_for(sym):
                log.info("%s: order still pending at the broker; no new orders", sym)
                continue
            if sym not in prices:
                log.warning("%s: no valid price; skipping", sym)
                continue
            try:
                plan, tech = self._plan(sym, today, as_of, prices[sym], capital, bear, scale)
            except Exception as exc:
                log.warning("%s: could not plan (%s); skipping", sym, exc)
                continue
            plans.append((plan, tech, prices[sym]))
        self.state.save()

        self._log_decisions(as_of, plans)
        executed = []
        for plan, tech, ltp in sorted(plans, key=lambda x: x[0].target_qty - self.state.qty(x[0].symbol)):
            held = self.state.qty(plan.symbol)
            delta = plan.target_qty - held
            log.info("%s: %s", plan.symbol, "; ".join(plan.notes))
            if delta < 0:
                d = check_sell(-delta, held)
                if d.allowed:
                    r = self._send(plan.symbol, "SELL", d.quantity, ltp, "; ".join(plan.notes))
                    executed.append({"symbol": plan.symbol, "side": "SELL", "qty": d.quantity, "status": r.status})
            elif delta > 0:
                if blocker := self._entry_blockers(plan.symbol, today):
                    log.info("%s: buy blocked: %s", plan.symbol, blocker)
                    continue
                last_stop = self.state.data["stopped_out"].get(plan.symbol)
                if last_stop and (today - date.fromisoformat(last_stop)).days < self.s.strategy.reentry_cooldown_days:
                    log.info("%s: buy skipped, stopped out on %s (cooldown)", plan.symbol, last_stop)
                    continue
                acct = self._account(prices)
                d = check_buy(plan.symbol, delta, ltp, held, acct, self.s.risk, analysed_close=tech.close)
                if d.allowed:
                    r = self._send(plan.symbol, "BUY", d.quantity, ltp, "; ".join(plan.notes), plan.stop, plan.take_profit)
                    executed.append({"symbol": plan.symbol, "side": "BUY", "qty": d.quantity, "status": r.status})
                else:
                    log.info("%s: buy blocked: %s", plan.symbol, d.reason)
        return executed

    def _log_decisions(self, as_of: date, plans) -> None:
        """Why each candidate was bought, trimmed or skipped (for the dashboard)."""
        f = self.s.path("decisions.json")
        try:
            hist = json.loads(f.read_text()) if f.exists() else []
        except ValueError:
            hist = []
        stamp = now_ist().isoformat(timespec="seconds")
        for plan, _tech, ltp in plans:
            hist.append({"time": stamp, "as_of": as_of.isoformat(), "symbol": plan.symbol, "price": round(ltp, 2),
                         "held": self.state.qty(plan.symbol), "target_qty": plan.target_qty,
                         "decision": "; ".join(plan.notes)})
        f.write_text(json.dumps(hist[-2000:], indent=1))

    def monitor(self) -> list[dict]:
        """Exit positions that hit their stop-loss or take-profit."""
        self.reconcile_pending()
        try:
            self.apply_corporate_actions(now_ist().date())
        except Exception as exc:
            log.warning("corporate action check failed: %s", exc)
        if not self.state.positions:
            return []
        prices = self._prices(list(self.state.positions))
        self._account(prices)   # rolls the day over so early exits count toward today
        exits = []
        for sym, pos in list(self.state.positions.items()):
            ltp = prices.get(sym)
            if ltp is None:
                continue
            if self.state.pending_for(sym, "SELL"):
                continue   # an exit is already working at the broker: never send a second one
            if pos.get("stop") and ltp <= pos["stop"]:
                reason = f"stop-loss hit ({ltp:.2f} <= {pos['stop']})"
            elif pos.get("target") and ltp >= pos["target"]:
                reason = f"target hit ({ltp:.2f} >= {pos['target']})"
            else:
                continue
            result = self._send(sym, "SELL", pos["qty"], ltp, reason)
            if reason.startswith("stop") and result.status not in ("REJECTED", "DRY_RUN"):
                self.state.data["stopped_out"][sym] = now_ist().date().isoformat()
                self.state.save()
            exits.append({"symbol": sym, "reason": reason, "status": result.status})
        return exits

    def square_off_intraday(self) -> None:
        """MIS positions must be closed before the broker's auto square-off (~15:20)."""
        if self.s.broker.product != "MIS":
            return
        self.reconcile_pending()
        prices = self._prices(list(self.state.positions))
        for sym, pos in list(self.state.positions.items()):
            if self.state.pending_for(sym, "SELL"):
                continue
            self._send(sym, "SELL", pos["qty"], prices.get(sym, pos["avg"]), "intraday square-off")

    def record_equity(self, today: date) -> dict:
        """Append today's equity to <data_dir>/equity.csv (one row per day)."""
        prices = self._prices(list(self.state.positions))
        exposure = sum(p["qty"] * prices.get(s, p["avg"]) for s, p in self.state.positions.items())
        row = {"date": today.isoformat(), "equity": round(self.state.cash + exposure, 2),
               "cash": round(self.state.cash, 2), "positions": len(self.state.positions),
               "realized_pnl": round(self.state.data["realized_pnl"], 2)}
        try:
            idx = market_data.recent_history(self.s.strategy.regime_index, today, lookback_days=10)
            row["index_close"] = round(float(idx["Close"].iloc[-1]), 2)
        except Exception:
            row["index_close"] = ""
        f = self.s.path("equity.csv")
        lines = f.read_text().splitlines() if f.exists() else []
        lines = [ln for ln in lines if not ln.startswith(row["date"] + ",")]   # one row per day
        if not lines:
            lines = [",".join(row)]
        lines.append(",".join(str(v) for v in row.values()))
        f.write_text("\n".join(lines) + "\n")
        return row

    def status(self) -> dict:
        prices = self._prices(list(self.state.positions))
        rows = []
        for s, p in self.state.positions.items():
            ltp = prices.get(s, p["avg"])
            rows.append({**p, "symbol": s, "ltp": ltp, "unrealized": round((ltp - p["avg"]) * p["qty"], 2)})
        exposure = sum(r["ltp"] * r["qty"] for r in rows)
        return {"broker": self.broker.name, "broker_funds": self.broker.funds(),
                "bot_cash": round(self.state.cash, 2), "bot_equity": round(self.state.cash + exposure, 2),
                "realized_pnl": round(self.state.data["realized_pnl"], 2), "positions": rows,
                "pending": self.state.data["pending"], "day": self.state.data["day"]}
