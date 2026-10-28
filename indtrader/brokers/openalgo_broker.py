"""OpenAlgo adapter (pip install openalgo).

OpenAlgo (https://github.com/marketcalls/openalgo) is a self-hosted, open-source
bridge with one API for 25+ Indian brokers: Angel One, Dhan, Upstox, Fyers,
Zerodha, Kotak, 5paisa, Shoonya, AliceBlue, ICICI Direct, ... Run the OpenAlgo
server, log in to your broker there, and set OPENALGO_API_KEY.
"""

from __future__ import annotations

import os

from indtrader.brokers.base import Broker, Holding, Order, OrderResult


class OpenAlgoBroker(Broker):
    name = "openalgo"

    def __init__(self, host: str, strategy: str = "indtrader", client=None):
        if client is None:
            from openalgo import api

            client = api(api_key=os.environ["OPENALGO_API_KEY"], host=host)
        self.client = client
        self.strategy = strategy

    @staticmethod
    def _ok(resp: dict) -> dict:
        if resp.get("status") != "success":
            raise RuntimeError(f"OpenAlgo error: {resp.get('message', resp)}")
        return resp

    def funds(self) -> float:
        return float(self._ok(self.client.funds())["data"]["availablecash"])

    def positions(self) -> dict[str, Holding]:
        out: dict[str, Holding] = {}
        holdings = self._ok(self.client.holdings())["data"].get("holdings", [])
        for h in holdings:
            qty = int(float(h.get("quantity", 0)))
            if qty:
                out[h["symbol"]] = Holding(h["symbol"], qty, float(h.get("average_price") or h.get("price") or 0))
        for p in self._ok(self.client.positionbook()).get("data", []):
            qty = int(float(p.get("quantity", 0)))
            if not qty:
                continue
            sym = p["symbol"]
            if sym in out:
                out[sym] = Holding(sym, out[sym].quantity + qty, out[sym].average_price)
            else:
                out[sym] = Holding(sym, qty, float(p.get("average_price") or 0))
        return {s: h for s, h in out.items() if h.quantity}

    def ltp(self, symbols: list[str], exchange: str = "NSE") -> dict[str, float]:
        return {s: float(self._ok(self.client.quotes(symbol=s, exchange=exchange))["data"]["ltp"]) for s in symbols}

    def place_order(self, order: Order) -> OrderResult:
        kwargs = {"price": str(order.price)} if order.order_type == "LIMIT" and order.price else {}
        resp = self.client.placeorder(
            strategy=self.strategy, symbol=order.symbol, action=order.side, exchange=order.exchange,
            price_type=order.order_type, product=order.product, quantity=int(order.quantity), **kwargs,
        )
        if resp.get("status") != "success":
            return OrderResult("", "REJECTED", message=str(resp.get("message", resp)))
        return OrderResult(str(resp.get("orderid", "")), "OPEN")

    def order_status(self, order_id: str) -> OrderResult | None:
        resp = self.client.orderstatus(order_id=order_id, strategy=self.strategy)
        if resp.get("status") != "success":
            return None
        d = resp["data"]
        st = str(d.get("order_status", "")).upper()
        status = "COMPLETE" if st == "COMPLETE" else "REJECTED" if st in ("REJECTED", "CANCELLED") else "OPEN"
        return OrderResult(order_id, status, int(float(d.get("quantity", 0))) if status == "COMPLETE" else 0,
                           float(d.get("average_price") or d.get("price") or 0) or None)
