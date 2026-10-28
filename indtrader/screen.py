"""Momentum + low-volatility + trend screen over an NSE index (the factor core).

Research consensus (see README): in India the best-evidenced edge for a retail
swing trader is rule-based momentum, smoothed with a low-volatility filter and
gated by trend/regime. The LLM then reviews only these candidates.

Score (similar in spirit to the NSE Momentum 30 indices): the average z-score
of 6-month and 12-month returns, both skipping the most recent month (short-term
reversal), each divided by annualised volatility. Filters: close above its
200-day average, not in the most volatile 20%, and a minimum median daily traded
value.

Caveat: backtests use *today's* index members (survivorship bias), so they
flatter the screen. Judge it on forward/paper results.
"""

from __future__ import annotations

import io
import logging
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from indtrader.signals.technical import trend_template

log = logging.getLogger(__name__)

INDEX_CSV = {
    "nifty50": "ind_nifty50list.csv",
    "nifty100": "ind_nifty100list.csv",
    "nifty200": "ind_nifty200list.csv",
    "nifty500": "ind_nifty500list.csv",
}
_URLS = ("https://archives.nseindia.com/content/indices/{f}", "https://www.niftyindices.com/IndexConstituent/{f}")


def index_members(index: str, cache_dir: Path) -> list[str]:
    """Current constituents (NSE symbols). Cached on disk; the cache is used if NSE is unreachable."""
    import requests

    fname = INDEX_CSV[index]
    cache = cache_dir / fname
    for url in _URLS:
        try:
            r = requests.get(url.format(f=fname), timeout=20, headers={"User-Agent": "Mozilla/5.0"})
            r.raise_for_status()
            df = pd.read_csv(io.StringIO(r.text))
            if "Symbol" in df.columns and len(df) > 10:
                cache.parent.mkdir(parents=True, exist_ok=True)
                cache.write_text(r.text)
                return [s.strip().upper() for s in df["Symbol"]]
        except Exception as exc:
            log.warning("index list from %s failed: %s", url, exc)
    if cache.exists():
        log.warning("using cached %s constituents", index)
        return [s.strip().upper() for s in pd.read_csv(cache)["Symbol"]]
    raise RuntimeError(f"could not get {index} constituents")


def industries(index: str, cache_dir: Path) -> dict[str, str]:
    """symbol -> NSE industry, from the cached constituent file (empty if not cached yet)."""
    f = cache_dir / INDEX_CSV[index]
    if not f.exists():
        return {}
    df = pd.read_csv(f)
    return {str(r.Symbol).strip().upper(): str(r.Industry).strip() for r in df.itertuples()} if "Industry" in df else {}


def download_closes(symbols: list[str], start: date, end: date) -> dict[str, pd.DataFrame]:
    """Daily OHLCV for many NSE symbols in one batched Yahoo request."""
    import yfinance as yf

    tickers = [f"{s}.NS" for s in symbols]
    raw = yf.download(tickers, start=str(start), end=str(end + timedelta(days=1)), auto_adjust=True,
                      progress=False, group_by="ticker", threads=True)
    out = {}
    for s, t in zip(symbols, tickers, strict=True):
        try:
            df = raw[t].dropna(subset=["Close"])
        except KeyError:
            continue
        if len(df):
            df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
            out[s] = df[["Open", "High", "Low", "Close", "Volume"]]
    return out


def score_universe(histories: dict[str, pd.DataFrame], as_of: date | None = None, *, min_traded_value_cr: float = 20.0,
                   vol_exclude_pct: float = 0.2, skip_days: int = 21, trend_template_required: bool = False) -> pd.DataFrame:
    """Rank stocks; only data up to `as_of` is used. Returns a table sorted by score (eligible first)."""
    rows = []
    for sym, df in histories.items():
        if as_of is not None:
            df = df.loc[: pd.Timestamp(as_of)]
        if len(df) < 260:
            continue
        close = df["Close"]
        rets = np.log(close).diff().dropna()
        vol = float(rets.iloc[-250:].std() * np.sqrt(252))
        if not np.isfinite(vol) or vol <= 0:
            continue
        ref = close.iloc[-1 - skip_days]
        r6 = float(ref / close.iloc[-1 - skip_days - 126] - 1)
        r12 = float(ref / close.iloc[-1 - skip_days - 231] - 1) if len(close) > skip_days + 231 else np.nan
        traded_cr = float((close * df["Volume"]).iloc[-60:].median() / 1e7)
        sma200 = float(close.iloc[-200:].mean())
        tt = trend_template(close)
        rows.append({"tt_passed": sum(tt.values()) if tt else 0,
                     "symbol": sym, "close": round(float(close.iloc[-1]), 2), "ret6m_pct": round(100 * r6, 1),
                     "ret12m_pct": round(100 * r12, 1) if np.isfinite(r12) else None, "vol_pct": round(100 * vol, 1),
                     "ra6": r6 / vol, "ra12": r12 / vol if np.isfinite(r12) else np.nan,
                     "above_200dma": bool(close.iloc[-1] > sma200), "traded_value_cr": round(traded_cr, 1)})
    if not rows:
        return pd.DataFrame()
    t = pd.DataFrame(rows)

    def z(x):
        return (x - x.mean()) / x.std(ddof=0) if x.std(ddof=0) > 0 else x * 0

    t["score"] = pd.concat([z(t["ra6"]), z(t["ra12"].fillna(t["ra6"]))], axis=1).mean(axis=1).round(3)
    vol_cut = t["vol_pct"].quantile(1 - vol_exclude_pct)
    t["eligible"] = t["above_200dma"] & (t["vol_pct"] <= vol_cut) & (t["traded_value_cr"] >= min_traded_value_cr)
    if trend_template_required:   # SEPA: all 7 price conditions + RS (score) in the top 30%
        t["eligible"] &= (t["tt_passed"] == 7) & (t["score"].rank(pct=True) >= 0.70)
    t = t.drop(columns=["ra6", "ra12"]).sort_values(["eligible", "score"], ascending=[False, False]).reset_index(drop=True)
    t["rank"] = range(1, len(t) + 1)
    return t


def momentum_rating(table: pd.DataFrame, symbol: str, top_n: int) -> str:
    """Factor-only rating: Buy inside the top N eligible names, Hold down to 2N
    (hysteresis cuts turnover), Underweight below that, Sell when ineligible."""
    row = table.loc[table["symbol"] == symbol]
    if row.empty:
        return "Hold"
    r = row.iloc[0]
    if not r["eligible"]:
        return "Sell"
    if r["rank"] <= top_n:
        return "Buy"
    return "Hold" if r["rank"] <= 2 * top_n else "Underweight"
