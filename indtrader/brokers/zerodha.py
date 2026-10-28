"""Zerodha Kite Connect adapter (pip install kiteconnect).

Env: KITE_API_KEY, KITE_API_SECRET, KITE_ACCESS_TOKEN (or run
`indtrader zerodha-login` once each trading day; tokens expire daily),
optional KITE_ALGO_ID (exchange-assigned algo id, SEBI retail-algo framework).
Your static IP must be whitelisted in the Kite developer console.
"""

from __future__ import annotations

import os
from pathlib import Path

from indtrader.brokers.base import Broker, Holding, Order, OrderResult

TOKEN_FILE = Path("state/kite_access_token")


def _read_token() -> str | None:
    # the file written by `indtrader zerodha-login` wins: it is refreshed every morning,
    # while an env var set at start-up goes stale after the first day
    if TOKEN_FILE.exists() and TOKEN_FILE.read_text().strip():
        return TOKEN_FILE.read_text().strip()
    return os.getenv("KITE_ACCESS_TOKEN") or None


def _client():
    from kiteconnect import KiteConnect

    kite = KiteConnect(api_key=os.environ["KITE_API_KEY"])
    token = _read_token()
    if not token:
        raise RuntimeError("No Kite access token: run `indtrader zerodha-login` or set KITE_ACCESS_TOKEN")
    kite.set_access_token(token)
    return kite


_STATUS = {"COMPLETE": "COMPLETE", "REJECTED": "REJECTED", "CANCELLED": "CANCELLED"}


def _result_from_order(o: dict) -> OrderResult:
    status = _STATUS.get(str(o.get("status", "")).upper(), "OPEN")
    return OrderResult(str(o["order_id"]), status, int(o.get("filled_quantity") or 0),
                       float(o["average_price"]) if o.get("average_price") else None,
                       o.get("status_message") or "")


def login_url() -> str:
    from kiteconnect import KiteConnect

    return KiteConnect(api_key=os.environ["KITE_API_KEY"]).login_url()


def exchange_request_token(request_token: str) -> str:
    from kiteconnect import KiteConnect

    kite = KiteConnect(api_key=os.environ["KITE_API_KEY"])
    session = kite.generate_session(request_token, api_secret=os.environ["KITE_API_SECRET"])
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(session["access_token"])
    return session["access_token"]


class ZerodhaBroker(Broker):
    name = "zerodha"

    def __init__(self, kite=None):
        self.kite = kite or _client()
        self.algo_id = os.getenv("KITE_ALGO_ID") or None

    def _call(self, method: str, *args, **kwargs):
        """Call Kite; on an expired token, re-read the token file once and retry
        (so a running scheduler picks up the morning `zerodha-login`)."""
        from kiteconnect.exceptions import TokenException

        try:
            return getattr(self.kite, method)(*args, **kwargs)
        except TokenException:
            token = _read_token()
            if not token or token == getattr(self.kite, "access_token", None):
                raise RuntimeError("Kite session expired: run `indtrader zerodha-login`") from None
            self.kite.set_access_token(token)
            return getattr(self.kite, method)(*args, **kwargs)

    def funds(self) -> float:
        eq = self._call("margins", "equity")
        return float(eq.get("net", eq.get("available", {}).get("live_balance", 0.0)))

    def positions(self) -> dict[str, Holding]:
        out: dict[str, Holding] = {}
        for h in self._call("holdings"):
            qty = int(h.get("quantity", 0)) + int(h.get("t1_quantity", 0))
            if qty:
                out[h["tradingsymbol"]] = Holding(h["tradingsymbol"], qty, float(h["average_price"]))
        # today's CNC/MIS trades (sells of holdings show up as negative net qty)
        for p in self._call("positions").get("net", []):
            if p.get("exchange") not in ("NSE", "BSE") or not p.get("quantity"):
                continue
            sym, qty = p["tradingsymbol"], int(p["quantity"])
            if sym in out:
                prev = out[sym]
                total = prev.quantity + qty
                avg = prev.average_price if qty < 0 else (
                    (prev.quantity * prev.average_price + qty * float(p["average_price"])) / total if total else 0.0)
                out[sym] = Holding(sym, total, avg)
            else:
                out[sym] = Holding(sym, qty, float(p["average_price"]))
        return {s: h for s, h in out.items() if h.quantity}

    def ltp(self, symbols: list[str], exchange: str = "NSE") -> dict[str, float]:
        keys = [f"{exchange}:{s}" for s in symbols]
        data = self._call("ltp", *keys)
        return {k.split(":", 1)[1]: float(v["last_price"]) for k, v in data.items()}

    def place_order(self, order: Order) -> OrderResult:
        kwargs = {}
        if order.order_type == "MARKET":
            kwargs["market_protection"] = -1   # exchange-mandated protection for API market orders
        from kiteconnect.exceptions import InputException, OrderException, PermissionException, TokenException

        try:
            oid = self._call(
                "place_order",
                variety="regular",
                exchange=order.exchange,
                tradingsymbol=order.symbol,
                transaction_type=order.side,
                quantity=int(order.quantity),
                product=order.product,
                order_type=order.order_type,
                price=order.price if order.order_type == "LIMIT" else None,
                validity="DAY",
                tag=order.tag[:20],
                algo_id=self.algo_id,
                **kwargs,
            )
        except (InputException, OrderException, PermissionException, TokenException, RuntimeError) as exc:
            return OrderResult("", "REJECTED", message=str(exc))   # Kite definitely did not accept it
        except Exception as exc:   # timeout / network: the order may or may not exist
            return OrderResult("", "UNKNOWN", message=str(exc))
        return OrderResult(str(oid), "OPEN")

    def order_status(self, order_id: str) -> OrderResult | None:
        hist = self._call("order_history", order_id)
        return _result_from_order(hist[-1]) if hist else None

    def find_order(self, symbol: str, side: str, tag: str) -> OrderResult | None:
        mine = [o for o in self._call("orders")
                if o.get("tradingsymbol") == symbol and o.get("transaction_type") == side and o.get("tag") == tag[:20]]
        return _result_from_order(mine[-1]) if mine else None
