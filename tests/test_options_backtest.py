import math
from datetime import date, timedelta

from indtrader.options_backtest import atm_vol, leg_charges, run, run_lotto, stt_rate, summary


def toy_days(spot_path, expiry=date(2026, 1, 16), start=date(2026, 1, 5)):
    """Daily option closes from a simple model: premium decays with time, moves with the spot."""
    days, d = {}, start
    for spot in spot_path:
        t = max((expiry - d).days, 0.5) / 365
        chain = {}
        for k in range(20000, 26050, 50):
            sd = spot * 0.15 * math.sqrt(t)
            c = max(spot - k, 0) + 0.4 * sd * math.exp(-((k - spot) / sd) ** 2 / 2)
            p = max(k - spot, 0) + 0.4 * sd * math.exp(-((k - spot) / sd) ** 2 / 2)
            chain[(float(k), "CE")], chain[(float(k), "PE")] = (round(c, 2), 100), (round(p, 2), 100)
        days[d] = {"spot": spot, "chains": {expiry: chain}}
        d += timedelta(days=1)
        while d.weekday() >= 5:
            d += timedelta(days=1)
    return days


def test_rates_and_charges_by_date():
    assert stt_rate(date(2023, 1, 2)) == 0.000625 and stt_rate(date(2025, 1, 2)) == 0.001 and stt_rate(date(2026, 5, 4)) == 0.0015
    assert leg_charges(date(2026, 5, 4), "SELL", 10, 65) > leg_charges(date(2023, 1, 2), "SELL", 10, 65)


def test_atm_vol_recovers_the_model():
    days = toy_days([23300] * 9)
    d0 = next(iter(days))
    chain = days[d0]["chains"][date(2026, 1, 16)]
    assert abs(atm_vol(chain, 23300, (date(2026, 1, 16) - d0).days) - 0.15) < 0.03


def test_quiet_market_takes_profit_and_crash_stops():
    calm = run("NIFTY", toy_days([23300] * 9), k=1.0, dte=5)
    assert calm and calm[0].pnl > 0
    crash = run("NIFTY", toy_days([23300] * 5 + [22300, 21800, 21500, 21500]), k=1.0, dte=5)
    assert crash and crash[0].reason == "stop" and crash[0].pnl < 0
    assert summary(calm)["trades"] == 1


def test_lotto_needs_trend_history_and_budget():
    up = toy_days([22800 + 60 * i for i in range(9)] + [23500, 23600])
    tr = run_lotto("NIFTY", up, budget=1000, dte=3)
    assert all(t.legs[0][1] == "CE" for t in tr)
