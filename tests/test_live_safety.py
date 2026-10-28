"""Regression tests for live-trading failure modes (pending orders, partial fills,
unknown placements, ledger accounting, scheduler)."""

from datetime import date, datetime

import pytest

from indtrader import data as market_data
from indtrader.brokers.base import Broker, Holding, OrderResult
from indtrader.engine import Engine
from indtrader.market import IST
from indtrader.scheduler import Scheduler
from indtrader.signals.llm_agent import LLMSignal, SignalStore


class FakeLiveBroker(Broker):
    """Holds orders OPEN until the test decides how they end."""

    name = "fake"

    def __init__(self, prices, funds=1_000_000.0):
        self.prices = prices
        self._funds = funds
        self.holdings: dict[str, int] = {}
        self.orders: dict[str, dict] = {}
        self.placed: list = []
        self.next_status = "OPEN"          # or "UNKNOWN"

    def funds(self):
        return self._funds

    def positions(self):
        return {s: Holding(s, q, 0.0) for s, q in self.holdings.items() if q}

    def ltp(self, symbols, exchange="NSE"):
        return {s: self.prices[s] for s in symbols if s in self.prices}

    def place_order(self, order):
        oid = f"O{len(self.placed) + 1}"
        self.placed.append(order)
        self.orders[oid] = {"order": order, "status": "OPEN", "filled": 0}
        if self.next_status == "UNKNOWN":
            return OrderResult("", "UNKNOWN", message="read timeout")
        return OrderResult(oid, "OPEN")

    def finish(self, oid, status="COMPLETE", filled=None, price=None):
        o = self.orders[oid]
        o["status"], o["filled"] = status, o["order"].quantity if filled is None else filled
        o["price"] = price or o["order"].price
        sign = 1 if o["order"].side == "BUY" else -1
        self.holdings[o["order"].symbol] = self.holdings.get(o["order"].symbol, 0) + sign * o["filled"]

    def order_status(self, oid):
        o = self.orders[oid]
        return OrderResult(oid, o["status"], o["filled"], o.get("price"))

    def find_order(self, symbol, side, tag):
        hits = [(k, o) for k, o in self.orders.items() if o["order"].symbol == symbol and o["order"].side == side]
        if not hits:
            return None
        k, o = hits[-1]
        return OrderResult(k, o["status"], o["filled"], o.get("price"))


@pytest.fixture
def live(settings, ohlcv, monkeypatch):
    settings.strategy.rsi_max_entry = 100
    settings.strategy.regime_filter = False
    hist = {"AAA": ohlcv(300, drift=0.004, seed=1, start_date="2025-08-01"),
            "BBB": ohlcv(300, drift=-0.003, seed=2, start_date="2025-08-01")}
    monkeypatch.setattr(market_data, "recent_history", lambda sym, as_of, lookback_days=300, exchange="NSE": hist[sym])
    prices = {s: float(h["Close"].iloc[-1]) for s, h in hist.items()}
    broker = FakeLiveBroker(prices)
    SignalStore(settings.path("signals", "_").parent).put(LLMSignal("AAA", "2026-10-27", "Buy"))
    eng = Engine(settings, broker)
    eng.fill_timeout_s = 0
    return eng, broker, prices


D = date(2026, 10, 28)


def test_pending_buy_is_not_doubled(live):
    eng, broker, _ = live
    eng.rebalance(D)
    assert len(broker.placed) == 1 and eng.state.pending_for("AAA", "BUY")
    eng.rebalance(D)                                  # e.g. scheduler retry or restart
    assert len(broker.placed) == 1


def test_pending_sell_is_not_repeated(live):
    eng, broker, prices = live
    eng.rebalance(D)
    broker.finish("O1")
    eng.reconcile_pending()
    qty = eng.state.qty("AAA")
    assert qty > 0
    prices["AAA"] = eng.state.positions["AAA"]["stop"] - 1
    eng.monitor()
    eng.monitor()
    eng.monitor()
    sells = [o for o in broker.placed if o.side == "SELL"]
    assert len(sells) == 1 and sells[0].quantity == qty


def test_partial_fill_then_cancel_is_tracked(live):
    eng, broker, _ = live
    eng.rebalance(D)
    ordered = broker.placed[0].quantity
    broker.finish("O1", status="CANCELLED", filled=ordered // 3)
    eng.reconcile_pending()
    assert eng.state.qty("AAA") == ordered // 3
    assert eng.state.positions["AAA"]["stop"] is not None    # the partial position is protected
    assert not eng.state.data["pending"]


def test_unknown_placement_is_resolved_by_lookup(live):
    eng, broker, _ = live
    broker.next_status = "UNKNOWN"
    eng.rebalance(D)
    # find_order located it (still OPEN): tracked as pending with its real id
    assert eng.state.data["pending"][0]["order_id"] == "O1"
    broker.finish("O1")
    eng.reconcile_pending()
    assert eng.state.qty("AAA") == broker.placed[0].quantity


def test_ledger_kill_switch_with_big_account(live):
    eng, broker, prices = live
    assert broker.funds() == 1_000_000 and eng.s.risk.capital == 100_000
    eng.rebalance(D)
    broker.finish("O1")
    eng.reconcile_pending()
    acct = eng._account(prices)
    assert acct.cash <= 100_000 - broker.placed[0].quantity * prices["AAA"] + 1   # bot money, not account money
    eng.state.data["day"]["start_equity"] = acct.equity
    prices["AAA"] *= 0.75                             # big loss on the position
    after = eng._account(prices)
    assert after.equity < acct.equity                 # the loss is visible ...
    eng.state.data["pending"].clear()
    eng.state.positions["AAA"]["stop"] = 1.0          # (keep the stop from exiting first)
    eng.state.data["stopped_out"].clear()
    SignalStore(eng.s.path("signals", "_").parent).put(LLMSignal("BBB", "2026-10-27", "Buy"))
    eng.s.strategy.trend_filter = False
    n = len(broker.placed)
    eng.rebalance(D)
    assert len(broker.placed) == n                    # ... and the kill switch blocks new buys


def test_add_never_lowers_trailed_stop(live):
    eng, *_ = live
    eng.state.apply_fill("ZZZ", "BUY", 10, 100.0, stop=90.0)
    eng.state.positions["ZZZ"]["stop"] = 105.0        # trailed up
    eng.state.apply_fill("ZZZ", "BUY", 5, 110.0, stop=96.0)
    assert eng.state.positions["ZZZ"]["stop"] == 105.0


def test_ledger_round_trip(live):
    eng, *_ = live
    cash0 = eng.state.cash
    eng.state.apply_fill("ZZZ", "BUY", 10, 100.0, charges=2.0)
    eng.state.apply_fill("ZZZ", "SELL", 10, 110.0, charges=3.0)
    assert eng.state.cash == pytest.approx(cash0 + 100 - 5)
    assert eng.state.data["realized_pnl"] == pytest.approx(95)


def test_bad_prices_do_not_crash(live):
    eng, broker, prices = live
    prices["AAA"] = 0.0
    prices["BBB"] = float("nan")
    assert eng.rebalance(D) == []
    assert eng.monitor() == []


def test_manual_sale_outside_bot_reduces_tracked_qty(live):
    eng, broker, _ = live
    eng.rebalance(D)
    broker.finish("O1")
    eng.reconcile_pending()
    broker.holdings["AAA"] = 2                       # user sold most of it in the broker app
    eng.reconcile_pending()
    assert eng.state.qty("AAA") == 2


# ---------------------------------------------------------------- scheduler
class FakeEngine:
    def __init__(self):
        self.calls = []
        self.fail_rebalance = 0

    def analyze_universe(self, today):
        self.calls.append("analysis")

    def rebalance(self, today):
        if self.fail_rebalance:
            self.fail_rebalance -= 1
            raise RuntimeError("boom")
        self.calls.append("rebalance")

    def monitor(self):
        self.calls.append("monitor")

    def square_off_intraday(self):
        pass

    def status(self):
        return {"bot_equity": 1, "bot_cash": 1, "realized_pnl": 0, "positions": []}


def _at(h, m, d=28):
    return datetime(2026, 10, d, h, m, tzinfo=IST)


def test_scheduler_flow_and_restart(settings):
    eng = FakeEngine()
    sch = Scheduler(eng, settings)
    sch.tick(_at(8, 0))
    assert eng.calls == []
    sch.tick(_at(8, 31))
    sch.analysis_thread.join()
    assert eng.calls == ["analysis"]
    eng.fail_rebalance = 1
    sch.tick(_at(9, 31))                            # rebalance fails, monitor still runs
    assert "monitor" in eng.calls and "rebalance" not in eng.calls
    sch.last_monitor = 0
    sch.tick(_at(9, 32))
    assert eng.calls.count("rebalance") == 1
    # a restart the same day does not repeat analysis or execution
    eng2 = FakeEngine()
    sch2 = Scheduler(eng2, settings)
    sch2.tick(_at(10, 0))
    assert "analysis" not in eng2.calls and "rebalance" not in eng2.calls
    # holidays: nothing at all
    sch2.tick(datetime(2026, 11, 10, 10, 0, tzinfo=IST))
    assert eng2.calls == ["monitor"]
