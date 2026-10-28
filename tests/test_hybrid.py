"""Hybrid mode: momentum screen proposes, LLM can only veto; India safety blocks."""

from datetime import date

import pandas as pd
import pytest

from indtrader import data as market_data
from indtrader.brokers.paper import PaperBroker
from indtrader.engine import Engine
from indtrader.screen import momentum_rating, score_universe
from indtrader.signals.llm_agent import LLMSignal, SignalStore

D = date(2026, 10, 28)
AS_OF = "2026-10-27"


class StubNSE:
    def __init__(self):
        self.surv, self.series_, self.results, self.cas = {}, {}, {}, []

    def surveillance(self):
        return self.surv

    def series(self):
        return self.series_

    def results_dates(self):
        return self.results

    def corporate_actions(self, start, end):
        return self.cas

    def announcements(self, symbol, limit=15):
        return []


@pytest.fixture
def hybrid(settings, ohlcv, monkeypatch):
    settings.strategy.signal_mode = "hybrid"
    settings.strategy.rsi_max_entry = 100
    settings.strategy.regime_filter = False
    settings.screen.top_n = 1
    hist = {"AAA": ohlcv(300, drift=0.004, seed=1, start_date="2025-08-01"),
            "BBB": ohlcv(300, drift=0.003, seed=3, start_date="2025-08-01"),
            "CCC": ohlcv(300, drift=-0.003, seed=2, start_date="2025-08-01")}
    monkeypatch.setattr(market_data, "recent_history", lambda sym, as_of, lookback_days=300, exchange="NSE": hist[sym])
    prices = {s: float(h["Close"].iloc[-1]) for s, h in hist.items()}
    broker = PaperBroker(settings.broker.paper_state_file, settings.risk.capital, settings.cost_model,
                         price_fn=lambda s, ex="NSE": prices[s])
    eng = Engine(settings, broker)
    table = pd.DataFrame([
        {"symbol": "AAA", "eligible": True, "rank": 1},
        {"symbol": "BBB", "eligible": True, "rank": 2},
        {"symbol": "CCC", "eligible": False, "rank": 3},
    ])
    monkeypatch.setattr(eng, "screen_table", lambda as_of: table)
    eng._nse = StubNSE()
    return eng, broker, prices


def _llm(eng, sym, rating, conf=70):
    SignalStore(eng.s.signals_root).put(LLMSignal(sym, AS_OF, rating, confidence=conf, source="claude-analyst"))


def test_factor_mode_needs_no_llm(hybrid):
    eng, *_ = hybrid
    eng.s.strategy.signal_mode = "factor"
    assert [e["symbol"] for e in eng.rebalance(D)] == ["AAA"]      # top-1 only


def test_hybrid_llm_reviewed_buy(hybrid):
    eng, *_ = hybrid
    _llm(eng, "AAA", "Overweight")
    assert [e["symbol"] for e in eng.rebalance(D)] == ["AAA"]


def test_hybrid_missing_review_blocks_and_veto_blocks(hybrid):
    eng, *_ = hybrid
    assert eng.rebalance(D) == []                                     # no LLM review -> hold (default)
    _llm(eng, "AAA", "Sell", conf=80)
    assert eng.rebalance(D) == []                                     # vetoed
    _llm(eng, "AAA", "Sell", conf=30)
    assert [e["symbol"] for e in eng.rebalance(D)] == ["AAA"]         # low-confidence veto ignored


def test_hybrid_llm_cannot_add_risk(hybrid):
    eng, *_ = hybrid
    _llm(eng, "BBB", "Buy", conf=95)                                  # rank 2 = factor Hold
    _llm(eng, "CCC", "Buy", conf=95)                                  # ineligible = factor Sell
    assert eng.rebalance(D) == []


def test_surveillance_and_results_blackout(hybrid):
    eng, *_ = hybrid
    eng.s.strategy.llm_missing = "proceed"
    eng._nse.surv = {"AAA": "LTASM Stage I"}
    assert eng.rebalance(D) == []
    eng._nse.surv = {}
    eng._nse.series_ = {"AAA": ("BE", "5")}
    assert eng.rebalance(D) == []
    eng._nse.series_ = {}
    eng._nse.results = {"AAA": [date(2026, 10, 30)]}
    assert eng.rebalance(D) == []
    eng._nse.results = {"AAA": [date(2026, 11, 20)]}                  # far away: fine
    assert [e["symbol"] for e in eng.rebalance(D)] == ["AAA"]


def test_split_rescales_position(hybrid, monkeypatch):
    eng, *_ = hybrid
    eng.state.apply_fill("AAA", "BUY", 10, 1000.0, stop=920.0, target=1200.0)
    today = date.today()
    eng._nse.cas = [{"symbol": "AAA", "exDate": today.strftime("%d-%b-%Y"),
                     "subject": "Face Value Split (Sub-Division) - From Rs 10/- Per Share To Rs 2/- Per Share"}]
    eng.apply_corporate_actions(today)
    eng.apply_corporate_actions(today)                                # idempotent
    pos = eng.state.positions["AAA"]
    assert (pos["qty"], pos["avg"], pos["stop"], pos["target"]) == (50, 200.0, 184.0, 240.0)


def test_momentum_rating_and_scores(ohlcv):
    hist = {f"S{i}": ohlcv(300, drift=0.001 * (i - 3), seed=i, start_date="2025-08-01") for i in range(8)}
    t = score_universe(hist, min_traded_value_cr=0, vol_exclude_pct=0.0)
    assert list(t["rank"]) == list(range(1, len(t) + 1))
    best = t.iloc[0]["symbol"]
    assert momentum_rating(t, best, top_n=2) in ("Buy", "Sell")       # Sell only if below its 200-DMA
    assert momentum_rating(t, "UNKNOWN", top_n=2) == "Hold"


def test_record_equity_one_row_per_day(hybrid):
    eng, *_ = hybrid
    eng.record_equity(D)
    eng.record_equity(D)
    eng.record_equity(date(2026, 10, 29))
    lines = eng.s.path("equity.csv").read_text().splitlines()
    assert lines[0].startswith("date,equity") and len(lines) == 3


def test_analysis_symbols_per_mode(hybrid):
    eng, *_ = hybrid
    eng.state.apply_fill("ZZZ", "BUY", 1, 10.0)
    assert eng.analysis_symbols(date(2026, 10, 27)) == ["AAA", "ZZZ"]     # top_n=1 + holdings
    eng.s.strategy.signal_mode = "llm"
    assert eng.analysis_symbols(date(2026, 10, 27)) == eng.s.universe


def test_sector_cap(hybrid, monkeypatch):
    eng, _, prices = hybrid
    prices["ZZZ"] = 10.0
    eng.s.strategy.llm_missing = "proceed"
    eng.s.risk.max_per_sector = 1
    monkeypatch.setattr(eng, "_sectors", lambda: {"AAA": "Pharma", "ZZZ": "Pharma"})
    eng.state.apply_fill("ZZZ", "BUY", 1, 10.0)
    eng.broker.state["positions"]["ZZZ"] = {"qty": 1, "avg": 10.0}    # held at the broker too
    assert eng.rebalance(D) == []                                     # a second pharma name is blocked
    monkeypatch.setattr(eng, "_sectors", lambda: {"AAA": "IT", "ZZZ": "Pharma"})
    assert [e["symbol"] for e in eng.rebalance(D)] == ["AAA"]
