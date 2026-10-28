"""Deterministic indicators used to confirm/size LLM signals."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    rs = gain / loss.replace(0, float("nan"))
    return (100 - 100 / (1 + rs)).fillna(100.0)


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    prev_close = df["Close"].shift(1)
    tr = pd.concat([
        df["High"] - df["Low"],
        (df["High"] - prev_close).abs(),
        (df["Low"] - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


@dataclass
class TechnicalSnapshot:
    close: float
    ema_trend: float
    rsi: float
    atr: float

    @property
    def uptrend(self) -> bool:
        return self.close > self.ema_trend


def snapshot(df: pd.DataFrame, trend_ema: int = 50, atr_period: int = 14) -> TechnicalSnapshot:
    if len(df) < max(trend_ema, atr_period) + 5:
        raise ValueError(f"need at least {max(trend_ema, atr_period) + 5} bars, got {len(df)}")
    close = df["Close"]
    return TechnicalSnapshot(
        close=float(close.iloc[-1]),
        ema_trend=float(ema(close, trend_ema).iloc[-1]),
        rsi=float(rsi(close).iloc[-1]),
        atr=float(atr(df, atr_period).iloc[-1]),
    )


def is_bear_market(index_close: pd.Series, sma: int = 200) -> bool:
    """Index below its `sma`-day simple moving average (False when history is too short)."""
    if len(index_close) < sma:
        return False
    return bool(index_close.iloc[-1] < index_close.iloc[-sma:].mean())


def trend_template(close: pd.Series) -> dict[str, bool]:
    """Mark Minervini's SEPA trend template, conditions 1-7 (condition 8, relative
    strength, is the screen's momentum rank). Needs ~1 year of closes.
    Adapted from himself65/finance-skills `sepa-strategy` (MIT)."""
    if len(close) < 230:
        return {}
    c = float(close.iloc[-1])
    ma50, ma150, ma200 = (float(close.iloc[-n:].mean()) for n in (50, 150, 200))
    ma200_month_ago = float(close.iloc[-221:-21].mean())
    window = close.iloc[-250:]
    low, high = float(window.min()), float(window.max())
    return {
        "price_above_150_200": c > ma150 and c > ma200,
        "ma150_above_ma200": ma150 > ma200,
        "ma200_rising_1m": ma200 > ma200_month_ago,
        "ma50_above_150_200": ma50 > ma150 and ma50 > ma200,
        "price_above_ma50": c > ma50,
        "30pct_above_52w_low": c >= 1.30 * low,
        "within_25pct_of_52w_high": c >= 0.75 * high,
    }
