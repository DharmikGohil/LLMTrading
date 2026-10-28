import numpy as np
import pandas as pd
import pytest

from indtrader.config import Settings


@pytest.fixture
def settings(tmp_path):
    s = Settings(universe=["AAA", "BBB"], data_dir=str(tmp_path / "state"))
    s.broker.paper_state_file = str(tmp_path / "state" / "paper.json")
    s.strategy.signal_mode = "llm"      # most tests exercise the LLM-driven path; hybrid has its own tests
    s.nse_checks = False                # no network in tests
    return s


def make_ohlcv(n=250, start=100.0, drift=0.002, seed=0, start_date="2025-01-01"):
    rng = np.random.default_rng(seed)
    close = start * np.exp(np.cumsum(drift + 0.01 * rng.standard_normal(n)))
    idx = pd.bdate_range(start_date, periods=n)
    openp = np.r_[close[0], close[:-1]] * (1 + 0.002 * rng.standard_normal(n))
    high = np.maximum(openp, close) * 1.01
    low = np.minimum(openp, close) * 0.99
    return pd.DataFrame({"Open": openp, "High": high, "Low": low, "Close": close, "Volume": 1e6}, index=idx)


@pytest.fixture
def ohlcv():
    return make_ohlcv
