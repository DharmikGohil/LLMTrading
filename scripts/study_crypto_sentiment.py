"""Crypto crowd extremes: Fear & Greed and funding (test plan H8; rules in research/prereg/H8a.json and H8b.json).

H8a is exploratory: the crowd-emotion brief already saw 2018-2026, so history can show whether an idea deserves a
forward test, never prove it. One question per seeded market lesson, measured the way the live scorer does (the
up-rate when the tag is on against the other days of the same period), on BTC and ETH:
  fear-rebound-7d         7-day up-rate after extreme fear (Fear & Greed below 25); the lesson expects up
  greed-pullback-7d       7-day up-rate after extreme greed (above 75); expects down
  crowded-longs-24h       24-hour up-rate after funding high (3-day average above 0.03% per 8 hours); expects down
  downtrend-continues-7d  7-day up-rate below the 50-day average; expects down
Each also gets the average return and the worst drawdown over 1, 7 and 30 days (before costs, after 0.30% and 0.60%
round-trip costs, and after the 31.2% tax line), a calendar-time portfolio's Sharpe ratio and maximum drawdown, and
the first day of each episode on its own. Two add-on rows change the BTC + ETH 50-day trend rule: hold a coin also
while its funding is negative, and go flat on a coin while its funding is high (scripts/crypto_backtest.simulate).
Timing: decide on day t's close (00:00 UTC), act at day t+1's open. Fear & Greed dated t and funding settled up to day
t's 16:00 settlement. Averages are taken across coins on each day first; Newey-West lags are at least the horizon.

H8b is the real test: two shadow paper arms (F+ and F-) on forward data only. Here: the F- line (the 90th percentile
of each coin's 7-day average Binance funding over 2020-2022 only), the OKX-against-Binance funding agreement check,
and the arms' verdict once the desk code records them.

Usage:
  python scripts/study_crypto_sentiment.py --exploratory     # H8a, full history to 2026-10-31 (outcomes already seen)
  python scripts/study_crypto_sentiment.py --period design   # H8a design years only (outcomes to 2022-12-31)
  python scripts/study_crypto_sentiment.py --period test     # refuses unless research/prereg/H8a.json is committed
  python scripts/study_crypto_sentiment.py --h8b-prep        # F- line from 2020-22 funding; OKX vs Binance, Oct 2026
  python scripts/study_crypto_sentiment.py --arms            # H8b verdict; refuses unless H8b.json is committed
Paper research only.
"""

from __future__ import annotations

import argparse
import contextlib
import importlib.util
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from indtrader.crypto_learn import nw_tstat  # noqa: E402
from indtrader.research import prereg  # noqa: E402
from indtrader.validation import deflated_sharpe  # noqa: E402


def _script(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_cms = _script("crypto_momentum_study")          # split_reused_tickers; it loads crypto_backtest as .cb
split_reused_tickers = _cms.split_reused_tickers
cb = _cms.cb                                     # simulate: costs and the after-tax book
FEE, SLIP, TAX = cb.FEE, cb.SLIP, cb.TAX

H8A, H8B = "H8a", "H8b"
DATA = ROOT / "data" / "crypto"
RESULTS = ROOT / "research" / "results"
PAPER = ROOT / "paper" / "crypto"
COINS = ("BTC", "ETH")
FG_FEAR, FG_GREED = 25, 75           # extreme fear below 25, extreme greed above 75 (crypto_learn.state)
FUND_HIGH = 0.0003                   # 0.03% per 8 hours
N3, N7 = 9, 21                       # settlements in 3 and 7 days
SMA_N = 50
HORIZONS = (1, 7, 30)
EPISODE_GAP = 7                      # tag-on stretches separated by at least 7 days with the tag off
COST_MULTS = (1, 2)                  # costs as in section 1.0, and doubled
TDS = 0.01
END = prereg.CRYPTO_TEST_END
DESIGN_END = prereg.CRYPTO_DESIGN_END
TEST_START = prereg.CRYPTO_TEST_START
SOURCE_START = {"fear_greed": "2018-06-01", "price": "2018-06-01", "funding": "2020-01-01"}
ENDPOINT_FIRST = "2025-06-30"        # section 2, rule 4: repeat with the end date at each month-end from here
OKX_URL = "https://www.okx.com/api/v5/public/funding-rate-history"
OKX_CHECK = ("2026-10-01", "2026-10-31")
METRICS = ("up", "ret", "net1", "at1", "net2", "at2", "mae")

LESSONS = (
    {"id": "fear-rebound-7d", "tag": "fg_extreme_fear", "source": "fear_greed", "h": 7, "expect": "up"},
    {"id": "greed-pullback-7d", "tag": "fg_extreme_greed", "source": "fear_greed", "h": 7, "expect": "down"},
    {"id": "crowded-longs-24h", "tag": "funding_high", "source": "funding", "h": 1, "expect": "down"},
    {"id": "downtrend-continues-7d", "tag": "below_50d", "source": "price", "h": 7, "expect": "down"},
)
ADDONS = (
    {"id": "addon-trend-or-negative-funding", "rule": "or_negative", "feeds": None,
     "rule_text": "each coin's half is held while its close is above its 50-day average OR its 3-day average funding is below 0"},
    {"id": "addon-flat-when-funding-high", "rule": "flat_high", "feeds": "crowded-longs-24h",
     "rule_text": "each coin's half is held while its close is above its 50-day average AND its 3-day average funding is not above 0.03%"},
)


# ---------------------------------------------------------------------------------------------------- data

def load_prices(end: str, coins=COINS) -> dict[str, pd.DataFrame]:
    """Daily candles cut at `end` when read, on a full calendar (a missing day is NaN, never skipped over)."""
    out = {}
    for coin in coins:
        df = pd.read_csv(DATA / f"{coin}.csv", parse_dates=["date"]).set_index("date").sort_index()
        parts = split_reused_tickers(coin, df)
        if len(parts) != 1:
            raise ValueError(f"{coin}: a reused ticker was found; this study expects one continuous coin")
        df = parts[0][1].loc[:end, ["open", "high", "low", "close"]].astype(float)
        out[coin] = df.reindex(pd.date_range(df.index[0], df.index[-1], freq="D"))
    return out


def load_fg(end: str) -> pd.Series:
    fg = pd.read_csv(DATA / "fear_greed.csv", parse_dates=["date"]).set_index("date")["value"].astype(float).sort_index()
    fg = fg[~fg.index.duplicated()].loc[:end]
    return fg.reindex(pd.date_range(fg.index[0], fg.index[-1], freq="D"))       # missing days stay NaN


def load_funding(coin: str, end: str) -> pd.Series:
    f = pd.read_csv(DATA / f"funding_{coin}.csv")
    t = pd.to_datetime(f["time"], utc=True).dt.tz_convert(None)
    s = pd.Series(f["rate"].astype(float).to_numpy(), index=pd.DatetimeIndex(t)).sort_index()
    s = s[~s.index.duplicated()]
    return s[s.index < pd.Timestamp(end) + pd.Timedelta(days=1)]


def settled_avg(rates: pd.Series, n: int) -> pd.Series:
    """Rolling mean of n settlements, NaN unless they are consecutive (8 hours apart)."""
    t = pd.Series(rates.index, index=rates.index)
    roll = rates.rolling(n, min_periods=n).mean()
    if n > 1:
        roll = roll.where((t - t.shift(n - 1)) == pd.Timedelta(hours=8 * (n - 1)))
    return roll


def funding_avg(rates: pd.Series, n: int, days: pd.DatetimeIndex, include_midnight: bool = False) -> pd.Series:
    """Average of the last n settled rates known at day t's decision (day t's close = 00:00 UTC of day t+1).

    Default (conservative): the settlement at 00:00 UTC of t+1 coincides with the decision and is left out, so the
    window ends with day t's 16:00 settlement. include_midnight=True takes it in (the live 00:10 UTC run sees it).
    NaN unless the window is complete and its latest settlement is at most 8 hours before the cutoff."""
    roll = settled_avg(rates, n).to_numpy()
    t = rates.index
    cutoff = days + pd.Timedelta(days=1)
    idx = t.searchsorted(cutoff, side="right" if include_midnight else "left") - 1
    out = np.full(len(days), np.nan)
    ok = idx >= 0
    if ok.any():
        last = t.to_numpy()[idx[ok]]
        fresh = (cutoff.to_numpy()[ok] - last) <= np.timedelta64(8, "h")
        out[np.flatnonzero(ok)] = np.where(fresh, roll[idx[ok]], np.nan)
    return pd.Series(out, index=days)


def build_tags(px: dict, fg: pd.Series, funding: dict) -> dict[str, pd.DataFrame]:
    """Per coin and day: 1.0 (tag on), 0.0 (off) or NaN (unknown), as known at day t's close."""
    out = {}
    for coin, df in px.items():
        days = df.index
        f = fg.reindex(days)
        close = df["close"]
        sma = close.rolling(SMA_N, min_periods=SMA_N).mean()
        f3 = funding_avg(funding[coin], N3, days) if coin in funding else pd.Series(np.nan, index=days)
        out[coin] = pd.DataFrame({
            "fg_extreme_fear": (f < FG_FEAR).astype(float).where(f.notna()),
            "fg_extreme_greed": (f > FG_GREED).astype(float).where(f.notna()),
            "below_50d": (~(close > sma)).astype(float).where(sma.notna() & close.notna()),   # live tag: not above
            "funding_avg3d": f3,
            "funding_high": (f3 > FUND_HIGH).astype(float).where(f3.notna()),
            "funding_negative": (f3 < 0).astype(float).where(f3.notna()),
        }, index=days)
    return out


# ---------------------------------------------------------------------------------------------------- events

def outcomes(df: pd.DataFrame, h: int) -> pd.DataFrame:
    """For a decision at day t's close: enter at open(t+1), exit at close(t+h). mae = lowest low of t+1..t+h
    against the entry (the worst drawdown inside the window). NaN when a day is missing."""
    o1 = df["open"].shift(-1)
    ret = df["close"].shift(-h) / o1 - 1
    mae = df["low"].rolling(h, min_periods=h).min().shift(-h) / o1 - 1
    ok = ret.notna() & mae.notna()
    return pd.DataFrame({"ret": ret.where(ok), "mae": mae.where(ok)})


def after_tax(x) -> np.ndarray:
    """One event: a profit after costs keeps 68.8% (31.2% tax), a loss is kept in full (no set-off)."""
    x = np.asarray(x, dtype=float)
    return np.where(x > 0, (1 - TAX) * x, x)


def coin_events(px: dict, tags: dict, tag: str, h: int, start, end) -> pd.DataFrame:
    """One row per coin-day t in [start, end] whose tag is known and whose outcome window t+1 .. t+h ends by `end`."""
    s, last_t = pd.Timestamp(start), pd.Timestamp(end) - pd.Timedelta(days=h)
    parts = []
    for coin, df in px.items():
        o = outcomes(df, h)
        d = tags[coin][tag].reindex(df.index)
        sel = (df.index >= s) & (df.index <= last_t) & d.notna().to_numpy() & o["ret"].notna().to_numpy()
        parts.append(pd.DataFrame({"day": df.index[sel], "coin": coin, "d": d.to_numpy()[sel],
                                   "ret": o["ret"].to_numpy()[sel], "mae": o["mae"].to_numpy()[sel]}))
    ev = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=["day", "coin", "d", "ret", "mae"])
    ev["up"] = (ev["ret"] > 0).astype(float)                     # price up, as the live scorer grades (px > spot)
    for m in COST_MULTS:
        net = ev["ret"] - m * 2 * (FEE + SLIP)
        ev[f"net{m}"] = net
        ev[f"at{m}"] = after_tax(net)
    return ev.sort_values(["day", "coin"]).reset_index(drop=True)


def group_means(ev: pd.DataFrame) -> pd.DataFrame:
    """Average across coins on each day, separately for tag-on and tag-off coins: one row per (day, group)."""
    if ev.empty:
        return pd.DataFrame(columns=["day", "d", *METRICS])
    return ev.groupby(["day", "d"], as_index=False)[list(METRICS)].mean().sort_values(["day", "d"]).reset_index(drop=True)


def _daynum(days) -> np.ndarray:
    return pd.to_datetime(pd.Series(days)).to_numpy().astype("datetime64[D]").astype(np.int64)


def nw_lags(h: int, n_days: int) -> int:
    """At least the horizon in days, and at least the usual automatic bandwidth floor(4 (n/100)^(2/9))."""
    return max(int(h), int(math.floor(4 * (max(n_days, 1) / 100) ** (2 / 9))))


def dk_slope(day: np.ndarray, d: np.ndarray, y: np.ndarray, lags: int) -> tuple[float, float]:
    """Difference in means (slope of y on a 0/1 dummy) and its t-statistic, with a Newey-West covariance over
    calendar days on the scores summed within each day (Driscoll-Kraay). With one row per consecutive day this is
    exactly crypto_learn.hac_slope_t; summing by day handles a day that holds both a tag-on and a tag-off row."""
    if len(y) < 3 or d.min() == d.max():
        return float("nan"), float("nan")
    X = np.column_stack([np.ones(len(d)), d])
    xtx_inv = np.linalg.inv(X.T @ X)
    beta = xtx_inv @ X.T @ y
    g = X * (y - X @ beta)[:, None]
    k = (day - day.min()).astype(int)
    G = np.zeros((int(k.max()) + 1, 2))
    np.add.at(G, k, g)
    S = G.T @ G
    for j in range(1, min(lags, len(G) - 1) + 1):
        c = G[j:].T @ G[:-j]
        S += (1 - j / (lags + 1)) * (c + c.T)
    V = xtx_inv @ S @ xtx_inv
    se = math.sqrt(max(float(V[1, 1]), 1e-18))
    return float(beta[1]), float(beta[1] / se)


def compare(gm: pd.DataFrame, h: int, metrics=METRICS) -> dict:
    """Tag-on against tag-off: daily group means, then the difference with a Newey-West t (in %, points for 'up')."""
    on, off = gm[gm["d"] == 1], gm[gm["d"] == 0]
    out: dict = {"days_on": int(on["day"].nunique()), "days_off": int(off["day"].nunique())}
    if len(on) < 3 or len(off) < 3:
        out["note"] = "fewer than 3 days in a group: no statistic"
        return out
    day = _daynum(gm["day"])
    lags = nw_lags(h, int(day.max() - day.min() + 1))
    out["nw_lags"] = lags
    d = gm["d"].to_numpy(float)
    for m in metrics:
        diff, t = dk_slope(day, d, gm[m].to_numpy(float), lags)
        se = abs(diff / t) if t and math.isfinite(t) else float("nan")
        out[m] = {"on": 100 * float(on[m].mean()), "off": 100 * float(off[m].mean()), "diff": 100 * diff, "t": t,
                  "ci95": [100 * (diff - 1.96 * se), 100 * (diff + 1.96 * se)]}
    return out


def episodes(on_days, gap: int = EPISODE_GAP) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """Tag-on days grouped into episodes: a new one starts after at least `gap` days with the tag off."""
    eps: list[list[pd.Timestamp]] = []
    for d in sorted(pd.DatetimeIndex(on_days).unique()):
        if eps and (d - eps[-1][1]).days - 1 < gap:
            eps[-1][1] = d
        else:
            eps.append([d, d])
    return [(a, b) for a, b in eps]


def ct_portfolio(px: dict, ev: pd.DataFrame, h: int, start, end, cost_side: float) -> tuple[pd.Series, pd.Series]:
    """Calendar-time portfolio: equal weight across the open event positions (enter at open t+1, exit at close t+h),
    rebalanced daily, `cost_side` at entry and at exit, zero return on days with nothing open. Returns the daily
    returns and the number of open positions."""
    days = pd.date_range(start, end, freq="D")
    num, cnt = np.zeros(len(days)), np.zeros(len(days))
    for coin, g in ev.groupby("coin"):
        df = px[coin].reindex(days)
        e = pd.Series(0.0, index=days)
        e.loc[pd.DatetimeIndex(g["day"])] = 1.0
        e = e.to_numpy()
        entry = np.r_[0.0, e[:-1]]
        exit_ = np.r_[np.zeros(h), e][: len(days)]
        n_open = pd.Series(e).rolling(h, min_periods=1).sum().shift(1).fillna(0).to_numpy()
        c, o = df["close"].to_numpy(), df["open"].to_numpy()
        r_entry = np.nan_to_num(c / o - 1)
        r_hold = np.nan_to_num(c / np.r_[np.nan, c[:-1]] - 1)
        num += entry * r_entry + (n_open - entry) * r_hold - cost_side * (entry + exit_)
        cnt += n_open
    r = np.where(cnt > 0, num / np.where(cnt > 0, cnt, 1), 0.0)
    return pd.Series(r, index=days), pd.Series(cnt, index=days)


def curve_stats(r: pd.Series, n_open: pd.Series, h: int) -> dict:
    eq = (1 + r).cumprod()
    sd = float(r.std(ddof=1))
    years = len(r) / 365.25
    return {"total_return_pct": 100 * (float(eq.iloc[-1]) - 1),
            "ann_return_pct": 100 * (float(eq.iloc[-1]) ** (1 / years) - 1) if years > 0 and eq.iloc[-1] > 0 else None,
            "sharpe": math.sqrt(365) * float(r.mean()) / sd if sd > 0 else None,
            "max_dd_pct": 100 * float((eq / eq.cummax() - 1).min()),
            "days_invested": int((n_open > 0).sum()),
            "nw_t_mean_daily": nw_tstat(r.to_numpy(), nw_lags(h, len(r)))}


# ---------------------------------------------------------------------------------------------------- H8a lessons

def half_bounds(source: str, half: str, end: str = END) -> tuple[str, str]:
    if half == "design":
        return SOURCE_START[source], DESIGN_END
    if half == "test":
        return TEST_START, end
    return SOURCE_START[source], end                               # full history


def lesson_half(lesson: dict, px: dict, tags: dict, start, end) -> dict:
    tag, s, e = lesson["tag"], pd.Timestamp(start), pd.Timestamp(end)
    on_by_coin = {}
    for coin, t in tags.items():
        x = t.loc[s:e, tag]
        on_by_coin[coin] = x.index[x == 1]
    pooled = pd.DatetimeIndex(sorted(set().union(*[set(v) for v in on_by_coin.values()])))
    eps = episodes(pooled)
    first_days = {a for a, _ in eps}
    out: dict = {"start": str(s.date()), "end": str(e.date()), "tag_days_pooled": len(pooled),
                 "tag_days_per_coin": {c: len(v) for c, v in on_by_coin.items()},
                 "episodes": len(eps), "episodes_per_coin": {c: len(episodes(v)) for c, v in on_by_coin.items()},
                 "known_days": int(sum(tags[c].loc[s:e, tag].notna().sum() for c in tags)), "by_horizon": {}}
    for h in HORIZONS:
        ev = coin_events(px, tags, tag, h, s, e)
        gm = group_means(ev)
        on_ev, off_ev = ev[ev["d"] == 1], ev[ev["d"] == 0]
        first_ev = on_ev[on_ev["day"].isin(first_days)]
        first = compare(pd.concat([group_means(first_ev), gm[gm["d"] == 0]]).sort_values(["day", "d"]), h)
        first["episodes_with_outcome"] = int(first_ev["day"].nunique())
        first["worst_drawdown_single_event_pct"] = 100 * float(first_ev["mae"].min()) if len(first_ev) else None
        first["portfolio"] = {}                    # section 1.0: Sharpe and maximum drawdown next to every return
        for m in COST_MULTS:
            r, n_open = ct_portfolio(px, first_ev, h, s, e, m * (FEE + SLIP))
            first["portfolio"][f"costs_x{m}_pre_tax"] = curve_stats(r, n_open, h)
        res = {"coin_events_on": len(on_ev), "coin_events_off": len(off_ev), "all": compare(gm, h),
               "worst_drawdown_single_event_pct": 100 * float(on_ev["mae"].min()) if len(on_ev) else None,
               "first_day_of_episode": first, "portfolio": {}}
        for grp, sub in (("tag_on", on_ev), ("tag_off", off_ev)):
            for m in COST_MULTS:
                r, n_open = ct_portfolio(px, sub, h, s, e, m * (FEE + SLIP))
                res["portfolio"][f"{grp}_costs_x{m}_pre_tax"] = curve_stats(r, n_open, h)
        if h == lesson["h"]:
            res["per_coin_up"] = {c: compare(group_means(ev[ev["coin"] == c]), h, ("up",)) for c in px}
        out["by_horizon"][str(h)] = res
    hl = out["by_horizon"][str(lesson["h"])]["all"]
    up = hl.get("up", {})
    out["headline"] = {"horizon_days": lesson["h"], "days_on": hl["days_on"], "days_off": hl["days_off"],
                       "episodes": len(eps), "up_on_pct": up.get("on"), "up_off_pct": up.get("off"),
                       "diff_pp": up.get("diff"), "t": up.get("t"), "ci95_pp": up.get("ci95")}
    return out


def lesson_endpoints(lesson: dict, px: dict, tags: dict) -> dict:
    """Section 2, rule 4: the 2023-26 headline repeated with the end date at each month-end from 30 Jun 2025."""
    rows = []
    for e in pd.date_range(ENDPOINT_FIRST, END, freq="ME"):
        c = compare(group_means(coin_events(px, tags, lesson["tag"], lesson["h"], TEST_START, e)), lesson["h"], ("up",))
        rows.append({"end": str(e.date()), "diff_pp": c.get("up", {}).get("diff"), "t": c.get("up", {}).get("t")})
    signs = {np.sign(r["diff_pp"]) for r in rows if r["diff_pp"] is not None}
    return {"rows": rows, "sign_flips": len(signs) > 1}


# ---------------------------------------------------------------------------------------------------- add-on rows

def sim_signals(px: dict, funding: dict, include_midnight: bool = False) -> dict:
    """The trend rule's own test (indtrader.crypto.above: more than 50 closes and the close above the mean of the
    last 50) and the 3-day average funding, per coin and day."""
    sig = {}
    for coin, df in px.items():
        close = df["close"]
        above = (close > close.rolling(SMA_N, min_periods=SMA_N).mean()) & (close.notna().cumsum() > SMA_N)
        f3 = funding_avg(funding[coin], N3, df.index, include_midnight) if coin in funding else pd.Series(np.nan, index=df.index)
        sig[coin] = {"above": dict(zip(df.index, above.to_numpy(bool), strict=True)),
                     "f3": dict(zip(df.index, f3.to_numpy(float), strict=True))}
    return sig


def hold_rule(kind: str, above: bool, f3: float, high: float = FUND_HIGH, inclusive: bool = False) -> bool:
    """Is a coin's share held? Unknown funding (NaN) never changes the plain rule."""
    if kind == "plain":
        return bool(above)
    if kind == "or_negative":
        return bool(above or f3 < 0)
    if kind == "flat_high":
        crowded = f3 >= high if inclusive else f3 > high
        return bool(above and not crowded)
    raise ValueError(kind)


def make_rule(kind: str, sig: dict, coins, **kw):
    w = 1.0 / len(coins)

    def fn(day, _closes):
        return {k: w for k in coins if hold_rule(kind, sig[k]["above"].get(day, False), sig[k]["f3"].get(day, np.nan), **kw)}
    return fn


def btc_hold(day, _closes):
    return {"BTC": 1.0}


@contextlib.contextmanager
def cost_level(mult: float):
    """Run crypto_backtest.simulate with its fee and slippage multiplied (it reads the module's FEE and SLIP)."""
    fee, slip = cb.FEE, cb.SLIP
    cb.FEE, cb.SLIP = fee * mult, slip * mult
    try:
        yield
    finally:
        cb.FEE, cb.SLIP = fee, slip


def run_sim(px: dict, fn, start, end, mult: float = 1, coins=COINS) -> dict:
    opens = pd.DataFrame({k: px[k]["open"] for k in coins}).loc[:end]
    closes = pd.DataFrame({k: px[k]["close"] for k in coins}).loc[:end]
    with cost_level(mult):
        r = cb.simulate(opens, closes, fn, str(start))
    e = r["equity"]
    rets = e.pct_change().dropna()
    years = (e.index[-1] - e.index[0]).days / 365.25
    traded = r["fees"] / ((FEE + SLIP) * mult)
    return {"equity": e,
            "pre_tax_return_pct": 100 * (float(e.iloc[-1]) - 1),
            "after_tax_return_pct": 100 * (float(r["after_tax_final"]) - 1),
            "cagr_pct": 100 * (float(e.iloc[-1]) ** (1 / years) - 1) if years > 0 else None,
            "sharpe": math.sqrt(365) * float(rets.mean()) / float(rets.std()) if rets.std() > 0 else None,
            "max_dd_pct": 100 * float((e / e.cummax() - 1).min()),
            "trades": int(r["trades"]), "fees_pct_of_start": 100 * float(r["fees"]),
            "tds_per_year_pct_of_start": 100 * TDS * traded / 2 / years if years > 0 else None}


def _no_curve(d: dict) -> dict:
    return {k: v for k, v in d.items() if k != "equity"}


def addon_activity(addon: dict, sig: dict, start, end) -> dict:
    """Coin-days on which the add-on's target differs from the plain rule's, and their episodes."""
    days = pd.date_range(start, end, freq="D")
    changed: dict[str, list] = {}
    for coin in COINS:
        changed[coin] = [d for d in days if hold_rule(addon["rule"], sig[coin]["above"].get(d, False), sig[coin]["f3"].get(d, np.nan))
                         != hold_rule("plain", sig[coin]["above"].get(d, False), np.nan)]
    pooled = sorted(set().union(*[set(v) for v in changed.values()]))
    return {"coin_days_changed": sum(len(v) for v in changed.values()), "days_changed_per_coin": {c: len(v) for c, v in changed.items()},
            "episodes": len(episodes(pooled)), "episodes_per_coin": {c: len(episodes(v)) for c, v in changed.items()}}


def addon_half(px: dict, sig: dict, start, end) -> tuple[dict, dict]:
    out: dict = {"start": str(start), "end": str(end)}
    curves = {}
    rules = [("plain", make_rule("plain", sig, COINS), COINS), ("hold_btc", btc_hold, ("BTC",))]
    rules += [(a["id"], make_rule(a["rule"], sig, COINS), COINS) for a in ADDONS]
    for m in COST_MULTS:
        res = {}
        for name, fn, coins in rules:
            r = run_sim(px, fn, start, end, m, coins)
            res[name] = _no_curve(r)
            if m == 1:
                curves[name] = r["equity"]
        out[f"costs_x{m}"] = res
    for a in ADDONS:
        out[a["id"]] = {"activity": addon_activity(a, sig, start, end)}
        for m in COST_MULTS:
            res = out[f"costs_x{m}"]
            out[a["id"]][f"after_tax_excess_vs_plain_pp_x{m}"] = res[a["id"]]["after_tax_return_pct"] - res["plain"]["after_tax_return_pct"]
            out[a["id"]][f"beats_plain_after_tax_x{m}"] = res[a["id"]]["after_tax_return_pct"] > res["plain"]["after_tax_return_pct"]
    return out, curves


def addon_endpoints(px: dict, sig: dict) -> dict:
    rows = []
    for e in pd.date_range(ENDPOINT_FIRST, END, freq="ME"):
        plain = run_sim(px, make_rule("plain", sig, COINS), TEST_START, e)["after_tax_return_pct"]
        row = {"end": str(e.date()), "plain_after_tax_pct": plain}
        for a in ADDONS:
            row[a["id"]] = run_sim(px, make_rule(a["rule"], sig, COINS), TEST_START, e)["after_tax_return_pct"] - plain
        rows.append(row)
    flips = {a["id"]: len({np.sign(r[a["id"]]) for r in rows}) > 1 for a in ADDONS}
    return {"rows": rows, "measure": "add-on after-tax return minus the plain rule's, percentage points of the start",
            "sign_flips": flips}


# ---------------------------------------------------------------------------------------------------- lines

def lesson_lines(lesson: dict, res: dict, addons: dict | None, endpoint: dict | None) -> dict:
    """The plan's 'deserves a forward test' lines, read conservatively (research/prereg/H8a.json, clarifications)."""
    want = 1 if lesson["expect"] == "up" else -1
    d, t = res["design"]["headline"], res["test"]["headline"]
    dd, td = d.get("diff_pp"), t.get("diff_pp")
    same_sign = dd is not None and td is not None and np.sign(dd) == np.sign(td) != 0
    claimed = same_sign and want * dd > 0
    no_flip = endpoint is not None and not endpoint["sign_flips"]
    t_ok = all(x.get("t") is not None and math.isfinite(x["t"]) and want * x["t"] >= 2 for x in (d, t))
    ep_ok = d["episodes"] >= 5 and t["episodes"] >= 5
    a = next((x for x in ADDONS if x["feeds"] == lesson["id"]), None)
    if a is None:
        why = ("this lesson is the plain trend rule itself, so it cannot be an add-on to it (the desk already runs it live)"
               if lesson["tag"] == "below_50d" else "the plan names no add-on row for this gauge; adding one would add trials")
        addon = {"met": False, "addon": None, "why": why}
    else:
        ds, ts = addons["design"][a["id"]], addons["test"][a["id"]]
        flip = addons["endpoints"]["sign_flips"][a["id"]]
        met = all(h[f"beats_plain_after_tax_x{m}"] for h in (ds, ts) for m in COST_MULTS) and not flip
        addon = {"met": bool(met), "addon": a["id"], "design_excess_pp": ds["after_tax_excess_vs_plain_pp_x1"],
                 "test_excess_pp": ts["after_tax_excess_vs_plain_pp_x1"],
                 "design_excess_pp_costs_x2": ds["after_tax_excess_vs_plain_pp_x2"],
                 "test_excess_pp_costs_x2": ts["after_tax_excess_vs_plain_pp_x2"], "endpoint_sign_flips": bool(flip)}
    lines = {"same_sign_both_halves": bool(same_sign), "in_claimed_direction": bool(claimed),
             "test_half_sign_stable_at_every_month_end": bool(no_flip),
             "nw_t_at_least_2_each_half_in_claimed_direction": bool(t_ok), "at_least_5_episodes_each_half": bool(ep_ok),
             "addon_beats_plain_after_tax_both_halves": addon}
    deserves = same_sign and claimed and no_flip and t_ok and ep_ok and addon["met"]
    return {"lines": lines, "deserves_forward_test": bool(deserves),
            "consequence": "a forward arm may be proposed (a new pre-registration and new trials)" if deserves else
            "no forward arm; the analyst may describe the gauge but not cite it as a reason"}


def addon_lines(a: dict, addons: dict) -> dict:
    ds, ts = addons["design"][a["id"]], addons["test"][a["id"]]
    flip = addons["endpoints"]["sign_flips"][a["id"]]
    return {"beats_plain_after_tax_design": bool(ds["beats_plain_after_tax_x1"]),
            "beats_plain_after_tax_test": bool(ts["beats_plain_after_tax_x1"]),
            "beats_plain_after_tax_design_costs_x2": bool(ds["beats_plain_after_tax_x2"]),
            "beats_plain_after_tax_test_costs_x2": bool(ts["beats_plain_after_tax_x2"]),
            "test_half_sign_stable_at_every_month_end": not flip,
            "addon_line_met": bool(all(h[f"beats_plain_after_tax_x{m}"] for h in (ds, ts) for m in COST_MULTS) and not flip),
            "feeds_lesson": a["feeds"]}


# ---------------------------------------------------------------------------------------------------- reproduction

def reproduce_brief(px: dict, fg: pd.Series, funding: dict) -> dict:
    """The crowd-emotion brief's figures (docs/test-plan.md H8a, 'What the scratch runs found'), BTC alone as the
    brief used, data to 2026-10-31. These rerun variants already in the ledger (sentiment_scratch past-1..7)."""
    btc = px["BTC"]
    close = btc["close"]
    f = fg.reindex(close.index)
    dist = close / close.rolling(SMA_N, min_periods=SMA_N).mean() - 1
    out: dict = {"corr_fg_vs_btc_distance_from_50d": {
        "brief": 0.79, "previous_day_distance": float(f.corr(dist.shift(1))), "same_day_distance": float(f.corr(dist))}}
    r7 = close.shift(-7) / close - 1
    r7o = close.shift(-7) / btc["open"].shift(-1) - 1
    fear = (f < FG_FEAR) & f.notna()
    out["btc_7d_after_extreme_fear"] = {
        "brief": {"up_pct_fear": 56.7, "up_pct_all": 52.6, "mean_fear_below_all": True},
        "close_to_close": {"n_fear": int((fear & r7.notna()).sum()), "up_pct_fear": 100 * float((r7[fear & r7.notna()] > 0).mean()),
                           "up_pct_all": 100 * float((r7.dropna() > 0).mean()), "mean_pct_fear": 100 * float(r7[fear].mean()),
                           "mean_pct_all": 100 * float(r7.mean())},
        "next_open_to_close": {"up_pct_fear": 100 * float((r7o[fear & r7o.notna()] > 0).mean()),
                               "up_pct_all": 100 * float((r7o.dropna() > 0).mean()), "mean_pct_fear": 100 * float(r7o[fear].mean()),
                               "mean_pct_all": 100 * float(r7o.mean())}}
    r30 = close.shift(-30) / close - 1
    below15 = f.index[(f < 15) & f.notna()]
    fg_runs = episodes(below15, gap=1)                 # consecutive days
    fg_gap7 = episodes(below15, gap=EPISODE_GAP)       # the plan's episode rule
    out["btc_30d_after_first_day_fg_below_15"] = {"brief": {"episodes": 14, "mean_pct_first_days": -3.9, "mean_pct_all": 4.2},
                                                   "mean_pct_all_days": 100 * float(r30.mean())}
    for name, eps in (("consecutive_runs", fg_runs), ("gap_7_days", fg_gap7)):
        v = r30.reindex([a for a, _ in eps]).dropna()
        out["btc_30d_after_first_day_fg_below_15"][name] = {"episodes": len(eps), "with_outcome": len(v),
                                                             "mean_pct_first_days": 100 * float(v.mean()) if len(v) else None}
    r1 = close.shift(-1) / close - 1
    out["btc_next_day_after_crowded_funding"] = {"brief": {"mean_pct_crowded": 0.16, "mean_pct_all": 0.14, "up_pct": 51.9, "days": 208}}
    for name, mid in (("window_to_day_t_16utc", False), ("window_to_t_plus_1_00utc", True)):
        f3 = funding_avg(funding["BTC"], N3, close.index, include_midnight=mid)
        known = f3.notna() & r1.notna()
        crowded = known & (f3 >= FUND_HIGH)
        out["btc_next_day_after_crowded_funding"][name] = {
            "days": int(crowded.sum()), "mean_pct_crowded": 100 * float(r1[crowded].mean()),
            "up_pct_crowded": 100 * float((r1[crowded] > 0).mean()),
            "mean_pct_all_days_with_funding": 100 * float(r1[known].mean())}
    sig = sim_signals(px, funding)
    btc_only = ("BTC",)
    p = run_sim(px, make_rule("plain", sig, btc_only), TEST_START, END, 1, btc_only)
    o = run_sim(px, make_rule("or_negative", sig, btc_only), TEST_START, END, 1, btc_only)
    out["btc_trend_addons_since_2023"] = {
        "brief": {"plain_pct": 390, "plain_max_dd_pct": -27, "or_negative_pct": 483, "or_negative_max_dd_pct": -38},
        "plain": {k: p[k] for k in ("pre_tax_return_pct", "max_dd_pct", "after_tax_return_pct")},
        "trend_or_negative_funding": {k: o[k] for k in ("pre_tax_return_pct", "max_dd_pct", "after_tax_return_pct")}}
    flat = {"brief": "going flat when funding is crowded hurt both BTC and ETH in 2020-26"}
    for coin in COINS:
        one = (coin,)
        a = run_sim(px, make_rule("plain", sig, one), SOURCE_START["funding"], END, 1, one)
        b = run_sim(px, make_rule("flat_high", sig, one, inclusive=True), SOURCE_START["funding"], END, 1, one)
        flat[coin] = {"plain_pct": a["pre_tax_return_pct"], "flat_when_crowded_pct": b["pre_tax_return_pct"],
                      "plain_after_tax_pct": a["after_tax_return_pct"], "flat_when_crowded_after_tax_pct": b["after_tax_return_pct"],
                      "hurt": b["pre_tax_return_pct"] < a["pre_tax_return_pct"]}
    out["flat_when_crowded_2020_26"] = flat
    counts = {"brief": {"design_fear": 493, "design_greed": 185, "test_fear": 186, "test_greed": 97}}
    full = load_fg("2100-01-01")                       # Fear & Greed values only (no outcomes), as the plan counted
    for name, lo, hi in (("design_2018_22", "2018-01-01", DESIGN_END), ("test_to_2026_10_31", TEST_START, END),
                         ("test_to_file_end", TEST_START, str(full.index[-1].date()))):
        x = full.loc[lo:hi].dropna()
        counts[name] = {"fear": int((x < FG_FEAR).sum()), "greed": int((x > FG_GREED).sum())}
    out["fear_greed_day_counts"] = counts
    out["status"] = reproduction_status(out)
    out["status_rule"] = ("A brief figure counts as reproduced when every number in it matches at the precision the brief "
                          "printed (counts exactly), in at least one of the alignments tried. Otherwise it keeps the plan's "
                          "label (section 2, rule 6).")
    return out


REPRODUCED = "reproduced from the repo by scripts/study_crypto_sentiment.py"
NOT_REPRODUCED = "unreviewed exploratory result, not reproducible from the repo"


def _matches(ours, brief) -> bool:
    """`ours` equals the brief's figure at the precision the brief printed it; counts and yes/no answers exactly."""
    if ours is None or (isinstance(ours, float) and not math.isfinite(ours)):
        return False
    if isinstance(brief, bool):
        return bool(ours) == brief
    if isinstance(brief, int) and isinstance(ours, int | np.integer):
        return int(ours) == brief
    dp = 0 if isinstance(brief, int) or "." not in repr(brief) else len(repr(brief).split(".")[1])
    return abs(float(ours) - float(brief)) <= 0.5 * 10 ** -dp + 1e-12


def reproduction_status(rep: dict) -> dict:
    """Which of the brief's figures (docs/test-plan.md H8a, 'What the scratch runs found') this script reproduces."""
    def ok(pairs) -> bool:
        return all(_matches(o, b) for o, b in pairs)

    c = rep["corr_fg_vs_btc_distance_from_50d"]
    f7, b7 = rep["btc_7d_after_extreme_fear"], rep["btc_7d_after_extreme_fear"]["brief"]
    f15, b15 = rep["btc_30d_after_first_day_fg_below_15"], rep["btc_30d_after_first_day_fg_below_15"]["brief"]
    cf, bc = rep["btc_next_day_after_crowded_funding"], rep["btc_next_day_after_crowded_funding"]["brief"]
    ta, bt = rep["btc_trend_addons_since_2023"], rep["btc_trend_addons_since_2023"]["brief"]
    dc, bd = rep["fear_greed_day_counts"], rep["fear_greed_day_counts"]["brief"]
    found = {
        "corr_fg_vs_btc_distance_from_50d": ok([(c["previous_day_distance"], c["brief"])]),
        "btc_7d_after_extreme_fear": any(ok([(f7[k]["up_pct_fear"], b7["up_pct_fear"]), (f7[k]["up_pct_all"], b7["up_pct_all"]),
                                             (f7[k]["mean_pct_fear"] < f7[k]["mean_pct_all"], b7["mean_fear_below_all"])])
                                         for k in ("close_to_close", "next_open_to_close")),
        "btc_30d_after_first_day_fg_below_15": any(ok([(f15[k]["episodes"], b15["episodes"]),
                                                       (f15[k]["mean_pct_first_days"], b15["mean_pct_first_days"]),
                                                       (f15["mean_pct_all_days"], b15["mean_pct_all"])])
                                                   for k in ("consecutive_runs", "gap_7_days")),
        "btc_next_day_after_crowded_funding": any(ok([(cf[k]["days"], bc["days"]), (cf[k]["mean_pct_crowded"], bc["mean_pct_crowded"]),
                                                      (cf[k]["up_pct_crowded"], bc["up_pct"]),
                                                      (cf[k]["mean_pct_all_days_with_funding"], bc["mean_pct_all"])])
                                                  for k in ("window_to_day_t_16utc", "window_to_t_plus_1_00utc")),
        "btc_trend_addons_since_2023": ok([(ta["plain"]["pre_tax_return_pct"], bt["plain_pct"]),
                                           (ta["plain"]["max_dd_pct"], bt["plain_max_dd_pct"]),
                                           (ta["trend_or_negative_funding"]["pre_tax_return_pct"], bt["or_negative_pct"]),
                                           (ta["trend_or_negative_funding"]["max_dd_pct"], bt["or_negative_max_dd_pct"])]),
        "flat_when_crowded_2020_26": all(rep["flat_when_crowded_2020_26"][k]["hurt"] for k in COINS),
        "fear_greed_day_counts": any(ok([(dc["design_2018_22"]["fear"], bd["design_fear"]),
                                         (dc["design_2018_22"]["greed"], bd["design_greed"]),
                                         (dc[k]["fear"], bd["test_fear"]), (dc[k]["greed"], bd["test_greed"])])
                                     for k in ("test_to_2026_10_31", "test_to_file_end")),
    }
    return {k: {"reproduced": bool(v), "label": REPRODUCED if v else NOT_REPRODUCED} for k, v in found.items()}


# ---------------------------------------------------------------------------------------------------- H8a runner

def _clean(x):
    if isinstance(x, dict):
        return {str(k): _clean(v) for k, v in x.items()}
    if isinstance(x, list | tuple):
        return [_clean(v) for v in x]
    if isinstance(x, np.bool_):
        return bool(x)
    if isinstance(x, np.integer):
        return int(x)
    if isinstance(x, float | np.floating):
        return None if not math.isfinite(float(x)) else float(f"{float(x):.8g}")      # 8 significant digits
    if isinstance(x, pd.Timestamp):
        return x.isoformat()
    return x


def run_h8a(halves: tuple[str, ...], kind: str) -> dict:
    end = DESIGN_END if halves == ("design",) else END
    px = load_prices(end)
    fg = load_fg(end)
    funding = {c: load_funding(c, end) for c in COINS}
    tags = build_tags(px, fg, funding)
    sig = sim_signals(px, funding)
    out: dict = {"test": H8A, "kind": kind, "label": "history, outcomes already seen" if kind == "exploratory" else kind,
                 "run_at": datetime.now(UTC).isoformat(timespec="seconds"), "data_end": end, "universe": list(COINS),
                 "lessons": {}, "addons": {}}
    for lesson in LESSONS:
        res = {"tag": lesson["tag"], "horizon_days": lesson["h"], "expect": lesson["expect"]}
        for half in halves:
            res[half] = lesson_half(lesson, px, tags, *half_bounds(lesson["source"], half, end))
        if "test" in halves:
            res["endpoint_check_test_half"] = lesson_endpoints(lesson, px, tags)
        out["lessons"][lesson["id"]] = res
    curves = {}
    for half in [h for h in halves if h in ("design", "test")]:
        out["addons"][half], curves[half] = addon_half(px, sig, *half_bounds("funding", half, end))
    if "test" in halves:
        out["addons"]["endpoints"] = addon_endpoints(px, sig)
    if kind == "exploratory":
        out["reproduction_of_brief"] = reproduce_brief(px, fg, funding)
        for lesson in LESSONS:
            r = out["lessons"][lesson["id"]]
            r["verdict"] = lesson_lines(lesson, r, out["addons"], r["endpoint_check_test_half"])
        for a in ADDONS:
            out["addons"].setdefault("lines", {})[a["id"]] = addon_lines(a, out["addons"])
    # one trial per lesson and per add-on row
    period = {"exploratory": "history 2018-2026-10-31", "design": "design", "test": "test"}[kind]
    main_half = "full" if kind == "exploratory" else halves[0]
    for lesson in LESSONS:
        r = out["lessons"][lesson["id"]]
        hl = r[main_half]["headline"]
        note = "; ".join(f"{h} diff {_fmt(r[h]['headline']['diff_pp'])}pp t {_fmt(r[h]['headline']['t'])} ep {r[h]['headline']['episodes']}"
                         for h in halves)
        if "verdict" in r:
            note += f"; deserves forward test: {r['verdict']['deserves_forward_test']}"
        prereg.log_trial(H8A, lesson["id"], period, f"uprate_diff_pp_{lesson['h']}d", hl["diff_pp"], t=hl["t"], n=hl["days_on"],
                         kind=kind, note=note)
    for a in ADDONS:
        ex = [out["addons"][h][a["id"]]["after_tax_excess_vs_plain_pp_x1"] for h in halves if h in out["addons"]]
        note = "; ".join(f"{h} after-tax excess {_fmt(out['addons'][h][a['id']]['after_tax_excess_vs_plain_pp_x1'])}pp"
                         for h in halves if h in out["addons"])
        prereg.log_trial(H8A, a["id"], period, "min_after_tax_excess_vs_plain_pp", min(ex) if ex else None,
                         n=sum(out["addons"][h][a["id"]]["activity"]["episodes"] for h in halves if h in out["addons"]),
                         kind=kind, note=note)
    n_trials = prereg.trial_count("crypto")
    for half, cv in curves.items():
        out["addons"][half]["deflated_sharpe"] = {name: deflated_sharpe(e, n_trials) for name, e in cv.items() if name != "hold_btc"}
    out["crypto_trial_count_after_this_run"] = n_trials
    out["deflated_sharpe_note"] = (
        "indtrader.validation.deflated_sharpe on each pre-tax equity curve; its 'sharpe' and 'sharpe_hurdle' are annualised "
        "with sqrt(252) by validation._sharpe (the other Sharpe ratios here use sqrt(365)); the probability itself does not "
        "depend on the annualisation. Null spread 1/sqrt(T) (the past trials' Sharpe ratios are unknown).")
    if kind == "exploratory":
        out["evidence_history"] = evidence_blocks(out)
    return _clean(out)


def evidence_blocks(out: dict) -> list[dict]:
    blocks = []
    for lesson in LESSONS:
        r = out["lessons"][lesson["id"]]
        hs = sorted({lesson["h"], 7, 30})              # the lesson's horizon, and 7 and 30 days as the plan asks
        first = {h: {str(k): {**{x: r[h]["by_horizon"][str(k)]["first_day_of_episode"].get(x)
                                 for x in ("episodes_with_outcome", "up", "ret", "at1", "worst_drawdown_single_event_pct")},
                              "portfolio_costs_x1_pre_tax": {x: r[h]["by_horizon"][str(k)]["first_day_of_episode"]
                                                             .get("portfolio", {}).get("costs_x1_pre_tax", {}).get(x)
                                                             for x in ("sharpe", "max_dd_pct")}}
                     for k in hs}
                 for h in ("design", "test", "full")}
        blocks.append({"id": lesson["id"], "evidence_history": {
            "label": "history, outcomes already seen", "changes_status": False,
            "source": "scripts/study_crypto_sentiment.py --exploratory (research/prereg/H8a.json)",
            "measured": f"{lesson['h']}-day up-rate of BTC and ETH from the next open, tag on against the other days of the same period; "
                        "coins averaged per day; Newey-West t over days",
            "tag": lesson["tag"], "horizon_h": 24 * lesson["h"], "expect": lesson["expect"],
            "design_years": r["design"]["headline"], "2023_26": r["test"]["headline"], "full_history": r["full"]["headline"],
            "mean_return_7d_30d_pct": {h: {str(k): {**{m: r[h]["by_horizon"][str(k)]["all"].get(m, {}).get("on")
                                                       for m in ("ret", "at1", "mae")},
                                                    "worst_drawdown_single_event_pct":
                                                        r[h]["by_horizon"][str(k)]["worst_drawdown_single_event_pct"]}
                                           for k in (7, 30)} for h in ("design", "test")},
            "first_day_of_episode": first,
            "deserves_forward_test": r["verdict"]["deserves_forward_test"], "lines": r["verdict"]["lines"]}})
    return blocks


def _fmt(x, nd: int = 2) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x:.{nd}f}"


def print_h8a(res: dict) -> None:
    print(f"H8a {res['kind']} ({res['label']}), BTC + ETH, data to {res['data_end']}")
    print(f"{'lesson':24} {'half':7} {'days on':>8} {'episodes':>8} {'up on %':>8} {'up off %':>8} {'diff pp':>8} {'t':>6}")
    for lid, r in res["lessons"].items():
        for half in ("design", "test", "full"):
            if half not in r:
                continue
            h = r[half]["headline"]
            print(f"{lid:24} {half:7} {h['days_on']:>8} {h['episodes']:>8} {_fmt(h['up_on_pct'], 1):>8} {_fmt(h['up_off_pct'], 1):>8} "
                  f"{_fmt(h['diff_pp'], 1):>8} {_fmt(h['t']):>6}")
        if "verdict" in r:
            v = r["verdict"]
            failed = [k for k, x in v["lines"].items() if not (x["met"] if isinstance(x, dict) else x)]
            print(f"  -> deserves a forward test: {v['deserves_forward_test']}" + (f" (fails: {', '.join(failed)})" if failed else ""))
    for half in ("design", "test"):
        if half not in res["addons"]:
            continue
        a = res["addons"][half]
        x1 = a["costs_x1"]
        print(f"add-ons {half} {a['start']}..{a['end']}: after tax % of start (pre-tax, max DD, Sharpe)")
        for name in ("hold_btc", "plain", *[x["id"] for x in ADDONS]):
            s = x1[name]
            extra = ""
            if name in a:
                x = a[name]
                extra = (f"  vs plain {_fmt(x['after_tax_excess_vs_plain_pp_x1'], 1)}pp"
                         f" (costs x2 {_fmt(x['after_tax_excess_vs_plain_pp_x2'], 1)}pp)")
            print(f"  {name:34} {_fmt(s['after_tax_return_pct'], 1):>8} ({_fmt(s['pre_tax_return_pct'], 1)}, {_fmt(s['max_dd_pct'], 1)}, "
                  f"{_fmt(s['sharpe'])}){extra}")
    for aid, ln in res["addons"].get("lines", {}).items():
        print(f"  {aid}: add-on line met: {ln['addon_line_met']}")
    st = res.get("reproduction_of_brief", {}).get("status")
    if st:
        print("brief's figures: reproduced " + ", ".join(k for k, v in st.items() if v["reproduced"]))
        print("  not reproduced (keep the plan's label): " + (", ".join(k for k, v in st.items() if not v["reproduced"]) or "none"))


def _rel(f: Path) -> str:
    try:
        return str(f.relative_to(ROOT))
    except ValueError:
        return str(f)


def write_results(res: dict, name: str) -> Path:
    RESULTS.mkdir(parents=True, exist_ok=True)
    f = RESULTS / name
    f.write_text(json.dumps(res, indent=1) + "\n")
    return f


# ---------------------------------------------------------------------------------------------------- H8b

def f_minus_line(rates: pd.Series, start: str = SOURCE_START["funding"], end: str = DESIGN_END, n: int = N7,
                 hours: tuple[int, ...] | None = (0,)) -> dict:
    """The 90th percentile of the n-settlement average over windows lying wholly inside [start, end] (UTC days),
    taken at the settlements whose hour is in `hours` (None: every settlement)."""
    t = pd.Series(rates.index, index=rates.index)
    roll = settled_avg(rates, n)
    first = t.shift(n - 1)
    ok = roll.notna() & (first >= pd.Timestamp(start)) & (t < pd.Timestamp(end) + pd.Timedelta(days=1))
    if hours is not None:
        ok &= pd.Series(rates.index.hour, index=rates.index).isin(hours)
    v = roll[ok]
    return {"p90": float(np.quantile(v.to_numpy(), 0.9)), "n_values": int(len(v)), "first_window_end": str(v.index[0]),
            "last_window_end": str(v.index[-1]), "median": float(v.median()), "max": float(v.max()),
            "share_above_p90": float((v > np.quantile(v.to_numpy(), 0.9)).mean())}


def fetch_okx(coin: str, since: str, session=None, max_pages: int = 30) -> pd.DataFrame:
    """OKX settled funding for <coin>-USDT-SWAP, newest first, paging back with `after` until `since`."""
    import requests

    s = session or requests.Session()
    since_ms = int(pd.Timestamp(since, tz="UTC").timestamp() * 1000)
    rows, after = [], None
    for _ in range(max_pages):
        params = {"instId": f"{coin}-USDT-SWAP", "limit": 100}
        if after:
            params["after"] = after
        js = s.get(OKX_URL, params=params, timeout=30).json()
        if str(js.get("code")) != "0":
            raise RuntimeError(f"OKX error: {str(js)[:200]}")
        page = js.get("data") or []
        if not page:
            break
        rows += page
        oldest = min(int(r["fundingTime"]) for r in page)
        if oldest <= since_ms:
            break
        after = str(oldest)
    return okx_frame(rows)


def okx_frame(rows: list[dict]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=["funding", "realized"])
    t = pd.to_datetime([int(r["fundingTime"]) for r in rows], unit="ms")
    df = pd.DataFrame({"funding": [float(r["fundingRate"]) for r in rows],
                       "realized": [float(r["realizedRate"]) if r.get("realizedRate") not in (None, "") else np.nan for r in rows]},
                      index=pd.DatetimeIndex(t))
    return df[~df.index.duplicated()].sort_index()


def compare_funding(binance: pd.Series, okx: pd.Series, start: str, end: str, line: float | None = None) -> dict:
    """How closely OKX's settled funding matches Binance's at the same settlements, and whether the 3-day and
    7-day averages (taken at the 00:00 UTC settlement, as the daily run sees them) give the same tags."""
    lo, hi = pd.Timestamp(start), pd.Timestamp(end) + pd.Timedelta(days=1)
    b = binance[(binance.index >= lo) & (binance.index < hi)]
    o = okx.dropna()
    o = o[(o.index >= lo) & (o.index < hi)]
    j = pd.concat({"binance": b, "okx": o}, axis=1).dropna()
    diff = j["okx"] - j["binance"]
    out: dict = {"settlements_binance": len(b), "settlements_okx": len(o), "matched": len(j),
                 "only_binance": [str(x) for x in b.index.difference(o.index)],
                 "only_okx": [str(x) for x in o.index.difference(b.index)]}
    if len(j) < 3:
        return out
    out.update({"mean_binance_pct": 100 * float(j["binance"].mean()), "mean_okx_pct": 100 * float(j["okx"].mean()),
                "corr": float(j["binance"].corr(j["okx"])), "mean_diff_okx_minus_binance_pct": 100 * float(diff.mean()),
                "mean_abs_diff_pct": 100 * float(diff.abs().mean()), "max_abs_diff_pct": 100 * float(diff.abs().max()),
                "same_sign_share": float((np.sign(j["okx"]) == np.sign(j["binance"])).mean())})
    for n, name in ((N3, "avg3d_at_00utc"), (N7, "avg7d_at_00utc")):
        jj = pd.concat({"binance": settled_avg(binance, n), "okx": settled_avg(okx.dropna(), n)}, axis=1)
        jj = jj[(jj.index >= lo) & (jj.index < hi) & (jj.index.hour == 0)].dropna()
        if len(jj) < 3:
            out[name] = {"n": len(jj)}
            continue
        dd = jj["okx"] - jj["binance"]
        res = {"n": len(jj), "corr": float(jj["binance"].corr(jj["okx"])), "mean_diff_pct": 100 * float(dd.mean()),
               "max_abs_diff_pct": 100 * float(dd.abs().max())}
        if n == N3:
            for tag, fn in (("funding_negative", lambda x: x < 0), ("funding_high", lambda x: x > FUND_HIGH)):
                bb, oo = fn(jj["binance"]), fn(jj["okx"])
                res[tag] = {"days_binance": int(bb.sum()), "days_okx": int(oo.sum()), "agree_share": float((bb == oo).mean())}
        if n == N7 and line is not None:
            bb, oo = jj["binance"] > line, jj["okx"] > line
            res["above_f_minus_line"] = {"days_binance": int(bb.sum()), "days_okx": int(oo.sum()), "agree_share": float((bb == oo).mean())}
        out[name] = res
    return out


def h8b_prep() -> dict:
    funding = {c: load_funding(c, END) for c in COINS}
    lines = {}
    for c in COINS:
        main = f_minus_line(funding[c])
        lines[c] = {"line_rate": main["p90"], "line_pct_per_8h": 100 * main["p90"], "method": main,
                    "sensitivity": {"every_settlement": f_minus_line(funding[c], hours=None),
                                    "windows_ending_16utc": f_minus_line(funding[c], hours=(16,))}}
    since = (pd.Timestamp(OKX_CHECK[0]) - pd.Timedelta(days=10)).strftime("%Y-%m-%d")
    checks, raw = {}, {}
    for c in COINS:
        ok = fetch_okx(c, since)
        checks[c] = {col: compare_funding(funding[c], ok[col], *OKX_CHECK, lines[c]["line_rate"]) for col in ("realized", "funding")}
        keep = ok[(ok.index >= pd.Timestamp(since)) & (ok.index < pd.Timestamp(OKX_CHECK[1]) + pd.Timedelta(days=1))]
        b = funding[c][(funding[c].index >= pd.Timestamp(since))]
        raw[c] = [{"time": str(t), "binance": b.get(t), "okx_funding": r["funding"], "okx_realized": r["realized"]}
                  for t, r in keep.iterrows()]
        checks[c]["okx_history_starts"] = str(ok.index[0]) if len(ok) else None
    return _clean({"test": H8B, "run_at": datetime.now(UTC).isoformat(timespec="seconds"), "f_minus_line": lines,
                   "okx_vs_binance": {"period": list(OKX_CHECK), "by_coin": checks}, "rows": raw})


def max_dd(s: pd.Series) -> float:
    return float((s / s.cummax() - 1).min())


def arms_verdict(values: pd.DataFrame, arm: str, n_trials: int) -> dict:
    """The H8b verdict for one arm. `values`: daily after-tax value (as if everything were sold that day) of
    'control' (Without LLM), 'hold' (Just hold BTC) and the arm, forward data only, indexed by date."""
    v = values[["control", "hold", arm]].dropna()
    if v.empty:
        return {"verdict": "no forward data yet"}
    start = v.index[0]
    cps = []
    k = 0
    while start + pd.DateOffset(months=12 + 6 * k) <= v.index[-1]:
        cps.append(start + pd.DateOffset(months=12 + 6 * k))
        k += 1
    if not cps:
        return {"verdict": "no verdict yet: the first checkpoint is 12 months after the start", "start": str(start.date()),
                "days": len(v)}
    cp = cps[-1]
    months = 12 + 6 * (len(cps) - 1)
    w = v.loc[:cp]
    ret = w.iloc[-1] / w.iloc[0] - 1
    dd = {c: max_dd(w[c]) for c in w}
    r = w.pct_change().dropna()
    diff = (r[arm] - r["control"]).to_numpy()
    t = nw_tstat(diff, nw_lags(1, len(diff)))
    dsr = deflated_sharpe(pd.Series(np.r_[1.0, np.cumprod(1 + diff)]), n_trials).get("deflated_sharpe")
    beats_control, beats_hold = bool(ret[arm] > ret["control"]), bool(ret[arm] > ret["hold"])
    dd_ok = bool(dd[arm] >= dd["control"])
    keep = beats_control and beats_hold and dd_ok
    adopt = keep and months > 12 and math.isfinite(t) and t >= 3.0 and dsr is not None and dsr >= 0.95
    verdict = ("adopt: candidate for a journal/changes.md entry (paper evidence; no real money)" if adopt
               else "keep running" if keep else "stop")
    return {"verdict": verdict, "checkpoint": str(cp.date()), "months": months, "after_tax_return_pct": {c: 100 * float(ret[c]) for c in w},
            "max_dd_pct": {c: 100 * dd[c] for c in w}, "beats_control": beats_control, "beats_hold": beats_hold,
            "dd_no_deeper_than_control": dd_ok, "nw_t_daily_diff_vs_control": t, "deflated_sharpe_diff": dsr, "n_trials": n_trials}


def run_arms(spec: dict) -> int:
    f = PAPER / "after_tax.csv"
    if not f.exists():
        print("H8b: the arms are not running yet. indtrader/crypto.py has no F+ / F- accounts and no "
              f"{_rel(f)} (date, control, hold, fplus, fminus: after-tax values), so there is no forward data.")
        return 0
    v = pd.read_csv(f, parse_dates=["date"]).set_index("date").sort_index()
    v = v[v.index >= pd.Timestamp(spec["_registered_at"][:10])]
    n = prereg.trial_count("crypto")
    for arm in ("fplus", "fminus"):
        if arm not in v:
            print(f"{arm}: no column in {f.name}")
            continue
        res = arms_verdict(v, arm, n)
        print(f"{arm}: {json.dumps(_clean(res))}")
        if res.get("checkpoint"):
            prereg.log_trial(H8B, arm, "forward", "after_tax_excess_vs_control_pp",
                             res["after_tax_return_pct"][arm] - res["after_tax_return_pct"]["control"],
                             t=res["nw_t_daily_diff_vs_control"], n=len(v), kind="test", note=res["verdict"])
    return 0


# ---------------------------------------------------------------------------------------------------- CLI

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--period", choices=("design", "test"))
    ap.add_argument("--exploratory", action="store_true", help="H8a over the full history (outcomes already seen)")
    ap.add_argument("--h8b-prep", action="store_true", help="F- line and the OKX-against-Binance check")
    ap.add_argument("--arms", action="store_true", help="H8b verdict on forward data")
    a = ap.parse_args(argv)
    if a.period == "test":
        prereg.require_committed(H8A)              # first: refuse unless the pre-registration is committed
    if a.arms:
        spec = prereg.require_committed(H8B)
        return run_arms(spec)
    if a.h8b_prep:
        res = h8b_prep()
        f = write_results(res, "H8b_prep.json")
        for c, ln in res["f_minus_line"].items():
            chk = res["okx_vs_binance"]["by_coin"][c]["realized"]
            print(f"{c}: F- line {ln['line_pct_per_8h']:.5f}% per 8h ({ln['method']['n_values']} daily 7-day averages, 2020-22); "
                  f"OKX vs Binance Oct 2026: {chk.get('matched')} matched, corr {_fmt(chk.get('corr'), 3)}, "
                  f"mean |diff| {_fmt(chk.get('mean_abs_diff_pct'), 5)}%")
        print(f"wrote {_rel(f)}")
        return 0
    if a.exploratory:
        prereg.load(H8A)
        res = run_h8a(("design", "test", "full"), "exploratory")
        f = write_results(res, "H8a.json")
    elif a.period:
        prereg.load(H8A)
        res = run_h8a((a.period,), a.period)
        f = write_results(res, f"H8a_{a.period}.json")
    else:
        ap.print_help()
        return 2
    print_h8a(res)
    print(f"wrote {_rel(f)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
