import pytest

kiteconnect = pytest.importorskip("kiteconnect")
from kiteconnect.exceptions import InputException, NetworkException, TokenException  # noqa: E402

from indtrader.brokers import zerodha  # noqa: E402
from indtrader.brokers.base import Order  # noqa: E402
from indtrader.brokers.zerodha import ZerodhaBroker  # noqa: E402


class FakeKite:
    def __init__(self):
        self.access_token = "old"
        self.raise_on_place = None
        self.expired = False

    def set_access_token(self, t):
        self.access_token = t
        self.expired = False

    def margins(self, seg):
        if self.expired:
            raise TokenException("expired")
        return {"net": 5000.0}

    def place_order(self, **kw):
        self.last = kw
        if self.raise_on_place:
            raise self.raise_on_place
        return "240101000001"

    def order_history(self, oid):
        return [{"order_id": oid, "status": "OPEN"},
                {"order_id": oid, "status": "CANCELLED", "filled_quantity": 4, "average_price": 101.5}]

    def orders(self):
        return [{"order_id": "1", "tradingsymbol": "INFY", "transaction_type": "BUY", "tag": "indtrader",
                 "status": "COMPLETE", "filled_quantity": 10, "average_price": 1500.0}]


def test_token_refresh_from_file(tmp_path, monkeypatch):
    monkeypatch.setattr(zerodha, "TOKEN_FILE", tmp_path / "tok")
    kite = FakeKite()
    b = ZerodhaBroker(kite)
    kite.expired = True
    with pytest.raises(RuntimeError, match="zerodha-login"):
        b.funds()                                   # no new token yet
    (tmp_path / "tok").write_text("fresh")
    kite.expired = True
    assert b.funds() == 5000.0 and kite.access_token == "fresh"


def test_order_outcomes():
    kite = FakeKite()
    b = ZerodhaBroker(kite)
    o = Order("INFY", "BUY", 10, price=1500.1)
    assert b.place_order(o).status == "OPEN" and kite.last["order_type"] == "LIMIT"
    kite.raise_on_place = InputException("bad price")
    assert b.place_order(o).status == "REJECTED"
    kite.raise_on_place = NetworkException("gateway timeout")
    assert b.place_order(o).status == "UNKNOWN"
    st = b.order_status("X")
    assert (st.status, st.filled_qty, st.avg_price) == ("CANCELLED", 4, 101.5)   # partial fill kept
    found = b.find_order("INFY", "BUY", "indtrader")
    assert (found.status, found.filled_qty) == ("COMPLETE", 10)
    assert b.find_order("TCS", "BUY", "indtrader") is None
