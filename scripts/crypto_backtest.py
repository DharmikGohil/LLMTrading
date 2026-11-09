"""Crypto strategy backtest on Binance daily candles (data/crypto, from scripts/download_crypto_klines.py).

Rules that trade a few times a week at most (Alpha Arena's lesson: over-trading lost the money):
- BTC buy and hold (the benchmark)
- equal-weight hold of the universe, rebalanced monthly
- BTC trend: hold BTC while its close is above its N-day average, else USDT (N = 50, 100, 200)
- cross-sectional momentum: weekly, hold the top k coins by L-day return among those above their 100-day average,
  equal weight; all USDT while BTC is below its 100-day average (k = 3, 5; L = 30, 90)
Execution: decide on day t's close, fill at day t+1's open. Costs: 0.1% fee plus 0.05% slippage on each trade's
value. A coin whose data ends (delisted) is sold at its last close.
India after tax: 31.2% (30% + 4% cess) on every profitable sale, with no relief for losses (they cannot be set off or
carried forward), and everything sold on the last day. The 1% TDS is creditable against that tax, so it is ignored.
Two universes:
- point in time: the large Binance coins of January 2020 (including ones that faded: EOS, NEO, XMR, XTZ, ETC)
- today's survivors: today's large coins (SOL, DOGE, AVAX... picked with hindsight, so it flatters)
The deflated Sharpe accounts for every variant tried.
Usage: python scripts/crypto_backtest.py [start=2020-01-01] [out.json]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from indtrader.validation import _sharpe, deflated_sharpe

DATA = Path(__file__).resolve().parent.parent / "data" / "crypto"
FEE, SLIP, TAX = 0.001, 0.0005, 0.312
UNIVERSES = {
    "jan-2020": ["BTC", "ETH", "XRP", "BCH", "LTC", "BNB", "EOS", "XTZ", "LINK", "XLM", "ADA", "TRX", "XMR", "ETC", "NEO"],
    "today": ["BTC", "ETH", "XRP", "BNB", "SOL", "DOGE", "ADA", "TRX", "LINK", "AVAX", "XLM", "DOT", "LTC", "BCH", "HBAR"],
}


def load(coins: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    o, c = {}, {}
    for coin in coins:
        f = DATA / f"{coin}.csv"
        if not f.exists():
            continue
        df = pd.read_csv(f, parse_dates=["date"]).set_index("date").sort_index()
        o[coin], c[coin] = df["open"].astype(float), df["close"].astype(float)
    return pd.DataFrame(o), pd.DataFrame(c)


def mark(q: dict, cash: float, cl: pd.Series) -> float:
    return cash + sum(v * cl[k] for k, v in q.items() if v and not np.isnan(cl.get(k, np.nan)))


def simulate(opens: pd.DataFrame, closes: pd.DataFrame, weights_fn, start: str, every: int = 1) -> dict:
    """weights_fn(day, closes_so_far) -> {coin: weight}; decided on day's close, filled at next open."""
    days = closes.index[closes.index >= pd.Timestamp(start)]
    cash, qty, cost = 1.0, {}, {}           # cost = average cost per unit, for tax
    cash_tax, tax_paid, fees = 1.0, 0.0, 0.0
    qty_t: dict = {}
    eq, eq_tax, trades = [], [], 0
    target: dict | None = None
    for i, day in enumerate(days):
        op = opens.loc[day]
        # 1) execute yesterday's decision at today's open (both books: pre-tax and India after-tax)
        if target is not None:
            for book in ("pre", "tax"):
                q = qty if book == "pre" else qty_t
                c0 = cash if book == "pre" else cash_tax
                px = {k: op[k] for k in set(q) | set(target) if not np.isnan(op.get(k, np.nan))}
                value = c0 + sum(q.get(k, 0) * px[k] for k in q if k in px)
                for k in sorted(set(q) | set(target), key=lambda k: target.get(k, 0)):   # sells first
                    if k not in px:
                        continue
                    want = target.get(k, 0) * value / px[k]
                    d = want - q.get(k, 0)
                    if abs(d * px[k]) < 1e-4 * value:
                        continue
                    trade_value = abs(d) * px[k]
                    fee = trade_value * (FEE + SLIP)
                    if d < 0:          # sell
                        gain = -d * (px[k] - cost.get((book, k), px[k]))
                        c0 += trade_value - fee
                        if book == "tax" and gain > 0:
                            c0 -= TAX * gain
                            tax_paid += TAX * gain
                    else:              # buy
                        old = q.get(k, 0)
                        cost[(book, k)] = (old * cost.get((book, k), 0) + d * px[k]) / (old + d)
                        c0 -= trade_value + fee
                    q[k] = q.get(k, 0) + d
                    if book == "pre":
                        fees += fee
                        trades += 1
                if book == "pre":
                    cash = c0
                else:
                    cash_tax = c0
            target = None
        # 2) delisted coins (no more data): sell at the last close
        cl = closes.loc[day]
        for book in ("pre", "tax"):
            q = qty if book == "pre" else qty_t
            for k in [k for k in q if q[k] > 0 and np.isnan(cl.get(k, np.nan))]:
                last = closes[k].loc[:day].dropna().iloc[-1]
                proceeds = q[k] * last * (1 - FEE - SLIP)
                if book == "pre":
                    cash += proceeds
                else:
                    gain = q[k] * (last - cost.get((book, k), last))
                    cash_tax += proceeds - (TAX * gain if gain > 0 else 0)
                q[k] = 0
        # 3) mark at the close; decide for tomorrow
        eq.append(mark(qty, cash, cl))
        eq_tax.append(mark(qty_t, cash_tax, cl))
        if i % every == 0 and i < len(days) - 1:
            target = weights_fn(day, closes.loc[:day])
    equity = pd.Series(eq, index=days)
    # India: sell everything on the last day, tax on remaining gains
    last = closes.loc[days[-1]]
    final_tax = cash_tax
    for k, v in qty_t.items():
        if v > 0 and not np.isnan(last.get(k, np.nan)):
            gain = v * (last[k] - cost.get(("tax", k), last[k]))
            final_tax += v * last[k] * (1 - FEE - SLIP) - (TAX * gain if gain > 0 else 0)
    return {"equity": equity, "after_tax_final": final_tax, "trades": trades, "fees": fees}


def stats(r: dict) -> dict:
    e = r["equity"]
    rets = e.pct_change().dropna()
    years = (e.index[-1] - e.index[0]).days / 365.25
    by = {}
    for lo, hi, name in (("2020", "2023", "2020-22"), ("2023", "2027", "2023-26")):
        part = e[(e.index >= lo) & (e.index < hi)]
        if len(part) > 1:
            by[name] = round(100 * (part.iloc[-1] / part.iloc[0] - 1), 1)
    return {"total_return_pct": round(100 * (e.iloc[-1] - 1), 1), "cagr_pct": round(100 * (e.iloc[-1] ** (1 / years) - 1), 1),
            "max_dd_pct": round(100 * float((e / e.cummax() - 1).min()), 1),
            "sharpe": round(float(np.sqrt(365) * rets.mean() / rets.std()), 2) if rets.std() > 0 else None,
            "trades": r["trades"], "fees_pct_of_start": round(100 * r["fees"], 1),
            "india_after_tax_return_pct": round(100 * (r["after_tax_final"] - 1), 1), "by_period": by}


def strategies(coins: list[str]):
    def btc_hold(day, c):
        return {"BTC": 1.0}

    def ew_hold(day, c):
        live = [k for k in coins if k in c and not np.isnan(c[k].iloc[-1])]
        return {k: 1 / len(live) for k in live}

    def btc_trend(n):
        def fn(day, c):
            s = c["BTC"].dropna()
            return {"BTC": 1.0} if len(s) > n and s.iloc[-1] > s.iloc[-n:].mean() else {}
        return fn

    def xs_mom(lookback, k):
        def fn(day, c):
            b = c["BTC"].dropna()
            if len(b) <= 100 or b.iloc[-1] < b.iloc[-100:].mean():
                return {}
            score = {}
            for coin in coins:
                if coin not in c:
                    continue
                s = c[coin].dropna()
                if len(s) <= max(lookback, 100) or np.isnan(c[coin].iloc[-1]):
                    continue
                if s.iloc[-1] > s.iloc[-100:].mean():
                    score[coin] = s.iloc[-1] / s.iloc[-lookback - 1] - 1
            top = sorted(score, key=score.get, reverse=True)[:k]
            return {t: 1 / len(top) for t in top} if top else {}
        return fn

    yield "BTC buy and hold", btc_hold, 1
    yield "Equal-weight hold (monthly)", ew_hold, 30
    for n in (50, 100, 200):
        yield f"BTC trend, {n}-day average", btc_trend(n), 1
    for lb in (30, 90):
        for k in (3, 5):
            yield f"Momentum top {k}, {lb}-day, weekly", xs_mom(lb, k), 7


def main(start: str, out: str | None) -> None:
    results, curves = {}, {}
    for uni, coins in UNIVERSES.items():
        opens, closes = load(coins)
        for name, fn, every in strategies(list(closes.columns)):
            if uni == "today" and name.startswith("BTC"):
                continue          # BTC-only rules do not depend on the universe
            key = f"{name} [{uni}]" if not name.startswith("BTC") else name
            r = simulate(opens, closes, fn, start, every)
            results[key] = stats(r)
            curves[key] = r["equity"]
    sharpes = [_sharpe(c.pct_change().dropna().to_numpy()) for c in curves.values()]
    for key, c in curves.items():
        results[key]["deflated_sharpe"] = deflated_sharpe(c, len(curves), sharpes).get("deflated_sharpe")
    df = pd.DataFrame(results).T
    pd.set_option("display.width", 250)
    print(df[["total_return_pct", "cagr_pct", "max_dd_pct", "sharpe", "deflated_sharpe", "trades",
              "fees_pct_of_start", "india_after_tax_return_pct", "by_period"]].to_string())
    if out:
        Path(out).write_text(json.dumps(results, indent=1, default=str))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "2020-01-01", sys.argv[2] if len(sys.argv) > 2 else None)
