"""TradingAgents (TauricResearch) wrapper for Indian equities.

Runs the multi-agent graph (analysts -> bull/bear debate -> trader -> risk team
-> portfolio manager) on `<SYMBOL>.NS` and caches the decision on disk, so a
day's analysis is paid for once and the execution step can reuse it.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path

from indtrader.config import Settings
from indtrader.market import IST, yahoo_symbol

log = logging.getLogger(__name__)

RATINGS = ("Buy", "Overweight", "Hold", "Underweight", "Sell")

_NUM = r"(?:Rs\.?|INR|₹)?\s*([0-9][0-9,]*(?:\.[0-9]+)?)"
_STOP_RE = re.compile(r"\*\*Stop Loss\*\*\s*:\s*" + _NUM, re.IGNORECASE)
_ENTRY_RE = re.compile(r"\*\*Entry Price\*\*\s*:\s*" + _NUM, re.IGNORECASE)
_TARGET_RE = re.compile(r"\*\*Price Target\*\*\s*:\s*" + _NUM, re.IGNORECASE)


def _first_number(pattern: re.Pattern, text: str) -> float | None:
    m = pattern.search(text or "")
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return None


@dataclass
class LLMSignal:
    symbol: str
    as_of: str                       # analysis date (data cut-off), YYYY-MM-DD
    rating: str                      # Buy/Overweight/Hold/Underweight/Sell/REVIEW
    entry_price: float | None = None
    stop_loss: float | None = None
    price_target: float | None = None
    summary: str = ""
    confidence: float | None = None  # 0-100 when the source reports one
    source: str = "tradingagents"
    created_at: str = field(default_factory=lambda: datetime.now(IST).isoformat(timespec="seconds"))

    @property
    def tradeable(self) -> bool:
        return self.rating in RATINGS

    @classmethod
    def from_state(cls, symbol: str, as_of: str, final_state: dict, rating: str) -> LLMSignal:
        trader = final_state.get("trader_investment_plan", "") or ""
        decision = final_state.get("final_trade_decision", "") or ""
        return cls(
            symbol=symbol,
            as_of=as_of,
            rating=rating,
            entry_price=_first_number(_ENTRY_RE, trader),
            stop_loss=_first_number(_STOP_RE, trader),
            price_target=_first_number(_TARGET_RE, decision),
            summary=decision[:4000],
        )


_SCORE = {"Buy": 2, "Overweight": 1, "Hold": 0, "Underweight": -1, "Sell": -2}
_BY_SCORE = {v: k for k, v in _SCORE.items()}


def consensus(ratings: list[str]) -> tuple[str, float]:
    """Majority vote over several runs' ratings.

    Returns (rating, agreement 0-100). A direction (bullish / bearish) needs a
    strict majority of all runs, REVIEW runs included; the rating is then the
    median strength of the runs on that side, rounded toward Hold. Anything
    else is Hold (or REVIEW when no run produced a rating).
    """
    valid = [_SCORE[r] for r in ratings if r in _SCORE]
    if not valid:
        return "REVIEW", 0.0
    n = len(ratings)
    for side in (1, -1):
        votes = sorted(abs(v) for v in valid if v * side > 0)
        if len(votes) * 2 > n:
            median = votes[(len(votes) - 1) // 2]          # lower median: the more cautious strength
            return _BY_SCORE[side * median], round(100 * len(votes) / n, 1)
    holds = sum(1 for v in valid if v == 0)
    return "Hold", round(100 * holds / n, 1)


class SignalStore:
    """One JSON file per (date, symbol) under <data_dir>/signals/."""

    def __init__(self, root: Path):
        self.root = root

    def _file(self, symbol: str, as_of: str) -> Path:
        return self.root / as_of / f"{symbol.upper()}.json"

    def get(self, symbol: str, as_of: str) -> LLMSignal | None:
        f = self._file(symbol, as_of)
        if not f.exists():
            return None
        return LLMSignal(**json.loads(f.read_text(encoding="utf-8")))

    def put(self, sig: LLMSignal) -> None:
        f = self._file(sig.symbol, sig.as_of)
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(asdict(sig), indent=2), encoding="utf-8")

    def latest(self, symbol: str, on_or_before: str) -> LLMSignal | None:
        if not self.root.exists():
            return None
        for d in sorted((p.name for p in self.root.iterdir() if p.is_dir()), reverse=True):
            if d <= on_or_before and (sig := self.get(symbol, d)):
                return sig
        return None


def build_ta_config(settings: Settings) -> dict:
    from tradingagents.default_config import build_default_config

    cfg = build_default_config()
    llm = settings.llm
    for key in ("llm_provider", "deep_think_llm", "quick_think_llm", "backend_url"):
        if getattr(llm, key):
            cfg[key] = getattr(llm, key)
    cfg["max_debate_rounds"] = llm.max_debate_rounds
    cfg["max_risk_discuss_rounds"] = llm.max_risk_discuss_rounds
    cfg["output_language"] = llm.output_language
    cfg["global_news_queries"] = list(llm.global_news_queries)
    cfg["data_vendors"] = {**cfg["data_vendors"], "fundamental_data": llm.fundamental_data_vendor}
    cfg["benchmark_ticker"] = "^NSEI" if settings.exchange == "NSE" else "^BSESN"
    if llm.runs > 1:
        # a checkpoint would replay the first run instead of drawing a new sample
        cfg["checkpoint_enabled"] = False
    return cfg


class TradingAgentsAnalyzer:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.store = SignalStore(settings.path("signals", "_").parent)
        self._graph = None

    @property
    def graph(self):
        if self._graph is None:
            from tradingagents.graph.trading_graph import TradingAgentsGraph

            self._graph = TradingAgentsGraph(
                selected_analysts=tuple(self.settings.llm.analysts),
                config=build_ta_config(self.settings),
            )
        return self._graph

    def analyze(self, symbol: str, as_of: date, portfolio: dict | None = None, force: bool = False) -> LLMSignal:
        """Run (or load cached) TradingAgents decision for `symbol` using data up to `as_of`."""
        as_of_s = as_of.isoformat()
        if not force and (cached := self.store.get(symbol, as_of_s)):
            log.info("%s %s: cached rating %s", symbol, as_of_s, cached.rating)
            return cached

        ticker = yahoo_symbol(symbol, self.settings.exchange)
        ctx = None
        if portfolio is not None:
            from tradingagents.portfolio import PortfolioContext

            ctx = PortfolioContext.model_validate(portfolio)
        runs = max(1, self.settings.llm.runs)
        results = []
        for i in range(runs):
            log.info("%s %s: running TradingAgents%s (a few minutes)...", ticker, as_of_s,
                     f" [run {i + 1}/{runs}]" if runs > 1 else "")
            results.append(self.graph.propagate(ticker, as_of_s, portfolio=ctx))
        ratings = [r for _, r in results]
        rating, agreement = consensus(ratings) if runs > 1 else (ratings[0], None)
        # levels (stop / target) come from a run that agrees with the consensus
        final_state = next((st for st, r in results if r == rating), results[-1][0])
        sig = LLMSignal.from_state(symbol.upper(), as_of_s, final_state, rating)
        if runs > 1:
            sig.confidence = agreement
            sig.summary = f"Consensus of {runs} runs: {', '.join(ratings)}\n\n" + sig.summary
        self.store.put(sig)
        try:
            self.graph.save_reports(final_state, ticker)
        except Exception as exc:  # reports are a convenience, never block trading
            log.warning("could not save report for %s: %s", ticker, exc)
        log.info("%s %s: rating=%s stop=%s target=%s", symbol, as_of_s, sig.rating, sig.stop_loss, sig.price_target)
        return sig
