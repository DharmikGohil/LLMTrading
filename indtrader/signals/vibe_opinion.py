"""Second opinion from a Vibe-Trading (HKUDS) multi-agent "investment committee".

The swarm runs in Vibe-Trading's own virtualenv via indtrader/vibe/runner.py
(subprocess), and its verdict is cached like a TradingAgents signal under
<data_dir>/signals_vibe/<date>/<SYMBOL>.json.

Look-ahead warning: Vibe-Trading's data tools always return the latest data,
so it is only honest for live/paper decisions on the most recent close, never
for backtests on past dates. analyze() refuses stale dates for that reason.
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
from datetime import date
from pathlib import Path

from indtrader.config import Settings
from indtrader.market import now_ist, previous_trading_day, yahoo_symbol
from indtrader.signals.llm_agent import LLMSignal, SignalStore

log = logging.getLogger(__name__)

PRESET_FILE = Path(__file__).resolve().parent.parent / "vibe" / "indtrader_india_committee.yaml"
RUNNER = Path(__file__).resolve().parent.parent / "vibe" / "runner.py"

_RATING_RE = re.compile(r"FINAL\s+RATING\s*[:\-]\s*\**\s*(Buy|Overweight|Hold|Underweight|Sell)\b", re.IGNORECASE)
_CONF_RE = re.compile(r"CONFIDENCE\s*[:\-]\s*\**\s*(\d{1,3})", re.IGNORECASE)


def parse_verdict(report: str) -> tuple[str, float | None]:
    """(rating, confidence) from the PM memo; REVIEW when no rating line is found."""
    ratings = _RATING_RE.findall(report or "")
    if not ratings:
        return "REVIEW", None
    rating = ratings[-1].capitalize()           # the closing line wins over quotes in the memo
    conf = _CONF_RE.findall(report or "")
    confidence = min(float(conf[-1]), 100.0) if conf else None
    return rating, confidence


class VibeTradingAnalyzer:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.cfg = settings.second_opinion
        self.store = SignalStore(settings.path("signals_vibe", "_").parent)

    def _python(self) -> str:
        return os.path.expanduser(self.cfg.vibe_python)

    def _run(self, *args: str, timeout_s: float) -> dict:
        cmd = [self._python(), str(RUNNER), "--preset-file", str(PRESET_FILE), *args]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s, env=os.environ.copy())
        except FileNotFoundError:
            return {"ok": False, "error": f"Vibe-Trading python not found: {self._python()} (run scripts/install_vibe.sh)"}
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": f"Vibe-Trading run exceeded {timeout_s:.0f}s"}
        for line in reversed(proc.stdout.strip().splitlines()):
            line = line.strip()
            if line.startswith("{"):
                try:
                    return json.loads(line)
                except json.JSONDecodeError:
                    break
        tail = (proc.stderr or proc.stdout or "").strip()[-500:]
        return {"ok": False, "error": f"runner exited {proc.returncode} without a result: {tail}"}

    def check(self) -> dict:
        """Validate the Vibe-Trading install and the preset without calling any LLM."""
        return self._run("--target", "RELIANCE.NS", "--market", "India (NSE)",
                         "--as-of", date.today().isoformat(), "--check", timeout_s=180)

    def analyze(self, symbol: str, as_of: date, force: bool = False) -> LLMSignal:
        as_of_s = as_of.isoformat()
        if not force and (cached := self.store.get(symbol, as_of_s)):
            return cached
        latest = previous_trading_day(now_ist().date(), self.settings.holidays)
        if as_of < previous_trading_day(latest, self.settings.holidays):
            raise ValueError(f"Vibe-Trading only sees today's data; refusing historical date {as_of_s} (look-ahead)")

        ticker = yahoo_symbol(symbol, self.settings.exchange)
        market = "India (NSE)" if self.settings.exchange == "NSE" else "India (BSE)"
        timeout_min = self.cfg.timeout_min
        log.info("%s %s: running Vibe-Trading committee (second opinion)...", ticker, as_of_s)
        res = self._run("--target", ticker, "--market", market, "--as-of", as_of_s,
                        "--timeout-min", str(timeout_min), timeout_s=timeout_min * 60 + 120)
        if not res.get("ok"):
            raise RuntimeError(f"Vibe-Trading failed for {symbol}: {res.get('error')}")
        rating, confidence = parse_verdict(res.get("final_report", ""))
        sig = LLMSignal(symbol=symbol.upper(), as_of=as_of_s, rating=rating, summary=res["final_report"][:4000],
                        confidence=confidence, source="vibe-trading")
        self.store.put(sig)
        log.info("%s %s: Vibe-Trading rating=%s confidence=%s", symbol, as_of_s, rating, confidence)
        return sig

