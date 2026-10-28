"""Indian market calendar, session times and symbol helpers.

All times are IST (Asia/Kolkata). NSE cash market:
  pre-open  09:00-09:08, normal session 09:15-15:30,
  MIS (intraday) auto square-off by brokers around 15:20-15:25.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")

MARKET_OPEN = time(9, 15)
MARKET_CLOSE = time(15, 30)

# NSE equity-segment trading holidays (weekdays only). Source: NSE circular
# for 2026. Update every December from
# https://www.nseindia.com/resources/exchange-communication-holidays
# Extra dates can be added through `market.extra_holidays` in config.yaml.
NSE_HOLIDAYS: set[date] = {
    date(2026, 1, 26),   # Republic Day
    date(2026, 3, 3),    # Holi
    date(2026, 3, 26),   # Shri Ram Navami
    date(2026, 3, 31),   # Shri Mahavir Jayanti
    date(2026, 4, 3),    # Good Friday
    date(2026, 4, 14),   # Dr. Baba Saheb Ambedkar Jayanti
    date(2026, 5, 1),    # Maharashtra Day
    date(2026, 5, 28),   # Bakri Id
    date(2026, 6, 26),   # Muharram
    date(2026, 9, 14),   # Ganesh Chaturthi
    date(2026, 10, 2),   # Mahatma Gandhi Jayanti
    date(2026, 10, 20),  # Dussehra
    date(2026, 11, 10),  # Diwali Balipratipada
    date(2026, 11, 24),  # Guru Nanak Jayanti
    date(2026, 12, 25),  # Christmas
}

# Weekend days on which the exchange holds a full special session
# (e.g. Union Budget day 2026-02-01, a Sunday).
SPECIAL_SESSIONS: set[date] = {date(2026, 2, 1)}


def now_ist() -> datetime:
    return datetime.now(IST)


def is_trading_day(d: date, extra_holidays: set[date] | None = None) -> bool:
    if d in SPECIAL_SESSIONS:
        return True
    if d.weekday() >= 5:
        return False
    return d not in NSE_HOLIDAYS and d not in (extra_holidays or set())


def previous_trading_day(d: date, extra_holidays: set[date] | None = None) -> date:
    d -= timedelta(days=1)
    while not is_trading_day(d, extra_holidays):
        d -= timedelta(days=1)
    return d


def next_trading_day(d: date, extra_holidays: set[date] | None = None) -> date:
    d += timedelta(days=1)
    while not is_trading_day(d, extra_holidays):
        d += timedelta(days=1)
    return d


def is_market_open(ts: datetime | None = None, extra_holidays: set[date] | None = None) -> bool:
    ts = (ts or now_ist()).astimezone(IST)
    return is_trading_day(ts.date(), extra_holidays) and MARKET_OPEN <= ts.time() < MARKET_CLOSE


def yahoo_symbol(symbol: str, exchange: str = "NSE") -> str:
    """RELIANCE -> RELIANCE.NS (NSE) / RELIANCE.BO (BSE). Already-suffixed symbols pass through."""
    s = symbol.strip().upper()
    if s.endswith((".NS", ".BO")) or s.startswith("^"):
        return s
    return f"{s}.NS" if exchange.upper() == "NSE" else f"{s}.BO"


def broker_symbol(symbol: str) -> tuple[str, str]:
    """RELIANCE.NS -> ("RELIANCE", "NSE"); RELIANCE.BO -> ("RELIANCE", "BSE"); bare -> NSE."""
    s = symbol.strip().upper()
    if s.endswith(".NS"):
        return s[:-3], "NSE"
    if s.endswith(".BO"):
        return s[:-3], "BSE"
    return s, "NSE"


# NSE cash-market tick sizes by price band (effective 15 Apr 2025, bands reviewed
# monthly on closing prices). Every tick divides the next larger one, so a price
# on a coarser grid is always valid on a finer one.
TICK_BANDS: tuple[tuple[float, float], ...] = (
    (250, 0.01), (1000, 0.05), (5000, 0.10), (10000, 0.50), (20000, 1.00), (float("inf"), 5.00),
)


def tick_size(price: float) -> float:
    for upper, tick in TICK_BANDS:
        if price < upper:
            return tick
    return TICK_BANDS[-1][1]


def round_to_tick(price: float, tick: float | None = None, side: str = "BUY") -> float:
    """Round a limit price onto the exchange tick grid, in the direction that keeps
    the order marketable (up for BUY, down for SELL).

    Without an explicit `tick`, uses the tick of a band 20% higher than `price`:
    since bands are set on last month's close, a stock near a band edge may
    already trade on the coarser grid, and the coarser grid is valid either way.
    """
    import math

    tick = tick or tick_size(price * 1.2)
    steps = price / tick
    steps = math.ceil(steps - 1e-9) if side.upper() == "BUY" else math.floor(steps + 1e-9)
    return round(steps * tick, 2)
