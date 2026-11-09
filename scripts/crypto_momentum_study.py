"""Crypto momentum study with a point-in-time universe, a design period and an untouched test period.

Universe: every coin in data/crypto (about 80, including ones that collapsed or were delisted: LUNA, FTT, WAVES, OMG,
XMR...). On each rebalance day the eligible coins are the 20 with the highest 30-day average traded value (USDT)
among those with at least 120 days of history. Only information available that day is used, so coins that later
failed are in the pool while they were big, and future winners join only once they trade heavily.

Variants are fixed before looking at results (no tuning on the test period):
  M1-M4  cross-sectional momentum: top k by L-day return (L 30/90, k 3/5), weekly, coin above its 50-day average,
         all USDT when BTC is below its 100-day average
  M5-M6  risk-adjusted momentum: top k by 90-day return / 90-day volatility (k 3/5), same filters
  M7     BTC + ETH trend: each held (50/50) while above its 50-day average
  M8     M3 with half the capital always in BTC (core-satellite)
  benchmarks: BTC buy and hold; BTC 50-day trend
Design period 2020-2022, test period 2023 to the latest bar. Costs and Indian tax as in scripts/crypto_backtest.py.
Usage: python scripts/crypto_momentum_study.py [out.json]
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pandas as pd

from indtrader.crypto import MOMENTUM, above, target_weights

ROOT = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("crypto_backtest", ROOT / "crypto_backtest.py")
cb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cb)

DATA = ROOT.parent / "data" / "crypto"
MIN_HISTORY = 120
PERIODS = {"design 2020-22": ("2020-01-01", "2022-12-31"), "test 2023-26": ("2023-01-01", "2100-01-01")}


def split_reused_tickers(name: str, df: pd.DataFrame) -> list[tuple[str, pd.DataFrame]]:
    """A ticker reused for a different coin (LUNA became LUNA 2.0 on 31 May 2022) shows as a gap of over a week with a
    price jump of more than 10x. Treat the two sides as separate coins, so no return is measured across the splice."""
    gap = df.index.to_series().diff().dt.days
    jump = df["close"] / df["close"].shift(1)
    cut = df.index[(gap > 7) & ((jump > 10) | (jump < 0.1))]
    if not len(cut):
        return [(name, df)]
    parts, start = [], df.index[0]
    for k, t in enumerate(cut):
        parts.append((name if k == 0 else f"{name}{k + 1}", df[(df.index >= start) & (df.index < t)]))
        start = t
    parts.append((f"{name}{len(cut) + 1}", df[df.index >= start]))
    return parts


def load_all():
    o, c, v = {}, {}, {}
    for f in sorted(DATA.glob("*.csv")):
        df = pd.read_csv(f, parse_dates=["date"]).set_index("date").sort_index()
        for name, part in split_reused_tickers(f.stem, df):
            if len(part) < MIN_HISTORY:
                continue
            o[name], c[name], v[name] = part["open"].astype(float), part["close"].astype(float), part["volume"].astype(float)
    return pd.DataFrame(o), pd.DataFrame(c), pd.DataFrame(v)


def variants(value30: pd.DataFrame):
    def btc_hold(day, c):
        return {"BTC": 1.0}

    def btc_trend(day, c):
        return {"BTC": 1.0} if above(c["BTC"], 50) else {}

    def btc_eth_trend(day, c):
        held = [k for k in ("BTC", "ETH") if above(c[k], 50)]
        return {k: 0.5 for k in held}

    def momentum(lookback: int, k: int, risk_adj: bool = False, core: float = 0.0):
        p = {**MOMENTUM, "lookback": lookback, "top_k": k, "risk_adjusted": risk_adj, "core_btc": core}

        def fn(day, c):
            return target_weights(c, value30, day, p)
        return fn

    yield "BTC buy and hold (benchmark)", btc_hold, 1
    yield "BTC 50-day trend (benchmark)", btc_trend, 1
    yield "M1 momentum top 3, 30-day", momentum(30, 3), 7
    yield "M2 momentum top 5, 30-day", momentum(30, 5), 7
    yield "M3 momentum top 3, 90-day", momentum(90, 3), 7
    yield "M4 momentum top 5, 90-day", momentum(90, 5), 7
    yield "M5 risk-adj momentum top 3, 90-day", momentum(90, 3, risk_adj=True), 7
    yield "M6 risk-adj momentum top 5, 90-day", momentum(90, 5, risk_adj=True), 7
    yield "M7 BTC + ETH 50-day trend", btc_eth_trend, 1
    yield "M8 half BTC + half M3", momentum(90, 3, core=0.5), 7


def main(out: str | None) -> None:
    opens, closes, vol = load_all()
    value30 = vol.rolling(30, min_periods=20).mean()
    print(f"{closes.shape[1]} coins, {closes.index[0].date()} to {closes.index[-1].date()}")
    rows, curves = {}, {}
    for period, (start, end) in PERIODS.items():
        o = opens.loc[:end]
        c = closes.loc[:end]
        for name, fn, every in variants(value30):
            r = cb.simulate(o, c, fn, start, every)
            s = cb.stats(r)
            rows.setdefault(name, {})[period] = {k: s[k] for k in ("total_return_pct", "cagr_pct", "max_dd_pct", "sharpe",
                                                                    "india_after_tax_return_pct", "trades")}
            if period.startswith("test"):
                curves[name] = r["equity"]
    sharpes = [cb._sharpe(c.pct_change().dropna().to_numpy()) for c in curves.values()]
    for name, c in curves.items():
        rows[name]["test 2023-26"]["deflated_sharpe"] = cb.deflated_sharpe(c, len(curves), sharpes).get("deflated_sharpe")
    for period in PERIODS:
        print(f"\n== {period}")
        head = f"{'variant':38}{'return':>10}{'CAGR':>8}{'maxDD':>8}{'Sharpe':>8}{'after tax':>11}{'trades':>8}"
        print(head + ("  defl.SR" if period.startswith("test") else ""))
        for name, per in rows.items():
            s = per[period]
            extra = f"  {s['deflated_sharpe']:.3f}" if period.startswith("test") and s.get("deflated_sharpe") is not None else ""
            print(f"{name:38}{s['total_return_pct']:>9.1f}%{s['cagr_pct']:>7.1f}%{s['max_dd_pct']:>7.1f}%{s['sharpe'] or 0:>8.2f}"
                  f"{s['india_after_tax_return_pct']:>10.1f}%{s['trades']:>8}{extra}")
    if out:
        Path(out).write_text(json.dumps(rows, indent=1, default=float))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
