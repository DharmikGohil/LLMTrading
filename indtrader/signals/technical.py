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
