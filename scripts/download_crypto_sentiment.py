"""Download crowd-emotion history for the crypto tests (docs/test-plan.md, crypto first).

- data/crypto/fear_greed.csv: alternative.me's daily Crypto Fear & Greed index since 2018-02-01 (date, value, label)
- data/crypto/funding_<COIN>.csv: Binance USD-M perpetual funding rates (every 8 hours) since 2020-01, from the public
  data.binance.vision monthly archive (complete months only)

Usage: python scripts/download_crypto_sentiment.py [--coins BTC,ETH]
The data folder is git-ignored; this script is how to rebuild it. Paper research only.
"""

from __future__ import annotations

import argparse
import csv
import io
import zipfile
from datetime import UTC, date, datetime
from pathlib import Path

import requests

OUT = Path("data/crypto")
ARCHIVE = "https://data.binance.vision/data/futures/um"


def fear_greed(s: requests.Session) -> int:
    rows = s.get("https://api.alternative.me/fng/?limit=0&format=json", timeout=60).json()["data"]
    rows = sorted(rows, key=lambda r: int(r["timestamp"]))
    with (OUT / "fear_greed.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "value", "label"])
        for r in rows:
            w.writerow([datetime.fromtimestamp(int(r["timestamp"]), UTC).date().isoformat(), r["value"], r["value_classification"]])
    return len(rows)


def _zip_rows(content: bytes) -> list[list[str]]:
    with zipfile.ZipFile(io.BytesIO(content)) as z:
        text = z.read(z.namelist()[0]).decode()
    out = []
    for line in text.splitlines():
        parts = line.split(",")
        if parts and parts[0].isdigit():          # skip the header row when there is one
            out.append(parts)
    return out


def funding(s: requests.Session, coin: str) -> int:
    rows: dict[int, float] = {}
    m = date(2020, 1, 1)
    today = datetime.now(UTC).date()
    while (m.year, m.month) < (today.year, today.month):
        r = s.get(f"{ARCHIVE}/monthly/fundingRate/{coin}USDT/{coin}USDT-fundingRate-{m:%Y-%m}.zip", timeout=60)
        if r.status_code == 200:
            for p in _zip_rows(r.content):
                rows[int(p[0])] = float(p[2])        # calc_time (ms), funding_interval_hours, last_funding_rate
        m = date(m.year + (m.month == 12), m.month % 12 + 1, 1)
    # the current month is not in the monthly archive yet; recent funding comes from the live OKX feed in
    # indtrader/crypto_learn.py
    with (OUT / f"funding_{coin}.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["time", "rate"])
        for t in sorted(rows):
            w.writerow([datetime.fromtimestamp(t / 1000, UTC).isoformat(timespec="seconds"), rows[t]])
    return len(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--coins", default="BTC,ETH")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    s = requests.Session()
    print(f"fear_greed.csv: {fear_greed(s)} days")
    for c in a.coins.split(","):
        print(f"funding_{c}.csv: {funding(s, c.strip().upper())} rates")


if __name__ == "__main__":
    main()
