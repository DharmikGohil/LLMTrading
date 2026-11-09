"""Round numbers: do daily highs and lows stop near round levels, and does price keep going after crossing one?

Test plan (docs/test-plan.md) H19c, BTC and ETH (--crypto). H19, NSE stocks and the Nifty, waits for the
point-in-time price table (P0-A) and is only a stub here. The rules are in research/prereg/H19c.json.

Levels: for a price p, s = 10^floor(log10 p), taken from the previous close. Majors are multiples of s, minors of s/10.
Random levels sit at (k + u) * spacing with the same spacing and an offset u drawn uniformly from [0, 1).
1. Clustering: a daily high within 0.5% under a level (strictly below it), a daily low within 0.5% above one.
2. Crossing: a daily close crosses a level that no close-to-close move crossed in the previous 10 days. The move from
   the next open to the close h = 1, 3, 7 days later, signed by the direction of the cross, after 0.30% costs (and
   0.60%), with the 31.2% after-tax line (profitable events keep 68.8%).
Each round-level statistic is ranked against the same statistic at 1,000 random offsets. Pass: above the 95th
percentile in the design period and again in the test period (which runs once, after the pre-registration commit).

Usage:
  python scripts/study_round_numbers.py --crypto --period design
  python scripts/study_round_numbers.py --crypto --period test      # refuses unless research/prereg/H19c.json is committed
  python scripts/study_round_numbers.py --crypto --counts-only      # design-period crossing counts only, no outcomes
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

from indtrader.crypto_learn import nw_tstat  # noqa: E402
from indtrader.research import prereg  # noqa: E402


def _script(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_cms = _script("crypto_momentum_study")          # split_reused_tickers; it loads crypto_backtest as .cb
split_reused_tickers = _cms.split_reused_tickers
FEE, SLIP, TAX = _cms.cb.FEE, _cms.cb.SLIP, _cms.cb.TAX

TEST_ID = "H19c"
DATA = ROOT / "data" / "crypto"
RESULTS = ROOT / "research" / "results"
COINS = ("BTC", "ETH")
KINDS = ("major", "minor")
WINDOW = 0.005           # "within 0.5%"
LOOKBACK = 10            # a crossing counts only if the level was not crossed in the previous 10 days
HORIZONS = (1, 3, 7)
N_RANDOM = 1000
SEED = 20261109
COST_MULTS = (1, 2)      # costs as in section 1.0, and doubled
EPISODE_GAP = 10         # clustering: hit days at the same level no more than 10 days apart are one episode
EPISODE_QUIET = 10       # crossings: a new episode starts after more than 10 days without an event
TDS = 0.01


# ---------------------------------------------------------------------------------------------- levels and events

def scale(p) -> np.ndarray:
    """s = 10^floor(log10 p), with s <= p < 10 s exactly (NaN stays NaN)."""
    p = np.asarray(p, dtype=float)
    with np.errstate(invalid="ignore", divide="ignore"):
        s = 10.0 ** np.floor(np.log10(p))
        s = np.where(s * 10 <= p, s * 10, s)
        s = np.where(s > p, s / 10, s)
    return s


def spacing(prev_close, kind: str) -> np.ndarray:
    """Level spacing for each day from the previous close: s for majors, s/10 for minors."""
    s = scale(prev_close)
    return s if kind == "major" else s / 10


def cluster_hits(high, low, g, u, window: float = WINDOW):
    """Highs that stop just below a level and lows that stop just above one.

    high, low, g: (T,) arrays (g = spacing per day); u: offsets as a fraction of the spacing (0 = round levels).
    Returns (hit_high, hit_low, level_above_high, level_below_low), each of shape (len(u), T). The level above a
    high is the nearest level strictly above it; a high within `window` of it (high >= (1 - window) * level) is a hit.
    Lows mirror this with the nearest level strictly below."""
    u = np.atleast_1d(np.asarray(u, dtype=float))[:, None]
    with np.errstate(invalid="ignore", divide="ignore"):
        above = (np.floor(high / g - u) + 1 + u) * g
        below = (np.ceil(low / g - u) - 1 + u) * g
        hh = high >= (1 - window) * above
        hl = (low <= (1 + window) * below) & (below > 0)
    return hh, hl, above, below


def fresh_crossings(close, g, u, lookback: int = LOOKBACK) -> np.ndarray:
    """+1 (up) / -1 (down) on a day whose close crosses a level that no close-to-close move crossed in the previous
    `lookback` days, else 0. Shape (len(u), T).

    Levels sit at (k + u) * g[t], g from the previous close. With n(x) = floor(x / g - u) (the number of the highest
    level at or below x), day t crosses levels n(close[t-1]) < k <= n(close[t]) going up. The moves of days
    t-lookback .. t-1 together crossed exactly the levels between the lowest and highest bucket of closes
    t-lookback-1 .. t-1, so a level crossed on day t is new if close[t]'s bucket is beyond all of them. A day without
    lookback + 1 earlier closes is never an event."""
    close = np.asarray(close, dtype=float)
    prev = pd.Series(close).shift(1).rolling(lookback + 1, min_periods=lookback + 1)
    hi, lo = prev.max().to_numpy(), prev.min().to_numpy()
    u = np.atleast_1d(np.asarray(u, dtype=float))[:, None]
    with np.errstate(invalid="ignore", divide="ignore"):
        n = np.floor(close / g - u)
        up = n > np.floor(hi / g - u)
        down = n < np.floor(lo / g - u)
    return up.astype(np.int8) - down.astype(np.int8)


def raw_crossings(close, g) -> np.ndarray:
    """Days whose close crossed at least one round level since the previous close (no 10-day rule)."""
    close = np.asarray(close, dtype=float)
    prev = np.r_[np.nan, close[:-1]]
    ok = np.isfinite(close) & np.isfinite(prev) & np.isfinite(g)
    with np.errstate(invalid="ignore", divide="ignore"):
        return ok & (np.floor(close / g) != np.floor(prev / g))


def forward_moves(open_, close, h: int) -> np.ndarray:
    """Return from the open of day t+1 to the close of day t+h (decide at t's close, act at t+1's open). NaN past the
    end of the data, which is cut at the period end, so no outcome after the period is ever used."""
    o = pd.Series(np.asarray(open_, dtype=float)).shift(-1).to_numpy()
    c = pd.Series(np.asarray(close, dtype=float)).shift(-h).to_numpy()
    with np.errstate(invalid="ignore", divide="ignore"):
        return c / o - 1


def after_tax(x, tax: float = TAX) -> np.ndarray:
    """India: a profitable event keeps (1 - tax) of its gain; a loss is kept in full (no set-off)."""
    x = np.asarray(x, dtype=float)
    with np.errstate(invalid="ignore"):
        return np.where(x > 0, x * (1 - tax), x)


# ------------------------------------------------------------------------------------------------------ statistics

def day_mean(values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """values (..., T, C), NaN where there is no event: average across coins on each day, then across days.
    Returns (mean over days with an event, the daily averages)."""
    cnt = np.isfinite(values).sum(-1)
    tot = np.nansum(values, -1)
    daily = np.where(cnt > 0, tot / np.maximum(cnt, 1), np.nan)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return np.nanmean(daily, -1), daily


def vs_random(value: float, random_values: np.ndarray) -> dict:
    """Rank a round-level statistic against the random offsets. Pass line: strictly above the 95th percentile."""
    r = np.asarray(random_values, dtype=float)
    r = r[np.isfinite(r)]
    if not len(r) or not np.isfinite(value):
        return {"round": _f(value), "n_random": int(len(r)), "above_p95": False}
    p95 = float(np.quantile(r, 0.95, method="higher"))
    return {"round": _f(value), "random_median": _f(np.median(r)), "random_p95": _f(p95),
            "round_minus_random_median": _f(value - np.median(r)),
            "share_random_below": _f(np.mean(r < value)), "p_value": _f((1 + np.sum(r >= value)) / (1 + len(r))),
            "n_random": int(len(r)), "above_p95": bool(value > p95)}


def nw_lags(n: int, h: int) -> int:
    """At least the horizon in days, and at least the Newey-West (1994) rule of thumb floor(4 (n/100)^(2/9))."""
    return max(h, int(4 * (max(n, 1) / 100) ** (2 / 9)))


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


def episodes(days, gap: int = EPISODE_GAP) -> int:
    """Event days no more than `gap` days apart form one episode (clustering: hit days at one level)."""
    d = np.unique(np.asarray(days, dtype="datetime64[D]"))
    if not len(d):
        return 0
    return int(1 + (np.diff(d) > np.timedelta64(gap, "D")).sum())


def crossing_episodes(days, quiet: int = EPISODE_QUIET) -> int:
    """Crossing episodes (research/prereg/H19c.json): event days pooled across coins; a new episode starts only after
    more than `quiet` days without an event, so event days up to quiet + 1 days apart are one episode."""
    return episodes(days, quiet + 1)


def calendar_portfolio(open_: np.ndarray, close: np.ndarray, events: np.ndarray, h: int, cost_side: float,
                       dates: pd.DatetimeIndex, first: int) -> dict:
    """Equal weight across open event positions, rebalanced daily; a down-cross is held short. Entry at the open of
    t+1, exit at the close of t+h, `cost_side` charged at entry and at exit; zero return on days with nothing open.
    Days from `first` to the last day of the data (the period end). Pre-tax."""
    T, _ = close.shape
    prev = np.vstack([np.full((1, close.shape[1]), np.nan), close[:-1]])
    with np.errstate(invalid="ignore", divide="ignore"):
        r_open, r_cc = close / open_ - 1, close / prev - 1
    num, den, sold = np.zeros(T), np.zeros(T), np.zeros(T)
    for t, c in zip(*np.nonzero(events), strict=True):
        if t + h >= T:
            continue
        path = [r_open[t + 1, c]] + [r_cc[t + j, c] for j in range(2, h + 1)]
        if not np.all(np.isfinite(path)):
            continue
        for j, r in enumerate(path, start=1):
            num[t + j] += events[t, c] * r - cost_side * ((j == 1) + (j == h))
            den[t + j] += 1
        sold[t + h] += 1
    ret = np.where(den > 0, num / np.maximum(den, 1), 0.0)[first:]
    share_sold = np.where(den > 0, sold / np.maximum(den, 1), 0.0)[first:]
    eq = np.cumprod(1 + ret)
    sd = ret.std(ddof=1) if len(ret) > 1 else 0.0
    years = pd.Series(share_sold, index=dates[first:]).groupby(dates[first:].year).sum()
    return {"days": int(len(ret)), "days_invested": int((den[first:] > 0).sum()),
            "total_return": _f(eq[-1] - 1) if len(eq) else None,
            "sharpe": _f(math.sqrt(365) * ret.mean() / sd, 2) if sd > 0 else None,
            "max_drawdown": _f((eq / np.maximum.accumulate(np.r_[1.0, eq])[1:] - 1).min()) if len(eq) else None,
            "approx_tds_pct_of_capital_by_year": {int(y): _f(100 * TDS * v, 2) for y, v in years.items()}}


def _f(x, nd: int = 6):
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return round(x, nd) if math.isfinite(x) else None


# ------------------------------------------------------------------------------------------------------------ data

def load_panel(end: str, coins=COINS) -> dict[str, pd.DataFrame]:
    """OHLC per coin, cut at `end` as soon as it is read: nothing after the period end reaches any calculation.
    A reused ticker is split into separate series (scripts/crypto_momentum_study.split_reused_tickers)."""
    out = {}
    for coin in coins:
        df = pd.read_csv(DATA / f"{coin}.csv", parse_dates=["date"]).set_index("date").sort_index()
        df = df.loc[: pd.Timestamp(end), ["open", "high", "low", "close"]].astype(float)
        for name, part in split_reused_tickers(coin, df):
            out[name] = part
    return out


def to_arrays(panel: dict[str, pd.DataFrame]):
    idx = pd.DatetimeIndex(sorted(set().union(*[df.index for df in panel.values()])))
    names = list(panel)
    arr = {f: np.column_stack([panel[n][f].reindex(idx).to_numpy() for n in names]) for f in ("open", "high", "low", "close")}
    return idx, names, arr


def period_bounds(period: str) -> tuple[str | None, str]:
    if period == "design":
        return None, prereg.CRYPTO_DESIGN_END
    return prereg.CRYPTO_TEST_START, prereg.CRYPTO_TEST_END


def check_spec(spec: dict) -> None:
    """The script's constants must match the pre-registration."""
    p = spec["parameters"]
    want = {"window": WINDOW, "lookback_days": LOOKBACK, "horizons": list(HORIZONS), "n_random": N_RANDOM,
            "random_seed": SEED, "fee": FEE, "slippage": SLIP, "tax": TAX, "cost_multipliers": list(COST_MULTS)}
    bad = {k: (p.get(k), v) for k, v in want.items() if p.get(k) != v}
    if bad:
        raise SystemExit(f"script constants differ from research/prereg/{TEST_ID}.json: {bad}")


def offsets(n_coins: int) -> np.ndarray:
    """The 1,000 random offsets, one per coin per draw, fixed seed: shape (N_RANDOM, n_coins)."""
    return np.random.default_rng(SEED).random((N_RANDOM, n_coins))


# ------------------------------------------------------------------------------------------------------- the study

def clustering(idx, names, arr, g, in_period, u_rand) -> dict:
    T, C = arr["close"].shape
    valid = in_period[:, None] & np.isfinite(arr["high"]) & np.isfinite(arr["low"]) & np.isfinite(g)
    hits = {"highs": [np.zeros((1, T, C)), np.zeros((N_RANDOM, T, C))], "lows": [np.zeros((1, T, C)), np.zeros((N_RANDOM, T, C))]}
    levels = {"highs": np.full((T, C), np.nan), "lows": np.full((T, C), np.nan)}
    for c in range(C):
        hh0, hl0, above0, below0 = cluster_hits(arr["high"][:, c], arr["low"][:, c], g[:, c], [0.0])
        hh, hl, _, _ = cluster_hits(arr["high"][:, c], arr["low"][:, c], g[:, c], u_rand[:, c])
        hits["highs"][0][0, :, c], hits["highs"][1][:, :, c] = hh0[0], hh
        hits["lows"][0][0, :, c], hits["lows"][1][:, :, c] = hl0[0], hl
        levels["highs"][:, c], levels["lows"][:, c] = above0[0], below0[0]
    out = {}
    side_rand, side_round = {}, {}
    for side, (h0, hr) in hits.items():
        v0 = np.where(valid, h0, np.nan)
        vr = np.where(valid, hr, np.nan)
        side_round[side], side_rand[side] = v0, vr
        m0, _ = day_mean(v0)
        mr, _ = day_mean(vr)
        excess = np.where(valid, h0[0] - hr.mean(0), np.nan)
        _, ex_daily = day_mean(excess)
        hit = (h0[0] > 0) & valid
        eps = sum(_level_episodes(idx[hit[:, c]], levels[side][hit[:, c], c]) for c in range(C))
        out[side] = {**vs_random(float(m0[0]), mr), "hit_coin_days": int(hit.sum()), "coin_days": int(valid.sum()),
                     "episodes": eps, "excess_nw": nw_summary(ex_daily, 1),
                     "round_rate_by_coin": {n: _f(np.nanmean(v0[0, :, c])) for c, n in enumerate(names)},
                     "hit_days_by_coin": {n: int(hit[:, c].sum()) for c, n in enumerate(names)}}
    both0 = (side_round["highs"] + side_round["lows"]) / 2
    bothr = (side_rand["highs"] + side_rand["lows"]) / 2
    out["combined (reported, not the pass line)"] = vs_random(float(day_mean(both0)[0][0]), day_mean(bothr)[0])
    out["pass_line_met"] = bool(out["highs"]["above_p95"] and out["lows"]["above_p95"])
    return out


def _level_episodes(days: pd.DatetimeIndex, lvls: np.ndarray) -> int:
    if not len(days):
        return 0
    s = pd.Series(np.asarray(days, dtype="datetime64[D]"), index=np.round(lvls, 8))
    return int(sum(episodes(v.to_numpy()) for _, v in s.groupby(level=0)))


def crossing(idx, names, arr, g, in_period, u_rand) -> dict:
    T, C = arr["close"].shape
    ev0 = np.zeros((T, C), dtype=np.int8)
    evr = np.zeros((N_RANDOM, T, C), dtype=np.int8)
    for c in range(C):
        ev0[:, c] = fresh_crossings(arr["close"][:, c], g[:, c], [0.0])[0]
        evr[:, :, c] = fresh_crossings(arr["close"][:, c], g[:, c], u_rand[:, c])
    ev0 = np.where(in_period[:, None], ev0, 0).astype(np.int8)
    evr = np.where(in_period[None, :, None], evr, 0).astype(np.int8)
    ev_days = idx[(ev0 != 0).any(1)]
    out = {"events_coin_days": int((ev0 != 0).sum()), "event_days": int(len(ev_days)), "episodes": crossing_episodes(ev_days),
           "up": int((ev0 > 0).sum()), "down": int((ev0 < 0).sum()),
           "events_by_coin": {n: int((ev0[:, c] != 0).sum()) for c, n in enumerate(names)},
           "random_events_median": int(np.median((evr != 0).sum((1, 2)))), "horizons": {}}
    first = int(np.argmax(in_period)) if in_period.any() else T
    rt = 2 * (FEE + SLIP)
    passed = True
    for h in HORIZONS:
        R = np.column_stack([forward_moves(arr["open"][:, c], arr["close"][:, c], h) for c in range(C)])
        d0 = np.where(ev0 != 0, ev0 * R, np.nan)[None]
        dr = np.where(evr != 0, evr * R[None], np.nan)
        got = d0[np.isfinite(d0)]
        res = {"events_with_outcome": int(len(got)), "gross_mean": _f(day_mean(d0)[0][0]),
               "share_positive_gross": _f(np.mean(got > 0)) if len(got) else None, "lines": {}}
        for mult in COST_MULTS:
            cost = mult * rt
            for taxed in (False, True):
                f0, fr = d0 - cost, dr - cost
                if taxed:
                    f0, fr = after_tax(f0), after_tax(fr)
                m0, daily0 = day_mean(f0)
                line = vs_random(float(m0[0]), day_mean(fr)[0])
                line["nw"] = nw_summary(daily0[0], h)
                res["lines"][f"costs {100 * cost:.2f}% {'after tax' if taxed else 'pre-tax'}"] = line
                passed &= line["above_p95"]
            res[f"portfolio costs {100 * mult * rt:.2f}%"] = calendar_portfolio(
                arr["open"], arr["close"], ev0, h, mult * (FEE + SLIP), idx, first)
        out["horizons"][f"{h}d"] = res
    out["pass_line_met"] = bool(passed)
    return out


def counts_only() -> dict:
    """Design-period crossing counts (no outcomes): raw crossing coin-days, as counted in the plan, and fresh events."""
    _, end = period_bounds("design")
    idx, names, arr = to_arrays(load_panel(end))
    prev = np.vstack([np.full((1, len(names)), np.nan), arr["close"][:-1]])
    out = {}
    for kind in KINDS:
        g = spacing(prev, kind)
        raw = np.column_stack([raw_crossings(arr["close"][:, c], g[:, c]) for c in range(len(names))])
        fresh = np.column_stack([fresh_crossings(arr["close"][:, c], g[:, c], [0.0])[0] for c in range(len(names))])
        out[kind] = {"raw_crossing_coin_days": int(raw.sum()), "fresh_event_coin_days": int((fresh != 0).sum()),
                     "fresh_event_days": int((fresh != 0).any(1).sum()), "episodes": crossing_episodes(idx[(fresh != 0).any(1)]),
                     "by_coin_raw": {n: int(raw[:, c].sum()) for c, n in enumerate(names)},
                     "by_coin_fresh": {n: int((fresh[:, c] != 0).sum()) for c, n in enumerate(names)}}
    return out


def run(period: str, spec: dict) -> dict:
    check_spec(spec)
    start, end = period_bounds(period)
    panel = load_panel(end)
    idx, names, arr = to_arrays(panel)
    if len(idx) and idx[-1] > pd.Timestamp(end):
        raise RuntimeError("data past the period end reached the study")
    in_period = np.ones(len(idx), dtype=bool) if start is None else np.asarray(idx >= pd.Timestamp(start))
    prev = np.vstack([np.full((1, len(names)), np.nan), arr["close"][:-1]])
    u_rand = offsets(len(names))
    res = {"id": TEST_ID, "period": period, "run_at": datetime.now(UTC).isoformat(timespec="seconds"),
           "coins": names, "data_from": str(idx[0].date()), "data_to": str(idx[-1].date()),
           "period_start": start or str(idx[0].date()), "period_end": end, "n_random": N_RANDOM, "seed": SEED,
           "costs_round_trip": 2 * (FEE + SLIP), "tax": TAX, "variants": {}}
    for kind in KINDS:
        g = spacing(prev, kind)
        res["variants"][f"{kind}-clustering"] = clustering(idx, names, arr, g, in_period, u_rand)
        res["variants"][f"{kind}-crossing"] = crossing(idx, names, arr, g, in_period, u_rand)
    return res


def log(res: dict) -> None:
    for variant, v in res["variants"].items():
        if variant.endswith("clustering"):
            lines = {s: v[s] for s in ("highs", "lows")}
            n = v["highs"]["hit_coin_days"] + v["lows"]["hit_coin_days"]
            binding = min(lines, key=lambda s: lines[s].get("share_random_below") or 0)
            t = v[binding]["excess_nw"].get("t")
        else:
            lines = {f"{h} {name}": line for h, hv in v["horizons"].items() for name, line in hv["lines"].items()}
            n = v["events_coin_days"]
            binding = min(lines, key=lambda s: lines[s].get("share_random_below") or 0)
            t = lines[binding]["nw"].get("t")
        value = lines[binding].get("share_random_below")
        prereg.log_trial(TEST_ID, variant, res["period"], "min_share_random_offsets_beaten", value, t=t, n=n,
                         asset="crypto", kind="design" if res["period"] == "design" else "test",
                         note=f"binding line: {binding}; pass line met: {v['pass_line_met']}")


def summary(res: dict) -> str:
    out = [f"H19c round numbers, {res['period']} period {res['period_start']} to {res['period_end']} "
           f"({', '.join(res['coins'])}; {res['n_random']} random offsets)"]
    for variant, v in res["variants"].items():
        out.append(f"\n{variant}: pass line met in this period = {'yes' if v['pass_line_met'] else 'no'}")
        if variant.endswith("clustering"):
            for s in ("highs", "lows"):
                x = v[s]
                out.append(f"  {s}: round {_pct(x['round'])} of coin-days vs random median {_pct(x.get('random_median'))}, "
                           f"95th pct {_pct(x.get('random_p95'))}; beats {_pct(x.get('share_random_below'), 1)} of offsets "
                           f"({x['hit_coin_days']} hit coin-days of {x['coin_days']}, {x['episodes']} level episodes, "
                           f"NW t of excess {x['excess_nw'].get('t')})")
        else:
            out.append(f"  events: {v['events_coin_days']} coin-days ({v['up']} up, {v['down']} down) on {v['event_days']} "
                       f"days in {v['episodes']} episodes; by coin {v['events_by_coin']}")
            for h, hv in v["horizons"].items():
                base = hv["lines"]["costs 0.30% pre-tax"]
                tax = hv["lines"]["costs 0.30% after tax"]
                pf = hv["portfolio costs 0.30%"]
                out.append(f"  {h}: n={hv['events_with_outcome']}, mean after 0.30% costs {_pct(base['round'], 2)} "
                           f"(after tax {_pct(tax['round'], 2)}) vs random median {_pct(base.get('random_median'), 2)}, "
                           f"95th pct {_pct(base.get('random_p95'), 2)}; beats {_pct(base.get('share_random_below'), 1)} "
                           f"of offsets; NW t {base['nw'].get('t')}; portfolio Sharpe {pf['sharpe']}, "
                           f"max DD {_pct(pf['max_drawdown'], 1)}")
    return "\n".join(out)


def _pct(x, nd: int = 2) -> str:
    return "n/a" if x is None else f"{100 * x:.{nd}f}%"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--crypto", action="store_true", help="H19c: BTC and ETH")
    ap.add_argument("--period", choices=("design", "test"), default="design")
    ap.add_argument("--counts-only", action="store_true", help="design-period crossing counts, no outcomes")
    args = ap.parse_args(argv)
    if not args.crypto:
        print("H19 (NSE stocks and the Nifty) waits for the point-in-time price table (P0-A). Use --crypto for H19c.")
        return 2
    if args.period == "test":
        spec = prereg.require_committed(TEST_ID)          # first: refuse unless the pre-registration is committed
        if args.counts_only:
            raise SystemExit("--counts-only covers the design period only")
    elif args.counts_only:
        print(json.dumps(counts_only(), indent=1))
        return 0
    else:
        spec = prereg.load(TEST_ID)
    res = run(args.period, spec)
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / f"{TEST_ID}_{args.period}.json").write_text(json.dumps(res, indent=1))
    log(res)
    print(summary(res))
    print(f"\nwritten: {RESULTS / f'{TEST_ID}_{args.period}.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
