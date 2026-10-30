"""Regression tests for the order-path audit of 30 Oct 2026: duplicate orders after timeouts, double-booked
fills, split/bonus reconciliation, capital changes, the control arm's exit levels and stale exits."""

from datetime import date, timedelta

import pytest

from indtrader import data as market_data
from indtrader.brokers.base import Broker, Holding, OrderResult
from indtrader.brokers.paper import PaperBroker
from indtrader.costs import CostModel
from indtrader.engine import BotState, Engine
from indtrader.market import now_ist
from indtrader.signals.llm_agent import LLMSignal, SignalStore
from indtrader.strategy import protective_levels


class FakeBroker(Broker):
    """A broker whose behaviour each test scripts: what place_order returns, what lookups return."""
    name = "fake"

    def __init__(self, price=100.0):
        self.price, self.sent, self.held, self.orders = price, [], {}, {}
        self.place = lambda order: OrderResult(f"OID{len(self.sent)}", "COMPLETE", order.quantity, self.price)
        self.find = lambda symbol, side, tag: None
        self.cancelled = []

    def funds(self):
        return 1e9

    def positions(self):
        return {s: Holding(s, q, self.price) for s, q in self.held.items() if q}

    def ltp(self, symbols, exchange="NSE"):
        return {s: self.price for s in symbols}

    def place_order(self, order):
        self.sent.append(order)
        r = self.place(order)
        if r.filled_qty:
            self.held[order.symbol] = self.held.get(order.symbol, 0) + (r.filled_qty if order.side == "BUY" else -r.filled_qty)
        self.orders[r.order_id] = r
        return r

    def order_status(self, order_id):
        return self.orders.get(order_id)

    def find_order(self, symbol, side, tag):
        return self.find(symbol, side, tag)

    def cancel_order(self, order_id):
        self.cancelled.append(order_id)
        self.orders[order_id] = OrderResult(order_id, "CANCELLED", 0, None)
        return True


@pytest.fixture
def eng(settings, ohlcv, monkeypatch):
    settings.strategy.rsi_max_entry = 100
    hist = ohlcv(300, drift=0.004, seed=1, start_date="2025-08-01")
    monkeypatch.setattr(market_data, "recent_history", lambda sym, as_of, lookback_days=300, exchange="NSE": hist)
    SignalStore(settings.path("signals", "_").parent).put(LLMSignal("AAA", "2026-10-27", "Buy"))
    broker = FakeBroker(price=float(hist["Close"].iloc[-1]))
    e = Engine(settings, broker)
    e.fill_timeout_s = 0
    return e


def test_lookup_failure_after_timeout_never_resends(eng):
    eng.broker.place = lambda order: OrderResult("", "UNKNOWN", message="timeout")

    def boom(*a):
        raise ConnectionError("network down")
    eng.broker.find = boom
    eng.rebalance(date(2026, 10, 28))
    assert len(eng.broker.sent) == 1
    pending = eng.state.data["pending"]
    assert len(pending) == 1 and pending[0]["tag"] == eng.broker.sent[0].tag
    eng.rebalance(date(2026, 10, 28))                 # retry: the pending order blocks a second BUY
    assert len(eng.broker.sent) == 1


def test_every_order_has_its_own_tag_and_no_fill_is_booked_twice(eng):
    eng.rebalance(date(2026, 10, 28))
    held = eng.state.qty("AAA")
    assert held > 0
    first = eng.broker.sent[0]
    assert len(first.tag) <= 20 and first.tag.startswith("indtrader")
    # an UNKNOWN sell whose lookup returns the earlier, already booked order must not book it again
    eng.broker.place = lambda order: OrderResult("", "UNKNOWN", message="timeout")
    first_id = next(iter(eng.broker.orders))
    eng.broker.find = lambda symbol, side, tag: eng.broker.orders[first_id] if tag == first.tag else None
    cash = eng.state.cash
    eng._send("AAA", "SELL", held, eng.broker.price, "stop-loss test")
    assert eng.broker.sent[-1].tag != first.tag
    assert eng.state.qty("AAA") == held and eng.state.cash == cash
    applied = eng.state.data["applied_orders"]
    eng._apply_result("AAA", "BUY", eng.broker.orders[first_id], 1.0, None, None)   # replaying a booked fill
    assert eng.state.qty("AAA") == held and applied.count(first_id) == 1


def test_split_shares_not_yet_credited_are_not_written_off(eng):
    eng.rebalance(date(2026, 10, 28))
    held = eng.state.qty("AAA")
    eng.nse.corporate_actions = lambda a, b: [{"symbol": "AAA", "exDate": date.today().strftime("%d-%b-%Y"),
                                                "subject": "Bonus 1:1"}]
    eng.apply_corporate_actions(date.today())
    assert eng.state.qty("AAA") == 2 * held
    eng.reconcile_pending()                           # broker still shows the old count
    assert eng.state.qty("AAA") == 2 * held


def test_paper_broker_applies_splits(tmp_path):
    b = PaperBroker(tmp_path / "p.json", 100000, CostModel(), price_fn=lambda s, ex="NSE": 100.0)
    b.state["positions"]["AAA"] = {"qty": 10, "avg": 200.0}
    b.apply_split("AAA", 2)
    assert b.positions()["AAA"].quantity == 20 and b.positions()["AAA"].average_price == 100.0


def test_capital_change_moves_the_baselines(tmp_path):
    f = tmp_path / "bot.json"
    st = BotState(f, 1_000_000)
    st.data["peak_equity"] = 1_050_000
    st.data["day"] = {"date": "2026-10-30", "start_equity": 1_020_000}
    st.save()
    st = BotState(f, 100_000)
    assert st.cash == 100_000 and st.data["peak_equity"] == 150_000 and st.data["day"]["start_equity"] == 120_000


def test_hybrid_book_ignores_llm_stop_and_target(eng, settings, monkeypatch):
    settings.strategy.signal_mode = "hybrid"
    monkeypatch.setattr(eng, "_rating", lambda sym, sig, as_of: ("Buy", ""))   # no screen download
    store = SignalStore(settings.path("signals", "_").parent)
    store.put(LLMSignal("AAA", "2026-10-27", "Buy", stop_loss=1.0, price_target=eng.broker.price * 1.05))
    plan, tech = eng._plan("AAA", date(2026, 10, 28), date(2026, 10, 27), eng.broker.price, 100000, False)
    stop, take = protective_levels(eng.broker.price, tech, settings.strategy)    # ATR levels, no LLM input
    assert (plan.stop, plan.take_profit) == (stop, take)


def test_stale_stop_exit_is_cancelled_and_repriced(eng):
    eng.rebalance(date(2026, 10, 28))
    pos = eng.state.positions["AAA"]
    eng.broker.place = lambda order: OrderResult(f"OID{len(eng.broker.sent)}", "OPEN")
    eng.broker.price = pos["stop"] - 1
    eng.monitor()                                     # stop hit: a LIMIT sell is left working
    assert len(eng.state.data["pending"]) == 1
    sent_before = len(eng.broker.sent)
    eng.monitor()                                     # too soon to re-price
    assert len(eng.broker.sent) == sent_before
    eng.state.data["pending"][0]["sent_at"] = (now_ist() - timedelta(minutes=5)).isoformat(timespec="seconds")
    eng.broker.place = lambda order: OrderResult(f"OID{len(eng.broker.sent)}", "COMPLETE", order.quantity, eng.broker.price)
    eng.monitor()
    assert eng.broker.cancelled and "AAA" not in eng.state.positions and not eng.state.data["pending"]


def test_depository_charge_once_per_stock_per_day():
    c = CostModel()
    assert c.charges("SELL", 10, 100) - c.charges("SELL", 10, 100, dp=False) == pytest.approx(c.dp_charge_per_sell)
