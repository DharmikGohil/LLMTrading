"""Forensic checks on the momentum backtest: survivorship, costs and execution delay.

Runs the factor-only momentum arm (the strategy the desks trade) over the same window several ways:
- survivorship: the NSE F&O stock list as it stood on the first trading day of the window (point in time, from
  data/futstk, see scripts/download_futstk_bhavcopy.py) against today's F&O list. Both lists use the same
  definition, so the gap between them is survivorship bias. Today's Nifty 200, the published backtest's universe,
  is run too.
- costs: charges x2 and slippage x4 (0.05% to 0.2% per side), on the published universe
- delay: every decision executed one trading day later than planned
Look-ahead is checked by design in indtrader/backtest.py: decisions use the previous close and fill at the open.
Usage: python scripts/backtest_forensics.py 2024-01-01 2026-11-06 [out.json]
"""

from __future__ import annotations

import csv
import gzip
import json
import logging
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from indtrader import data as market_data
from indtrader.backtest import momentum_rating_fn, run_backtest
from indtrader.config import load_settings
from indtrader.costs import CostModel
from indtrader.screen import download_closes, index_members

ROOT = Path(__file__).resolve().parent.parent
FUT = ROOT / "data" / "futstk"


def fno_list(on_or_after: str | None = None, last: bool = False) -> tuple[str, list[str]]:
    """Stock-future symbols traded on the first day >= on_or_after (or on the last day in the data)."""
    by_day: dict[str, set] = {}
    for f in sorted(FUT.glob("*.csv.gz")):
        with gzip.open(f, "rt") as fh:
            for r in csv.DictReader(fh):
                by_day.setdefault(r["date"], set()).add(r["symbol"])
    days = sorted(by_day)
    day = days[-1] if last else next(d for d in days if d >= on_or_after)
    return day, sorted(by_day[day])


def run(settings, d0: date, d1: date, symbols: list[str], bench: pd.Series, delay: int = 0) -> dict:
    hist = download_closes(symbols, d0 - timedelta(days=420), d1)
    fn = momentum_rating_fn(hist, settings)
    if delay:
        days = sorted({d for h in hist.values() for d in h.index})

        def delayed(symbol, h, as_of):   # decide as if it were `delay` trading days earlier
            ts = pd.Timestamp(as_of)
            i = max(0, next((k for k, d in enumerate(days) if d >= ts), len(days) - 1) - delay)
            earlier = days[i]
            return fn(symbol, h.loc[:earlier], earlier.date())
        rating = delayed
    else:
        rating = fn
    res = run_backtest(settings, d0, d1, rating, histories=hist, benchmark=bench)
    st = res.stats
    return {"universe": len(symbols), "with_data": len(hist), "total_return_pct": st["total_return_pct"],
            "cagr_pct": st["cagr_pct"], "max_drawdown_pct": st["max_drawdown_pct"], "sharpe": st["sharpe"],
            "trades": st["trades"], "charges": st["total_charges"], "benchmark_return_pct": st.get("benchmark_return_pct")}


def main(start: str, end: str, out: str | None) -> None:
    logging.basicConfig(level=logging.WARNING)
    s = load_settings(str(ROOT / "config" / "india_paper.yaml"))
    d0, d1 = date.fromisoformat(start), date.fromisoformat(end)
    bench = market_data.history(s.strategy.regime_index, d0 - timedelta(days=400), d1)["Close"]
    nifty200 = index_members(s.screen.index, s.path("universe", "_").parent)
    day_then, fno_then = fno_list(start)
    day_now, fno_now = fno_list(last=True)
    left = sorted(set(fno_then) - set(fno_now))
    results = {"window": [start, end], "fno_then_date": day_then, "fno_now_date": day_now,
               "fno_dropped_since": left, "runs": {}}

    results["runs"]["published: Nifty 200 today"] = run(s, d0, d1, nifty200, bench)
    results["runs"]["F&O list today (survivors)"] = run(s, d0, d1, fno_now, bench)
    results["runs"][f"F&O list on {day_then} (point in time)"] = run(s, d0, d1, fno_then, bench)

    base_charges, base_costs = CostModel.charges, dict(s.costs or {})
    slip = base_costs.get("slippage_pct", CostModel.slippage_pct)
    CostModel.charges = lambda self, *a, **k: 2 * base_charges(self, *a, **k)
    s.costs = {**base_costs, "slippage_pct": 4 * slip}
    results["runs"]["Nifty 200 today, charges x2, slippage x4"] = run(s, d0, d1, nifty200, bench)
    CostModel.charges, s.costs = base_charges, base_costs

    results["runs"]["Nifty 200 today, decisions 1 day late"] = run(s, d0, d1, nifty200, bench, delay=1)

    print(json.dumps(results, indent=1))
    if out:
        Path(out).write_text(json.dumps(results, indent=1))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
