"""H10c study script: levels exactly as chart.py codes them, the hit/bounce rules, random levels, the test-period lock."""

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from indtrader.crypto import universe
from indtrader.research.prereg import NotPreregistered
from indtrader.signals.chart import support_resistance
from indtrader.signals.technical import atr

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("study_candles_levels", ROOT / "scripts" / "study_candles_levels.py")
S = importlib.util.module_from_spec(_spec)
sys.modules["study_candles_levels"] = S      # dataclasses need their module registered
_spec.loader.exec_module(S)


def make_seg(n=420, start=100.0, seed=1, coin="AAA", vol=0.03):
    rng = np.random.default_rng(seed)
    c = start * np.exp(np.cumsum(vol * rng.standard_normal(n)))
    o = np.r_[c[0], c[:-1]] * (1 + 0.005 * rng.standard_normal(n))
    h = np.maximum(o, c) * (1 + np.abs(0.01 * rng.standard_normal(n)))
    lo = np.minimum(o, c) * (1 - np.abs(0.01 * rng.standard_normal(n)))
    dates = pd.date_range("2019-01-01", periods=n, freq="D").to_numpy()
    return S.Seg(coin, dates, o, h, lo, c)


def chart_levels(seg, e):
    lv = support_resistance(seg.frame().iloc[e - 249: e + 1])
    return sorted(x["price"] for x in lv["support"]), sorted(x["price"] for x in lv["resistance"])


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_levels_match_chart_code_every_day(seed):
    seg = make_seg(seed=seed)
    for e in range(249, len(seg)):
        sup, res = S.levels_at(seg, e, round_prices=True)
        assert (sorted(sup), sorted(res)) == chart_levels(seg, e)
        assert (sorted(sup), sorted(res)) == tuple(sorted(x) for x in S.levels_exact(seg, e))


def test_unrounded_levels_differ_only_by_rounding_for_cheap_coins():
    seg = make_seg(start=0.05, seed=4)
    diffs = 0
    for e in range(249, len(seg), 7):
        sup, res = S.levels_at(seg, e, round_prices=False)
        assert all(p > 0 for p in sup + res)
        diffs += any(abs(p - round(p, 2)) > 1e-12 for p in sup + res)
    assert diffs > 0                     # rounding to cents would move these levels


def test_levels_match_on_btc_design_data():
    f = ROOT / "data" / "crypto" / "BTC.csv"
    if not f.exists():
        pytest.skip("data/crypto not downloaded")
    seg = S.to_segs("BTC", S.read_coin("BTC", "2022-12-31"))[0]
    for e in range(249, len(seg), 9):
        sup, res = S.levels_at(seg, e, round_prices=True)
        assert (sorted(sup), sorted(res)) == chart_levels(seg, e)


def test_windowed_atr_is_chart_atr_on_the_window():
    seg = make_seg(n=300)
    w = S.windowed_atr(seg)
    assert np.isnan(w[248]) and not np.isnan(w[249])
    for e in (249, 260, 299):
        want = float(atr(seg.frame().iloc[e - 249: e + 1]).iloc[-1])
        assert w[e] == pytest.approx(want, rel=1e-10)


def test_first_hit_walks_back_to_touch_or_away():
    p, a = np.array([100.0]), np.array([10.0])            # touch band [98, 102]; away: low >= 110 or high <= 90
    lo = np.array([99, 120, 111, 104, 0.0])
    hi = np.array([105, 130, 115, 108, 0.0])
    assert S.first_hit(lo, hi, np.array([4]), p, a)[0]     # bar 2 is away before bar 0's touch
    lo2 = np.array([120, 101, 104, 104, 0.0])
    hi2 = np.array([130, 106, 108, 108, 0.0])
    assert not S.first_hit(lo2, hi2, np.array([4]), p, a)[0]  # touched at bar 1, never 1 ATR away since
    lo3 = np.full(5, 104.0)
    hi3 = np.full(5, 108.0)
    assert S.first_hit(lo3, hi3, np.array([4]), p, a)[0]    # nothing found: first hit


def manual_seg(closes, lows=None, highs=None):
    c = np.asarray(closes, float)
    lo = np.asarray(lows if lows is not None else c - 5, float)
    hi = np.asarray(highs if highs is not None else c + 5, float)
    return S.Seg("X", pd.date_range("2020-01-01", periods=len(c)).to_numpy(), c.copy(), hi, lo, c)


def test_support_hit_bounce_and_break():
    base = [120.0] * 10
    lows = [115.0] * 10 + [101, 95, 99, 105, 110]
    highs = [125.0] * 10 + [110, 106, 108, 112, 115]
    seg = manual_seg(base + [105, 99, 104, 110, 112], lows, highs)
    r, p, side, a = np.array([10]), np.array([100.0]), np.array([1]), np.array([10.0])
    sc = S.score_levels(seg, r, p, side, a)
    assert sc["first"][0] and sc["bounce"][0] and sc["valid"][0] and sc["money_ok"][0]
    seg2 = manual_seg(base + [105, 99, 97, 110, 112], lows, highs)  # a close at 97 is 0.3 ATR through
    sc2 = S.score_levels(seg2, r, p, side, a)
    assert sc2["first"][0] and not sc2["bounce"][0]
    lows_miss = [115.0] * 10 + [103, 95, 99, 105, 110]               # low 103 is above the 0.2 ATR zone
    sc3 = S.score_levels(manual_seg(base + [105, 99, 104, 110, 112], lows_miss, highs), r, p, side, a)
    assert not sc3["first"][0]


def test_resistance_is_the_mirror_and_window_must_fit():
    base = [120.0] * 10
    highs = [125.0] * 10 + [139, 135, 130, 128]
    lows = [115.0] * 10 + [118, 117, 116, 115]
    seg = manual_seg(base + [130, 141, 125, 122], lows, highs)
    sc = S.score_levels(seg, np.array([10]), np.array([140.0]), np.array([-1]), np.array([10.0]))
    assert sc["first"][0] and sc["bounce"][0] and sc["valid"][0]
    assert not sc["money_ok"][0]                                       # no open at r+4
    seg_short = manual_seg(base + [130, 141], lows[:12], highs[:12])
    sc2 = S.score_levels(seg_short, np.array([10]), np.array([140.0]), np.array([-1]), np.array([10.0]))
    assert sc2["first"][0] and not sc2["valid"][0]


def test_membership_matches_indtrader_universe():
    rng = np.random.default_rng(0)
    days = pd.date_range("2020-01-01", periods=300)
    closes, vol = {}, {}
    for k in range(26):
        s = pd.Series(np.exp(np.cumsum(0.02 * rng.standard_normal(300))), index=days)
        v = pd.Series(rng.lognormal(10 + k % 5, 1, 300), index=days)
        start = int(rng.integers(0, 150))
        stop = 300 if k % 7 else int(rng.integers(200, 300))
        s.iloc[:start] = np.nan
        s.iloc[stop:] = np.nan
        v[s.isna()] = np.nan
        closes[f"C{k}"], vol[f"C{k}"] = s, v
    closes, vol = pd.DataFrame(closes), pd.DataFrame(vol)
    member = S.top_n_membership(closes, vol)
    value30 = vol.rolling(30, min_periods=20).mean()
    for day in days[130::11]:
        assert set(member.columns[member.loc[day]]) == set(universe(closes, value30, day))


def test_split_gaps_cuts_long_halts_only():
    idx = pd.DatetimeIndex(list(pd.date_range("2022-01-01", periods=5)) + list(pd.date_range("2022-01-09", periods=3))
                           + list(pd.date_range("2022-03-01", periods=4)))
    df = pd.DataFrame({"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1.0}, index=idx)
    assert [len(p) for p in S.split_gaps(df)] == [8, 4]


def test_trade_return_costs_and_tax_line():
    o = np.array([100, 100, 101, 102, 103, 110.0])
    got = S.trade_return(o, np.array([0]))[0]
    assert got == pytest.approx(103 * (1 - 0.0015) / (100 * 1.0015) - 1)
    assert S.trade_return(o, np.array([0]), 0.003)[0] < got
    assert S.after_tax(np.array([0.10, -0.05])) == pytest.approx([0.0688, -0.05])


def test_episodes_merge_hits_three_days_apart():
    d = pd.Series(pd.to_datetime(["2021-01-01", "2021-01-02", "2021-01-04", "2021-01-10", "2021-01-14", "2021-02-01"]))
    assert S.episodes(d) == 4


def test_bootstrap_gap_brackets_zero_when_equal():
    rng = np.random.default_rng(3)
    oh = rng.integers(20, 40, 36).astype(float)
    ob = np.round(oh * 0.6)
    rh = np.repeat(oh[:, None], 50, axis=1)
    rb = np.repeat(ob[:, None], 50, axis=1)
    lo, hi = S.bootstrap_gap(oh, ob, rh, rb, n_boot=200)
    assert lo == pytest.approx(0) and hi == pytest.approx(0)


def test_random_sets_are_reproducible_and_pipeline_runs(tmp_path, monkeypatch):
    logged = []
    monkeypatch.setattr(S.prereg, "log_trial", lambda *a, **k: logged.append((a, k)))
    monkeypatch.setattr(S.prereg, "trial_count", lambda asset="crypto": 32)
    segs = [make_seg(n=330, seed=5, coin="BTC"), make_seg(n=330, seed=6, coin="ETH", start=20.0)]
    start = pd.Timestamp("2000-01-01")
    r1 = S.run_universe(segs, "btc_eth", "design", start, exact=True, money=True)
    r2 = S.run_universe(segs, "btc_eth", "design", start, exact=True, money=True)
    assert np.array_equal(r1["_rand_rates"], r2["_rand_rates"])
    assert r1["hits"] > 0 and 0 <= r1["bounce_rate_ours"] <= 1
    assert r1["random"]["p5"] <= r1["random"]["median"] <= r1["random"]["p95"]
    assert r1["coin_days_scored"] == 2 * (330 - 250)
    top = S.run_universe(segs, "top20", "design", start, exact=False, money=False)
    assert top["hits"] == r1["hits"] or abs(top["hits"] - r1["hits"]) <= 3   # rounding to cents barely matters at $20+
    spec = {"pass_fail": {"pass_fixed_in_plan": "x"}}
    out = S.finish("design", spec, {"btc_eth": r1, "top20": top}, segs, pd.Timestamp(segs[0].dates[250]),
                   pd.Timestamp(segs[0].dates[-1]), tmp_path)
    saved = json.loads((tmp_path / "H10c_design.json").read_text())
    assert saved["universes"]["btc_eth"]["hits"] == r1["hits"]
    assert "book" in out["money_check"] and "trade_book_costs" in out["money_check"]["book"]
    assert {a[1] for a, _ in logged} == {"btc_eth", "top20", "money_check"}
    assert all(k["kind"] == "design" for _, k in logged)
    assert "verdict" in S.report(out)


def test_test_period_refuses_before_any_data(monkeypatch):
    def refuse(test_id):
        raise NotPreregistered("not committed")

    def no_data(*a, **k):
        raise AssertionError("data loaded before the pre-registration check")

    monkeypatch.setattr(S.prereg, "require_committed", refuse)
    monkeypatch.setattr(S, "build", no_data)
    monkeypatch.setattr(S, "load_universe", no_data)
    monkeypatch.setattr(S.prereg, "log_trial", no_data)
    with pytest.raises(NotPreregistered):
        S.main(["--crypto", "--period", "test"])
    with pytest.raises(NotPreregistered):
        S.run("test")


def test_stock_part_is_a_stub(capsys):
    assert S.main([]) == 1
    assert "not built yet" in capsys.readouterr().out
