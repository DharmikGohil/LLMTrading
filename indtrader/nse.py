"""NSE public data the bot uses for safety checks: surveillance lists (ASM/GSM),
the board-meeting/results calendar, corporate actions and trade-for-trade
series. Polite access: browser user-agent, ~1 request/second, cached per day
under <data_dir>/nse/. Every function fails open with a warning (returns empty),
so an NSE outage never stops trading or stop-loss monitoring.
"""

from __future__ import annotations

import io
import json
import logging
import re
import time
from datetime import date, datetime
from pathlib import Path

log = logging.getLogger(__name__)

BASE = "https://www.nseindia.com/api/"
ARCHIVE = "https://nsearchives.nseindia.com/content/"
_HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36",
            "Accept": "application/json,text/csv,*/*", "Accept-Language": "en-US,en;q=0.9"}
_last_call = [0.0]


def _get(url: str) -> str:
    import requests

    wait = 1.0 - (time.monotonic() - _last_call[0])
    if wait > 0:
        time.sleep(wait)
    _last_call[0] = time.monotonic()
    r = requests.get(url, headers=_HEADERS, timeout=20)
    r.raise_for_status()
    return r.text


class NSEData:
    def __init__(self, cache_dir: Path, today: date | None = None):
        self.dir = cache_dir
        self.today = today or date.today()

    def _cached(self, name: str, url: str) -> str | None:
        f = self.dir / self.today.isoformat() / name
        if f.exists():
            return f.read_text(encoding="utf-8")
        try:
            text = _get(url)
        except Exception as exc:
            log.warning("NSE %s unavailable: %s", name, exc)
            return None
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8")
        return text

    def surveillance(self) -> dict[str, str]:
        """symbol -> reason, for stocks under ASM / GSM (100% margin, trade-for-trade, tight bands)."""
        out: dict[str, str] = {}
        if txt := self._cached("asm.json", BASE + "reportASM"):
            try:
                data = json.loads(txt)
                for part in ("longterm", "shortterm"):
                    for row in (data.get(part) or {}).get("data", []):
                        out[row["symbol"]] = row.get("survDesc") or f"ASM {part}"
            except (ValueError, KeyError, TypeError) as exc:
                log.warning("could not parse ASM list: %s", exc)
        if txt := self._cached("gsm.json", BASE + "reportGSM"):
            try:
                for row in json.loads(txt):
                    out[row["symbol"]] = row.get("survDesc") or "GSM"
            except (ValueError, KeyError, TypeError) as exc:
                log.warning("could not parse GSM list: %s", exc)
        return out

    def series(self) -> dict[str, tuple[str, str]]:
        """symbol -> (series, price band %) from sec_list.csv. Series other than EQ (e.g. BE) is trade-for-trade."""
        txt = self._cached("sec_list.csv", ARCHIVE + "equities/sec_list.csv")
        if not txt:
            return {}
        import pandas as pd

        try:
            df = pd.read_csv(io.StringIO(txt))
            return {str(r.Symbol).strip(): (str(r.Series).strip(), str(r.Band).strip()) for r in df.itertuples()}
        except Exception as exc:
            log.warning("could not parse sec_list.csv: %s", exc)
            return {}

    def results_dates(self) -> dict[str, list[date]]:
        """symbol -> upcoming board meetings that consider financial results."""
        txt = self._cached("events.json", BASE + "event-calendar")
        out: dict[str, list[date]] = {}
        if not txt:
            return out
        try:
            for row in json.loads(txt):
                purpose = f"{row.get('purpose', '')} {row.get('bm_desc', '')}".lower()
                if "result" not in purpose:
                    continue
                d = datetime.strptime(row["date"], "%d-%b-%Y").date()
                out.setdefault(row["symbol"], []).append(d)
        except (ValueError, KeyError, TypeError) as exc:
            log.warning("could not parse event calendar: %s", exc)
        return out

    def corporate_actions(self, start: date, end: date) -> list[dict]:
        url = (BASE + "corporates-corporateActions?index=equities"
               f"&from_date={start:%d-%m-%Y}&to_date={end:%d-%m-%Y}")
        txt = self._cached(f"ca_{start}_{end}.json", url)
        try:
            return json.loads(txt) if txt else []
        except ValueError:
            return []

    def announcements(self, symbol: str, limit: int = 15) -> list[dict]:
        """Latest exchange filings for a symbol (primary-source news)."""
        txt = self._cached(f"ann_{symbol}.json", BASE + f"corporate-announcements?index=equities&symbol={symbol}")
        try:
            rows = json.loads(txt) if txt else []
        except ValueError:
            return []
        return [{"time": r.get("an_dt"), "category": r.get("desc"), "text": (r.get("attchmntText") or "")[:400],
                 "pdf": r.get("attchmntFile")} for r in rows[:limit]]


class NullNSE:
    """No-op stand-in (nse_checks: false, tests)."""

    def surveillance(self):
        return {}

    def series(self):
        return {}

    def results_dates(self):
        return {}

    def corporate_actions(self, start, end):
        return []

    def announcements(self, symbol, limit=15):
        return []


_SPLIT = re.compile(r"(?:split|sub-?division).*?r[se]\.?\s*([\d.]+)\D+?to\s*r[se]\.?\s*([\d.]+)", re.IGNORECASE)
_BONUS = re.compile(r"bonus\s*(\d+)\s*:\s*(\d+)", re.IGNORECASE)


def adjustment_factor(subject: str) -> float | None:
    """Shares multiply by this factor on the ex-date (prices divide by it).
    'Face Value Split (Sub-Division) - From Rs 10/- Per Share To Rs 2/- Per Share' -> 5.0
    'Bonus 1:1' (1 new for 1 held) -> 2.0. Dividends and others -> None."""
    if m := _SPLIT.search(subject or ""):
        old, new = float(m.group(1)), float(m.group(2))
        return old / new if new > 0 and old > new else None
    if m := _BONUS.search(subject or ""):
        new, held = int(m.group(1)), int(m.group(2))
        return (held + new) / held if held > 0 and new > 0 else None
    return None
