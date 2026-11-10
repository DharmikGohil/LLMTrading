"""Build the price data for Candle City, the trading-practice game at /game.

Writes web/public/game/series.json in the shape set out in web/components/game/CONTRACT.md (section 1):
daily candles for five coins (from data/crypto/<COIN>.csv, Binance spot USDT pairs) and for the Nifty 50 index
and five large NSE stocks (from yfinance, split- and dividend-adjusted, from 2012). Every series ends on END.
Prices are rounded to 4 significant digits (at least 2 decimals under 10) so the file stays under 1.2 MB.

Rebuild (from the repo root; needs pandas and yfinance and an internet connection for the NSE part):
    python scripts/download_crypto_klines.py 2018-06 BTC ETH SOL BNB XRP   # optional: refresh the coin CSVs
    python scripts/build_game_data.py
To move the cut-off date, change END below (and the "end" the game shows comes along with it).
"""

from __future__ import annotations

import csv
import json
import math
import sys
import warnings
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore", module="yfinance")   # pandas deprecation chatter from inside yfinance

ROOT = Path(__file__).resolve().parent.parent
CRYPTO_DIR = ROOT / "data" / "crypto"
OUT = ROOT / "web" / "public" / "game" / "series.json"

END = date(2026, 10, 31)          # last candle of every series (inclusive)
CRYPTO_START = date(2018, 1, 1)   # or the first row of the CSV, whichever is later (listing date)
INDIA_START = date(2012, 1, 1)
MAX_BYTES = 1_200_000             # size budget from the contract
EPOCH = date(1970, 1, 1)

# id, name, symbol, file stem. One-side cost 0.15% = exchange fee + slippage.
CRYPTO = [
    ("btc", "Bitcoin", "BTC/USDT", "BTC"),
    ("eth", "Ether", "ETH/USDT", "ETH"),
    ("sol", "Solana", "SOL/USDT", "SOL"),
    ("bnb", "BNB", "BNB/USDT", "BNB"),
    ("xrp", "XRP", "XRP/USDT", "XRP"),
]
CRYPTO_COST = 0.0015

# id, name, symbol shown in the game, yfinance ticker. One-side cost 0.12% = brokerage, taxes and slippage.
INDIA = [
    ("nifty", "Nifty 50", "NIFTY 50", "^NSEI"),
    ("reliance", "Reliance Industries", "RELIANCE", "RELIANCE.NS"),
    ("tcs", "Tata Consultancy Services", "TCS", "TCS.NS"),
    ("hdfcbank", "HDFC Bank", "HDFCBANK", "HDFCBANK.NS"),
    ("infy", "Infosys", "INFY", "INFY.NS"),
    ("icicibank", "ICICI Bank", "ICICIBANK", "ICICIBANK.NS"),
]
INDIA_COST = 0.0012

Candle = tuple[int, float, float, float, float]   # (days since 1970-01-01, open, high, low, close)


def round_price(x: float) -> float | int:
    """4 significant digits, never fewer than 2 decimals under 10; whole numbers come back as int (shorter JSON)."""
    decimals = 3 - math.floor(math.log10(x))
    if x < 10:
        decimals = max(decimals, 2)
    r = round(x, decimals)
    return int(r) if r == int(r) else r


def valid(o: float, h: float, l: float, c: float) -> bool:  # noqa: E741 (l = low, as in OHLC)
    return all(isinstance(v, float) and math.isfinite(v) and v > 0 for v in (o, h, l, c))


def clean(rows: list[tuple[date, float, float, float, float]]) -> list[Candle]:
    """Sort, de-duplicate by date, drop holiday filler rows, round, and keep high/low as the true extremes."""
    by_day: dict[date, tuple[float, float, float, float]] = {}
    for d, o, h, l, c in rows:  # noqa: E741
        if valid(o, h, l, c):
            by_day[d] = (o, h, l, c)           # a repeated date keeps the last row
    out: list[Candle] = []
    prev_close = None
    for d in sorted(by_day):
        raw = by_day[d]
        # yfinance pads some NSE holidays (e.g. election days) with a zero-range candle at the previous close.
        # Nothing traded, and a candle with no range would distort the ATR, so skip it.
        if prev_close is not None and all(v == prev_close for v in raw):
            continue
        prev_close = raw[3]
        o, h, l, c = (round_price(v) for v in raw)  # noqa: E741
        # Adjusted feeds occasionally put the open or close a hair outside the high-low range; widen the range.
        out.append(((d - EPOCH).days, o, max(o, h, l, c), min(o, h, l, c), c))
    return out


def load_crypto(stem: str) -> list[Candle]:
    path = CRYPTO_DIR / f"{stem}.csv"
    rows = []
    with path.open(newline="") as fh:
        for r in csv.DictReader(fh):
            try:
                d = date.fromisoformat(r["date"])
                o, h, l, c = (float(r[k]) for k in ("open", "high", "low", "close"))  # noqa: E741
            except (KeyError, TypeError, ValueError):
                continue                       # missing or unreadable price: drop the row
            if CRYPTO_START <= d <= END:
                rows.append((d, o, h, l, c))
    return clean(rows)


def load_india(ticker: str) -> list[Candle]:
    df = yf.download(
        ticker,
        start=INDIA_START.isoformat(),
        end=(END + timedelta(days=1)).isoformat(),   # yfinance's end is exclusive
        auto_adjust=True,
        progress=False,
        multi_level_index=False,
        threads=False,
    )
    if df is None or df.empty:
        raise RuntimeError(f"yfinance returned no rows for {ticker}")
    df = df[["Open", "High", "Low", "Close"]].apply(pd.to_numeric, errors="coerce").dropna()
    rows = []
    for ts, (o, h, l, c) in zip(df.index, df.itertuples(index=False, name=None), strict=True):  # noqa: E741
        d = ts.date()                          # NSE bars are dated by the Indian trading day; keep that date
        if INDIA_START <= d <= END:
            rows.append((d, float(o), float(h), float(l), float(c)))
    return clean(rows)


def pack(sid: str, name: str, symbol: str, market: str, district: str, cur: str, cost: float, candles: list[Candle]) -> dict:
    if len(candles) < 400:
        raise RuntimeError(f"{sid}: only {len(candles)} candles, too few for the game")
    t, o, h, l, c = (list(col) for col in zip(*candles, strict=True))  # noqa: E741
    return {"id": sid, "name": name, "symbol": symbol, "market": market, "district": district, "cur": cur,
            "cost": cost, "t": t, "o": o, "h": h, "l": l, "c": c}


def main() -> int:
    series = []
    for sid, name, symbol, stem in CRYPTO:
        series.append(pack(sid, name, symbol, "crypto", "docks", "$", CRYPTO_COST, load_crypto(stem)))
    for sid, name, symbol, ticker in INDIA:
        series.append(pack(sid, name, symbol, "india", "market", "₹", INDIA_COST, load_india(ticker)))

    # One series per line: valid JSON, compact, and a diff of a rebuild stays readable.
    head = json.dumps({"version": 1, "built": date.today().isoformat(), "end": END.isoformat()}, separators=(",", ":"))
    body = ",\n".join(json.dumps(s, separators=(",", ":"), ensure_ascii=False) for s in series)
    text = head[:-1] + ',"series":[\n' + body + "\n]}\n"
    json.loads(text)                           # fail loudly rather than ship broken JSON

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8")
    size = OUT.stat().st_size
    for s in series:
        first = (EPOCH + timedelta(days=s["t"][0])).isoformat()
        last = (EPOCH + timedelta(days=s["t"][-1])).isoformat()
        print(f"{s['id']:<10} {len(s['t']):>5} candles  {first} .. {last}")
    print(f"wrote {OUT.relative_to(ROOT)}: {size:,} bytes ({size / 1e6:.2f} MB)")
    if size > MAX_BYTES:
        print(f"warning: over the {MAX_BYTES:,}-byte budget", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
