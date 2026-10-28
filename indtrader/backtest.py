"""Daily portfolio backtest with Indian costs, using the same sizing/risk code
as live trading.

Signal sources:
  technical  - deterministic EMA/RSI ratings (free; validates the plumbing)
  llm        - TradingAgents ratings cached under <data_dir>/signals/ (run
               `indtrader analyze --date D` for past dates first; each date x
               symbol costs one full multi-agent LLM run)

Decisions use data up to the previous close and execute at today's open;
stop-losses/targets are checked against the day's low/high (stop first when
both are touched: the conservative assumption).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, timedelta

import numpy as np
import pandas as pd

from indtrader import data as market_data
from indtrader.config import Settings
from indtrader.risk import AccountView, check_buy
from indtrader.signals.llm_agent import SignalStore
from indtrader.signals.technical import ema, is_bear_market, rsi, snapshot
from indtrader.strategy import plan_target, protective_levels

# Returns a rating, or (rating, llm_stop, llm_target) when the source has levels.
RatingFn = Callable[[str, pd.DataFrame, date], str | None | tuple]


def technical_rating(symbol: str, hist: pd.DataFrame, as_of: date) -> str | None:
    close = hist["Close"]
    if len(close) < 60:
        return None
    e20, e50, r = ema(close, 20).iloc[-1], ema(close, 50).iloc[-1], rsi(close).iloc[-1]
    c = close.iloc[-1]
    if c > e50 and e20 > e50 and 50 <= r <= 70:
        return "Buy"
    if c < e50 and e20 < e50:
        return "Sell"
    if c < e20:
        return "Underweight"
    return "Hold"


def momentum_rating_fn(histories: dict[str, pd.DataFrame], settings: Settings, recompute_every: int = 5) -> RatingFn:
    """Factor-only arm: ratings from the momentum screen, re-ranked every `recompute_every` days."""
    from indtrader.screen import momentum_rating, score_universe

    sc = settings.screen
    cache: dict = {"day": None, "table": None, "age": 10**9}

    def fn(symbol: str, hist: pd.DataFrame, as_of: date) -> str | None:
        if cache["day"] != as_of:
            cache["age"] += 1
            cache["day"] = as_of
            if cache["age"] >= recompute_every:
                cache["table"] = score_universe(histories, as_of, min_traded_value_cr=sc.min_traded_value_cr,
                                                vol_exclude_pct=sc.vol_exclude_pct)
                cache["age"] = 0
        return momentum_rating(cache["table"], symbol, sc.top_n) if cache["table"] is not None else None

    return fn


def llm_rating_fn(settings: Settings) -> RatingFn:
    store = SignalStore(settings.signals_root)

    def fn(symbol: str, hist: pd.DataFrame, as_of: date) -> str | None:
        sig = store.latest(symbol, as_of.isoformat())
        if not sig or (as_of - date.fromisoformat(sig.as_of)).days > settings.strategy.max_signal_age_days:
            return None
        return sig.rating, sig.stop_loss, sig.price_target

    return fn


@dataclass
class BacktestResult:
    equity: pd.Series
    trades: pd.DataFrame
    benchmark: pd.Series | None = None
    stats: dict = field(default_factory=dict)


def _stats(equity: pd.Series, trades: pd.DataFrame, benchmark: pd.Series | None) -> dict:
    rets = equity.pct_change().dropna()
    years = max((equity.index[-1] - equity.index[0]).days / 365.25, 1 / 365.25)
    dd = equity / equity.cummax() - 1
    sells = trades[trades["side"] == "SELL"] if len(trades) else trades
    out = {
        "start_equity": round(float(equity.iloc[0]), 2),
        "end_equity": round(float(equity.iloc[-1]), 2),
        "total_return_pct": round(100 * (equity.iloc[-1] / equity.iloc[0] - 1), 2),
        "cagr_pct": round(100 * ((equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1), 2),
        "max_drawdown_pct": round(100 * float(dd.min()), 2),
        "sharpe": round(float(np.sqrt(252) * rets.mean() / rets.std()), 2) if rets.std() > 0 else 0.0,
        "trades": int(len(trades)),
        "win_rate_pct": round(100 * float((sells["pnl"] > 0).mean()), 1) if len(sells) else None,
        "total_charges": round(float(trades["charges"].sum()), 2) if len(trades) else 0.0,
    }
    if benchmark is not None and len(benchmark) > 1:
        out["benchmark_return_pct"] = round(100 * (benchmark.iloc[-1] / benchmark.iloc[0] - 1), 2)
    return out


def run_backtest(settings: Settings, start: date, end: date, rating_fn: RatingFn = technical_rating,
                 histories: dict[str, pd.DataFrame] | None = None,
                 benchmark: pd.Series | None = None) -> BacktestResult:
    """`benchmark` (index closes, ideally with ~1 year of warm-up before `start`)
    is used for the regime filter and for comparison."""
    s, r, costs = settings.strategy, settings.risk, settings.cost_model
    if histories is None:
        histories = {sym: market_data.history(sym, start - timedelta(days=400), end, settings.exchange)
                     for sym in settings.universe}
        try:
            bench = market_data.history(s.regime_index, start - timedelta(days=400), end)
            benchmark = bench["Close"]
        except Exception:
            benchmark = None
    dates = sorted({d for h in histories.values() for d in h.index if pd.Timestamp(start) <= d <= pd.Timestamp(end)})
    if not dates:
        raise ValueError("no trading days in range")

    cash = r.capital
    pos: dict[str, dict] = {}
    stopped_out: dict[str, pd.Timestamp] = {}
    trades: list[dict] = []
    curve: dict[pd.Timestamp, float] = {}
    orders_today = 0

    def fill(sym: str, side: str, qty: int, price: float, day, why: str, stop=None, target=None):
        nonlocal cash, orders_today
        px = price * (1 + costs.slippage_pct) if side == "BUY" else price * (1 - costs.slippage_pct)
        ch = costs.charges(side, qty, px, settings.broker.product)
        pnl = None
        if side == "BUY":
            p = pos.setdefault(sym, {"qty": 0, "avg": 0.0, "opened": day})
            p["avg"] = (p["qty"] * p["avg"] + qty * px) / (p["qty"] + qty)
            p["qty"] += qty
            p["stop"], p["target"] = stop, target
            cash -= qty * px + ch
        else:
            p = pos[sym]
            pnl = qty * (px - p["avg"]) - ch
            p["qty"] -= qty
            cash += qty * px - ch
            if p["qty"] == 0:
                del pos[sym]
            if why.startswith("stop"):
                stopped_out[sym] = day
        orders_today += 1
        trades.append({"date": day.date(), "symbol": sym, "side": side, "qty": qty, "price": round(px, 2),
                       "charges": ch, "pnl": pnl, "reason": why})

    def mark(day) -> float:
        val = cash
        for sym, p in pos.items():
            h = histories[sym]
            val += p["qty"] * float(h.loc[:day, "Close"].iloc[-1])
        return val

    def bear_on(day) -> bool:
        if not s.regime_filter or benchmark is None:
            return False
        return is_bear_market(benchmark.loc[: day - pd.Timedelta(days=1)], s.regime_sma)

    prev_equity = r.capital
    for day in dates:
        orders_today = 0
        bars = {sym: h.loc[day] for sym, h in histories.items() if day in h.index}
        # 1) gaps through stops at the open
        for sym in list(pos):
            if sym in bars and pos[sym].get("stop") and bars[sym]["Open"] <= pos[sym]["stop"]:
                fill(sym, "SELL", pos[sym]["qty"], float(bars[sym]["Open"]), day, "stop (gap)")
        # 2) rebalance at the open on yesterday's information
        plans = []
        bear = bear_on(day)
        for sym, h in histories.items():
            if sym not in bars:
                continue
            past = h.loc[: day - pd.Timedelta(days=1)]
            if len(past) < s.trend_ema + 5:
                continue
            tech = snapshot(past, s.trend_ema, s.atr_period)
            out = rating_fn(sym, past, past.index[-1].date())
            rating, llm_stop, llm_target = out if isinstance(out, tuple) else (out, None, None)
            held = pos.get(sym, {}).get("qty", 0)
            price = float(bars[sym]["Open"])
            held_days = (day - pos[sym]["opened"]).days if sym in pos else None
            plan = plan_target(sym, rating, price, tech, held, min(r.capital, prev_equity), s, r,
                               llm_stop, llm_target, bear_market=bear, held_days=held_days)
            plans.append((plan.target_qty - held, sym, plan, tech, price, held))
        for delta, sym, plan, tech, price, held in sorted(plans, key=lambda x: x[0]):
            if delta < 0:
                fill(sym, "SELL", -delta, price, day, f"rebalance {'; '.join(plan.notes)}")
            elif delta > 0:
                if sym in stopped_out and (day - stopped_out[sym]).days < s.reentry_cooldown_days:
                    continue
                exposure = sum(p["qty"] * float(bars[k]["Open"]) if k in bars else p["qty"] * p["avg"] for k, p in pos.items())
                acct = AccountView(min(cash, max(r.capital - exposure, 0)), cash + exposure, prev_equity,
                                   exposure, len(pos), orders_today)
                d = check_buy(sym, delta, price, held, acct, r, analysed_close=tech.close)
                if d.allowed:
                    fill(sym, "BUY", d.quantity, price, day, f"rebalance {'; '.join(plan.notes)}", plan.stop, plan.take_profit)
        # 3) intraday stop / target
        for sym in list(pos):
            if sym not in bars:
                continue
            p, bar = pos[sym], bars[sym]
            if p.get("stop") and bar["Low"] <= p["stop"]:
                fill(sym, "SELL", p["qty"], min(float(bar["Open"]), p["stop"]), day, "stop-loss")
            elif p.get("target") and bar["High"] >= p["target"]:
                fill(sym, "SELL", p["qty"], max(float(bar["Open"]), p["target"]), day, "target")
        # 4) trail stops on today's close
        for sym, p in pos.items():
            h = histories[sym].loc[:day]
            if p.get("stop") and len(h) >= s.trend_ema + 5:
                trail, _ = protective_levels(float(h["Close"].iloc[-1]), snapshot(h, s.trend_ema, s.atr_period), s)
                p["stop"] = max(p["stop"], trail)
        prev_equity = mark(day)
        curve[day] = prev_equity

    equity = pd.Series(curve).sort_index()
    tdf = pd.DataFrame(trades, columns=["date", "symbol", "side", "qty", "price", "charges", "pnl", "reason"])
    bench = None
    if benchmark is not None:
        bench = benchmark.loc[(benchmark.index >= equity.index[0]) & (benchmark.index <= equity.index[-1])]
        bench = bench / bench.iloc[0] * r.capital if len(bench) else None
    stats = _stats(equity, tdf, bench)
    stats["equal_weight_buy_hold_pct"] = _equal_weight_buy_hold(histories, equity.index[0], equity.index[-1], costs)
    return BacktestResult(equity, tdf, bench, stats)


def _equal_weight_buy_hold(histories: dict[str, pd.DataFrame], start, end, costs) -> float | None:
    """Ablation baseline: buy the same universe in equal weight on day one and hold."""
    rets = []
    for h in histories.values():
        seg = h.loc[(h.index >= start) & (h.index <= end)]
        if len(seg) > 1:
            gross = float(seg["Close"].iloc[-1] / seg["Open"].iloc[0])
            rets.append(gross * (1 - costs.stt_delivery_pct) ** 2 - 1)
    return round(100 * float(np.mean(rets)), 2) if rets else None


__all__ = ["run_backtest", "technical_rating", "llm_rating_fn", "BacktestResult"]
