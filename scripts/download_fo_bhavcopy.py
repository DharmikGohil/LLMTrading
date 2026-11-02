"""Download NSE's daily F&O bhavcopy and keep the index options needed for the options backtest.

Writes data/fo/<YYYY>.csv.gz with one row per contract per day:
    date, symbol, expiry, strike, type, close, settle, oi, volume, fut_close
for NIFTY, BANKNIFTY and FINNIFTY options expiring within 45 days, plus the near-month future's close
(`fut_close`, the underlying proxy). Old-format files are used until 5 Jul 2024, NSE's UDiFF files after.
Resumable: days already in the year file are skipped. Usage: python scripts/download_fo_bhavcopy.py 2020 2026
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

SYMBOLS = {"NIFTY", "BANKNIFTY", "FINNIFTY"}
OUT = Path(__file__).resolve().parent.parent / "data" / "fo"
UDIFF_FROM = date(2024, 7, 8)
HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
FIELDS = ["date", "symbol", "expiry", "strike", "type", "close", "settle", "oi", "volume", "fut_close"]


def url(d: date) -> str:
    if d >= UDIFF_FROM:
        return f"https://nsearchives.nseindia.com/content/fo/BhavCopy_NSE_FO_0_0_0_{d:%Y%m%d}_F_0000.csv.zip"
    mon = d.strftime("%b").upper()
    return f"https://nsearchives.nseindia.com/content/historical/DERIVATIVES/{d:%Y}/{mon}/fo{d:%d}{mon}{d:%Y}bhav.csv.zip"


def rows_for(d: date, raw: bytes) -> list[dict]:
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        text = z.read(z.namelist()[0]).decode("utf-8", "replace")
    out, futs = [], {}
    for r in csv.DictReader(io.StringIO(text)):
        if d >= UDIFF_FROM:
            sym, inst = r.get("TckrSymb", ""), r.get("FinInstrmTp", "")
            if sym not in SYMBOLS:
                continue
            exp = date.fromisoformat(r["XpryDt"])
            if inst == "IDF":
                futs.setdefault(sym, []).append((exp, float(r["ClsPric"] or 0)))
                continue
            if inst != "IDO":
                continue
            strike, typ = float(r["StrkPric"]), r["OptnTp"]
            close, settle = float(r["ClsPric"] or 0), float(r["SttlmPric"] or 0)
            oi, vol = int(float(r["OpnIntrst"] or 0)), int(float(r["TtlTradgVol"] or 0))
        else:
            sym, inst = r.get("SYMBOL", ""), r.get("INSTRUMENT", "")
            if sym not in SYMBOLS:
                continue
            exp = datetime.strptime(r["EXPIRY_DT"], "%d-%b-%Y").date()
            if inst == "FUTIDX":
                futs.setdefault(sym, []).append((exp, float(r["CLOSE"] or 0)))
                continue
            if inst != "OPTIDX":
                continue
            strike, typ = float(r["STRIKE_PR"]), r["OPTION_TYP"]
            close, settle = float(r["CLOSE"] or 0), float(r["SETTLE_PR"] or 0)
            oi, vol = int(float(r["OPEN_INT"] or 0)), int(float(r["CONTRACTS"] or 0))
        if 0 <= (exp - d).days <= 45:
            out.append({"date": d.isoformat(), "symbol": sym, "expiry": exp.isoformat(), "strike": strike, "type": typ,
                        "close": close, "settle": settle, "oi": oi, "volume": vol})
    near = {s: min(v)[1] for s, v in futs.items() if v}
    for row in out:
        row["fut_close"] = near.get(row["symbol"], "")
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
                for attempt in range(3):
                    try:
                        r = s.get(url(d), headers=HEADERS, timeout=30)
                        break
                    except requests.RequestException:
                        time.sleep(2 * (attempt + 1))
                else:
                    r = None
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
