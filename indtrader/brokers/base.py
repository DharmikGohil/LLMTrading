"""Broker-neutral interface. Symbols are bare NSE/BSE trading symbols (e.g. RELIANCE)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Literal

Side = Literal["BUY", "SELL"]


@dataclass
class Order:
    symbol: str
    side: Side
    quantity: int
    order_type: Literal["MARKET", "LIMIT"] = "LIMIT"
    price: float | None = None
    product: Literal["CNC", "MIS"] = "CNC"
    exchange: str = "NSE"
    reason: str = ""
    tag: str = "indtrader"


@dataclass
class OrderResult:
    order_id: str
    # UNKNOWN: the request failed in a way that does not tell whether the broker
    # accepted it (timeout, network error); the engine looks it up by tag.
    status: Literal["COMPLETE", "OPEN", "REJECTED", "CANCELLED", "UNKNOWN", "DRY_RUN"]
    filled_qty: int = 0
    avg_price: float | None = None
    message: str = ""


@dataclass
class Holding:
    symbol: str
    quantity: int
    average_price: float
    extra: dict = field(default_factory=dict)


class Broker(ABC):
    name: str = "base"

    @abstractmethod
    def funds(self) -> float:
        """Free cash available for equity trading (rupees)."""

    @abstractmethod
    def positions(self) -> dict[str, Holding]:
        """Net long quantity per symbol, delivery holdings plus today's trades."""

    @abstractmethod
    def ltp(self, symbols: list[str], exchange: str = "NSE") -> dict[str, float]:
        """Last traded price per symbol."""

    @abstractmethod
    def place_order(self, order: Order) -> OrderResult: ...

    def order_status(self, order_id: str) -> OrderResult | None:  # pragma: no cover - optional
        return None

    def cancel_order(self, order_id: str) -> bool:  # pragma: no cover - optional
        """Ask the broker to cancel a working order. True if the request was accepted."""
        return False

    def find_order(self, symbol: str, side: str, tag: str) -> OrderResult | None:  # pragma: no cover - optional
        """Today's most recent order for symbol/side/tag, used after an UNKNOWN placement."""
        return None


TERMINAL = ("COMPLETE", "REJECTED", "CANCELLED")
