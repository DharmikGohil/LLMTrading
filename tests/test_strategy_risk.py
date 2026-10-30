from indtrader.config import RiskSettings, StrategySettings
from indtrader.risk import AccountView, check_buy, check_sell
from indtrader.signals.llm_agent import LLMSignal
from indtrader.signals.technical import TechnicalSnapshot, snapshot
from indtrader.strategy import plan_target, protective_levels

S, R = StrategySettings(), RiskSettings(capital=100000)
UP = TechnicalSnapshot(close=100, ema_trend=95, rsi=60, atr=2)
DOWN = TechnicalSnapshot(close=100, ema_trend=105, rsi=40, atr=2)


def test_buy_sizes_by_risk_and_allocation():
    p = plan_target("X", "Buy", 100, UP, 0, 100000, S, R)
    # ATR stop = 100 - 2*2 = 96 -> risk 4/share -> 1000/4 = 250; alloc 20% = 200 shares
    assert p.target_qty == 200
    assert p.stop == 96.0 and p.take_profit == 110.0


def test_llm_stop_used_when_sane_else_atr():
    assert protective_levels(100, UP, S, llm_stop=92)[0] == 92
    assert protective_levels(100, UP, S, llm_stop=99.5)[0] == 96   # too tight -> ATR fallback
    assert protective_levels(100, UP, S, llm_stop=50)[0] == 96     # too wide -> ATR fallback


def test_filters_block_entries():
    assert plan_target("X", "Buy", 100, DOWN, 0, 100000, S, R).target_qty == 0
    hot = TechnicalSnapshot(close=100, ema_trend=90, rsi=85, atr=2)
    assert plan_target("X", "Buy", 100, hot, 0, 100000, S, R).target_qty == 0


def test_bearish_only_trims_and_hold_keeps():
    assert plan_target("X", "Sell", 100, UP, 150, 100000, S, R).target_qty == 0
    assert plan_target("X", "Underweight", 100, UP, 150, 100000, S, R).target_qty == 50
    assert plan_target("X", "Underweight", 100, UP, 10, 100000, S, R).target_qty == 10
    assert plan_target("X", "Hold", 100, DOWN, 77, 100000, S, R).target_qty == 77
    assert plan_target("X", "REVIEW", 100, UP, 5, 100000, S, R).target_qty == 5


def _acct(**kw):
    base = dict(cash=100000, equity=100000, start_of_day_equity=100000, gross_exposure=0, open_positions=0, orders_today=0)
    return AccountView(**{**base, **kw})


def test_risk_limits():
    assert check_buy("X", 100, 100, 0, _acct(), R).quantity == 100
    assert check_buy("X", 500, 100, 0, _acct(), R).quantity == 200            # 20% position cap
    assert not check_buy("X", 10, 100, 0, _acct(equity=96000), R).allowed    # kill switch
    assert not check_buy("X", 10, 100, 0, _acct(open_positions=5), R).allowed
    assert check_buy("X", 10, 100, 3, _acct(open_positions=5), R).allowed     # adding to existing is fine
    assert not check_buy("X", 5, 100, 0, _acct(), R).allowed                  # below min order value
    assert not check_buy("X", 100, 110, 0, _acct(), R, analysed_close=100).allowed  # gapped away
    assert check_sell(50, 20).quantity == 20


def test_snapshot(ohlcv):
    snap = snapshot(ohlcv(120, drift=0.01))
    assert snap.uptrend and snap.atr > 0 and 0 <= snap.rsi <= 100


def test_parse_trader_levels():
    state = {
        "trader_investment_plan": "**Action**: Buy\n\n**Entry Price**: ₹2,450.5\n\n**Stop Loss**: 2,310\n",
        "final_trade_decision": "**Rating**: Buy\n\n**Price Target**: Rs. 2800\n",
    }
    sig = LLMSignal.from_state("RELIANCE", "2026-10-27", state, "Buy")
    assert (sig.entry_price, sig.stop_loss, sig.price_target) == (2450.5, 2310.0, 2800.0)
    none = LLMSignal.from_state("X", "2026-10-27", {"trader_investment_plan": "**Stop Loss**: not provided"}, "Hold")
    assert none.stop_loss is None


def test_exposure_scale_and_vol_target():
    import numpy as np
    import pandas as pd

    from indtrader.strategy import vol_scale

    s, r = StrategySettings(), RiskSettings(capital=100000)
    full = plan_target("X", "Buy", 100, UP, 0, 100000, s, r)
    half = plan_target("X", "Buy", 100, UP, 0, 100000, s, r, exposure_scale=0.5)
    none = plan_target("X", "Buy", 100, UP, 0, 100000, s, r, exposure_scale=0.0)
    assert half.target_qty == full.target_qty // 2 and none.target_qty == 0
    assert plan_target("X", "Sell", 100, UP, 50, 100000, s, r, exposure_scale=0.0).target_qty == 0   # exits unaffected

    rng = np.random.default_rng(0)
    calm = pd.Series(100 * np.cumprod(1 + 0.005 * rng.standard_normal(200)))
    wild = pd.Series(100 * np.cumprod(1 + 0.03 * rng.standard_normal(200)))
    assert vol_scale(calm, s) == 1.0                       # off by default
    s.vol_target = 0.15
    assert vol_scale(calm, s) == 1.0 and 0 < vol_scale(wild, s) < 0.5
