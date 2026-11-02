"""End-of-day backtest of the options desk's iron condors (and the lotto leg) on NSE bhavcopy data.

Data: data/fo/<year>.csv.gz from scripts/download_fo_bhavcopy.py (daily closes of index options).
Method, matching the live desk as closely as daily data allows:
- implied volatility from the at-the-money straddle: straddle ~ 0.8 * S * sigma * sqrt(T)
- enter `dte` trading days before each expiry when flat; short strikes `k` standard deviations out,
  wings `wing` points beyond; fills at the close, minus slippage on every leg
- exits checked at each close: take profit at 50% of the credit, stop when the loss equals the credit,
  else close on the last trading day before expiry
- charges per leg with the STT and exchange rates in force on the trade date
Limits: intraday moves between closes are not seen (a stop can only fill at a close, possibly worse than
live); daily data has no bid/ask, so slippage is a flat assumption; P&L uses today's lot sizes so years
compare like for like.
"""

from __future__ import annotations

import csv
import gzip
import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data" / "fo"
LOTS = {"NIFTY": 65, "BANKNIFTY": 30, "FINNIFTY": 60}
STEP = {"NIFTY": 50, "BANKNIFTY": 100, "FINNIFTY": 50}
WING = {"NIFTY": 200, "BANKNIFTY": 500, "FINNIFTY": 200}


def stt_rate(d: date) -> float:
    if d >= date(2026, 4, 1):
        return 0.0015
    if d >= date(2024, 10, 1):
        return 0.001
    return 0.000625


def exchange_rate(d: date) -> float:
    return 0.0003503 if d >= date(2024, 10, 1) else 0.0005


def leg_charges(d: date, side: str, premium: float, qty: int) -> float:
    value = premium * qty
    if value <= 0:
        return 0.0
    exch, sebi = value * exchange_rate(d), value * 0.000001
    stt = value * stt_rate(d) if side == "SELL" else 0.0
    stamp = value * 0.00003 if side == "BUY" else 0.0
    return 20 + exch + sebi + stt + stamp + (20 + exch + sebi) * 0.18


def load(symbol: str, years: range | None = None) -> dict[date, dict]:
    """date -> {"spot": fut_close, "chains": {expiry: {(strike, type): (close, volume)}}}"""
    days: dict[date, dict] = {}
    for f in sorted(DATA.glob("*.csv.gz")):
        if years and int(f.stem.split(".")[0]) not in years:
            continue
        with gzip.open(f, "rt") as fh:
            for r in csv.DictReader(fh):
                if r["symbol"] != symbol:
                    continue
                d = date.fromisoformat(r["date"])
                day = days.setdefault(d, {"spot": float(r["fut_close"] or 0), "chains": defaultdict(dict)})
                close, vol = float(r["close"] or 0), int(r["volume"] or 0)
                # untraded contracts carry a stale close: use NSE's settlement price for them instead
                price = close if vol > 0 else float(r["settle"] or 0) or close
                day["chains"][date.fromisoformat(r["expiry"])][(float(r["strike"]), r["type"])] = (price, vol)
    return dict(sorted(days.items()))


def atm_vol(chain: dict, spot: float, days_left: int) -> float | None:
    strikes = sorted({k for k, _ in chain})
    if not strikes or spot <= 0:
        return None
    k = min(strikes, key=lambda s: abs(s - spot))
    c, p = chain.get((k, "CE")), chain.get((k, "PE"))
    if not c or not p or c[0] <= 0 or p[0] <= 0:
        return None
    t = max(days_left, 1) / 365
    return (c[0] + p[0]) / (0.8 * spot * math.sqrt(t))


@dataclass
class Trade:
    symbol: str
    entry: date
    exit: date
    expiry: date
    legs: list
    credit_pts: float
    pnl: float
    reason: str


def run(symbol: str, days: dict[date, dict], k: float = 1.0, dte: int = 5, managed: bool = True,
        slip_pct: float = 0.02, slip_min: float = 0.5, wing: int | None = None) -> list[Trade]:
    lot, step, wing = LOTS[symbol], STEP[symbol], wing or WING[symbol]
    dates = list(days)
    idx = {d: i for i, d in enumerate(dates)}
    expiries = sorted({e for d in dates for e in days[d]["chains"]})
    trades: list[Trade] = []
    busy_until: date | None = None

    def slip(p: float) -> float:
        return max(slip_min, p * slip_pct)

    for e in expiries:
        before = [d for d in dates if d < e]
        if len(before) < dte or (busy_until and before[-dte] <= busy_until):
            continue
        d0 = before[-dte]
        day = days[d0]
        chain, spot = day["chains"].get(e), day["spot"]
        if not chain:
            continue
        vol = atm_vol(chain, spot, (e - d0).days)
        if not vol or not 0.03 < vol < 1.5:
            continue
        sd = spot * vol * math.sqrt(max((e - d0).days, 1) / 365)
        sc = math.ceil((spot + k * sd) / step) * step
        sp = math.floor((spot - k * sd) / step) * step
        spec = [(sc, "CE", "SELL"), (sp, "PE", "SELL"), (sc + wing, "CE", "BUY"), (sp - wing, "PE", "BUY")]
        quotes = [chain.get((float(s), t)) for s, t, _ in spec]
        if any(q is None or q[0] <= 0 or q[1] <= 0 for q in quotes):   # every leg must have traded that day
            continue
        fills = [(q[0] - slip(q[0])) if side == "SELL" else (q[0] + slip(q[0])) for q, (_, _, side) in zip(quotes, spec, strict=True)]
        if any(f <= 0 for f in fills):
            continue
        credit = fills[0] + fills[1] - fills[2] - fills[3]
        if credit <= 0:
            continue
        charges = sum(leg_charges(d0, side, f, lot) for f, (_, _, side) in zip(fills, spec, strict=True))
        last = before[-1]
        exit_day, reason, close_cost = last, "time exit", None
        for d in dates[idx[d0] + 1: idx[last] + 1]:
            ch = days[d]["chains"].get(e, {})
            qs = [ch.get((float(s), t)) for s, t, _ in spec]
            if any(q is None for q in qs):
                continue   # a leg not traded that day: hold the last mark
            px = [(q[0] + slip(q[0])) if side == "SELL" else max(q[0] - slip(q[0]), 0.0) for q, (_, _, side) in zip(qs, spec, strict=True)]
            cost = px[0] + px[1] - px[2] - px[3]
            close_cost, exit_day = (cost, px), d
            if managed and cost <= 0.5 * credit:
                reason = "take profit"
                break
            if managed and cost >= 2 * credit:
                reason = "stop"
                break
        if close_cost is None:
            continue
        cost, px = close_cost
        exit_side = {"SELL": "BUY", "BUY": "SELL"}
        exit_charges = sum(leg_charges(exit_day, exit_side[side], p, lot) for p, (_, _, side) in zip(px, spec, strict=True) if p > 0)
        pnl = (credit - cost) * lot - charges - exit_charges
        trades.append(Trade(symbol, d0, exit_day, e, spec, round(credit, 2), round(pnl, 2), reason))
        busy_until = exit_day
    return trades


def run_lotto(symbol: str, days: dict[date, dict], budget: float = 1000.0, dte: int = 5,
              slip_pct: float = 0.02, slip_min: float = 0.5) -> list[Trade]:
    """Buy the nearest out-of-the-money option (5-day trend direction) whose lot fits the budget; sell at 2x or
    on the last day before expiry."""
    lot = LOTS[symbol]
    dates = list(days)
    idx = {d: i for i, d in enumerate(dates)}
    trades, busy_until = [], None
    for e in sorted({e for d in dates for e in days[d]["chains"]}):
        before = [d for d in dates if d < e]
        if len(before) < dte + 5 or (busy_until and before[-dte] <= busy_until):
            continue
        d0 = before[-dte]
        i0 = idx[d0]
        spot, prev = days[d0]["spot"], days[dates[i0 - 5]]["spot"]
        kind = "CE" if spot >= prev else "PE"
        chain = days[d0]["chains"].get(e, {})
        strikes = sorted({s for s, t in chain if t == kind and (s > spot if kind == "CE" else s < spot)},
                         reverse=(kind == "PE"))
        pick = None
        for s in strikes:
            c, vol = chain[(s, kind)]
            ask = c + max(slip_min, c * slip_pct)
            if c > 0 and vol > 0 and ask * lot <= budget:
                pick = (s, ask)
                break
        if not pick:
            continue
        s, ask = pick
        cost = ask * lot + leg_charges(d0, "BUY", ask, lot)
        last, value, exit_day, reason = before[-1], 0.0, before[-1], "time exit"
        for d in dates[i0 + 1: idx[last] + 1]:
            q = days[d]["chains"].get(e, {}).get((s, kind))
            if not q:
                continue
            value, exit_day = max(q[0] - max(slip_min, q[0] * slip_pct), 0.0), d
            if value >= 2 * ask:
                reason = "target"
                break
        proceeds = value * lot - (leg_charges(exit_day, "SELL", value, lot) if value > 0 else 0)
        trades.append(Trade(symbol, d0, exit_day, e, [(s, kind, "BUY")], round(-ask, 2), round(proceeds - cost, 2), reason))
        busy_until = exit_day
    return trades


def summary(trades: list[Trade], capital: float = 100000.0) -> dict:
    if not trades:
        return {"trades": 0}
    pnl = [t.pnl for t in trades]
    eq, peak, mdd = capital, capital, 0.0
    for p in pnl:
        eq += p
        peak = max(peak, eq)
        mdd = min(mdd, (eq - peak) / peak)
    rets = [p / capital for p in pnl]
    mean = sum(rets) / len(rets)
    sd = (sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)) ** 0.5 if len(rets) > 1 else 0
    span_years = max((trades[-1].exit - trades[0].entry).days / 365.25, 0.1)
    per_year = len(trades) / span_years
    by_year = defaultdict(float)
    for t in trades:
        by_year[t.entry.year] += t.pnl
    return {"trades": len(trades), "total_pnl": round(sum(pnl)), "return_pct": round(100 * sum(pnl) / capital, 1),
            "win_rate": round(100 * sum(p > 0 for p in pnl) / len(pnl)), "avg": round(sum(pnl) / len(pnl)),
            "worst": round(min(pnl)), "best": round(max(pnl)), "max_dd_pct": round(100 * mdd, 1),
            "sharpe": round(mean / sd * math.sqrt(per_year), 2) if sd else None,
            "by_year": {y: round(v) for y, v in sorted(by_year.items())},
            "exits": {r: sum(t.reason == r for t in trades) for r in sorted({t.reason for t in trades})}}
