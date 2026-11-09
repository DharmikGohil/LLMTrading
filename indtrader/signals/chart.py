"""Chart reading: the indicators and levels a discretionary trader looks at, computed the standard way.

What each one is for, and what the evidence says, is in docs/technical-analysis.md. In short: trend and momentum
(moving averages, 52-week highs, relative strength) carry real evidence and drive the strategy; the rest here
(MACD, Bollinger Bands, candlesticks, support/resistance) are reading aids for timing and stop placement, not
signals that make money on their own after costs.

All functions take a daily OHLCV frame with columns Open, High, Low, Close, Volume (oldest first).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from indtrader.signals.technical import atr, ema, rsi


def sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(period).mean()


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    """Gerald Appel's MACD: EMA(fast) - EMA(slow), its EMA(signal), and the histogram (difference)."""
    line = ema(close, fast) - ema(close, slow)
    sig = ema(line, signal)
    return pd.DataFrame({"macd": line, "signal": sig, "hist": line - sig})


def bollinger(close: pd.Series, period: int = 20, k: float = 2.0) -> pd.DataFrame:
    """John Bollinger's bands: SMA(period) +/- k population standard deviations; %B and bandwidth."""
    mid = close.rolling(period).mean()
    sd = close.rolling(period).std(ddof=0)
    upper, lower = mid + k * sd, mid - k * sd
    return pd.DataFrame({"mid": mid, "upper": upper, "lower": lower,
                         "pct_b": (close - lower) / (upper - lower), "bandwidth": (upper - lower) / mid})


def swing_points(df: pd.DataFrame, k: int = 5) -> tuple[list[tuple[int, float]], list[tuple[int, float]]]:
    """Fractal pivots: a swing high is the highest high of the k bars on each side; likewise swing lows."""
    hi, lo = df["High"].to_numpy(), df["Low"].to_numpy()
    highs, lows = [], []
    for i in range(k, len(df) - k):
        if hi[i] == hi[i - k: i + k + 1].max():
            highs.append((i, float(hi[i])))
        if lo[i] == lo[i - k: i + k + 1].min():
            lows.append((i, float(lo[i])))
    return highs, lows


def support_resistance(df: pd.DataFrame, lookback: int = 250, k: int = 5, tol_atr: float = 0.6,
                       max_levels: int = 4) -> dict:
    """Horizontal levels where price turned more than once.

    Swing highs and lows over `lookback` bars are clustered: points within `tol_atr` x ATR(14) of each other form one
    level (its price is their average). A level's strength is its number of touches, with recent touches counting
    more. Levels below the last close are support, above are resistance (a broken resistance becomes support, as
    traders read it). Returns the strongest `max_levels` on each side, nearest first.
    """
    d = df.iloc[-lookback:]
    if len(d) < 2 * k + 10:
        return {"support": [], "resistance": []}
    a = float(atr(d).iloc[-1])
    tol = max(tol_atr * a, 1e-9)
    highs, lows = swing_points(d, k)
    pts = sorted(highs + lows, key=lambda p: p[1])
    clusters: list[list[tuple[int, float]]] = []
    for p in pts:
        if clusters and p[1] - np.mean([q[1] for q in clusters[-1]]) <= tol:
            clusters[-1].append(p)
        else:
            clusters.append([p])
    n = len(d)
    levels = []
    for c in clusters:
        if len(c) < 2:
            continue
        price = float(np.mean([q[1] for q in c]))
        weight = sum(0.5 + 0.5 * i / n for i, _ in c)          # recent touches count up to 2x old ones
        levels.append({"price": round(price, 2), "touches": len(c), "strength": round(weight, 2),
                       "last_touch": str(d.index[max(i for i, _ in c)].date())})
    last = float(d["Close"].iloc[-1])
    sup = sorted([lv for lv in levels if lv["price"] < last], key=lambda lv: -lv["strength"])[:max_levels]
    res = sorted([lv for lv in levels if lv["price"] >= last], key=lambda lv: -lv["strength"])[:max_levels]
    for lv in sup + res:
        lv["distance_atr"] = round((lv["price"] - last) / a, 2) if a else None
    return {"support": sorted(sup, key=lambda lv: -lv["price"]), "resistance": sorted(res, key=lambda lv: lv["price"])}


def candle_patterns(df: pd.DataFrame, trend_bars: int = 10) -> list[str]:
    """Classic single and two-bar candlestick patterns on the last bar, read in context of the prior trend.

    Doji, hammer and hanging man, shooting star and inverted hammer, bullish/bearish engulfing, inside bar, and the
    outside (range expansion) bar. Context: the close `trend_bars` ago against the last close.
    """
    if len(df) < trend_bars + 2:
        return []
    o, h, lo, c = (df[col].to_numpy(dtype=float) for col in ("Open", "High", "Low", "Close"))
    i = len(df) - 1
    body, rng = abs(c[i] - o[i]), h[i] - lo[i]
    if rng <= 0:
        return []
    upper, lower = h[i] - max(o[i], c[i]), min(o[i], c[i]) - lo[i]
    falling = c[i - 1] < c[i - 1 - trend_bars]
    rising = c[i - 1] > c[i - 1 - trend_bars]
    out = []
    if body <= 0.1 * rng:
        out.append("doji")
    if lower >= 2 * body and upper <= 0.25 * rng and body > 0:
        out.append("hammer" if falling else "hanging man" if rising else "hammer-shaped")
    if upper >= 2 * body and lower <= 0.25 * rng and body > 0:
        out.append("shooting star" if rising else "inverted hammer" if falling else "inverted-hammer-shaped")
    pb_lo, pb_hi = min(o[i - 1], c[i - 1]), max(o[i - 1], c[i - 1])
    if c[i] > o[i] and c[i - 1] < o[i - 1] and o[i] <= pb_lo and c[i] >= pb_hi:
        out.append("bullish engulfing")
    if c[i] < o[i] and c[i - 1] > o[i - 1] and o[i] >= pb_hi and c[i] <= pb_lo:
        out.append("bearish engulfing")
    if h[i] < h[i - 1] and lo[i] > lo[i - 1]:
        out.append("inside bar")
    if h[i] > h[i - 1] and lo[i] < lo[i - 1]:
        out.append("outside bar")
    return out


def chart_read(df: pd.DataFrame) -> dict:
    """One block for the analyst: MACD state, Bollinger position and squeeze, levels, last candle, volume."""
    close, vol = df["Close"], df["Volume"]
    out: dict = {}
    if len(close) >= 35:
        m = macd(close)
        last, prev = m.iloc[-1], m.iloc[-2]
        crossed = next((n for n in range(1, 6) if np.sign(m["hist"].iloc[-n]) != np.sign(m["hist"].iloc[-n - 1])), None)
        out["macd"] = {"macd": round(float(last["macd"]), 2), "signal": round(float(last["signal"]), 2),
                       "hist": round(float(last["hist"]), 2), "above_signal": bool(last["macd"] > last["signal"]),
                       "above_zero": bool(last["macd"] > 0), "hist_rising": bool(last["hist"] > prev["hist"]),
                       "crossed_bars_ago": crossed}
    if len(close) >= 140:
        b = bollinger(close)
        bw = b["bandwidth"].dropna()
        out["bollinger"] = {"upper": round(float(b["upper"].iloc[-1]), 2), "lower": round(float(b["lower"].iloc[-1]), 2),
                            "pct_b": round(float(b["pct_b"].iloc[-1]), 2),
                            "bandwidth_pct": round(100 * float(bw.iloc[-1]), 2),
                            "squeeze_6m_low": bool(bw.iloc[-1] <= bw.iloc[-126:].min() * 1.05)}
    out["levels"] = support_resistance(df)
    out["candles"] = candle_patterns(df)
    if len(vol) >= 50 and float(vol.iloc[-50:].mean()) > 0:
        out["volume_vs_50d"] = round(float(vol.iloc[-1] / vol.iloc[-50:].mean()), 2)
    if len(close) >= 15:
        out["rsi14"] = round(float(rsi(close).iloc[-1]), 1)
    return out
