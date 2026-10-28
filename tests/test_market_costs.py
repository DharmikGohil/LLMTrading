from datetime import date, datetime

from indtrader.costs import CostModel
from indtrader.market import (
    IST,
    broker_symbol,
    is_market_open,
    is_trading_day,
    previous_trading_day,
    round_to_tick,
    yahoo_symbol,
)


def test_calendar():
    assert not is_trading_day(date(2026, 10, 2))       # Gandhi Jayanti
    assert not is_trading_day(date(2026, 10, 31))      # Saturday
    assert is_trading_day(date(2026, 2, 1))            # Budget-day Sunday session
    assert previous_trading_day(date(2026, 10, 21)) == date(2026, 10, 19)  # skips Dussehra
    assert is_market_open(datetime(2026, 10, 28, 10, 0, tzinfo=IST))
    assert not is_market_open(datetime(2026, 10, 28, 15, 30, tzinfo=IST))
    assert not is_market_open(datetime(2026, 10, 28, 9, 0, tzinfo=IST))


def test_symbols_and_ticks():
    assert yahoo_symbol("reliance") == "RELIANCE.NS"
    assert yahoo_symbol("TCS", "BSE") == "TCS.BO"
    assert yahoo_symbol("INFY.NS") == "INFY.NS"
    assert broker_symbol("INFY.BO") == ("INFY", "BSE")
    assert round_to_tick(100.01, side="BUY") == 100.05
    assert round_to_tick(100.04, side="SELL") == 100.0
    assert round_to_tick(100.05, side="BUY") == 100.05


def test_delivery_costs():
    cm = CostModel()
    buy = cm.charges("BUY", 100, 1000)     # turnover 1 lakh
    # STT 100 + stamp 15 + exchange 2.97 + sebi 0.10 + GST 18% of 3.07
    assert abs(buy - (100 + 15 + 2.97 + 0.10 + 0.18 * 3.07)) < 0.05
    sell = cm.charges("SELL", 100, 1000)
    assert abs(sell - (100 + 2.97 + 0.10 + 0.18 * 3.07 + 15.34)) < 0.05


def test_intraday_brokerage_cap():
    cm = CostModel()
    small = cm.charges("BUY", 10, 100, "MIS")    # 0.03% of 1000 = 0.30
    big = cm.charges("BUY", 1000, 1000, "MIS")   # capped at 20
    assert small < 1
    # turnover 10 lakh: brokerage capped at 20, stamp 30, exchange 29.70, SEBI 1, GST on (20 + 29.70 + 1)
    assert abs(big - (20 + 30 + 29.70 + 1 + 0.18 * 50.70)) < 0.05
