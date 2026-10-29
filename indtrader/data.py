"""Market data from Yahoo Finance (NSE `.NS` / BSE `.BO`).

Yahoo's daily bars are fine for end-of-day / swing decisions. For live
prices during market hours prefer the broker's quote API (Broker.ltp),
since Yahoo quotes can lag.
"""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from indtrader.market import yahoo_symbol


def history(symbol: str, start: date | str, end: date | str | None = None, exchange: str = "NSE") -> pd.DataFrame:
    """Daily OHLCV with columns Open, High, Low, Close, Volume, indexed by date.

    `end` is inclusive.
    """
    import yfinance as yf

    end_dt = pd.Timestamp(end or date.today()) + pd.Timedelta(days=1)
    df = yf.Ticker(yahoo_symbol(symbol, exchange)).history(
        start=str(pd.Timestamp(start).date()), end=str(end_dt.date()), auto_adjust=True, actions=False
    )
    if df.empty:
        raise ValueError(f"No data for {symbol} from Yahoo Finance")
    df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
    # Yahoo sometimes returns an empty (NaN) bar for the latest day; drop it rather than poison indicators
    return df[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"])


def recent_history(symbol: str, as_of: date, lookback_days: int = 300, exchange: str = "NSE") -> pd.DataFrame:
    return history(symbol, as_of - timedelta(days=lookback_days), as_of, exchange)


def last_price(symbol: str, exchange: str = "NSE") -> float:
    import yfinance as yf

    info = yf.Ticker(yahoo_symbol(symbol, exchange)).fast_info
    return float(info["last_price"])
