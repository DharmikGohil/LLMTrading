"""Fact sheet for an analyst (human or LLM): price action, technicals, relative
strength and whatever fundamentals Yahoo returns, all computed from data up to
`as_of`. Grounds the analysis in real numbers instead of memory."""

from __future__ import annotations

from datetime import date

import pandas as pd

from indtrader import data as market_data
from indtrader.market import yahoo_symbol
from indtrader.signals.technical import atr, ema, is_bear_market, rsi


def _ret(close: pd.Series, days: int) -> float | None:
    return round(100 * (close.iloc[-1] / close.iloc[-days - 1] - 1), 2) if len(close) > days else None


def _fundamentals(symbol: str, exchange: str) -> dict:
    keys = ["trailingPE", "forwardPE", "priceToBook", "returnOnEquity", "debtToEquity", "profitMargins",
            "revenueGrowth", "earningsGrowth", "dividendYield", "marketCap", "sector", "industry"]
    try:
        import yfinance as yf

        info = yf.Ticker(yahoo_symbol(symbol, exchange)).info or {}
        out = {k: info.get(k) for k in keys if info.get(k) is not None}
        return out or {"note": "Yahoo returned no fundamentals; use screener.in / company filings"}
    except Exception as exc:
        return {"note": f"fundamentals unavailable ({exc.__class__.__name__}); use screener.in / company filings"}


def build_brief(symbol: str, as_of: date, exchange: str = "NSE", index: str = "^NSEI") -> dict:
    df = market_data.recent_history(symbol, as_of, lookback_days=420, exchange=exchange)
    close, vol = df["Close"], df["Volume"]
    last = float(close.iloc[-1])
    a = float(atr(df).iloc[-1])
    brief = {
        "symbol": symbol.upper(),
        "yahoo": yahoo_symbol(symbol, exchange),
        "data_as_of": str(df.index[-1].date()),
        "close": round(last, 2),
        "returns_pct": {"1w": _ret(close, 5), "1m": _ret(close, 21), "3m": _ret(close, 63), "6m": _ret(close, 126),
                        "1y": _ret(close, 250)},
        "ema20": round(float(ema(close, 20).iloc[-1]), 2),
        "ema50": round(float(ema(close, 50).iloc[-1]), 2),
        "sma200": round(float(close.iloc[-200:].mean()), 2) if len(close) >= 200 else None,
        "rsi14": round(float(rsi(close).iloc[-1]), 1),
        "atr14": round(a, 2),
        "atr_pct": round(100 * a / last, 2),
        "high_52w": round(float(close.iloc[-250:].max()), 2),
        "low_52w": round(float(close.iloc[-250:].min()), 2),
        "pct_from_52w_high": round(100 * (last / float(close.iloc[-250:].max()) - 1), 2),
        "volume_20d_vs_100d": round(float(vol.iloc[-20:].mean() / vol.iloc[-100:].mean()), 2) if len(vol) >= 100 else None,
        "last_10_closes": [round(float(x), 2) for x in close.iloc[-10:]],
    }
    try:
        idx = market_data.recent_history(index, as_of, lookback_days=420)["Close"]
        brief["index"] = {"symbol": index, "close": round(float(idx.iloc[-1]), 2),
                          "bear_regime_below_200dma": is_bear_market(idx, 200),
                          "returns_pct": {"1m": _ret(idx, 21), "3m": _ret(idx, 63)}}
        r3, i3 = _ret(close, 63), _ret(idx, 63)
        if r3 is not None and i3 is not None:
            brief["relative_strength_3m_pct"] = round(r3 - i3, 2)
    except Exception as exc:
        brief["index"] = {"error": str(exc)}
    brief["fundamentals"] = _fundamentals(symbol, exchange)
    return brief
