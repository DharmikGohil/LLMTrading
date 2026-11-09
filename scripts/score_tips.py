"""Score a tip sheet (social-media stock tips with targets and stops) the same way the desk's own calls are scored.

Input: a JSON file in journal/tips/ with market, entry_date, index_entry (the index level at entry) and
tips [{symbol, entry, target: [low, high], stop}]. For each tip, on daily bars from the entry date:
- which came first, the first target or the stop (a day that touches both counts as the stop: the conservative
  assumption), and on which trading day
- the return so far, and at 5 and 20 trading days, each minus the index's return from its entry level
Usage: python scripts/score_tips.py journal/tips/2026-11-08-muhurat.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def first_touch(high, low, target: float, stop: float) -> str:
    for k, (h, lo) in enumerate(zip(high, low, strict=True)):
        if lo <= stop:
            return f"STOP first (day {k + 1})"
        if h >= target:
            return f"TARGET first (day {k + 1})"
    return "open"


def main(path: str) -> None:
    import yfinance as yf

    sheet = json.loads(Path(path).read_text())
    india = sheet.get("market", "India") == "India"
    index = "^NSEI" if india else "^GSPC"
    tickers = [t["symbol"] + (".NS" if india else "") for t in sheet["tips"]]
    raw = yf.download(tickers + [index], start=sheet["entry_date"], progress=False, auto_adjust=False)
    ix = raw["Close"][index].dropna()
    i0 = float(sheet["index_entry"])
    print(f"{sheet['name']}\nentry {sheet['entry_date']}, {len(ix)} index sessions so far\n")
    print(f"{'symbol':11}{'entry':>9}{'now':>9}{'return':>9}{'vs index':>10}  {'first touch':24}{'5d vs idx':>10}{'20d vs idx':>11}")
    for t, tk in zip(sheet["tips"], tickers, strict=True):
        c = raw["Close"][tk].dropna()
        if c.empty:
            print(f"{t['symbol']:11}  no data yet")
            continue
        e = float(t["entry"])
        touch = first_touch(raw["High"][tk].dropna(), raw["Low"][tk].dropna(), t["target"][0], t["stop"])
        at = {}
        for n in (5, 20):
            if len(c) >= n and len(ix) >= n:
                at[n] = f"{100 * ((c.iloc[n - 1] / e) - (ix.iloc[n - 1] / i0)):+.2f}%"
        idx_now = ix.iloc[-1] if len(ix) else i0
        r = c.iloc[-1] / e - 1
        print(f"{t['symbol']:11}{e:9.2f}{c.iloc[-1]:9.2f}{100 * r:+8.2f}%{100 * (r - (idx_now / i0 - 1)):+9.2f}%  "
              f"{touch:24}{at.get(5, '-'):>10}{at.get(20, '-'):>11}")


if __name__ == "__main__":
    main(sys.argv[1])
