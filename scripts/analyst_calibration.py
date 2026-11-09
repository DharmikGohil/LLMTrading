"""Is the analyst's confidence calibrated? Score every past rating against what happened next.

For each rating in signals/ (India) and signals_us/ (US): the stock's return from the close of the analysis date over
the next `H` trading days, minus the index's (Nifty 50 or S&P 500). A bullish call (Buy, Overweight) is right if that
excess is positive; a bearish call (Underweight, Sell) is right if it is negative. Holds are not scored.
Grouped by stated confidence: a calibrated analyst's 60% calls are right about 60% of the time.
Repeat ratings of the same stock on consecutive days are not independent, so treat the counts with care.
Usage: python scripts/analyst_calibration.py [horizon_days=5]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DESKS = {"India": (ROOT / "signals", "^NSEI", ".NS"), "US": (ROOT / "signals_us", "^GSPC", "")}
BULL, BEAR = {"Buy", "Overweight"}, {"Underweight", "Sell"}
BANDS = [(0, 59.99, "55-59"), (60, 64.99, "60-64"), (65, 69.99, "65-69"), (70, 100, "70+")]


def ratings() -> list[dict]:
    out = []
    for market, (folder, _, _) in DESKS.items():
        for f in sorted(folder.glob("*/*.json")):
            if f.name.startswith("_"):
                continue
            r = json.loads(f.read_text())
            if r.get("source") == "claude-analyst" and r.get("rating") in BULL | BEAR:
                out.append({"market": market, "symbol": r["symbol"], "date": r["as_of"], "rating": r["rating"],
                            "confidence": float(r.get("confidence") or 0)})
    return out


def main(h: int) -> None:
    import yfinance as yf

    rows = ratings()
    if not rows:
        print("no ratings found")
        return
    scored = []
    for market, (_, index, suffix) in DESKS.items():
        mine = [r for r in rows if r["market"] == market]
        if not mine:
            continue
        tickers = sorted({r["symbol"] + suffix for r in mine}) + [index]
        start = min(r["date"] for r in mine)
        px = yf.download(tickers, start=start, progress=False, auto_adjust=True)["Close"]
        px.index = px.index.tz_localize(None).normalize()
        for r in mine:
            col = r["symbol"] + suffix
            if col not in px:
                continue
            s, ix = px[col].dropna(), px[index].dropna()
            d = pd.Timestamp(r["date"])
            i = s.index.searchsorted(d, side="right") - 1          # close of the analysis date
            if i < 0 or i + h >= len(s):
                continue
            t0, t1 = s.index[i], s.index[i + h]
            if t0 not in ix.index or t1 not in ix.index:
                continue
            excess = (s.iloc[i + h] / s.iloc[i] - 1) - (ix[t1] / ix[t0] - 1)
            right = excess > 0 if r["rating"] in BULL else excess < 0
            scored.append({**r, "excess_pct": round(100 * excess, 2), "right": bool(right)})
    if not scored:
        print(f"no rating has {h} trading days of history yet")
        return
    df = pd.DataFrame(scored)
    print(f"{len(df)} directional ratings with {h} trading days of outcome "
          f"({df['date'].min()} to {df['date'].max()})\n")
    for name, part in [("all", df), *df.groupby("market")]:
        print(f"== {name}: hit rate {100 * part['right'].mean():.0f}% on {len(part)} calls, "
              f"mean confidence {part['confidence'].mean():.0f}%")
        for lo, hi, label in BANDS:
            b = part[(part["confidence"] >= lo) & (part["confidence"] <= hi)]
            if len(b):
                print(f"   confidence {label:5}: {len(b):3} calls, right {100 * b['right'].mean():3.0f}% "
                      f"(stated {b['confidence'].mean():.0f}%), mean excess {b['excess_pct'].mean():+.2f}%")
        for side, names in (("bullish", BULL), ("bearish", BEAR)):
            b = part[part["rating"].isin(names)]
            if len(b):
                print(f"   {side:8}: {len(b):3} calls, right {100 * b['right'].mean():3.0f}%, mean excess {b['excess_pct'].mean():+.2f}%")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 5)
