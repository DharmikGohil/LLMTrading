"""Head-and-shoulders tops and double tops: after a completed top, do coins do worse than comparable coins?

Test plan (docs/test-plan.md) H9c on crypto (--crypto). H9, the NSE stock version, waits for the point-in-time price
table (P0-A) and is only a stub here. The exact rules are in research/prereg/H9c.json; the detectors are in
indtrader/research/patterns.py (Lo, Mamaysky & Wang 2000, plus the plan's completion rule).

Step 1 (the signal): for each of 4 variants (kernel or swing turning points x head-and-shoulders or double top), the
events are completed tops on coins in the day's top-20 universe. Outcome: the return from the next day's open over 1,
7 and 30 days, net of 0.30% round-trip costs, minus the average net return of the other coins in the same 30-day-
return quintile that day (the main comparison), averaged across coins per date, Newey-West t with lags >= horizon.
The design-period events are counted first; a variant with fewer than 300 stops at "too little data" and none of its
outcomes are computed. Step 2 (the exit flag on the BTC + ETH 50-day trend rule) runs only if a variant passes the
step-1 design line.

Usage:
  python scripts/study_head_shoulders.py --crypto --counts-only     # design-period event counts, no outcomes
  python scripts/study_head_shoulders.py --crypto --period design
  python scripts/study_head_shoulders.py --crypto --period test     # refuses unless research/prereg/H9c.json is committed
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
import warnings
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from indtrader.crypto import MIN_HISTORY, TOP_N, above  # noqa: E402
from indtrader.crypto_learn import nw_tstat  # noqa: E402
from indtrader.research import patterns, prereg  # noqa: E402
from indtrader.validation import deflated_sharpe  # noqa: E402


def _script(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_cms = _script("crypto_momentum_study")          # split_reused_tickers; it loads crypto_backtest as .cb (simulate)
split_reused_tickers = _cms.split_reused_tickers
cb = _cms.cb
FEE, SLIP, TAX = cb.FEE, cb.SLIP, cb.TAX

TEST_ID = "H9c"
DATA = ROOT / "data" / "crypto"
RESULTS = ROOT / "research" / "results"
NOT_COINS = {"fear_greed", "funding_BTC", "funding_ETH"}
VARIANTS = tuple(f"{m}-{k}" for m in patterns.METHODS for k in patterns.KINDS)   # kernel-hs, kernel-dt, swing-hs, swing-dt
HORIZONS = (1, 7, 30)
MIN_EVENTS = 300
PASS_T_DESIGN, PASS_T_TEST, PASS_SHARE = -3.0, -2.0, 0.5
RET_LOOKBACK = 30            # 30-day return for the quintile match
QUINTILES = 5
N_RANDOM = 1000
SEED = 909
COST_MULTS = (1, 2)
EPISODE_GAP = 30             # a coin's events no more than 30 days apart are one episode
GAP_SPLIT = 7                # a series is cut into separate coins at a gap of more than 7 days
DESK = ("BTC", "ETH")
TREND_SMA = 50
STEP2_DESIGN_START = "2020-01-01"
WALK_FORWARD = 4
TDS = 0.01


# ------------------------------------------------------------------------------------------------------------ data

def split_gaps(df: pd.DataFrame, gap: int = GAP_SPLIT) -> list[pd.DataFrame]:
    """Cut a series at every gap of more than `gap` days: no window or return crosses such a gap."""
    d = df.index.to_series().diff().dt.days.to_numpy()
    cuts = [0, *np.flatnonzero(d > gap).tolist(), len(df)]
    return [df.iloc[a:b] for a, b in zip(cuts[:-1], cuts[1:], strict=True) if b > a]


def load_panel(end: str) -> dict[str, pd.DataFrame]:
    """Every coin file, cut at `end` as soon as it is read (nothing later reaches any calculation). A reused ticker is
    split (crypto_momentum_study.split_reused_tickers), then any gap of over 7 days starts a new series; series with
    fewer than MIN_HISTORY rows are dropped, as crypto_momentum_study.load_all does (they can never join the top 20)."""
    out = {}
    for f in sorted(DATA.glob("*.csv")):
        if f.stem in NOT_COINS:
            continue
        df = pd.read_csv(f, parse_dates=["date"]).set_index("date").sort_index()
        df = df.loc[: pd.Timestamp(end), ["open", "high", "low", "close", "volume"]].astype(float)
        if df.empty:
            continue
        for name, part in split_reused_tickers(f.stem, df):
            for k, seg in enumerate(split_gaps(part)):
                if len(seg) >= MIN_HISTORY:
                    out[name if k == 0 else f"{name}~{k + 1}"] = seg
    return out


def to_arrays(panel: dict[str, pd.DataFrame]) -> tuple[pd.DatetimeIndex, list[str], dict[str, np.ndarray]]:
    idx = pd.DatetimeIndex(sorted(set().union(*[df.index for df in panel.values()])))
    names = list(panel)
    arr = {f: np.column_stack([panel[n][f].reindex(idx).to_numpy() for n in names])
           for f in ("open", "high", "low", "close", "volume")}
    return idx, names, arr


def period_bounds(period: str) -> tuple[str | None, str]:
    if period == "design":
        return None, prereg.CRYPTO_DESIGN_END
    return prereg.CRYPTO_TEST_START, prereg.CRYPTO_TEST_END


def universe_mask(close: np.ndarray, volume: np.ndarray, top_n: int = TOP_N, min_history: int = MIN_HISTORY) -> np.ndarray:
    """(T, C) True where a coin is in that day's top 20 by 30-day average traded value among coins with at least 120
    days of history and a close that day: indtrader.crypto.universe, vectorised. Uses data up to that day only."""
    T, C = close.shape
    hist = np.cumsum(np.isfinite(close), axis=0)
    value30 = pd.DataFrame(volume).rolling(30, min_periods=20).mean().to_numpy()
    elig = (hist >= min_history) & np.isfinite(close) & np.isfinite(value30)
    v = np.where(elig, value30, -np.inf)
    order = np.argsort(-v, axis=1, kind="stable")
    rank = np.empty_like(order)
    rank[np.arange(T)[:, None], order] = np.arange(C)[None, :]
    return elig & (rank < top_n)


def quintiles(close: np.ndarray, univ: np.ndarray, lookback: int = RET_LOOKBACK, q: int = QUINTILES) -> np.ndarray:
    """(T, C) quintile 0..4 of the 30-day return (close t / close t-30) among the day's universe; -1 outside it."""
    T, C = close.shape
    prev = np.vstack([np.full((lookback, C), np.nan), close[:-lookback]])
    with np.errstate(invalid="ignore", divide="ignore"):
        r = close / prev - 1
    out = np.full((T, C), -1, dtype=int)
    for t in range(T):
        m = np.flatnonzero(univ[t] & np.isfinite(r[t]))
        if not len(m):
            continue
        order = m[np.argsort(r[t, m], kind="stable")]
        out[t, order] = (np.arange(len(m)) * q) // len(m)
    return out


def life(close: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Last row with a close per coin, and whether the coin's data ends inside the period (delisted: sold at its last
    close) rather than at the period end."""
    T, C = close.shape
    fin = np.isfinite(close)
    last = np.array([np.flatnonzero(fin[:, c])[-1] if fin[:, c].any() else -1 for c in range(C)])
    return last, last < T - 1


def forward_returns(open_: np.ndarray, close: np.ndarray, h: int, last: np.ndarray, delisted: np.ndarray) -> np.ndarray:
    """(T, C) return from the open of t+1 to the close of t+h. A coin whose data ends (inside the period) before t+h
    is sold at its last close; a window that runs past the period end (the data is cut there) is NaN, so no outcome
    after the period is used. NaN when there is no open on t+1."""
    T, C = close.shape
    out = np.full((T, C), np.nan)
    rows = np.arange(T)
    for c in range(C):
        if last[c] < 1:
            continue
        o1 = np.r_[open_[1:, c], np.nan]
        end = rows + h
        xc = np.full(T, np.nan)
        inside = end <= last[c]
        xc[inside] = close[end[inside], c]
        if delisted[c]:
            xc[~inside] = close[last[c], c]
        ok = rows + 1 <= last[c]
        with np.errstate(invalid="ignore", divide="ignore"):
            out[ok, c] = xc[ok] / o1[ok] - 1
    return out


def after_tax(x, tax: float = TAX) -> np.ndarray:
    """India: a profitable event keeps (1 - tax) of its gain; a loss is kept in full (no set-off)."""
    x = np.asarray(x, dtype=float)
    with np.errstate(invalid="ignore"):
        return np.where(x > 0, x * (1 - tax), x)


# ---------------------------------------------------------------------------------------------------------- events

def detect_events(arr: dict[str, np.ndarray], names: list[str]) -> dict[str, list[dict]]:
    """Every pattern each detector finds on each coin (detected and, if so, completed), rows of the panel."""
    out: dict[str, list[dict]] = {v: [] for v in VARIANTS}
    for c, _name in enumerate(names):
        fin = np.flatnonzero(np.isfinite(arr["close"][:, c]))
        if not len(fin):
            continue
        a, b = fin[0], fin[-1] + 1
        close, high, low = arr["close"][a:b, c], arr["high"][a:b, c], arr["low"][a:b, c]
        found = patterns.detect_kernel(close) + patterns.detect_swing(high, low, close)
        for p in found:
            out[f"{p.method}-{p.kind}"].append({
                "coin": c, "detect": int(a + p.detect), "complete": None if p.complete is None else int(a + p.complete),
                "points": [(int(a + r), float(v)) for r, v in p.points]})
    return out


def completed_events(found: list[dict], univ: np.ndarray, first: int) -> list[dict]:
    """Completed tops on a coin in the top-20 universe on the completion day, inside the period; one event per coin
    and completion day (the earliest-detected pattern)."""
    seen: dict[tuple[int, int], dict] = {}
    for p in sorted(found, key=lambda p: p["detect"]):
        c = p["complete"]
        if c is None or c < first or not univ[c, p["coin"]]:
            continue
        seen.setdefault((p["coin"], c), p)
    return sorted(seen.values(), key=lambda p: (p["complete"], p["coin"]))


def comparables(quint: np.ndarray, c: int, i: int) -> np.ndarray:
    q = quint[c, i]
    if q < 0:
        return np.empty(0, dtype=int)
    m = np.flatnonzero(quint[c] == q)
    return m[m != i]


def episodes(rows_by_coin: dict[int, list[int]], gap: int = EPISODE_GAP) -> int:
    """Per coin, events no more than `gap` days apart form one episode."""
    n = 0
    for rows in rows_by_coin.values():
        r = np.unique(rows)
        if len(r):
            n += int(1 + (np.diff(r) > gap).sum())
    return n


def count(events: list[dict], ctx: dict) -> dict:
    """Event counts, with no outcome: the 300 floor uses events whose 30-day window ends inside the period, with an
    open on the next day and at least one other universe coin (with an open on the next day) in the same quintile."""
    T = ctx["T"]
    opn, quint, idx, names = ctx["arr"]["open"], ctx["quint"], ctx["idx"], ctx["names"]
    usable, by_coin = [], {}
    for e in events:
        c, i = e["complete"], e["coin"]
        nxt = c + 1 < T and np.isfinite(opn[c + 1, i])
        comps = comparables(quint, c, i)
        has_comp = bool(nxt and any(np.isfinite(opn[c + 1, j]) for j in comps))
        if c + max(HORIZONS) <= T - 1 and nxt and has_comp:
            usable.append(e)
            by_coin.setdefault(i, []).append(c)
    years = pd.Series([idx[e["complete"]].year for e in usable], dtype=int).value_counts().sort_index()
    return {"completed_in_universe": len(events), "usable": len(usable),
            "event_days": len({e["complete"] for e in usable}), "episodes": episodes(by_coin),
            "by_year": {int(y): int(n) for y, n in years.items()},
            "by_coin": dict(sorted(((names[i], len(v)) for i, v in by_coin.items()), key=lambda kv: -kv[1])),
            "btc_eth": sum(1 for e in usable if names[e["coin"]] in DESK), "_usable": usable}


# ------------------------------------------------------------------------------------------------------ statistics

def nw_lags(n: int, h: int) -> int:
    """At least the horizon in days, and at least the Newey-West (1994) rule of thumb floor(4 (n/100)^(2/9))."""
    return max(h, int(4 * (max(n, 1) / 100) ** (2 / 9)))


def day_average(rows: np.ndarray, values: np.ndarray) -> np.ndarray:
    """Average across coins on each completion day first (NaN values dropped), in date order."""
    ok = np.isfinite(values)
    s = pd.Series(values[ok]).groupby(rows[ok]).mean()
    return s.sort_index().to_numpy()


def nw_summary(daily: np.ndarray, h: int) -> dict:
    x = np.asarray(daily, dtype=float)
    x = x[np.isfinite(x)]
    if len(x) < 3:
        return {"n_days": int(len(x)), "mean": _f(x.mean()) if len(x) else None, "t": None}
    lags = nw_lags(len(x), h)
    t = nw_tstat(x, lags)
    m = float(x.mean())
    se = abs(m / t) if np.isfinite(t) and t != 0 else float("nan")
    return {"n_days": int(len(x)), "mean": _f(m), "t": _f(t, 3), "lags": lags,
            "ci95": [_f(m - 1.96 * se), _f(m + 1.96 * se)] if np.isfinite(se) else None}


def book(paths: list[list[tuple[int, float]]], first: int, T: int, idx: pd.DatetimeIndex) -> dict:
    """Calendar-time book: equal weight across open positions each day, zero on days with none. paths: per position,
    (row, that day's return, costs already in). Days from `first` to the period end."""
    num, den, sold = np.zeros(T), np.zeros(T), np.zeros(T)
    for p in paths:
        for row, r in p:
            num[row] += r
            den[row] += 1
        if p:
            sold[p[-1][0]] += 1
    ret = np.where(den > 0, num / np.maximum(den, 1), 0.0)[first:]
    share_sold = np.where(den > 0, sold / np.maximum(den, 1), 0.0)[first:]
    eq = np.cumprod(1 + ret)
    sd = ret.std(ddof=1) if len(ret) > 1 else 0.0
    years = pd.Series(share_sold, index=idx[first:]).groupby(idx[first:].year).sum()
    return {"days": int(len(ret)), "days_invested": int((den[first:] > 0).sum()),
            "total_return": _f(eq[-1] - 1) if len(eq) else None,
            "sharpe": _f(math.sqrt(365) * ret.mean() / sd, 2) if sd > 0 else None,
            "max_drawdown": _f((eq / np.maximum.accumulate(eq) - 1).min()) if len(eq) else None,
            "approx_tds_pct_of_capital_by_year": {int(y): _f(100 * TDS * v, 2) for y, v in years.items()}}


def daily_path(open_: np.ndarray, close: np.ndarray, c: int, j: int, h: int, last: np.ndarray) -> list[tuple[int, float]]:
    """Daily returns of a position bought at the open of c+1 and sold at the close of c+h (or at the coin's last close
    if its data ends first)."""
    end = min(c + h, last[j])
    out = []
    for row in range(c + 1, end + 1):
        base = open_[row, j] if row == c + 1 else close[row - 1, j]
        r = close[row, j] / base - 1
        out.append((row, float(r) if np.isfinite(r) else 0.0))          # a missing day inside a short gap counts as flat
    return out


def outcomes(events: list[dict], ctx: dict, variant: str) -> dict:
    """Step-1 statistics for one variant and one set of events (only called when the event count is >= 300)."""
    arr, quint, univ, T, first = ctx["arr"], ctx["quint"], ctx["univ"], ctx["T"], ctx["first"]
    last, idx = ctx["last"], ctx["idx"]
    vi = VARIANTS.index(variant)
    rt = 2 * (FEE + SLIP)
    res = {}
    for h in HORIZONS:
        FR = ctx["fr"][h]
        rows, coins, re, rq, rqt, rqt2, rew, rr_mean, rr_sets, paths_ev, paths_ab = [], [], [], [], [], [], [], [], [], [], []
        for e in events:
            c, i = e["complete"], e["coin"]
            r = FR[c, i]
            comps = [j for j in comparables(quint, c, i) if np.isfinite(FR[c, j])]
            if not np.isfinite(r) or not comps:
                continue
            rows.append(c)
            coins.append(i)
            re.append(r)
            rq.append(float(np.mean(FR[c, comps])))
            rqt.append(float(np.mean(after_tax(FR[c, comps] - rt))))
            rqt2.append(float(np.mean(after_tax(FR[c, comps] - 2 * rt))))
            members = np.flatnonzero(univ[c] & np.isfinite(FR[c]))
            rew.append(float(np.mean(FR[c, members])))
            elig = ctx["rand_elig"][h][i]
            rng = np.random.default_rng([SEED, vi, h, c, i])
            draws = FR[elig[rng.integers(len(elig), size=N_RANDOM)], i] if len(elig) else np.full(N_RANDOM, np.nan)
            rr_mean.append(float(np.mean(draws)))
            rr_sets.append(draws)
            pe = daily_path(arr["open"], arr["close"], c, i, h, last)
            pe = [(row, r_ - (FEE + SLIP) * ((k == 0) + (k == len(pe) - 1))) for k, (row, r_) in enumerate(pe)]
            paths_ev.append(pe)
            basket = {}
            for j in comps:
                for row, r_ in daily_path(arr["open"], arr["close"], c, j, h, last):
                    basket.setdefault(row, []).append(r_)
            ab = [(row, r_ - float(np.sum(basket.get(row, [0.0]))) / len(comps))
                  for row, r_ in daily_path(arr["open"], arr["close"], c, i, h, last)]
            paths_ab.append(ab)
        rows_a, re_a, rq_a = np.array(rows), np.array(re), np.array(rq)
        n = len(rows_a)
        if not n:
            res[f"{h}d"] = {"events_with_outcome": 0}
            continue
        by_coin = {}
        for c, i in zip(rows, coins, strict=True):
            by_coin.setdefault(i, []).append(c)
        ab_daily = day_average(rows_a, re_a - rq_a)
        out = {"events_with_outcome": int(n), "event_days": int(len(set(rows))), "episodes": episodes(by_coin),
               "main_vs_quintile": {**nw_summary(ab_daily, h),
                                    "note": "event net return minus the average net return of the other coins in its "
                                            "30-day-return quintile; the same 0.30% round trip is charged on both sides"},
               "share_events_below_quintile": _f(np.mean(re_a < rq_a)),
               "main_after_tax": nw_summary(day_average(rows_a, after_tax(re_a - rt) - np.array(rqt)), h),
               "main_after_tax_costs_doubled": nw_summary(day_average(rows_a, after_tax(re_a - 2 * rt) - np.array(rqt2)), h),
               "vs_ew_top20": nw_summary(day_average(rows_a, re_a - np.array(rew)), h),
               "lines": {}}
        rr_a = np.array(rr_mean)
        out["vs_same_coin_random_dates"] = nw_summary(day_average(rows_a, re_a - rr_a), h)
        sets = np.array(rr_sets)                             # (n, N_RANDOM)
        actual = float(np.mean(day_average(rows_a, re_a - rt)))
        rand_means = np.array([np.mean(day_average(rows_a, sets[:, j] - rt)) for j in range(N_RANDOM)])
        rand_means = rand_means[np.isfinite(rand_means)]
        out["vs_same_coin_random_dates"].update({
            "event_mean_net": _f(actual), "random_sets_median": _f(np.median(rand_means)) if len(rand_means) else None,
            "share_random_sets_below_event_mean": _f(np.mean(rand_means < actual)) if len(rand_means) else None})
        for mult in COST_MULTS:
            cost = mult * rt
            for taxed in (False, True):
                x = re_a - cost
                if taxed:
                    x = after_tax(x)
                out["lines"][f"event return, costs {100 * cost:.2f}% {'after tax' if taxed else 'pre-tax'}"] = \
                    nw_summary(day_average(rows_a, x), h)
        out["event_book_costs_0.30%"] = book(paths_ev, first, T, idx)
        out["abnormal_book_vs_quintile"] = book(paths_ab, first, T, idx)
        res[f"{h}d"] = out
    return res


def design_pass(res: dict) -> tuple[bool, float | None, float | None, str]:
    """Step 1 design line: Newey-West t <= -3 on the main comparison at every horizon (1, 7 and 30 days).
    Returns (passed, binding t = the largest of the three, its mean, the binding horizon)."""
    ts = {h: (res[f"{h}d"].get("main_vs_quintile") or {}).get("t") for h in HORIZONS}
    if any(t is None for t in ts.values()):
        return False, None, None, ""
    hb = max(ts, key=ts.get)
    return all(t <= PASS_T_DESIGN for t in ts.values()), ts[hb], res[f"{hb}d"]["main_vs_quintile"]["mean"], f"{hb}d"


def _f(x, nd: int = 6):
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return round(x, nd) if math.isfinite(x) else None


# ------------------------------------------------------------------------------------------- step 2: the exit flag

def exit_flag_state(close: pd.Series, flags: set, n: int = TREND_SMA) -> pd.Series:
    """True on days when the coin's half is held out by a completed top: from the completion day (decided at its
    close) until the next fresh close above the n-day average (above that day, not above the day before). A flag on
    the same day as a fresh close above wins."""
    s = close.dropna()
    sma = s.rolling(n).mean()
    ab = (s > sma) & (s.expanding().count() > n)
    fresh = ab & ~ab.shift(1, fill_value=False)
    out, state = [], False
    for day in s.index:
        if day in flags:
            state = True
        elif state and fresh.loc[day]:
            state = False
        out.append(state)
    return pd.Series(out, index=s.index)


def trend_weights(out_state: dict[str, pd.Series] | None):
    """The BTC + ETH 50-day trend rule (half each while above its 50-day average), optionally with the exit flag."""
    def fn(day, c):
        w = {}
        for k in DESK:
            if k in c and above(c[k], TREND_SMA) and not (out_state and bool(out_state[k].get(day, False))):
                w[k] = 0.5
        return w
    return fn


def _simulate(opens, closes, fn, start, mult: int = 1) -> dict:
    fee, slip = cb.FEE, cb.SLIP
    try:
        cb.FEE, cb.SLIP = mult * fee, mult * slip
        return cb.simulate(opens, closes, fn, start)
    finally:
        cb.FEE, cb.SLIP = fee, slip


def step2(flags: dict[str, set], panel: dict[str, pd.DataFrame], start: str, end: str) -> dict:
    """Plain BTC + ETH 50-day trend against the same rule with the exit flag, and just hold BTC, from `start` to `end`
    with scripts/crypto_backtest.py simulate (costs, the after-tax book); costs doubled; 4 walk-forward windows."""
    opens = pd.DataFrame({k: panel[k]["open"] for k in DESK}).loc[:end]
    closes = pd.DataFrame({k: panel[k]["close"] for k in DESK}).loc[:end]
    state = {k: exit_flag_state(closes[k], flags.get(k, set())) for k in DESK}
    rules = {"plain trend": trend_weights(None), "trend + exit flag": trend_weights(state),
             "just hold BTC": lambda day, c: {"BTC": 1.0}}
    out = {"start": start, "end": end, "flags": {k: sorted(str(d.date()) for d in v) for k, v in flags.items()}, "rules": {}}
    curves = {}
    for name, fn in rules.items():
        r = _simulate(opens, closes, fn, start)
        r2 = _simulate(opens, closes, fn, start, 2)
        s = cb.stats(r)
        curves[name] = r["equity"]
        out["rules"][name] = {**{k: s[k] for k in ("total_return_pct", "cagr_pct", "max_dd_pct", "sharpe", "trades",
                                                   "india_after_tax_return_pct")},
                              "costs_doubled_return_pct": cb.stats(r2)["total_return_pct"],
                              "costs_doubled_after_tax_return_pct": cb.stats(r2)["india_after_tax_return_pct"]}
    days = closes.index[closes.index >= pd.Timestamp(start)]
    parts = np.array_split(np.arange(len(days)), WALK_FORWARD)
    wins, windows = 0, []
    for p in parts:
        a, b = days[p[0]], days[p[-1]]
        o, c = opens.loc[:b], closes.loc[:b]
        f = cb.stats(_simulate(o, c, rules["trend + exit flag"], str(a.date())))["india_after_tax_return_pct"]
        g = cb.stats(_simulate(o, c, rules["plain trend"], str(a.date())))["india_after_tax_return_pct"]
        windows.append({"from": str(a.date()), "to": str(b.date()), "flag_after_tax_pct": f, "plain_after_tax_pct": g})
        wins += int(f > g)
    out["walk_forward"] = windows
    out["deflated_sharpe_flag"] = deflated_sharpe(curves["trend + exit flag"], max(prereg.trial_count("crypto"), 1))
    fl, pl = out["rules"]["trend + exit flag"], out["rules"]["plain trend"]
    out["lines"] = {"beats_plain_after_tax": fl["india_after_tax_return_pct"] > pl["india_after_tax_return_pct"],
                    "walk_forward_windows_won": wins,
                    "max_dd_no_deeper": fl["max_dd_pct"] >= pl["max_dd_pct"]}
    out["pass_line_met"] = bool(out["lines"]["beats_plain_after_tax"] and wins >= 3 and out["lines"]["max_dd_no_deeper"])
    return out


# ------------------------------------------------------------------------------------------------------- the study

def check_spec(spec: dict) -> None:
    """The script's and detector's constants must match the pre-registration."""
    p = spec["parameters"]
    want = {"window": patterns.WINDOW, "lag": patterns.LAG, "tolerance": patterns.TOL, "dt_min_gap": patterns.DT_MIN_GAP,
            "complete_within": patterns.COMPLETE_WITHIN, "bandwidth_factor": patterns.BW_FACTOR,
            "bandwidth_grid": [float(patterns.BW_GRID[0]), float(patterns.BW_GRID[-1]), 0.1], "swing_k": patterns.SWING_K,
            "horizons": list(HORIZONS), "min_events": MIN_EVENTS, "top_n": TOP_N, "min_history": MIN_HISTORY,
            "return_lookback": RET_LOOKBACK, "quintiles": QUINTILES, "n_random": N_RANDOM, "seed": SEED, "fee": FEE,
            "slippage": SLIP, "tax": TAX, "cost_multipliers": list(COST_MULTS), "episode_gap": EPISODE_GAP,
            "gap_split_days": GAP_SPLIT, "trend_sma": TREND_SMA, "step2_design_start": STEP2_DESIGN_START,
            "pass_t_design": PASS_T_DESIGN, "pass_t_test": PASS_T_TEST, "pass_share_of_design": PASS_SHARE}
    bad = {k: (p.get(k), v) for k, v in want.items() if p.get(k) != v}
    if bad:
        raise SystemExit(f"script constants differ from research/prereg/{TEST_ID}.json: {bad}")


def context(idx: pd.DatetimeIndex, names: list[str], arr: dict[str, np.ndarray], first: int) -> dict:
    """Everything the counts and outcomes need, computed from the panel (data up to the period end)."""
    univ = universe_mask(arr["close"], arr["volume"])
    last, delisted = life(arr["close"])
    return {"idx": idx, "names": names, "arr": arr, "T": len(idx), "first": first, "univ": univ,
            "quint": quintiles(arr["close"], univ), "last": last, "delisted": delisted}


def build(period: str) -> tuple[dict, dict]:
    start, end = period_bounds(period)
    panel = load_panel(end)
    idx, names, arr = to_arrays(panel)
    if idx[-1] != pd.Timestamp(end):
        raise RuntimeError(f"the panel must end on the period end {end}, not {idx[-1].date()}")
    if (np.diff(idx.values).astype("timedelta64[D]").astype(int) != 1).any():
        raise RuntimeError("the panel's dates are not consecutive days")
    first = 0 if start is None else int(np.searchsorted(idx, pd.Timestamp(start)))
    ctx = context(idx, names, arr, first)
    ctx.update({"panel": panel, "start": start, "end": end})
    found = detect_events(arr, names)
    ctx["found"] = found
    events = {v: completed_events(found[v], ctx["univ"], first) for v in VARIANTS}
    detected = {v: {"patterns_detected": sum(1 for p in found[v] if p["detect"] >= first),
                    "completed_any_coin": sum(1 for p in found[v] if p["complete"] is not None and p["complete"] >= first)}
                for v in VARIANTS}
    return ctx, {"events": events, "detected": detected}


def counts_only() -> dict:
    ctx, ev = build("design")
    out = {}
    for v in VARIANTS:
        n = count(ev["events"][v], ctx)
        n.pop("_usable")
        out[v] = {**ev["detected"][v], **n}
    return out


def add_outcome_inputs(ctx: dict) -> None:
    arr, first, univ = ctx["arr"], ctx["first"], ctx["univ"]
    ctx["fr"] = {h: forward_returns(arr["open"], arr["close"], h, ctx["last"], ctx["delisted"]) for h in HORIZONS}
    ctx["rand_elig"] = {h: [np.flatnonzero(univ[first:, i] & np.isfinite(ctx["fr"][h][first:, i])) + first
                            for i in range(len(ctx["names"]))] for h in HORIZONS}


def run(period: str, spec: dict, only: list[str] | None = None) -> dict:
    check_spec(spec)
    ctx, ev = build(period)
    idx, names = ctx["idx"], ctx["names"]
    res = {"id": TEST_ID, "period": period, "run_at": datetime.now(UTC).isoformat(timespec="seconds"),
           "data_from": str(idx[0].date()), "data_to": str(idx[-1].date()),
           "period_start": ctx["start"] or str(idx[0].date()), "period_end": ctx["end"], "series": len(names),
           "costs_round_trip": 2 * (FEE + SLIP), "tax": TAX, "min_events": MIN_EVENTS, "variants": {}}
    counted = {}
    for v in VARIANTS:                                  # 1) count every variant before any outcome
        n = count(ev["events"][v], ctx)
        counted[v] = n.pop("_usable")
        res["variants"][v] = {"counts": {**ev["detected"][v], **n}}
    # Design: outcomes only for variants with >= 300 events. Test: every variant that passed the design line, whatever
    # its test-period count (prereg clarification on the 300 floor), so the outcome inputs are needed for all of them.
    need = [v for v in VARIANTS if (only is None or v in only) and (period == "test" or len(counted[v]) >= MIN_EVENTS)]
    if need:
        add_outcome_inputs(ctx)
    for v in VARIANTS:
        out = res["variants"][v]
        if only is not None and v not in only:
            out["status"] = "not run in this period: it did not pass the step-1 design line"
            continue
        if period == "design" and len(counted[v]) < MIN_EVENTS:
            out["status"] = f"too little data: {len(counted[v])} usable events, fewer than {MIN_EVENTS}; no outcome computed"
            out["pass_line_met"] = False
            continue
        out["status"] = "outcomes computed"
        out["top20"] = outcomes(counted[v], ctx, v)
        desk = [e for e in counted[v] if names[e["coin"]] in DESK]
        out["btc_eth"] = (outcomes(desk, ctx, v) if len(desk) >= MIN_EVENTS else
                          f"too little data: {len(desk)} BTC and ETH events, fewer than {MIN_EVENTS}; no outcome computed")
        ok, t, m, hb = design_pass(out["top20"])
        out["binding"] = {"horizon": hb, "t": t, "mean": m}
        out["pass_line_met"] = ok if period == "design" else None
    res["_ctx"] = ctx
    res["_events"] = counted
    return res


def test_lines(res: dict, design: dict) -> None:
    """Test period: t <= -2 at every horizon and at least half the design effect (test mean <= design mean / 2)."""
    for v, out in res["variants"].items():
        if "top20" not in out:
            continue
        d = design["variants"][v]["top20"]
        ok = True
        for h in HORIZONS:
            tm = out["top20"][f"{h}d"].get("main_vs_quintile") or {}      # no test events at this horizon: fails
            dm = d[f"{h}d"]["main_vs_quintile"]["mean"]
            ok &= tm.get("t") is not None and tm["t"] <= PASS_T_TEST and tm["mean"] <= PASS_SHARE * dm
        out["pass_line_met"] = bool(ok)


def flags_for_step2(res: dict, passing: list[str]) -> dict[str, set]:
    """Completion days of every completed top on BTC and ETH found by the passing variants, from the start of the
    data (a flag raised before the step-2 start still holds the coin out until its next fresh close above)."""
    ctx = res["_ctx"]
    flags: dict[str, set] = {k: set() for k in DESK}
    for v in passing:
        for p in ctx["found"][v]:
            n = ctx["names"][p["coin"]]
            if n in DESK and p["complete"] is not None:
                flags[n].add(ctx["idx"][p["complete"]])
    return flags


def log(res: dict) -> None:
    kind = "design" if res["period"] == "design" else "test"
    for v, out in res["variants"].items():
        if out.get("status", "").startswith("not run"):
            continue
        n = out["counts"]["usable"]
        if "top20" not in out:
            prereg.log_trial(TEST_ID, v, res["period"], "usable_events", n, n=n, asset="crypto", kind=kind,
                             note=f"too little data (<{MIN_EVENTS}): no outcome computed")
            continue
        b = out["binding"]
        prereg.log_trial(TEST_ID, v, res["period"], "main_abnormal_mean_at_binding_horizon", b["mean"], t=b["t"], n=n,
                         asset="crypto", kind=kind,
                         note=f"binding horizon {b['horizon']} (the largest t of 1/7/30d); pass line met: {out['pass_line_met']}")
    s2 = res.get("step2")
    if isinstance(s2, dict) and "rules" in s2:
        fl, pl = s2["rules"]["trend + exit flag"], s2["rules"]["plain trend"]
        prereg.log_trial(TEST_ID, "step2-exit-flag", res["period"], "after_tax_return_pct_minus_plain",
                         fl["india_after_tax_return_pct"] - pl["india_after_tax_return_pct"], asset="crypto", kind=kind,
                         note=f"walk-forward windows won {s2['lines']['walk_forward_windows_won']}/4; "
                              f"pass line met: {s2['pass_line_met']}")


def summary(res: dict) -> str:
    out = [f"H9c double tops and head-and-shoulders, {res['period']} period {res['period_start']} to {res['period_end']} "
           f"({res['series']} coin series; top-20 universe; events need >= {res['min_events']})"]
    for v, x in res["variants"].items():
        c = x["counts"]
        out.append(f"\n{v}: {x.get('status')}")
        out.append(f"  patterns detected {c['patterns_detected']}, completed (any coin) {c['completed_any_coin']}, "
                   f"completed in the top 20 {c['completed_in_universe']}, usable {c['usable']} on {c['event_days']} days in "
                   f"{c['episodes']} episodes (BTC/ETH {c['btc_eth']}); by year {c['by_year']}")
        if "top20" in x:
            for h, hv in x["top20"].items():
                if not hv.get("events_with_outcome"):
                    continue
                m = hv["main_vs_quintile"]
                bk = hv["event_book_costs_0.30%"]
                out.append(f"  {h}: n={hv['events_with_outcome']}, vs same-quintile coins {_pct(m['mean'], 2)} (NW t {m['t']}, "
                           f"95% CI {m.get('ci95')}); after tax {_pct(hv['main_after_tax']['mean'], 2)}; vs EW top 20 "
                           f"{_pct(hv['vs_ew_top20']['mean'], 2)} (t {hv['vs_ew_top20']['t']}); vs same coin on random dates "
                           f"{_pct(hv['vs_same_coin_random_dates']['mean'], 2)} (t {hv['vs_same_coin_random_dates']['t']}); "
                           f"event book Sharpe {bk['sharpe']}, max DD {_pct(bk['max_drawdown'], 1)}")
            out.append(f"  step-1 line met in this period: {x.get('pass_line_met')}")
    s2 = res.get("step2")
    out.append(f"\nstep 2 (exit flag on the BTC + ETH 50-day trend): {s2 if isinstance(s2, str) else ''}")
    if isinstance(s2, dict) and "rules" in s2:
        for name, r in s2["rules"].items():
            out.append(f"  {name}: return {r['total_return_pct']}%, after tax {r['india_after_tax_return_pct']}%, "
                       f"max DD {r['max_dd_pct']}%, Sharpe {r['sharpe']}")
        out.append(f"  lines {s2['lines']}; pass line met: {s2['pass_line_met']}")
    return "\n".join(out)


def _pct(x, nd: int = 2) -> str:
    return "n/a" if x is None else f"{100 * x:.{nd}f}%"


def _public(res: dict) -> dict:
    return {k: v for k, v in res.items() if not k.startswith("_")}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--crypto", action="store_true", help="H9c: the daily top-20 crypto universe, and BTC and ETH alone")
    ap.add_argument("--period", choices=("design", "test"), default="design")
    ap.add_argument("--counts-only", action="store_true", help="design-period event counts, no outcomes")
    args = ap.parse_args(argv)
    if args.period == "test":
        spec = prereg.require_committed(TEST_ID)          # first: refuse unless the pre-registration is committed
    if not args.crypto:
        print("H9 (NSE stocks) waits for the point-in-time price table (P0-A). Use --crypto for H9c.")
        return 2
    if args.counts_only:
        if args.period == "test":
            raise SystemExit("--counts-only covers the design period only")
        print(json.dumps(counts_only(), indent=1))
        return 0
    RESULTS.mkdir(parents=True, exist_ok=True)
    if args.period == "design":
        spec = prereg.load(TEST_ID)
        res = run("design", spec)
        passing = [v for v, x in res["variants"].items() if x.get("pass_line_met")]
        if passing:
            res["step2"] = step2(flags_for_step2(res, passing), res["_ctx"]["panel"], STEP2_DESIGN_START, res["period_end"])
            res["step2"]["variants"] = passing
        else:
            res["step2"] = "not run: no variant passed the step-1 design line"
    else:
        dfile = RESULTS / f"{TEST_ID}_design.json"
        if not dfile.exists():
            raise SystemExit(f"{dfile} is missing: the test period runs only after the design period")
        design = json.loads(dfile.read_text())
        passing = [v for v, x in design["variants"].items() if x.get("pass_line_met")]
        if not passing:
            short = all(str(x.get("status", "")).startswith("too little data") for x in design["variants"].values())
            why = ("every variant stopped at 'too little data' in the design period (fewer than 300 events): no "
                   "conclusion is drawn (section 3, T1)" if short else
                   "no variant passed the step-1 design line, so H9c failed in the design period")
            res = {"id": TEST_ID, "period": "test", "run_at": datetime.now(UTC).isoformat(timespec="seconds"),
                   "status": f"not run: {why}"}
            (RESULTS / f"{TEST_ID}_test.json").write_text(json.dumps(res, indent=1))
            print(res["status"])
            return 0
        res = run("test", spec, only=passing)
        test_lines(res, design)
        res["step2"] = step2(flags_for_step2(res, passing), res["_ctx"]["panel"], prereg.CRYPTO_TEST_START, res["period_end"])
        res["step2"]["variants"] = passing
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        (RESULTS / f"{TEST_ID}_{args.period}.json").write_text(json.dumps(_public(res), indent=1, default=str))
    log(res)
    print(summary(res))
    print(f"\nwritten: {RESULTS / f'{TEST_ID}_{args.period}.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
