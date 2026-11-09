import pytest

from indtrader.research import prereg


def test_missing_preregistration_refuses_to_run():
    with pytest.raises(prereg.NotPreregistered):
        prereg.require_committed("NO_SUCH_TEST")


def test_trial_ledger_counts_distinct_variants(tmp_path, monkeypatch):
    monkeypatch.setattr(prereg, "TRIALS", tmp_path / "trials.csv")
    prereg.log_trial("X", "a", "design", "sharpe", 0.5, kind="design")
    prereg.log_trial("X", "a", "test", "sharpe", 0.4)          # same variant, another period: still one trial
    prereg.log_trial("X", "b", "design", "sharpe", 0.1, kind="design")
    prereg.log_trial("Y", "a", "design", "sharpe", 0.1, kind="design", asset="stocks")
    assert prereg.trial_count("crypto") == 2 and prereg.trial_count("stocks") == 1
