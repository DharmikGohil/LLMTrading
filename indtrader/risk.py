"""Portfolio-level pre-trade checks. Sells (risk-reducing) always pass;
buys must clear every limit."""

from __future__ import annotations

import math
from dataclasses import dataclass

from indtrader.config import RiskSettings


@dataclass
class AccountView:
    cash: float
    equity: float                    # cash + market value of bot positions
    start_of_day_equity: float
    gross_exposure: float            # market value of bot positions
    open_positions: int
    orders_today: int


@dataclass
class Decision:
    allowed: bool
    quantity: int
    reason: str = ""


def check_buy(symbol: str, qty: int, price: float, held_qty: int, acct: AccountView, r: RiskSettings,
              analysed_close: float | None = None) -> Decision:
    if qty <= 0:
        return Decision(False, 0, "zero quantity")
    if acct.orders_today >= r.max_orders_per_day:
        return Decision(False, 0, "max orders per day reached")
    day_pnl = acct.equity - acct.start_of_day_equity
    if acct.start_of_day_equity > 0 and day_pnl <= -r.max_daily_loss_pct * acct.start_of_day_equity:
        return Decision(False, 0, f"daily loss kill switch (P&L {day_pnl:,.0f})")
    if analysed_close and abs(price / analysed_close - 1) > r.max_price_deviation_pct:
        return Decision(False, 0, f"price {price:.2f} moved >{r.max_price_deviation_pct:.0%} from analysed close {analysed_close:.2f}")
    if held_qty == 0 and acct.open_positions >= r.max_open_positions:
        return Decision(False, 0, f"max open positions ({r.max_open_positions})")

    cap = r.capital
    room_exposure = r.max_gross_exposure_pct * cap - acct.gross_exposure
    room_position = r.max_position_pct * cap - held_qty * price
    room = min(room_exposure, room_position, acct.cash * 0.995)   # keep a sliver for charges
    qty = min(qty, math.floor(max(room, 0) / price))
    if qty <= 0:
        return Decision(False, 0, "no room (cash/exposure/position limit)")
    if qty * price < r.min_order_value:
        return Decision(False, 0, f"order value {qty * price:,.0f} < min {r.min_order_value:,.0f}")
    return Decision(True, qty, "ok")


def check_sell(qty: int, held_qty: int) -> Decision:
    qty = min(qty, held_qty)
    return Decision(qty > 0, qty, "ok" if qty > 0 else "nothing to sell")
