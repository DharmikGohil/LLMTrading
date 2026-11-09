import csv
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from indtrader.research import prereg

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("study_round_numbers", ROOT / "scripts" / "study_round_numbers.py")
srn = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(srn)


def test_scale_and_spacing():
    p = np.array([7521.0, 9999.99, 10000.0, 10000.01, 99.5, 100.0, 1000.0, 999.9])
    assert srn.scale(p).tolist() == [1000, 1000, 10000, 10000, 10, 100, 1000, 100]
    assert srn.spacing([65000.0], "major").tolist() == [10000]
    assert srn.spacing([65000.0], "minor").tolist() == [1000]
    assert srn.spacing([85.0], "minor").tolist() == [1]          # ETH below $100: minors every $1
    assert np.isnan(srn.scale([np.nan])[0])


def test_cluster_hits_strictly_below_and_above():
    g = np.full(6, 1000.0)
    high = np.array([9960.0, 9940.0, 10000.0, 9951.0, 10001.0, 10990.0])
    low = np.array([10040.0, 10060.0, 10000.0, 10049.0, 9999.0, 11050.0])
    hh, hl, above, below = srn.cluster_hits(high, low, g, [0.0])
    assert hh[0].tolist() == [True, False, False, True, False, True]    # 10,000 exactly reached it: not "below"
    assert above[0, 2] == 11000.0
    assert hl[0].tolist() == [True, False, False, True, False, True]
    assert below[0, 2] == 9000.0
    # an offset of half the spacing moves the levels to ...9,500 / 10,500...
    hh, hl, _, _ = srn.cluster_hits(np.array([10460.0]), np.array([10540.0]), np.array([1000.0]), [0.5])
    assert hh[0, 0] and hl[0, 0]


def test_fresh_crossings_ten_day_rule():
    c = np.full(48, 9500.0)
    c[20] = 10100.0                    # day 20: fresh up-cross of 10,000
    c[31] = 10200.0                    # day 31: 10,000 was crossed (down) on day 21, which is t-10: blocked
    c[33] = 10200.0                    # day 33: 10,000 crossed on days 31 and 32: blocked
    c[46] = 10200.0                    # day 46: last crossing of 10,000 on day 34 (t-12): fresh again
    g = np.full(48, 1000.0)
    ev = srn.fresh_crossings(c, g, [0.0])[0]
    assert ev[20] == 1 and ev[21] == 0 and ev[31] == 0 and ev[33] == 0 and ev[46] == 1
    assert set(np.nonzero(ev)[0]) == {20, 46}
    # a crossing exactly 11 days earlier no longer blocks: day 21 down-cross, day 32 up-cross
    c2 = np.full(40, 9500.0)
    c2[20] = 10100.0
    c2[32] = 10100.0
    ev2 = srn.fresh_crossings(c2, np.full(40, 1000.0), [0.0])[0]
    assert ev2[32] == 1


def test_fresh_crossings_down_multi_level_and_warmup():
    c = np.r_[np.full(15, 8300.0), 5900.0, 5800.0]
    ev = srn.fresh_crossings(c, np.full(len(c), 1000.0), [0.0])[0]
    assert ev[15] == -1 and ev[16] == 0          # 8,000, 7,000 and 6,000 at once is one event; 5,800 crosses none
    early = np.r_[np.full(5, 9500.0), 10100.0]
    assert srn.fresh_crossings(early, np.full(6, 1000.0), [0.0])[0].tolist() == [0] * 6   # needs 11 earlier closes


def test_forward_moves_and_after_tax():
    o = np.array([100.0, 101.0, 102.0, 103.0, 104.0])
    c = np.array([101.0, 102.0, 103.0, 104.0, 105.0])
    r1 = srn.forward_moves(o, c, 1)
    assert r1[0] == pytest.approx(102.0 / 101.0 - 1) and np.isnan(r1[-1])
    r3 = srn.forward_moves(o, c, 3)
    assert r3[0] == pytest.approx(104.0 / 101.0 - 1) and np.isnan(r3[2])
    assert srn.after_tax(np.array([0.1, -0.1, np.nan])).tolist()[:2] == pytest.approx([0.0688, -0.1])


def test_day_mean_averages_coins_first():
    v = np.array([[0.02, 0.04], [np.nan, -0.03], [np.nan, np.nan]])
    m, daily = srn.day_mean(v)
    assert daily[0] == pytest.approx(0.03) and daily[1] == pytest.approx(-0.03) and np.isnan(daily[2])
    assert m == pytest.approx(0.0)


def test_vs_random_needs_strictly_above_p95():
    r = np.arange(1000, dtype=float)
    p95 = float(np.quantile(r, 0.95, method="higher"))
    assert not srn.vs_random(p95, r)["above_p95"]
    assert srn.vs_random(p95 + 0.5, r)["above_p95"]
    assert srn.vs_random(5000.0, np.r_[r, np.nan])["n_random"] == 1000


def test_episodes():
    d = pd.to_datetime(["2020-01-01", "2020-01-05", "2020-01-15", "2020-01-26", "2020-01-26"])
    assert srn.episodes(d) == 2            # gaps 4, 10 (same episode), 11 (new)
    assert srn.episodes([]) == 0


def test_crossing_episodes_need_more_than_ten_quiet_days():
    # pre-registration: a new crossing episode starts after MORE than 10 days without an event
    ten_quiet = pd.to_datetime(["2020-01-01", "2020-01-12"])        # Jan 2..11: 10 days without an event
    eleven_quiet = pd.to_datetime(["2020-01-01", "2020-01-13"])     # Jan 2..12: 11 days without an event
    assert srn.crossing_episodes(ten_quiet) == 1
    assert srn.crossing_episodes(eleven_quiet) == 2
    assert srn.crossing_episodes([]) == 0


def test_calendar_portfolio_drawdown_counts_from_starting_capital():
    idx = pd.date_range("2020-01-01", periods=4, freq="D")
    o = np.array([[100.0], [100.0], [100.0], [90.0]])
    c = np.array([[100.0], [90.0], [90.0], [90.0]])
    ev = np.zeros((4, 1), dtype=np.int8)
    ev[0, 0] = 1                                             # long from day 1's open; day 1 loses 10%
    pf = srn.calendar_portfolio(o, c, ev, 1, 0.0, idx, 1)    # the reported window starts on the losing day
    assert pf["max_drawdown"] == pytest.approx(-0.10, abs=1e-9)


def _synthetic(tmp_path, days=1900, seed=1):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2018-06-01", periods=days, freq="D")          # runs into 2023
    for coin, start in (("BTC", 7500.0), ("ETH", 580.0)):
        close = start * np.exp(np.cumsum(0.03 * rng.standard_normal(days)))
        close[idx > "2022-12-31"] = 1e9                                  # poison: must never be read
        op = np.r_[start, close[:-1]]
        df = pd.DataFrame({"date": idx.strftime("%Y-%m-%d"), "open": op, "high": np.maximum(op, close) * 1.01,
                           "low": np.minimum(op, close) * 0.99, "close": close, "volume": 1.0})
        df.to_csv(tmp_path / f"{coin}.csv", index=False)


def test_load_panel_cuts_at_period_end(tmp_path, monkeypatch):
    _synthetic(tmp_path)
    monkeypatch.setattr(srn, "DATA", tmp_path)
    panel = srn.load_panel("2022-12-31")
    assert set(panel) == {"BTC", "ETH"}
    assert all(df.index.max() == pd.Timestamp("2022-12-31") and df["close"].max() < 1e9 for df in panel.values())


def test_design_run_on_synthetic_data(tmp_path, monkeypatch):
    _synthetic(tmp_path)
    monkeypatch.setattr(srn, "DATA", tmp_path)
    monkeypatch.setattr(srn, "RESULTS", tmp_path / "results")
    monkeypatch.setattr(prereg, "TRIALS", tmp_path / "trials.csv")
    assert srn.main(["--crypto", "--period", "design"]) == 0
    res = json.loads((tmp_path / "results" / "H19c_design.json").read_text())
    assert res["data_to"] == "2022-12-31"
    assert set(res["variants"]) == {"major-clustering", "minor-clustering", "major-crossing", "minor-crossing"}
    cross = res["variants"]["minor-crossing"]
    assert cross["events_coin_days"] > 0
    assert cross["horizons"]["1d"]["lines"]["costs 0.30% pre-tax"]["n_random"] == 1000
    assert cross["horizons"]["7d"]["events_with_outcome"] <= cross["horizons"]["1d"]["events_with_outcome"]
    rows = list(csv.DictReader((tmp_path / "trials.csv").open()))
    assert len(rows) == 4 and {r["kind"] for r in rows} == {"design"} and {r["period"] for r in rows} == {"design"}


def test_test_period_refuses_before_touching_data(monkeypatch):
    def refuse(test_id):
        raise prereg.NotPreregistered(test_id)

    def no_data(*a, **k):
        raise AssertionError("data was read before the pre-registration check")

    monkeypatch.setattr(prereg, "require_committed", refuse)
    monkeypatch.setattr(srn, "load_panel", no_data)
    monkeypatch.setattr(srn, "run", no_data)
    with pytest.raises(prereg.NotPreregistered):
        srn.main(["--crypto", "--period", "test"])
    with pytest.raises(prereg.NotPreregistered):
        srn.main(["--crypto", "--period", "test", "--counts-only"])


def test_stock_part_is_a_stub(capsys):
    assert srn.main([]) == 2
    assert "P0-A" in capsys.readouterr().out


def test_constants_match_the_preregistration():
    srn.check_spec(prereg.load("H19c"))


def test_calendar_portfolio_one_short_event():
    idx = pd.date_range("2020-01-01", periods=5, freq="D")
    o = np.array([[100.0], [100.0], [110.0], [121.0], [121.0]])
    c = np.array([[100.0], [110.0], [121.0], [121.0], [121.0]])
    ev = np.zeros((5, 1), dtype=np.int8)
    ev[0, 0] = -1                                            # down-cross on day 0: short from day 1's open for 2 days
    pf = srn.calendar_portfolio(o, c, ev, 2, 0.0015, idx, 0)
    assert pf["days_invested"] == 2
    assert pf["total_return"] == pytest.approx((1 - 0.10 - 0.0015) * (1 - 0.10 - 0.0015) - 1, abs=1e-6)
    assert pf["max_drawdown"] < 0


def test_test_period_path_on_synthetic_data(tmp_path, monkeypatch):
    rng = np.random.default_rng(3)
    idx = pd.date_range("2018-06-01", "2026-11-08", freq="D")
    for coin, start in (("BTC", 7500.0), ("ETH", 580.0)):
        close = start * np.exp(np.cumsum(0.03 * rng.standard_normal(len(idx))))
        close[idx > "2026-10-31"] = 1e9                          # poison after the fixed end date
        op = np.r_[start, close[:-1]]
        pd.DataFrame({"date": idx.strftime("%Y-%m-%d"), "open": op, "high": np.maximum(op, close) * 1.01,
                      "low": np.minimum(op, close) * 0.99, "close": close, "volume": 1.0}).to_csv(tmp_path / f"{coin}.csv", index=False)
    monkeypatch.setattr(srn, "DATA", tmp_path)
    monkeypatch.setattr(srn, "RESULTS", tmp_path / "results")
    monkeypatch.setattr(prereg, "TRIALS", tmp_path / "trials.csv")
    monkeypatch.setattr(prereg, "require_committed", lambda test_id: prereg.load(test_id))
    assert srn.main(["--crypto", "--period", "test"]) == 0
    res = json.loads((tmp_path / "results" / "H19c_test.json").read_text())
    assert res["period_start"] == "2023-01-01" and res["data_to"] == "2026-10-31"
    clus = res["variants"]["major-clustering"]["highs"]
    assert clus["coin_days"] == 2 * len(pd.date_range("2023-01-01", "2026-10-31"))
    rows = list(csv.DictReader((tmp_path / "trials.csv").open()))
    assert {r["kind"] for r in rows} == {"test"}
