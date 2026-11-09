"""H10 and H10c: the site's candles and support/resistance levels, exactly as coded (docs/test-plan.md).

--crypto runs H10c: does the price turn at the levels indtrader/signals/chart.py draws more often than at random
levels? The rules are fixed in research/prereg/H10c.json (copied from the plan; read it for every clarification):
- levels: chart.support_resistance as coded (250-bar lookback, k = 5 swings, 0.6 ATR clusters, at least 2 touches, up
  to 4 a side), redrawn every day from bars up to day t-1's close and tested on day t. BTC and ETH use the function
  itself; the daily top-20 universe uses a copy of it with the 2-decimal price rounding removed (coins under $1).
- hit: previous close above a support and the day's low within 0.2 ATR above it (resistance mirrored), first hits
  only (the price must have been at least 1 ATR away since it last touched the level).
- bounce: no close more than 0.2 ATR beyond the level on the hit day and the next 3 days. Bounce rate = bounces / hits.
- random levels: per coin-day, 1,000 sets with as many levels as ours, uniform in the 250-day high-low range, scored by
  the same function. Pass: our rate above the random rates' 95th percentile, in design and again in test.
- money check (report only, BTC and ETH): buy the next open after a support hit, sell 3 days later at the open, 0.30%
  costs (and doubled), the 31.2% after-tax line, against the same trade at random-level hits.

--period design runs on data cut at 2022-12-31. --period test refuses unless research/prereg/H10c.json is committed and
unchanged, and then runs 2023-01-01 to 2026-10-31 once. Every run appends its trials to research/trials.csv.
Without --crypto it says the stock part (H10) is not built yet.

Usage: python scripts/study_candles_levels.py --crypto --period design
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import zlib
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from indtrader.crypto import MIN_HISTORY, TOP_N
from indtrader.crypto_learn import nw_tstat
from indtrader.research import prereg
from indtrader.signals.chart import support_resistance
from indtrader.validation import deflated_sharpe

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DATA = ROOT / "data" / "crypto"
RESULTS = ROOT / "research" / "results"
TEST_ID = "H10c"


def _load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


cb = _load_script("crypto_backtest")              # simulate(): costs and the after-tax book
cms = _load_script("crypto_momentum_study")       # split_reused_tickers(): LUNA's reused ticker

# chart.support_resistance as coded, and the H10c rules (research/prereg/H10c.json)
LOOKBACK, K, TOL_ATR, MAX_LEVELS, ATR_N = 250, 5, 0.6, 4, 14
HIT_ATR, BOUNCE_ATR, AWAY_ATR = 0.2, 0.2, 1.0
BOUNCE_DAYS, HOLD_DAYS = 3, 3          # closes t..t+3; buy open t+1, sell open t+4
N_RANDOM, SEED, BOOT_SEED, N_BOOT = 1000, 1010, 1011, 2000
GAP_DAYS, EPISODE_GAP = 7, 3
TAX = 0.312
COST_SIDE = cb.FEE + cb.SLIP            # 0.15% a side, about 0.30% a round trip
NW_LAGS = HOLD_DAYS
PERIOD_CODE = {"design": 1, "test": 2}
CHUNK = 4_000_000                       # random levels scored per block (memory bound)


# ---------------------------------------------------------------- data
@dataclass
class Seg:
    """One unbroken daily series of a coin (no gap over GAP_DAYS). `coin` is the panel column it belongs to."""
    coin: str
    dates: np.ndarray
    o: np.ndarray
    h: np.ndarray
    l: np.ndarray  # noqa: E741  (low)
    c: np.ndarray
    member: np.ndarray | None = None    # in the top 20 at that row's close; None = always in (BTC and ETH main)
    cache: dict = field(default_factory=dict)

    def __len__(self) -> int:
        return len(self.c)

    def frame(self) -> pd.DataFrame:
        return pd.DataFrame({"Open": self.o, "High": self.h, "Low": self.l, "Close": self.c},
                            index=pd.DatetimeIndex(self.dates))


def read_coin(name: str, end: str) -> pd.DataFrame:
    df = pd.read_csv(DATA / f"{name}.csv", parse_dates=["date"]).set_index("date").sort_index()
    return df.loc[: pd.Timestamp(end)].astype(float)


def split_gaps(df: pd.DataFrame, gap_days: int = GAP_DAYS) -> list[pd.DataFrame]:
    """Cut a series at every gap of more than `gap_days` days, so no window or outcome spans a long halt."""
    gap = df.index.to_series().diff().dt.days.to_numpy()
    cut = np.flatnonzero(gap > gap_days)
    bounds = [0, *cut.tolist(), len(df)]
    return [df.iloc[a:b] for a, b in zip(bounds[:-1], bounds[1:], strict=True) if b > a]


def to_segs(coin: str, df: pd.DataFrame) -> list[Seg]:
    return [Seg(coin, p.index.to_numpy(), p["open"].to_numpy(), p["high"].to_numpy(), p["low"].to_numpy(),
                p["close"].to_numpy()) for p in split_gaps(df)]


def load_universe(end: str) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    """Every coin file cut at `end`, LUNA split as crypto_momentum_study.load_all does (parts under 120 rows
    dropped), and the daily top-20 membership of indtrader.crypto.universe(), vectorised."""
    parts: dict[str, pd.DataFrame] = {}
    for f in sorted(DATA.glob("*.csv")):
        if f.stem in ("fear_greed", "funding_BTC", "funding_ETH"):
            continue
        df = read_coin(f.stem, end)
        for name, part in cms.split_reused_tickers(f.stem, df):
            if len(part) >= MIN_HISTORY:
                parts[name] = part
    closes = pd.DataFrame({k: v["close"] for k, v in parts.items()})
    vol = pd.DataFrame({k: v["volume"] for k, v in parts.items()})
    return parts, top_n_membership(closes, vol)


def top_n_membership(closes: pd.DataFrame, vol: pd.DataFrame, top_n: int = TOP_N) -> pd.DataFrame:
    """indtrader.crypto.universe() for every day at once: the top_n by 30-day mean traded value among coins with
    MIN_HISTORY days of closes that have a close that day."""
    value30 = vol.rolling(30, min_periods=20).mean()
    eligible = (closes.notna().cumsum() >= MIN_HISTORY) & closes.notna()
    tv = value30.where(eligible)
    return tv.rank(axis=1, ascending=False, method="first") <= top_n


# ---------------------------------------------------------------- levels
def windowed_atr(seg: Seg, n: int = LOOKBACK, period: int = ATR_N) -> np.ndarray:
    """ATR(14) as chart.support_resistance gets it: technical.atr on the n-bar window ending at each bar (Wilder EWM
    restarted at the window's first bar, whose true range is high - low). NaN until a full window exists."""
    if "watr" in seg.cache:
        return seg.cache["watr"]
    h, lo, c = seg.h, seg.l, seg.c
    prev = np.r_[np.nan, c[:-1]]
    tr = np.nanmax(np.vstack([h - lo, np.abs(h - prev), np.abs(lo - prev)]), axis=0)
    full = pd.Series(tr).ewm(alpha=1 / period, adjust=False).mean().to_numpy()
    out = np.full(len(c), np.nan)
    if len(c) >= n:
        e = np.arange(n - 1, len(c))
        s = e - n + 1
        out[e] = full[e] + (1 - 1 / period) ** (n - 1) * ((h[s] - lo[s]) - full[s])
    seg.cache["watr"] = out
    return out


def swing_flags(seg: Seg, k: int = K) -> tuple[np.ndarray, np.ndarray]:
    """chart.swing_points on the whole series: bar i is a swing high if its high is the highest of bars i-k..i+k."""
    if "swings" in seg.cache:
        return seg.cache["swings"]
    n = len(seg.c)
    sh, sl = np.zeros(n, bool), np.zeros(n, bool)
    if n >= 2 * k + 1:
        wh = np.lib.stride_tricks.sliding_window_view(seg.h, 2 * k + 1).max(axis=1)
        wl = np.lib.stride_tricks.sliding_window_view(seg.l, 2 * k + 1).min(axis=1)
        sh[k: n - k] = seg.h[k: n - k] == wh
        sl[k: n - k] = seg.l[k: n - k] == wl
    seg.cache["swings"] = (np.flatnonzero(sh), np.flatnonzero(sl))
    return seg.cache["swings"]


def levels_at(seg: Seg, e: int, round_prices: bool) -> tuple[list[float], list[float]]:
    """chart.support_resistance on the LOOKBACK bars ending at bar e, as coded, optionally without rounding the
    level price. Returns (support prices, resistance prices). Swings inside the window are those with k bars on each
    side inside it, the same set chart.swing_points finds on the window slice."""
    n = LOOKBACK
    s = e - n + 1
    if s < 0:
        return [], []
    a = float(windowed_atr(seg)[e])
    tol = max(TOL_ATR * a, 1e-9)
    hi_idx, lo_idx = swing_flags(seg)
    lo_b, hi_b = s + K, e - K
    hs = hi_idx[np.searchsorted(hi_idx, lo_b): np.searchsorted(hi_idx, hi_b, side="right")]
    ls = lo_idx[np.searchsorted(lo_idx, lo_b): np.searchsorted(lo_idx, hi_b, side="right")]
    highs = [(int(i - s), float(seg.h[i])) for i in hs]
    lows = [(int(i - s), float(seg.l[i])) for i in ls]
    pts = sorted(highs + lows, key=lambda p: p[1])
    clusters: list[list[tuple[int, float]]] = []
    for p in pts:
        if clusters and p[1] - np.mean([q[1] for q in clusters[-1]]) <= tol:
            clusters[-1].append(p)
        else:
            clusters.append([p])
    levels = []
    for cl in clusters:
        if len(cl) < 2:
            continue
        price = float(np.mean([q[1] for q in cl]))
        weight = sum(0.5 + 0.5 * i / n for i, _ in cl)
        levels.append((round(price, 2) if round_prices else price, round(weight, 2)))
    last = float(seg.c[e])
    sup = sorted([lv for lv in levels if lv[0] < last], key=lambda lv: -lv[1])[:MAX_LEVELS]
    res = sorted([lv for lv in levels if lv[0] >= last], key=lambda lv: -lv[1])[:MAX_LEVELS]
    return [lv[0] for lv in sup], [lv[0] for lv in res]


def levels_exact(seg: Seg, e: int) -> tuple[list[float], list[float]]:
    """chart.support_resistance itself on the window ending at bar e (BTC and ETH, levels exactly as coded)."""
    if "frame" not in seg.cache:
        seg.cache["frame"] = seg.frame()
    lv = support_resistance(seg.cache["frame"].iloc[e - LOOKBACK + 1: e + 1])
    return [x["price"] for x in lv["support"]], [x["price"] for x in lv["resistance"]]


# ---------------------------------------------------------------- scoring (shared by our levels and random ones)
def fwd_extremes(seg: Seg, days: int = BOUNCE_DAYS) -> tuple[np.ndarray, np.ndarray]:
    """Lowest and highest close over bars r..r+days (NaN when the window runs past the series end)."""
    if "fwd" not in seg.cache:
        n = len(seg.c)
        fmin, fmax = np.full(n, np.nan), np.full(n, np.nan)
        if n > days:
            w = np.lib.stride_tricks.sliding_window_view(seg.c, days + 1)
            fmin[: n - days], fmax[: n - days] = w.min(axis=1), w.max(axis=1)
        seg.cache["fwd"] = (fmin, fmax)
    return seg.cache["fwd"]


def first_hit(lo: np.ndarray, hi: np.ndarray, r: np.ndarray, p: np.ndarray, a: np.ndarray,
              max_back: int = LOOKBACK) -> np.ndarray:
    """True where a hit at level p on bar r is a first hit: walking back from bar r-1, a bar at least 1 ATR away from
    p (wholly above p + ATR or wholly below p - ATR) comes before any bar touching [p - 0.2 ATR, p + 0.2 ATR].
    Unresolved within max_back bars (or at the series start) counts as a first hit."""
    out = np.ones(len(r), bool)
    band_lo, band_hi = p - HIT_ATR * a, p + HIT_ATR * a
    away_lo, away_hi = p - AWAY_ATR * a, p + AWAY_ATR * a
    active = np.arange(len(r))
    for j in range(1, max_back + 1):
        if not active.size:
            break
        u = r[active] - j
        active, u = active[u >= 0], u[u >= 0]
        touch = (lo[u] <= band_hi[active]) & (hi[u] >= band_lo[active])
        away = (lo[u] >= away_hi[active]) | (hi[u] <= away_lo[active])
        out[active[touch]] = False
        active = active[~(touch | away)]
    return out


def score_levels(seg: Seg, r: np.ndarray, p: np.ndarray, side: np.ndarray, a: np.ndarray) -> dict[str, np.ndarray]:
    """Score levels p (side +1 support, -1 resistance) on hit bars r with the ATR ruler a (known at r-1).
    first: a first hit; bounce: no close beyond 0.2 ATR on r..r+3; valid: closes r..r+3 exist; money_ok: open r+4 exists."""
    lo, hi, c = seg.l, seg.h, seg.c
    prev = c[r - 1]
    sup = side > 0
    hit = np.where(sup, (prev > p) & (lo[r] <= p + HIT_ATR * a), (prev < p) & (hi[r] >= p - HIT_ATR * a))
    first = np.zeros(len(r), bool)
    idx = np.flatnonzero(hit)
    if idx.size:
        first[idx] = first_hit(lo, hi, r[idx], p[idx], a[idx])
    fmin, fmax = fwd_extremes(seg)
    with np.errstate(invalid="ignore"):
        bounce = np.where(sup, fmin[r] >= p - BOUNCE_ATR * a, fmax[r] <= p + BOUNCE_ATR * a)
    n = len(c)
    return {"first": first, "bounce": bounce & first, "valid": r + BOUNCE_DAYS <= n - 1,
            "money_ok": r + 1 + HOLD_DAYS <= n - 1}


# ---------------------------------------------------------------- one universe, one period
def scored_rows(seg: Seg, start: pd.Timestamp) -> np.ndarray:
    """Hit bars r: a full LOOKBACK window ends at r-1, r falls on or after `start`, and (top 20) the coin was in the
    universe at r-1's close."""
    r = np.arange(LOOKBACK, len(seg))
    r = r[seg.dates[r] >= np.datetime64(start)]
    if seg.member is not None:
        r = r[seg.member[r - 1]]
    return r


@dataclass
class Tally:
    months: np.ndarray                       # month codes (year*12 + month-1) of the period, in order
    ours: list = field(default_factory=list)
    rh: np.ndarray | None = None             # random first hits [month, set]
    rb: np.ndarray | None = None             # random bounces [month, set]
    rside_h: np.ndarray | None = None        # [side(0 support, 1 resistance), set]
    rside_b: np.ndarray | None = None
    money_rand: dict = field(default_factory=dict)   # seg index -> (rows, bool[rows, set]) random support first hits
    n_levels: int = 0
    coin_days: int = 0
    dropped: int = 0

    def __post_init__(self):
        m = len(self.months)
        self.rh, self.rb = np.zeros((m, N_RANDOM)), np.zeros((m, N_RANDOM))
        self.rside_h, self.rside_b = np.zeros((2, N_RANDOM)), np.zeros((2, N_RANDOM))


def month_code(dates: np.ndarray) -> np.ndarray:
    d = pd.DatetimeIndex(dates)
    return (d.year * 12 + d.month - 1).to_numpy()


def run_universe(segs: list[Seg], name: str, period: str, start: pd.Timestamp, exact: bool, money: bool) -> dict:
    rows_by_seg = [scored_rows(s, start) for s in segs]
    all_dates = np.concatenate([s.dates[r] for s, r in zip(segs, rows_by_seg, strict=True)] or [np.array([], "M8[ns]")])
    if not all_dates.size:
        raise RuntimeError(f"{name}: no scoreable coin-days")
    codes = month_code(all_dates)
    tally = Tally(np.arange(codes.min(), codes.max() + 1))
    m0 = int(codes.min())
    rngs: dict[str, np.random.Generator] = {}
    for si, (seg, rows) in enumerate(zip(segs, rows_by_seg, strict=True)):
        if not rows.size:
            continue
        tally.coin_days += len(rows)
        a_hit = windowed_atr(seg)[rows - 1]
        # our levels, drawn from the window ending at r-1
        lv_r, lv_p, lv_s, n_lv = [], [], [], np.zeros(len(rows), int)
        for k, r in enumerate(rows):
            sup, res = levels_exact(seg, r - 1) if exact else levels_at(seg, r - 1, round_prices=False)
            n_lv[k] = len(sup) + len(res)
            lv_r += [r] * n_lv[k]
            lv_p += sup + res
            lv_s += [1] * len(sup) + [-1] * len(res)
        tally.n_levels += int(n_lv.sum())
        if lv_r:
            r_arr, p_arr, s_arr = np.asarray(lv_r), np.asarray(lv_p, float), np.asarray(lv_s)
            sc = score_levels(seg, r_arr, p_arr, s_arr, windowed_atr(seg)[r_arr - 1])
            tally.dropped += int((sc["first"] & ~sc["valid"]).sum())
            tally.ours.append(pd.DataFrame({"coin": seg.coin, "seg": si, "row": r_arr, "date": seg.dates[r_arr],
                                            "price": p_arr, "side": s_arr, **sc})[lambda d: d["first"]])
        # random levels: as many as ours per coin-day, uniform in the 250-bar high-low range ending at r-1
        rng = rngs.setdefault(seg.coin, np.random.default_rng(np.random.SeedSequence(
            [SEED, PERIOD_CODE[period], zlib.crc32(name.encode()), zlib.crc32(seg.coin.encode())])))
        lo250 = pd.Series(seg.l).rolling(LOOKBACK).min().to_numpy()[rows - 1]
        hi250 = pd.Series(seg.h).rolling(LOOKBACK).max().to_numpy()[rows - 1]
        cnt = n_lv * N_RANDOM
        mrand = np.zeros((len(rows), N_RANDOM), bool) if money else None
        bounds = np.searchsorted(np.cumsum(cnt), np.arange(CHUNK, int(cnt.sum()) + CHUNK, CHUNK), side="right")
        b0 = 0
        for b1 in np.unique(np.r_[bounds, len(rows)]):
            if b1 <= b0:
                continue
            ks = np.arange(b0, b1)
            c_k = cnt[ks]
            tot = int(c_k.sum())
            if tot:
                kk = np.repeat(ks, c_k)
                set_idx = (np.arange(tot) - np.repeat(np.cumsum(c_k) - c_k, c_k)) % N_RANDOM
                r_k = rows[kk]
                p_k = lo250[kk] + rng.random(tot) * (hi250[kk] - lo250[kk])
                s_k = np.where(p_k < seg.c[r_k - 1], 1, -1)
                sc = score_levels(seg, r_k, p_k, s_k, a_hit[kk])
                ok = sc["first"] & sc["valid"]
                mi = month_code(seg.dates[r_k[ok]]) - m0
                flat = mi * N_RANDOM + set_idx[ok]
                size = len(tally.months) * N_RANDOM
                tally.rh += np.bincount(flat, minlength=size).reshape(-1, N_RANDOM)
                tally.rb += np.bincount(flat, weights=sc["bounce"][ok], minlength=size).reshape(-1, N_RANDOM)
                sd = (s_k[ok] < 0).astype(int) * N_RANDOM + set_idx[ok]
                tally.rside_h += np.bincount(sd, minlength=2 * N_RANDOM).reshape(2, N_RANDOM)
                tally.rside_b += np.bincount(sd, weights=sc["bounce"][ok], minlength=2 * N_RANDOM).reshape(2, N_RANDOM)
                if money:
                    mm = sc["first"] & sc["money_ok"] & (s_k > 0)
                    mrand[kk[mm], set_idx[mm]] = True
            b0 = b1
        if money:
            tally.money_rand[si] = (rows, mrand)
    out = summarise(tally, name)
    out["_money_rand"] = tally.money_rand
    return out


def episodes(days: pd.Series, gap: int = EPISODE_GAP) -> int:
    """Hit days of one coin no more than `gap` days apart form one episode."""
    d = pd.Series(sorted(set(pd.DatetimeIndex(days)))).diff().dt.days
    return int((d.isna() | (d > gap)).sum())


def bootstrap_gap(oh: np.ndarray, ob: np.ndarray, rh: np.ndarray, rb: np.ndarray, n_boot: int = N_BOOT,
                  seed: int = BOOT_SEED) -> tuple[float, float]:
    """95% interval of (our rate - median random rate), resampling calendar months with replacement."""
    rng = np.random.default_rng(seed)
    m = len(oh)
    w = np.zeros((n_boot, m))
    np.add.at(w, (np.repeat(np.arange(n_boot), m), rng.integers(0, m, n_boot * m)), 1.0)
    with np.errstate(invalid="ignore", divide="ignore"):
        ours = (w @ ob) / (w @ oh)
        rand = np.median((w @ rb) / (w @ rh), axis=1)
    gap = (ours - rand)[np.isfinite(ours - rand)]
    return float(np.percentile(gap, 2.5)), float(np.percentile(gap, 97.5))


def summarise(t: Tally, name: str) -> dict:
    ours = pd.concat(t.ours, ignore_index=True) if t.ours else pd.DataFrame(
        columns=["coin", "seg", "row", "date", "price", "side", "first", "bounce", "valid", "money_ok"])
    ev = ours[ours["valid"]]
    m0 = int(t.months[0])
    mi = month_code(ev["date"].to_numpy()) - m0 if len(ev) else np.array([], int)
    oh = np.bincount(mi, minlength=len(t.months)).astype(float)
    ob = np.bincount(mi, weights=ev["bounce"].to_numpy(float), minlength=len(t.months))
    rand_rates = t.rb.sum(0) / t.rh.sum(0)
    ours_rate = float(ob.sum() / oh.sum()) if oh.sum() else float("nan")
    p95, med = float(np.percentile(rand_rates, 95)), float(np.median(rand_rates))
    lo, hi = bootstrap_gap(oh, ob, t.rh, t.rb)
    side_rates = {}
    for k, (lab, sgn) in enumerate((("support", 1), ("resistance", -1))):
        e = ev[ev["side"] == sgn]
        with np.errstate(invalid="ignore", divide="ignore"):
            rr = t.rside_b[k] / t.rside_h[k]
        side_rates[lab] = {"hits": len(e), "ours": round(float(e["bounce"].mean()), 4) if len(e) else None,
                           "random_median": round(float(np.nanmedian(rr)), 4) if np.isfinite(rr).any() else None,
                           "random_p95": round(float(np.nanpercentile(rr, 95)), 4) if np.isfinite(rr).any() else None}
    by_year = {str(y): {"hits": len(g), "bounce_rate": round(float(g["bounce"].mean()), 4)}
               for y, g in ev.groupby(pd.DatetimeIndex(ev["date"]).year)}
    hit_days = ev.groupby("seg")["date"]
    return {
        "universe": name,
        "coin_days_scored": t.coin_days,
        "first_scored_month": f"{m0 // 12}-{m0 % 12 + 1:02d}",
        "levels_tested": t.n_levels,
        "levels_per_coin_day": round(t.n_levels / t.coin_days, 2),
        "hits": len(ev), "bounces": int(ev["bounce"].sum()),
        "coin_days_with_hit": int(ev.drop_duplicates(["seg", "row"]).shape[0]),
        "episodes": int(sum(episodes(g) for _, g in hit_days)),
        "coins_with_hits": int(ev["coin"].nunique()),
        "hits_dropped_outcome_outside_data": t.dropped,
        "bounce_rate_ours": round(ours_rate, 4),
        "random": {"median": round(med, 4), "p5": round(float(np.percentile(rand_rates, 5)), 4), "p95": round(p95, 4),
                   "mean_hits_per_set": round(float(t.rh.sum() / N_RANDOM), 1)},
        "percentile_of_ours": round(float((rand_rates < ours_rate).mean()), 4),
        "gap_vs_random_median": round(ours_rate - med, 4),
        "gap_bootstrap_95": [round(lo, 4), round(hi, 4)],
        "above_95th_percentile": bool(ours_rate > p95),
        "by_side_descriptive": side_rates,
        "by_year_descriptive": by_year,
        "_ours": ours, "_rand_rates": rand_rates,
    }


# ---------------------------------------------------------------- money check (BTC and ETH, report only)
def trade_return(o: np.ndarray, r: np.ndarray, cost_side: float = COST_SIDE) -> np.ndarray:
    """Buy at the open of r+1, sell at the open of r+1+HOLD_DAYS, paying cost_side on each side's value."""
    return o[r + 1 + HOLD_DAYS] * (1 - cost_side) / (o[r + 1] * (1 + cost_side)) - 1


def after_tax(x: np.ndarray) -> np.ndarray:
    return np.where(x > 0, (1 - TAX) * x, x)


def day_mean(dates: np.ndarray, x: np.ndarray) -> pd.Series:
    return pd.Series(x).groupby(pd.DatetimeIndex(dates)).mean().sort_index()


def max_dd(eq: pd.Series) -> float:
    return float((eq / eq.cummax() - 1).min())


def money_check(res: dict, segs: list[Seg], start: pd.Timestamp) -> dict:
    ours = res["_ours"]
    tr = ours[(ours["side"] > 0) & ours["money_ok"]].drop_duplicates(["seg", "row"]).sort_values("date")
    out: dict = {"universe": "BTC and ETH", "trades": len(tr)}
    if not len(tr):
        return out
    lines = {}
    for label, cs in (("costs", COST_SIDE), ("costs_doubled", 2 * COST_SIDE)):
        net = np.concatenate([trade_return(segs[s].o, g["row"].to_numpy(), cs) for s, g in tr.groupby("seg")])
        dates = np.concatenate([g["date"].to_numpy() for _, g in tr.groupby("seg")])
        for tax_label, x in (("pre_tax", net), ("after_tax", after_tax(net))):
            d = day_mean(dates, x)
            lines[f"{label}_{tax_label}"] = {"mean_pct": round(100 * float(d.mean()), 3),
                                              "median_pct": round(100 * float(d.median()), 3),
                                              "nw_t": round(nw_tstat(d.to_numpy(), NW_LAGS), 2),
                                              "hit_days": len(d), "share_positive": round(float((d > 0).mean()), 3)}
    out["per_event"] = lines
    out["episodes"] = int(sum(episodes(g["date"]) for _, g in tr.groupby("seg")))
    # the same trade at random-level support first hits, per random set (coins averaged per day first)
    rows_all, dates_all, ret_all, m_all = [], [], [], []
    for si, (rows, mrand) in res["_money_rand"].items():
        ok = rows + 1 + HOLD_DAYS <= len(segs[si]) - 1
        rows_all.append(rows[ok])
        dates_all.append(segs[si].dates[rows[ok]])
        ret_all.append(trade_return(segs[si].o, rows[ok]))
        m_all.append(mrand[ok])
    dates_all, ret_all, m_all = np.concatenate(dates_all), np.concatenate(ret_all), np.concatenate(m_all)
    uniq, inv = np.unique(dates_all, return_inverse=True)
    g = np.zeros((len(uniq), len(dates_all)))
    g[inv, np.arange(len(dates_all))] = 1.0
    s_ = g @ (m_all * ret_all[:, None])
    n_ = g @ m_all.astype(float)
    with np.errstate(invalid="ignore", divide="ignore"):
        per_set = np.nanmean(np.where(n_ > 0, s_ / n_, np.nan), axis=0)
    ours_mean = lines["costs_pre_tax"]["mean_pct"] / 100
    out["random_sets"] = {"median_mean_pct": round(100 * float(np.median(per_set)), 3),
                          "p5_mean_pct": round(100 * float(np.percentile(per_set, 5)), 3),
                          "p95_mean_pct": round(100 * float(np.percentile(per_set, 95)), 3),
                          "mean_trades_per_set": round(float(m_all.sum() / N_RANDOM), 1),
                          "percentile_of_ours": round(float((per_set < ours_mean).mean()), 4)}
    # the book: half the account on a coin while one of its trades is open (scripts/crypto_backtest.py simulate)
    hits = {segs[s].coin: set(pd.DatetimeIndex(g["date"])) for s, g in ours[ours["side"] > 0].groupby("seg")}
    coins = sorted({s.coin for s in segs})
    opens = pd.DataFrame({s.coin: pd.Series(s.o, index=pd.DatetimeIndex(s.dates)) for s in segs})
    closes = pd.DataFrame({s.coin: pd.Series(s.c, index=pd.DatetimeIndex(s.dates)) for s in segs})

    def weights(day, _closes):
        return {k: 1 / len(coins) for k in coins
                if any(day - pd.Timedelta(days=j) in hits.get(k, ()) for j in range(HOLD_DAYS))}

    def hold_btc(day, _closes):
        return {"BTC": 1.0}

    book = {}
    try:
        for label, mult in (("costs", 1), ("costs_doubled", 2)):
            cb.FEE, cb.SLIP = 0.001 * mult, 0.0005 * mult
            for nm, fn, o_, c_ in (("trade_book", weights, opens, closes),
                                   ("just_hold_btc", hold_btc, opens[["BTC"]], closes[["BTC"]])):
                r = cb.simulate(o_, c_, fn, str(start.date()))
                s = cb.stats(r)
                book[f"{nm}_{label}"] = {"total_return_pct": s["total_return_pct"], "cagr_pct": s["cagr_pct"],
                                         "sharpe": s["sharpe"], "max_dd_pct": s["max_dd_pct"],
                                         "after_tax_return_pct": s["india_after_tax_return_pct"], "trades": s["trades"]}
                if nm == "trade_book" and mult == 1:
                    out["_equity"] = r["equity"]
    finally:
        cb.FEE, cb.SLIP = 0.001, 0.0005
    out["book"] = book
    eq = out["_equity"]
    held = eq.index.to_series().apply(lambda d: [k for k in coins if any(d - pd.Timedelta(days=j) in hits.get(k, ())
                                                                          for j in range(1, HOLD_DAYS + 1))])
    sales = sum(int(((held.apply(lambda h, k=k: k in h)).astype(int).diff() == -1).sum()) for k in coins)
    years = (eq.index[-1] - eq.index[0]).days / 365.25
    out["tds_note"] = {"sales": sales, "sales_per_year": round(sales / years, 1),
                       "approx_tds_pct_of_book_per_year": round(sales / years * 0.01 / len(coins) * 100, 2),
                       "note": "1% TDS on each sale's value, not modelled; each sale is about half the book"}
    return out


# ---------------------------------------------------------------- driver
def build(period: str) -> tuple[dict, pd.Timestamp, pd.Timestamp]:
    if period == "design":
        end, start = prereg.CRYPTO_DESIGN_END, pd.Timestamp("2000-01-01")
    else:
        end, start = prereg.CRYPTO_TEST_END, pd.Timestamp(prereg.CRYPTO_TEST_START)
    parts, member = load_universe(end)
    main_segs = [s for coin in ("BTC", "ETH") for s in to_segs(coin, read_coin(coin, end))]
    top_segs = []
    for coin, df in parts.items():
        for s in to_segs(coin, df):
            s.member = member[coin].reindex(pd.DatetimeIndex(s.dates)).fillna(False).to_numpy(bool)
            top_segs.append(s)
    return {"btc_eth": main_segs, "top20": top_segs}, start, pd.Timestamp(end)


def public(d: dict) -> dict:
    return {k: v for k, v in d.items() if not k.startswith("_")}


def run(period: str, out_dir: Path = RESULTS) -> dict:
    spec = prereg.require_committed(TEST_ID) if period == "test" else prereg.load(TEST_ID)
    universes, start, end = build(period)
    res = {name: run_universe(segs, name, period, start, exact=(name == "btc_eth"), money=(name == "btc_eth"))
           for name, segs in universes.items()}
    btc_segs = universes["btc_eth"]
    first_day = max(start, pd.Timestamp(min(s.dates[LOOKBACK] for s in btc_segs if len(s) > LOOKBACK)))
    return finish(period, spec, res, btc_segs, first_day, end, out_dir)


def finish(period: str, spec: dict, res: dict, btc_segs: list[Seg], first_day: pd.Timestamp, end: pd.Timestamp,
           out_dir: Path) -> dict:
    money = money_check(res["btc_eth"], btc_segs, first_day)
    kind = period
    for name in ("btc_eth", "top20"):
        r = res[name]
        prereg.log_trial(TEST_ID, name, period, "bounce_rate_gap_vs_random_median", r["gap_vs_random_median"],
                         n=r["hits"], kind=kind,
                         note=f"ours {r['bounce_rate_ours']} random median {r['random']['median']} p95 {r['random']['p95']} "
                              f"pctile {r['percentile_of_ours']} above_p95={r['above_95th_percentile']}")
    if money.get("per_event"):
        m = money["per_event"]["costs_pre_tax"]
        prereg.log_trial(TEST_ID, "money_check", period, "mean_net_ret_3d_pct", m["mean_pct"], t=m["nw_t"],
                         n=m["hit_days"], kind=kind,
                         note=f"report only; after tax {money['per_event']['costs_after_tax']['mean_pct']}%, doubled costs "
                              f"{money['per_event']['costs_doubled_pre_tax']['mean_pct']}%, random median "
                              f"{money['random_sets']['median_mean_pct']}%")
    eq = money.pop("_equity", None)
    if eq is not None:
        money["book"]["deflated_sharpe"] = deflated_sharpe(eq, prereg.trial_count("crypto"))
    out = {"test": TEST_ID, "period": period, "data_end": str(end.date()), "scored_from": str(first_day.date()),
           "registered_commit": spec.get("_registered_commit"),
           "universes": {k: public(v) for k, v in res.items()}, "money_check": money,
           "pass_line": spec["pass_fail"]["pass_fixed_in_plan"],
           "this_period": {k: res[k]["above_95th_percentile"] for k in res}}
    if period == "test":
        design = json.loads((out_dir / f"{TEST_ID}_design.json").read_text())
        both = {k: bool(design["this_period"][k] and res[k]["above_95th_percentile"]) for k in res}
        out["verdict"] = "pass" if all(both.values()) else "mixed (counts as fail)" if any(both.values()) else "fail"
        out["by_universe_both_periods"] = both
    else:
        out["verdict"] = "design only: the verdict needs the test period"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{TEST_ID}_{period}.json").write_text(json.dumps(out, indent=1, default=str))
    return out


def report(out: dict) -> str:
    lines = [f"H10c support/resistance against random levels, {out['period']} period "
             f"({out['scored_from']} to {out['data_end']})"]
    for name, r in out["universes"].items():
        lines.append(
            f"  {name:8} hits {r['hits']:>6} (coin-days {r['coin_days_with_hit']}, episodes {r['episodes']}); "
            f"bounce rate ours {r['bounce_rate_ours']:.3f}, random median {r['random']['median']:.3f}, "
            f"p95 {r['random']['p95']:.3f}; ours at percentile {100 * r['percentile_of_ours']:.1f}; "
            f"gap {r['gap_vs_random_median']:+.3f} [{r['gap_bootstrap_95'][0]:+.3f}, {r['gap_bootstrap_95'][1]:+.3f}]; "
            f"above p95: {r['above_95th_percentile']}")
    m = out["money_check"]
    if m.get("per_event"):
        e = m["per_event"]
        b = m["book"]
        lines.append(f"  money check (report only, BTC+ETH): {m['trades']} trades on {e['costs_pre_tax']['hit_days']} days, "
                     f"{m['episodes']} episodes; mean 3-day net {e['costs_pre_tax']['mean_pct']:+.2f}% "
                     f"(NW t {e['costs_pre_tax']['nw_t']:+.2f}), after tax {e['costs_after_tax']['mean_pct']:+.2f}%, "
                     f"costs doubled {e['costs_doubled_pre_tax']['mean_pct']:+.2f}%; random-level median "
                     f"{m['random_sets']['median_mean_pct']:+.2f}% (ours at percentile "
                     f"{100 * m['random_sets']['percentile_of_ours']:.1f})")
        tb, bh = b["trade_book_costs"], b["just_hold_btc_costs"]
        lines.append(f"  book: return {tb['total_return_pct']}% (after tax {tb['after_tax_return_pct']}%), Sharpe {tb['sharpe']}, "
                     f"max DD {tb['max_dd_pct']}%; just hold BTC {bh['total_return_pct']}% (after tax "
                     f"{bh['after_tax_return_pct']}%), Sharpe {bh['sharpe']}, max DD {bh['max_dd_pct']}%")
    lines.append(f"  verdict: {out['verdict']}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--crypto", action="store_true", help="H10c on data/crypto")
    ap.add_argument("--period", choices=("design", "test"), default="design")
    args = ap.parse_args(argv)
    if not args.crypto:
        print("H10 (stocks: candles and levels on the NSE point-in-time table) is not built yet; run with --crypto for H10c.")
        return 1
    if args.period == "test":
        prereg.require_committed(TEST_ID)          # refuse before touching any data
    out = run(args.period)
    print(report(out))
    print(f"wrote {RESULTS / f'{TEST_ID}_{args.period}.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
