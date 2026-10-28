"""Paper-trading broker: fills marketable orders at LTP (+slippage) and charges
Indian transaction costs. State persists to a JSON file between runs."""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from indtrader.brokers.base import Broker, Holding, Order, OrderResult
from indtrader.costs import CostModel
from indtrader.market import IST


class PaperBroker(Broker):
    name = "paper"

    def __init__(self, state_file: str | Path, starting_cash: float, costs: CostModel,
                 price_fn: Callable[[str, str], float]):
        self.state_file = Path(state_file)
        self.costs = costs
        self.price_fn = price_fn
        if self.state_file.exists():
            self.state = json.loads(self.state_file.read_text(encoding="utf-8"))
        else:
            self.state = {"cash": starting_cash, "positions": {}, "orders": [], "realized_pnl": 0.0, "charges": 0.0}
            self._save()

    def _save(self) -> None:
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(json.dumps(self.state, indent=2), encoding="utf-8")

    def funds(self) -> float:
        return float(self.state["cash"])

    def positions(self) -> dict[str, Holding]:
        return {s: Holding(s, int(p["qty"]), float(p["avg"])) for s, p in self.state["positions"].items() if p["qty"]}

    def ltp(self, symbols: list[str], exchange: str = "NSE") -> dict[str, float]:
        return {s: float(self.price_fn(s, exchange)) for s in symbols}

    def place_order(self, order: Order) -> OrderResult:
        oid = f"PAPER-{uuid.uuid4().hex[:10]}"
        ltp = self.price_fn(order.symbol, order.exchange)
        slip = self.costs.slippage_pct
        fill = ltp * (1 + slip) if order.side == "BUY" else ltp * (1 - slip)
        if order.order_type == "LIMIT" and order.price is not None and (
                (order.side == "BUY" and order.price < fill) or (order.side == "SELL" and order.price > fill)):
            return self._record(order, OrderResult(oid, "REJECTED", message=f"limit {order.price} not marketable at {fill:.2f}"))
        qty = order.quantity
        charges = self.costs.charges(order.side, qty, fill, order.product)
        pos = self.state["positions"].setdefault(order.symbol, {"qty": 0, "avg": 0.0})

        if order.side == "BUY":
            cost = qty * fill + charges
            if cost > self.state["cash"] + 1e-6:
                return self._record(order, OrderResult(oid, "REJECTED", message="insufficient funds"))
            new_qty = pos["qty"] + qty
            pos["avg"] = (pos["qty"] * pos["avg"] + qty * fill) / new_qty
            pos["qty"] = new_qty
            self.state["cash"] -= cost
        else:
            if qty > pos["qty"]:
                return self._record(order, OrderResult(oid, "REJECTED", message="short selling not allowed in CNC"))
            self.state["realized_pnl"] += qty * (fill - pos["avg"]) - charges
            pos["qty"] -= qty
            self.state["cash"] += qty * fill - charges
            if pos["qty"] == 0:
                del self.state["positions"][order.symbol]
        self.state["charges"] += charges
        return self._record(order, OrderResult(oid, "COMPLETE", qty, round(fill, 2), f"charges Rs {charges:.2f}"))

    def _record(self, order: Order, result: OrderResult) -> OrderResult:
        self.state["orders"].append({
            "time": datetime.now(IST).isoformat(timespec="seconds"), "id": result.order_id,
            "symbol": order.symbol, "side": order.side, "qty": order.quantity, "status": result.status,
            "price": result.avg_price, "reason": order.reason, "message": result.message,
        })
        self._save()
        return result
