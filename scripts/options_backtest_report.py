"""Run the options backtest grid and print one table plus the details of the best variants.

Usage: python scripts/options_backtest_report.py [out.json]
"""

from __future__ import annotations

import json
import sys

import pandas as pd

from indtrader.options_backtest import load, run, run_lotto, summary
from indtrader.validation import _sharpe, deflated_sharpe

SYMBOLS = ["NIFTY", "BANKNIFTY", "FINNIFTY"]
GRID = [(k, dte, managed) for k in (0.75, 1.0, 1.25, 1.5) for dte in (3, 5) for managed in (True, False)]


def equity(trades, capital=100000.0) -> pd.Series:
    if not trades:
        return pd.Series(dtype=float)
    s = pd.Series([t.pnl for t in trades], index=pd.to_datetime([t.exit for t in trades])).groupby(level=0).sum()
    return capital + s.cumsum()


def main(out: str | None) -> None:
    rows, curves = [], {}
    data = {sym: load(sym) for sym in SYMBOLS}
    for sym, days in data.items():
        if not days:
            continue
        for k, dte, managed in GRID:
            tr = run(sym, days, k=k, dte=dte, managed=managed)
            sm = summary(tr)
            if not sm.get("trades"):
                continue
            name = f"{sym} k={k} dte={dte} {'managed' if managed else 'hold'}"
            curves[name] = equity(tr)
            rows.append({"variant": name, **{x: sm[x] for x in ("trades", "return_pct", "win_rate", "avg", "worst",
                                                              "max_dd_pct", "sharpe")}, "by_year": sm["by_year"],
                         "exits": sm["exits"]})
    trial_sharpes = [_sharpe(c.pct_change().dropna().to_numpy()) for c in curves.values() if len(c) > 2]
    for r in rows:
        r["deflated_sharpe"] = deflated_sharpe(curves[r["variant"]], len(rows), trial_sharpes).get("deflated_sharpe")
    df = pd.DataFrame(rows).sort_values("return_pct", ascending=False)
    pd.set_option("display.width", 220)
    print(df[["variant", "trades", "return_pct", "win_rate", "avg", "worst", "max_dd_pct", "sharpe", "deflated_sharpe"]]
          .to_string(index=False))
    print(f"\n{len(rows)} variants tested; deflated Sharpe accounts for all of them (>= 0.95 robust).")
    for r in df.head(3).to_dict("records"):
        print(f"\n{r['variant']}: by year {r['by_year']}, exits {r['exits']}")

    lotto = {}
    for sym, days in data.items():
        tr = run_lotto(sym, days)
        if tr:
            staked = 1000 * len(tr)
            lotto[sym] = {"trades": len(tr), "total_pnl": round(sum(t.pnl for t in tr)), "staked": staked,
                          "win_rate": round(100 * sum(t.pnl > 0 for t in tr) / len(tr)),
                          "return_on_staked_pct": round(100 * sum(t.pnl for t in tr) / staked, 1),
                          "by_year": summary(tr, 1000)["by_year"]}
    print("\nRs 1,000 lotto (one option per expiry, Rs 1,000 staked each time):")
    for sym, v in lotto.items():
        print(f"  {sym}: {v}")
    if out:
        with open(out, "w") as fh:
            json.dump({"condors": df.to_dict("records"), "lotto": lotto}, fh, indent=1, default=str)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
