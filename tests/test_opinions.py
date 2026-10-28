import json
import os
import stat
from datetime import date

import pandas as pd
import pytest

from indtrader.config import RiskSettings, SecondOpinionSettings, StrategySettings
from indtrader.market import now_ist, previous_trading_day
from indtrader.signals.llm_agent import LLMSignal, consensus
from indtrader.signals.technical import TechnicalSnapshot, is_bear_market
from indtrader.signals.vibe_opinion import VibeTradingAnalyzer, parse_verdict
from indtrader.strategy import combine_opinions, plan_target

S, R = StrategySettings(), RiskSettings(capital=100000)
UP = TechnicalSnapshot(close=100, ema_trend=95, rsi=60, atr=2)


def _sig(rating, conf=None):
    return LLMSignal("X", "2026-10-27", rating, confidence=conf, source="vibe-trading")


# ---------------------------------------------------------------- consensus
@pytest.mark.parametrize("ratings, expected", [
    (["Buy", "Buy", "Buy"], ("Buy", 100.0)),
    (["Buy", "Overweight", "Hold"], ("Overweight", 66.7)),      # cautious median of the bullish side
    (["Buy", "Sell", "Hold"], ("Hold", 33.3)),                  # no majority -> Hold
    (["Sell", "Underweight", "Buy"], ("Underweight", 66.7)),
    (["Buy", "REVIEW", "REVIEW"], ("Hold", 0.0)),               # one vote out of three is not a majority
    (["REVIEW", "REVIEW"], ("REVIEW", 0.0)),
])
def test_consensus(ratings, expected):
    assert consensus(ratings) == expected


# ---------------------------------------------------------------- second opinion
def test_second_opinion_disabled_passes_through():
    assert combine_opinions("Buy", _sig("Sell", 90), SecondOpinionSettings(enabled=False)) == ("Buy", "")


def test_veto_mode():
    cfg = SecondOpinionSettings(enabled=True, mode="veto", min_confidence=50)
    assert combine_opinions("Buy", _sig("Sell", 80), cfg)[0] == "Hold"
    assert combine_opinions("Buy", _sig("Sell", 30), cfg)[0] == "Buy"            # low confidence ignored
    assert combine_opinions("Buy", _sig("Hold", 70), cfg)[0] == "Overweight"     # softened
    assert combine_opinions("Overweight", _sig("Buy", 70), cfg)[0] == "Overweight"
    # can never add risk or block a sell
    assert combine_opinions("Hold", _sig("Buy", 99), cfg)[0] == "Hold"
    assert combine_opinions("Sell", _sig("Buy", 99), cfg)[0] == "Sell"
    assert combine_opinions(None, _sig("Buy", 99), cfg)[0] is None


def test_confirm_mode_and_missing():
    cfg = SecondOpinionSettings(enabled=True, mode="confirm", min_confidence=60)
    assert combine_opinions("Buy", _sig("Overweight", 70), cfg)[0] == "Buy"
    assert combine_opinions("Buy", _sig("Overweight", 40), cfg)[0] == "Hold"
    assert combine_opinions("Buy", _sig("Hold", 90), cfg)[0] == "Hold"
    assert combine_opinions("Buy", None, cfg)[0] == "Hold"
    assert combine_opinions("Buy", _sig("REVIEW"), cfg)[0] == "Hold"
    proceed = SecondOpinionSettings(enabled=True, on_missing="proceed")
    assert combine_opinions("Buy", None, proceed)[0] == "Buy"


def test_parse_verdict():
    memo = "The bull case cited a FINAL RATING: Buy from a broker...\n\nDecision...\nFINAL RATING: **Underweight**\nCONFIDENCE: 72"
    assert parse_verdict(memo) == ("Underweight", 72.0)
    assert parse_verdict("no verdict here") == ("REVIEW", None)
    assert parse_verdict("FINAL RATING: hold\nCONFIDENCE: 250") == ("Hold", 100.0)


# ---------------------------------------------------------------- regime / holding period
def test_bear_regime_and_min_hold():
    normal = plan_target("X", "Buy", 100, UP, 0, 100000, S, R)
    bear = plan_target("X", "Buy", 100, UP, 0, 100000, S, R, bear_market=True)
    assert bear.target_qty == normal.target_qty // 2
    young = plan_target("X", "Sell", 100, UP, 100, 100000, S, R, held_days=1)
    assert young.target_qty == 100
    old = plan_target("X", "Sell", 100, UP, 100, 100000, S, R, held_days=10)
    assert old.target_qty == 0


def test_is_bear_market():
    up = pd.Series(range(1, 301), dtype=float)
    assert not is_bear_market(up)
    assert is_bear_market(pd.concat([up, pd.Series([50.0])], ignore_index=True))
    assert not is_bear_market(up[:50])


# ---------------------------------------------------------------- Vibe-Trading subprocess bridge
def _fake_python(tmp_path, payload: dict, noise: str = "log line\n"):
    script = tmp_path / "fake-python"
    script.write_text(f"#!/bin/sh\nprintf '%s' '{noise}'\necho '{json.dumps(payload)}'\n")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return str(script)


def test_vibe_analyzer_parses_and_caches(settings, tmp_path):
    settings.second_opinion.enabled = True
    settings.second_opinion.vibe_python = _fake_python(
        tmp_path, {"ok": True, "status": "completed", "final_report": "memo\\nFINAL RATING: Sell\\nCONFIDENCE: 65"})
    an = VibeTradingAnalyzer(settings)
    as_of = previous_trading_day(now_ist().date())
    sig = an.analyze("RELIANCE", as_of)
    assert (sig.rating, sig.confidence, sig.source) == ("Sell", 65.0, "vibe-trading")
    os.remove(settings.second_opinion.vibe_python)          # cached: no second subprocess call
    assert an.analyze("RELIANCE", as_of).rating == "Sell"


def test_vibe_analyzer_errors(settings, tmp_path):
    settings.second_opinion.vibe_python = _fake_python(tmp_path, {"ok": False, "error": "no API key"})
    an = VibeTradingAnalyzer(settings)
    with pytest.raises(RuntimeError, match="no API key"):
        an.analyze("TCS", previous_trading_day(now_ist().date()))
    with pytest.raises(ValueError, match="look-ahead"):
        an.analyze("TCS", date(2024, 1, 2))
    settings.second_opinion.vibe_python = str(tmp_path / "missing-python")
    assert "not found" in VibeTradingAnalyzer(settings).check()["error"]
