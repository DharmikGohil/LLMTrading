"""Download daily Binance spot candles (USDT pairs) from Binance's public archive, data.binance.vision.

Writes data/crypto/<SYMBOL>.csv: date, open, high, low, close, volume (quote volume in USDT).
Monthly archive files up to last month, then daily files for the current month. Resumable per symbol.
Usage: python scripts/download_crypto_klines.py 2018-06 BTC ETH XRP ...
"""

from __future__ import annotations

import csv
import io
import sys
import zipfile
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import requests

OUT = Path(__file__).resolve().parent.parent / "data" / "crypto"
BASE = "https://data.binance.vision/data/spot"


def _rows(raw: bytes) -> list[list]:
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        text = z.read(z.namelist()[0]).decode()
    out = []
    for r in csv.reader(io.StringIO(text)):
        if not r or not r[0].isdigit():
            continue
        ts = int(r[0])
        ts = ts // 1000 if ts > 10**14 else ts          # archive switched to microseconds in 2025
        d = datetime.fromtimestamp(ts / 1000, tz=UTC).date()
        out.append([d.isoformat(), r[1], r[2], r[3], r[4], r[7]])
    return out


def months(start: str) -> list[str]:
    y, m = map(int, start.split("-"))
    today = date.today()
    out = []
    while (y, m) < (today.year, today.month):
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def fetch(session: requests.Session, url: str) -> bytes | None:
    r = session.get(url, timeout=30)
    return r.content if r.status_code == 200 and r.content[:2] == b"PK" else None


def main(start: str, coins: list[str]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    s = requests.Session()
    for coin in coins:
        pair = f"{coin}USDT"
        f = OUT / f"{coin}.csv"
        rows: dict[str, list] = {}
        if f.exists():
            with f.open() as fh:
                for r in csv.reader(fh):
                    if r and r[0] != "date":
                        rows[r[0]] = r
        have_months = {k[:7] for k in rows}
        for ym in months(start):
            if ym in have_months and ym != max(have_months, default=""):
                continue
            raw = fetch(s, f"{BASE}/monthly/klines/{pair}/1d/{pair}-1d-{ym}.zip")
            for r in _rows(raw) if raw else []:
                rows[r[0]] = r
        d = date.today().replace(day=1)
        while d < date.today():
            raw = fetch(s, f"{BASE}/daily/klines/{pair}/1d/{pair}-1d-{d.isoformat()}.zip")
            for r in _rows(raw) if raw else []:
                rows[r[0]] = r
            d += timedelta(days=1)
        with f.open("w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["date", "open", "high", "low", "close", "volume"])
            for k in sorted(rows):
                w.writerow(rows[k])
        print(f"{coin}: {len(rows)} days ({min(rows) if rows else '-'} to {max(rows) if rows else '-'})", flush=True)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
