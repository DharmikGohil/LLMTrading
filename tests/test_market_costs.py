from datetime import date, datetime

from indtrader.costs import CostModel
from indtrader.market import (
    IST,
    broker_symbol,
    is_market_open,
    is_trading_day,
    previous_trading_day,
    round_to_tick,
    tick_size,
    yahoo_symbol,
)


def test_calendar():
    assert not is_trading_day(date(2026, 10, 2))       # Gandhi Jayanti
    assert not is_trading_day(date(2026, 10, 31))      # Saturday
    assert is_trading_day(date(2026, 2, 1))            # Budget-day Sunday session
    assert previous_trading_day(date(2026, 10, 21)) == date(2026, 10, 19)  # skips Dussehra
    assert is_market_open(datetime(2026, 10, 28, 10, 0, tzinfo=IST))
    assert not is_market_open(datetime(2026, 10, 28, 15, 30, tzinfo=IST))
    assert not is_market_open(datetime(2026, 10, 28, 15, 16, tzinfo=IST))   # closing auction (F&O stocks)
    assert is_market_open(datetime(2026, 12, 8, 15, 20, tzinfo=IST))         # after 7 Dec continuous to 15:30
    assert not is_trading_day(date(2026, 1, 15))
    assert not is_market_open(datetime(2026, 10, 28, 9, 0, tzinfo=IST))


def test_symbols_and_ticks():
    assert yahoo_symbol("reliance") == "RELIANCE.NS"
    assert yahoo_symbol("TCS", "BSE") == "TCS.BO"
    assert yahoo_symbol("INFY.NS") == "INFY.NS"
    assert broker_symbol("INFY.BO") == ("INFY", "BSE")
    assert round_to_tick(100.01, tick=0.05, side="BUY") == 100.05
    assert round_to_tick(100.04, tick=0.05, side="SELL") == 100.0
    assert round_to_tick(100.05, tick=0.05, side="BUY") == 100.05
    # NSE price bands (Apr 2025): 0.01 < 250, 0.05 < 1000, 0.10 < 5000, 0.50 < 10000, 1 < 20000, else 5
    assert [tick_size(p) for p in (100, 500, 2500, 7000, 15000, 30000)] == [0.01, 0.05, 0.10, 0.50, 1.00, 5.00]
    assert round_to_tick(100.013, side="BUY") == 100.02
    assert round_to_tick(1412.34, side="BUY") == 1412.4      # 0.10 grid
    assert round_to_tick(1412.34, side="SELL") == 1412.3
    assert round_to_tick(900.03, side="BUY") == 900.1         # near the 1000 edge: coarser 0.10 grid is safe
    assert round_to_tick(2963.0, side="BUY") == 2963.0


def test_delivery_costs():
    cm = CostModel()
    buy = cm.charges("BUY", 100, 1000)     # turnover 1 lakh
    # STT 100 + stamp 15 + exchange 3.07 + sebi 0.10 + GST 18% of 3.17
    assert abs(buy - (100 + 15 + 3.07 + 0.10 + 0.18 * 3.17)) < 0.05
    sell = cm.charges("SELL", 100, 1000)
    assert abs(sell - (100 + 3.07 + 0.10 + 0.18 * 3.17 + 15.34)) < 0.05


def test_intraday_brokerage_cap():
    cm = CostModel()
    small = cm.charges("BUY", 10, 100, "MIS")    # 0.03% of 1000 = 0.30
    big = cm.charges("BUY", 1000, 1000, "MIS")   # capped at 20
    assert small < 1
    # turnover 10 lakh: brokerage capped at 20, stamp 30, exchange 30.70, SEBI 1, GST on (20 + 30.70 + 1)
    assert abs(big - (20 + 30 + 30.70 + 1 + 0.18 * 51.70)) < 0.05
