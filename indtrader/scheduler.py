"""Daily IST scheduler: analysis -> execution -> monitoring -> end of day.

- Each step has its own error handling, so a failing step never stops stop-loss
  monitoring.
- Analysis (minutes per stock) runs in a background thread; monitoring keeps
  running meanwhile, and execution waits for it.
- Completed steps are saved to <data_dir>/scheduler.json, so a restart does not
  repeat the day's execution.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from datetime import datetime

from indtrader.market import is_market_open, is_trading_day
from indtrader.notify import notify

log = logging.getLogger(__name__)

MAX_ATTEMPTS = 3


class Scheduler:
    def __init__(self, engine, settings):
        self.eng = engine
        self.s = settings
        self.file = settings.path("scheduler.json")
        self.done: dict[str, str] = json.loads(self.file.read_text()) if self.file.exists() else {}
        self.attempts: dict[str, int] = {}
        self.analysis_thread: threading.Thread | None = None
        self.last_monitor = 0.0

    def _mark(self, key: str, day: str) -> None:
        self.done[key] = day
        self.file.write_text(json.dumps(self.done, indent=2))

    def _due(self, key: str, hhmm: str, now: datetime) -> bool:
        return now.strftime("%H:%M") >= hhmm and self.done.get(key) != now.date().isoformat()

    def _attempt(self, key: str, day: str, fn) -> None:
        """Run a step; after MAX_ATTEMPTS failures give up for the day."""
        try:
            fn()
            self._mark(key, day)
        except Exception as exc:
            n = self.attempts.get(f"{key}:{day}", 0) + 1
            self.attempts[f"{key}:{day}"] = n
            log.exception("%s failed (attempt %d)", key, n)
            notify(f"[indtrader] ERROR in {key} (attempt {n}/{MAX_ATTEMPTS}): {exc}")
            if n >= MAX_ATTEMPTS:
                notify(f"[indtrader] giving up on {key} for {day}")
                self._mark(key, day)

    def _run_analysis(self, today) -> None:
        self._attempt("analysis", today.isoformat(), lambda: self.eng.analyze_universe(today))

    def tick(self, now: datetime) -> None:
        today = now.date()
        day = today.isoformat()
        sch = self.s.schedule
        if not is_trading_day(today, self.s.holidays):
            return
        analysing = self.analysis_thread is not None and self.analysis_thread.is_alive()
        market_open = is_market_open(now, self.s.holidays)

        if self._due("analysis", sch.analysis_time, now) and not analysing:
            self.analysis_thread = threading.Thread(target=self._run_analysis, args=(today,), daemon=True, name="analysis")
            self.analysis_thread.start()
            analysing = True

        # execution waits for today's analysis (finished or given up)
        if (self._due("execution", sch.execution_time, now) and market_open and not analysing
                and self.done.get("analysis") == day):
            self._attempt("execution", day, lambda: self.eng.rebalance(today))

        if market_open and time.monotonic() - self.last_monitor >= sch.monitor_interval_min * 60:
            self.last_monitor = time.monotonic()
            try:
                self.eng.monitor()
            except Exception as exc:
                log.exception("monitor failed")
                notify(f"[indtrader] ERROR in monitor: {exc}")

        if self._due("eod", sch.eod_time, now):
            self._attempt("eod", day, self._eod)

    def _eod(self) -> None:
        self.eng.square_off_intraday()
        st = self.eng.status()
        notify("[indtrader] EOD: bot equity Rs {:,.0f} (cash {:,.0f}, realised {:+,.0f}); positions: {}".format(
            st["bot_equity"], st["bot_cash"], st["realized_pnl"],
            ", ".join(f"{p['symbol']} {p['qty']} ({p['unrealized']:+,.0f})" for p in st["positions"]) or "none"))

    def run_forever(self, clock, poll_s: float = 30) -> None:
        notify(f"[indtrader] scheduler started: broker={self.s.broker.name} dry_run={self.s.dry_run} "
               f"universe={self.s.universe}")
        while True:
            self.tick(clock())
            time.sleep(poll_s)
