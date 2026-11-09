import json
from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from indtrader import crypto_learn
from indtrader.crypto_learn import Learner, baseline, nw_tstat, state


class FakeAPI:
    """Daily closes on a gentle uptrend, a settable live price, and 1-minute klines at any requested time."""

    def __init__(self, price=100.0):
        self.price = price
        self.future = {}                      # due timestamp (s) -> price

    def quotes(self, coins):
        return {c: {"bid": self.price, "ask": self.price, "last": self.price, "change_pct": 0.0} for c in coins}

    def daily(self, coin, limit=400):
        idx = pd.date_range(end=pd.Timestamp(datetime.now(UTC).date()) - pd.Timedelta(days=1), periods=limit, freq="D")
        rng = np.random.default_rng(1)
        close = 80 * np.exp(np.cumsum(rng.normal(0.0005, 0.02, limit)))
        return pd.DataFrame({"open": close, "close": close, "value": 1e9}, index=idx)

    def _get(self, path, **p):
        t = p["startTime"] / 1000
        px = self.future.get(round(t), self.price)
        return [[p["startTime"], str(px), str(px), str(px), str(px)]]


class FakeFeeds:
    def __init__(self, fg=80, funding=0.05):
        self.fg, self.f = fg, funding

    def fear_greed(self):
        return {"value": self.fg, "label": "Greed", "change_7d": 5}

    def funding(self, coin):
        return {"last_pct": self.f, "avg3d_pct": self.f, "annual_pct": self.f * 3 * 365}


def learner(tmp_path, **kw):
    return Learner(tmp_path, api=FakeAPI(**kw), feeds=FakeFeeds(), lessons=tmp_path / "lessons.json")


def test_baseline_is_a_coin_flip_with_a_volatility_range():
    b = baseline(100.0, 0.02, 24)
    assert b["p_up"] == 0.5 and b["lo"] < 100 < b["hi"]
    wide = baseline(100.0, 0.02, 168)
    assert wide["hi"] - wide["lo"] > b["hi"] - b["lo"]          # a longer horizon gets a wider range


def test_state_tags_come_from_the_data():
    close = pd.Series(np.linspace(50, 100, 400))
    st = state(close, 101.0, {"value": 85}, {"avg3d_pct": 0.05})
    assert {"above_50d", "above_200d", "fg_extreme_greed", "funding_high"} <= set(st["tags"])
    st = state(close[::-1].reset_index(drop=True), 49.0, {"value": 10}, {"avg3d_pct": -0.01})
    assert {"below_50d", "fg_extreme_fear", "funding_negative"} <= set(st["tags"])


def test_record_writes_the_call_and_a_baseline_and_blocks_rapid_repeats(tmp_path):
    ln = learner(tmp_path)
    rows = ln.record("btc", 24, 0.6, 95, 105, "test")
    assert [r["source"] for r in rows] == ["llm", "base"] and rows[0]["id"] == rows[1]["id"]
    assert rows[1]["p_up"] == 0.5 and rows[0]["tags"] == rows[1]["tags"]
    with pytest.raises(ValueError):
        ln.record("BTC", 24, 0.6, 95, 105, "again")             # within 6 hours
    with pytest.raises(ValueError):
        ln.record("ETH", 24, 0.6, 101, 105, "range must contain the price")
    with pytest.raises(ValueError):
        ln.record("ETH", 24, 1.0, 95, 105, "certainty is not allowed")


def test_score_grades_due_calls_with_brier_and_range(tmp_path, monkeypatch):
    ln = learner(tmp_path)
    ln.record("BTC", 24, 0.8, 95, 105, "bullish")
    later = datetime.now(UTC) + timedelta(hours=25)
    monkeypatch.setattr(crypto_learn, "now_utc", lambda: later)
    due = datetime.fromisoformat(next(r for r in crypto_learn._read(ln.fc))["due"])
    ln.api.future[round(due.timestamp())] = 110.0                 # price rose, outside the LLM's range
    rows = {r["source"]: r for r in ln.score()}
    assert rows["llm"]["up"] == 1 and rows["llm"]["brier"] == pytest.approx(0.04)
    assert rows["base"]["brier"] == pytest.approx(0.25)
    assert rows["llm"]["inside"] == 0
    assert ln.score() == []                                        # nothing is scored twice
    s = ln.summary()["24h"]
    assert s["n"] == 1 and s["brier_llm"] < s["brier_base"] and s["verdict"] == "too few calls to tell"


def test_newey_west_t_shrinks_with_overlap():
    rng = np.random.default_rng(0)
    x = np.repeat(rng.normal(0.05, 0.2, 100), 3)                  # each value repeated: heavy overlap
    assert abs(nw_tstat(x, 3)) < abs(nw_tstat(x, 0))


def test_lessons_change_status_only_on_evidence(tmp_path, monkeypatch):
    ln = learner(tmp_path)
    ln.lessons.write_text(json.dumps([
        {"id": "greed", "lesson": "In extreme greed my up-calls are too bullish", "tag": "fg_extreme_greed",
         "horizon_h": 24, "expect": "worse", "status": "hypothesis"},
        {"id": "mkt", "lesson": "In extreme greed BTC falls over the next day", "kind": "market",
         "tag": "fg_extreme_greed", "horizon_h": 24, "expect": "down", "status": "hypothesis"},
    ]))
    # 40 scored pairs where the LLM said 80% up and the price fell every time
    rows_sc = []
    t0 = datetime(2026, 1, 1, tzinfo=UTC)
    for i in range(40):
        made = (t0 + timedelta(hours=8 * i)).isoformat()
        for src, p in (("llm", 0.8), ("base", 0.5)):
            rows_sc.append({"id": f"f{i}", "source": src, "coin": "BTC", "horizon_h": 24, "made": made, "due": made,
                            "spot": 100, "px": 99, "up": 0, "p_up": p, "brier": round((p - 0) ** 2, 6),
                            "inside": 1, "pinball": 0.1, "tags": "fg_extreme_greed;above_50d"})
    # and 40 calls without the tag, where the price rose 3 times in 4 (the yardstick for the market lesson)
    for i in range(40, 80):
        made = (t0 + timedelta(hours=8 * i)).isoformat()
        up = 0 if i % 4 == 0 else 1
        for src, p in (("llm", 0.5), ("base", 0.5)):
            rows_sc.append({"id": f"f{i}", "source": src, "coin": "BTC", "horizon_h": 24, "made": made, "due": made,
                            "spot": 100, "px": 101 if up else 99, "up": up, "p_up": p, "brier": 0.25,
                            "inside": 1, "pinball": 0.1, "tags": "fg_neutral;above_50d"})
    crypto_learn._append(ln.sc, crypto_learn.SC_COLS, rows_sc)
    out = {le["id"]: le for le in ln.update_lessons()}
    assert out["greed"]["status"] == "confirmed" and out["greed"]["evidence"]["n"] == 40
    ev = out["mkt"]["evidence"]
    assert out["mkt"]["status"] == "confirmed" and ev["up_pct"] == 0.0 and ev["other_up_pct"] == 75.0


def test_market_lesson_needs_a_contrast_not_a_coin_flip(tmp_path):
    """If every call carries the tag, there is nothing to compare with, so the lesson cannot be confirmed."""
    ln = learner(tmp_path)
    ln.lessons.write_text(json.dumps([{"id": "m", "lesson": "x", "kind": "market", "tag": "fg_fear", "horizon_h": 24,
                                       "expect": "up", "status": "hypothesis"}]))
    t0 = datetime(2026, 1, 1, tzinfo=UTC)
    rows = [{"id": f"f{i}", "source": "base", "coin": "BTC", "horizon_h": 24, "made": (t0 + timedelta(hours=8 * i)).isoformat(),
             "due": "", "spot": 100, "px": 101, "up": 1, "p_up": 0.5, "brier": 0.25, "inside": 1, "pinball": 0.1,
             "tags": "fg_fear"} for i in range(60)]
    crypto_learn._append(ln.sc, crypto_learn.SC_COLS, rows)
    le = ln.update_lessons()[0]
    assert le["status"] == "hypothesis" and le["evidence"]["t"] is None
