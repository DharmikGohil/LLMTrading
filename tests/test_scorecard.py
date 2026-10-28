import json

import numpy as np
import pandas as pd

from indtrader.scorecard import collect_signals, grade, summarize


def test_scorecard_end_to_end(tmp_path):
    root = tmp_path / "signals"
    d = root / "2026-01-05"
    d.mkdir(parents=True)
    for sym, rating in (("UP", "Buy"), ("DOWN", "Sell"), ("FLAT", "Hold")):
        (d / f"{sym}.json").write_text(json.dumps({"symbol": sym, "rating": rating, "source": "claude-analyst"}))
    (d / "_screen.json").write_text(json.dumps({"candidates": ["UP", "DOWN"]}))
    idx = pd.bdate_range("2026-01-05", periods=30)
    series = {"UP": pd.Series(np.linspace(100, 130, 30), idx), "DOWN": pd.Series(np.linspace(100, 80, 30), idx),
              "FLAT": pd.Series(100.0, idx)}
    nifty = pd.Series(np.linspace(100, 102, 30), idx)

    sig = collect_signals({"x": root})
    assert set(sig["source"]) == {"claude-analyst", "momentum-screen"}
    graded = grade(sig, lambda s: series[s], nifty, horizon=10)
    summ = summarize(graded).set_index("source")
    a = summ.loc["claude-analyst"]
    assert a["graded"] == 3 and a["hit_rate_pct"] == 100.0 and a["rank_ic"] > 0.9
    assert a["bullish_mean_excess_pct"] > 0 > a["bearish_mean_excess_pct"]
    m = summ.loc["momentum-screen"]
    assert m["hit_rate_pct"] == 50.0                                   # one Buy up, one Buy down
    late = grade(sig, lambda s: series[s].iloc[:5], nifty, horizon=10)   # window not elapsed
    assert summarize(late)["pending"].sum() == len(sig)
