from datetime import date

import pytest

from indtrader import data as market_data
from indtrader.backtest import run_backtest, technical_rating
from indtrader.brokers.paper import PaperBroker
from indtrader.engine import Engine
from indtrader.signals.llm_agent import LLMSignal, SignalStore


@pytest.fixture
def setup(settings, ohlcv, monkeypatch):
    settings.strategy.rsi_max_entry = 100     # synthetic uptrend is permanently "overbought"
    hist = {"AAA": ohlcv(300, drift=0.004, seed=1, start_date="2025-08-01"),
            "BBB": ohlcv(300, drift=-0.003, seed=2, start_date="2025-08-01")}
    prices = {s: float(h["Close"].iloc[-1]) for s, h in hist.items()}
    monkeypatch.setattr(market_data, "recent_history", lambda sym, as_of, lookback_days=300, exchange="NSE": hist[sym])
    broker = PaperBroker(settings.broker.paper_state_file, settings.risk.capital, settings.cost_model,
                         price_fn=lambda s, ex="NSE": prices[s])
    store = SignalStore(settings.path("signals", "_").parent)
    for sym, rating in (("AAA", "Buy"), ("BBB", "Sell")):
        store.put(LLMSignal(sym, "2026-10-27", rating))
    return Engine(settings, broker), broker, prices


def test_rebalance_monitor_cycle(setup):
    eng, broker, prices = setup
    executed = eng.rebalance(date(2026, 10, 28))
    assert [e["symbol"] for e in executed] == ["AAA"]           # BBB Sell with nothing held -> no-op
    pos = eng.state.positions["AAA"]
    assert pos["qty"] > 0 and pos["stop"] < prices["AAA"] < pos["target"]
    assert broker.positions()["AAA"].quantity == pos["qty"]
    assert broker.funds() < 100000

    # second run on the same signal does not pyramid
    assert eng.rebalance(date(2026, 10, 28)) == []

    prices["AAA"] = pos["stop"] - 1                              # crash through the stop
    exits = eng.monitor()
    assert exits and "stop-loss" in exits[0]["reason"]
    assert "AAA" not in eng.state.positions and not broker.positions()


def test_bot_ignores_manual_holdings(setup):
    eng, broker, prices = setup
    broker.state["positions"]["BBB"] = {"qty": 50, "avg": 90.0}   # user's own shares
    eng.rebalance(date(2026, 10, 28))
    assert broker.positions()["BBB"].quantity == 50              # Sell rating did not touch them


def test_dry_run_sends_nothing(setup, settings):
    eng, broker, _ = setup
    settings.dry_run = True
    eng.rebalance(date(2026, 10, 28))
    assert broker.positions() == {} and broker.funds() == 100000


def test_backtest_runs(settings, ohlcv):
    hist = {"AAA": ohlcv(400, drift=0.003, seed=3, start_date="2024-06-03"),
            "BBB": ohlcv(400, drift=-0.001, seed=4, start_date="2024-06-03")}
    res = run_backtest(settings, date(2025, 1, 1), date(2025, 12, 31), technical_rating, histories=hist)
    st = res.stats
    assert st["trades"] > 0 and st["total_charges"] > 0
    assert st["max_drawdown_pct"] <= 0
    assert set(res.trades["side"]) <= {"BUY", "SELL"}
    # never more invested than capital (cash never negative)
    assert res.equity.min() > 0


def test_no_rebuy_after_stop(setup):
    eng, broker, prices = setup
    eng.rebalance(date(2026, 10, 28))
    prices["AAA"] = eng.state.positions["AAA"]["stop"] - 1
    eng.monitor()
    prices["AAA"] += 1.5
    assert eng.rebalance(date.today()) == []          # cooldown blocks the immediate re-entry


def test_halt_blocks_orders(setup, settings):
    eng, broker, _ = setup
    settings.path("HALT").write_text("test")
    eng.rebalance(date(2026, 10, 28))
    assert broker.positions() == {} and broker.funds() == 100000
