"""Download NSE's daily F&O bhavcopy and keep the stock futures, for the open-interest build-up study.

Writes data/futstk/<YYYY>.csv.gz with one row per stock future per day:
    date, symbol, expiry, close, prev_close, oi, oi_change, volume
Old-format files are used until 5 Jul 2024, NSE's UDiFF files after (same split as download_fo_bhavcopy.py).
Resumable: days already in the year file are skipped. Usage: python scripts/download_futstk_bhavcopy.py 2023 2026
"""

from __future__ import annotations

import csv
import gzip
import io
import sys
import time
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path

import requests

OUT = Path(__file__).resolve().parent.parent / "data" / "futstk"
UDIFF_FROM = date(2024, 7, 8)
HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
FIELDS = ["date", "symbol", "expiry", "close", "prev_close", "oi", "oi_change", "volume"]


def url(d: date) -> str:
    if d >= UDIFF_FROM:
        return f"https://nsearchives.nseindia.com/content/fo/BhavCopy_NSE_FO_0_0_0_{d:%Y%m%d}_F_0000.csv.zip"
    mon = d.strftime("%b").upper()
    return f"https://nsearchives.nseindia.com/content/historical/DERIVATIVES/{d:%Y}/{mon}/fo{d:%d}{mon}{d:%Y}bhav.csv.zip"


def _f(x) -> float:
    try:
        return float(x or 0)
    except ValueError:
        return 0.0


def rows_for(d: date, raw: bytes) -> list[dict]:
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        text = z.read(z.namelist()[0]).decode("utf-8", "replace")
    out = []
    for r in csv.DictReader(io.StringIO(text)):
        if d >= UDIFF_FROM:
            if r.get("FinInstrmTp") != "STF":
                continue
            out.append({"symbol": r["TckrSymb"], "expiry": r["XpryDt"], "close": _f(r["ClsPric"]),
                        "prev_close": _f(r.get("PrvsClsgPric")), "oi": int(_f(r["OpnIntrst"])),
                        "oi_change": int(_f(r.get("ChngInOpnIntrst"))), "volume": int(_f(r["TtlTradgVol"]))})
        else:
            if r.get("INSTRUMENT") != "FUTSTK":
                continue
            out.append({"symbol": r["SYMBOL"], "expiry": datetime.strptime(r["EXPIRY_DT"], "%d-%b-%Y").date().isoformat(),
                        "close": _f(r["CLOSE"]), "prev_close": 0.0, "oi": int(_f(r["OPEN_INT"])),
                        "oi_change": int(_f(r["CHG_IN_OI"])), "volume": int(_f(r["CONTRACTS"]))})
    for row in out:
        row["date"] = d.isoformat()
    return out


def main(y0: int, y1: int) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    s = requests.Session()
    for year in range(y0, y1 + 1):
        f = OUT / f"{year}.csv.gz"
        done = set()
        if f.exists():
            with gzip.open(f, "rt") as fh:
                done = {r["date"] for r in csv.DictReader(fh)}
        d, end = date(year, 1, 1), min(date(year, 12, 31), date.today() - timedelta(days=1))
        new = 0
        while d <= end:
            if d.weekday() < 5 and d.isoformat() not in done:
                r = None
                for attempt in range(3):
                    try:
                        r = s.get(url(d), headers=HEADERS, timeout=30)
                        break
                    except requests.RequestException:
                        time.sleep(2 * (attempt + 1))
                if r is not None and r.status_code == 200 and r.content[:2] == b"PK":
                    rows = rows_for(d, r.content)
                    write_header = not f.exists()
                    with gzip.open(f, "at", newline="") as fh:
                        w = csv.DictWriter(fh, FIELDS)
                        if write_header:
                            w.writeheader()
                        w.writerows(rows)
                    new += 1
                time.sleep(0.25)
            d += timedelta(days=1)
        print(f"{year}: {new} new days", flush=True)


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]))
