"""Does the open-interest build-up read (long build-up, short covering, short build-up, long unwinding) predict returns?

Data: data/futstk/<year>.csv.gz from scripts/download_futstk_bhavcopy.py (NSE stock futures, end of day).
Per stock per day:
- price change: the near-month future's close against the same contract's previous close
- OI change: total open interest across all expiries against the previous day's total (so rollover does not
  register as unwinding in one month and build-up in the next)
- bucket: price up + OI up = LONG_BUILD, price down + OI up = SHORT_BUILD, price up + OI down = SHORT_COVER,
  price down + OI down = LONG_UNWIND; moves inside a small deadband are NEUTRAL
Outcome: the same contract's return over the next 1 and 5 trading days, minus the average of all F&O stocks that
day (cross-sectional excess), so a market-wide move does not count as a signal.
Reported per bucket and per period: count, mean excess (bps), a t-stat over daily averages, and a long/short
portfolio (long the bullish buckets, short the bearish ones) after costs.
Usage: python scripts/oi_buildup_study.py [out.json]
"""

from __future__ import annotations

import csv
import gzip
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data" / "futstk"
PRICE_BAND, OI_BAND = 0.001, 0.005          # moves smaller than 0.1% (price) or 0.5% (OI) count as no change
COST = 0.0006                                # round-trip cost per leg: futures charges + slippage, about 6 bps
BUCKETS = ["LONG_BUILD", "SHORT_COVER", "SHORT_BUILD", "LONG_UNWIND", "NEUTRAL"]


def load() -> tuple[list[str], dict]:
    """date -> symbol -> {expiry: (close, oi)}"""
    days: dict[str, dict] = defaultdict(lambda: defaultdict(dict))
    for f in sorted(DATA.glob("*.csv.gz")):
        with gzip.open(f, "rt") as fh:
            for r in csv.DictReader(fh):
                days[r["date"]][r["symbol"]][r["expiry"]] = (float(r["close"]), int(r["oi"]))
    return sorted(days), days


def bucket(p: float, o: float) -> str:
    if abs(p) < PRICE_BAND or abs(o) < OI_BAND:
        return "NEUTRAL"
    if o > 0:
        return "LONG_BUILD" if p > 0 else "SHORT_BUILD"
    return "SHORT_COVER" if p > 0 else "LONG_UNWIND"


def tstat(xs: list[float]) -> float | None:
    n = len(xs)
    if n < 3:
        return None
    m = sum(xs) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1))
    return m / (sd / math.sqrt(n)) if sd else None


def main(out: str | None) -> None:
    dates, days = load()
    idx = {d: i for i, d in enumerate(dates)}
    obs = []   # (date, symbol, bucket, oi_chg, fwd1, fwd5)
    for i in range(1, len(dates) - 5):
        d, prev = dates[i], dates[i - 1]
        for sym, exps in days[d].items():
            pexps = days[prev].get(sym)
            if not pexps:
                continue
            near = min(exps)                                   # nearest expiry still listed today
            if near not in pexps or near <= d:
                continue
            c, c0 = exps[near][0], pexps[near][0]
            oi, oi0 = sum(v[1] for v in exps.values()), sum(v[1] for v in pexps.values())
            if c <= 0 or c0 <= 0 or oi0 <= 0:
                continue
            p, o = c / c0 - 1, oi / oi0 - 1
            fwd = {}
            for h in (1, 5):
                j = idx[d] + h
                nxt = days[dates[j]].get(sym, {}).get(near) if j < len(dates) else None
                fwd[h] = (nxt[0] / c - 1) if nxt and nxt[0] > 0 else None
            obs.append((d, sym, bucket(p, o), o, fwd[1], fwd[5]))

    # cross-sectional excess
    mean = {h: defaultdict(list) for h in (1, 5)}
    for d, _, _, _, f1, f5 in obs:
        if f1 is not None:
            mean[1][d].append(f1)
        if f5 is not None:
            mean[5][d].append(f5)
    avg = {h: {d: sum(v) / len(v) for d, v in mean[h].items()} for h in (1, 5)}

    def period(d: str) -> str:
        return "2023-24" if d < "2025-01-01" else "2025-26"

    res: dict = {"days": len(dates), "first": dates[0], "last": dates[-1], "observations": len(obs), "by_bucket": {}}
    for per in ("all", "2023-24", "2025-26"):
        for h in (1, 5):
            daily = {b: defaultdict(list) for b in BUCKETS}
            for d, _, b, _, f1, f5 in obs:
                f = f1 if h == 1 else f5
                if f is None or (per != "all" and period(d) != per):
                    continue
                daily[b][d].append(f - avg[h][d])
            for b in BUCKETS:
                per_day = [sum(v) / len(v) for v in daily[b].values()]
                n = sum(len(v) for v in daily[b].values())
                if not per_day:
                    continue
                res["by_bucket"][f"{per} h={h} {b}"] = {
                    "n": n, "days": len(per_day), "mean_excess_bps": round(1e4 * sum(per_day) / len(per_day), 1),
                    "t": round(tstat(per_day) or 0, 2)}

    # long bullish buckets, short bearish buckets, next day, equal weight, after costs
    by_day = defaultdict(lambda: {"long": [], "short": []})
    for d, _, b, _, f1, _ in obs:
        if f1 is None:
            continue
        if b in ("LONG_BUILD", "SHORT_COVER"):
            by_day[d]["long"].append(f1)
        elif b in ("SHORT_BUILD", "LONG_UNWIND"):
            by_day[d]["short"].append(f1)
    ls = []
    for d in sorted(by_day):
        L, S = by_day[d]["long"], by_day[d]["short"]
        if L and S:
            ls.append((d, (sum(L) / len(L) - sum(S) / len(S)) / 2 - COST))
    rets = [r for _, r in ls]
    if rets:
        m = sum(rets) / len(rets)
        sd = math.sqrt(sum((r - m) ** 2 for r in rets) / (len(rets) - 1))
        eq = 1.0
        for r in rets:
            eq *= 1 + r
        res["long_short_next_day"] = {
            "days": len(rets), "mean_bps_after_cost": round(1e4 * m, 2), "t": round(tstat(rets) or 0, 2),
            "sharpe_annual": round(m / sd * math.sqrt(252), 2) if sd else None, "total_return_pct": round(100 * (eq - 1), 1),
            "by_period": {}}
        for per in ("2023-24", "2025-26"):
            xs = [r for d, r in ls if period(d) == per]
            res["long_short_next_day"]["by_period"][per] = {
                "days": len(xs), "mean_bps_after_cost": round(1e4 * sum(xs) / len(xs), 2) if xs else None,
                "t": round(tstat(xs) or 0, 2)}
    print(json.dumps(res, indent=1))
    if out:
        Path(out).write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
