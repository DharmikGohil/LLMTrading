import numpy as np
import pandas as pd

from indtrader.validation import bootstrap_sharpe_ci, deflated_sharpe, walk_forward


def _curve(drift, n=500, seed=0):
    rng = np.random.default_rng(seed)
    return pd.Series(100000 * np.cumprod(1 + drift + 0.01 * rng.standard_normal(n)), index=pd.bdate_range("2024-01-01", periods=n))


def test_bootstrap_detects_edge_and_noise():
    strong = bootstrap_sharpe_ci(_curve(0.003))
    assert strong["edge_shown"] and strong["ci_low"] < strong["sharpe"] < strong["ci_high"]
    assert not bootstrap_sharpe_ci(_curve(0.0, seed=1))["edge_shown"]


def test_walk_forward_windows():
    eq = _curve(0.002)
    out = walk_forward(eq, 4, benchmark=eq * 0 + 100000)
    assert len(out["windows"]) == 4 and out["measured_on"] == "excess_pct"
    assert out["windows"][0]["start"] == "2024-01-01"


def test_deflated_sharpe_penalises_many_trials():
    eq = _curve(0.0008, n=700, seed=3)
    one, many = deflated_sharpe(eq, 1), deflated_sharpe(eq, 50)
    assert many["sharpe_hurdle"] > one["sharpe_hurdle"] == 0
    assert many["deflated_sharpe"] < one["deflated_sharpe"]
    assert deflated_sharpe(_curve(0.004, seed=4), 10)["verdict"] == "robust"
    assert deflated_sharpe(_curve(0.0, seed=5), 10)["verdict"] == "likely luck"
