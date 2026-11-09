import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from indtrader.crypto import universe
from indtrader.research import patterns as pt
from indtrader.research import prereg
from indtrader.signals.chart import swing_points

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("study_head_shoulders", ROOT / "scripts" / "study_head_shoulders.py")
shs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(shs)


def path(knots, n=81):
    return np.interp(np.arange(n), [k[0] for k in knots], [k[1] for k in knots])


# A head-and-shoulders top: shoulders 100 and 100.5, head 130, troughs 70 and 70.5, then a fall through the neckline.
HS = path([(0, 50), (12, 100), (20, 70), (28, 130), (36, 70.5), (44, 100.5), (48, 60), (80, 55)])
# A double top: peaks 100 and 100.8, 24 days apart, the lowest close between them 60, then a fall.
DT = path([(0, 40), (20, 100), (32, 60), (44, 100.8), (56, 40), (80, 40)])


def swing(c):
    return pt.detect_swing(c * 1.002, c * 0.998, c)


# ------------------------------------------------------------------------------------------------- the detectors

@pytest.mark.parametrize("detector", [pt.detect_kernel, swing])
def test_head_and_shoulders_found_and_completed(detector):
    pats = detector(HS)
    hs = [p for p in pats if p.kind == "hs"]
    assert len(hs) == 1 and not [p for p in pats if p.kind == "dt"]    # the head is above Ea: not a double top
    p = hs[0]
    assert [r for r, _ in p.points] == [12, 20, 28, 36, 44]
    assert p.detect == 44 + 3                                         # the last turning point is 3 days old
    neck_48 = p.neckline(48)
    assert HS[48] < neck_48 and p.complete == 48                      # first close below the line through E2 and E4
    assert all(HS[s] >= p.neckline(s) for s in range(p.detect + 1, 48))


@pytest.mark.parametrize("detector", [pt.detect_kernel, swing])
def test_double_top_found_and_completed(detector):
    pats = detector(DT)
    dt = [p for p in pats if p.kind == "dt"]
    assert len(dt) == 1 and not [p for p in pats if p.kind == "hs"]
    p = dt[0]
    assert [r for r, _ in p.points] == [20, 44] and p.detect == 47
    assert p.neckline(50) == pytest.approx(60.0)                     # the lowest close between the peaks
    first_below = next(s for s in range(48, 81) if DT[s] < 60)
    assert p.complete == first_below


@pytest.mark.parametrize("detector", [pt.detect_kernel, swing])
def test_no_patterns_on_a_rising_staircase_or_a_straight_line(detector):
    # each peak 6% above the last: the shoulders and the two peaks are never within 1.5%
    knots, x, y = [], 0, 50.0
    for _ in range(20):
        knots += [(x, y), (x + 6, y * 1.15)]
        x, y = x + 9, y * 1.06
    stairs = path(knots, x)
    assert detector(stairs) == []
    assert detector(np.linspace(10, 30, 200)) == []


def test_tolerance_gap_and_completion_rules():
    # shoulders 3% apart: no head-and-shoulders
    off = path([(0, 50), (12, 100), (20, 70), (28, 130), (36, 70.5), (44, 103.5), (48, 60), (80, 55)])
    assert not [p for p in swing(off) if p.kind == "hs"]
    # double-top peaks 20 days apart: too close
    near = path([(0, 40), (24, 100), (34, 60), (44, 100.8), (56, 40), (80, 40)])
    assert not [p for p in swing(near) if p.kind == "dt"]
    # detected but never closes below the neckline within 10 days: not complete
    hold = path([(0, 50), (12, 100), (20, 70), (28, 130), (36, 70.5), (44, 100.5), (52, 80), (80, 80)])
    hs = [p for p in swing(hold) if p.kind == "hs"]
    assert len(hs) == 1 and hs[0].complete is None


def test_within_and_alternate():
    assert pt.within(100, 103) and not pt.within(100, 103.1)        # 1.5% of the average either side
    turns = [(1, 10.0, 1), (3, 12.0, 1), (5, 5.0, -1), (6, 4.0, -1), (8, 11.0, 1), (9, 11.0, 1)]
    assert pt.alternate(turns) == [(3, 12.0, 1), (6, 4.0, -1), (8, 11.0, 1)]     # highest peak, lowest trough, earlier tie
    # a row that is both a peak and a trough is entered in the order that alternates
    assert pt.alternate([(1, 5.0, -1), (2, 9.0, 1), (2, 3.0, -1)]) == [(1, 5.0, -1), (2, 9.0, 1), (2, 3.0, -1)]
    assert pt.alternate([(1, 9.0, 1), (2, 9.5, 1), (2, 3.0, -1)]) == [(1, 9.0, 1), (2, 3.0, -1), (2, 9.5, 1)]


def test_swings_used_only_from_bar_i_plus_3():
    c = HS.copy()
    hi, lo = c * 1.002, c * 0.998
    highs, _ = swing_points(pd.DataFrame({"High": hi, "Low": lo}), 3)
    assert 44 in [i for i, _ in highs]
    for cut in (45, 46):                                              # the swing at 44 is not known yet
        assert not [p for p in pt.detect_swing(hi[:cut + 1], lo[:cut + 1], c[:cut + 1]) if p.kind == "hs"]
    assert [p.detect for p in pt.detect_swing(hi[:48], lo[:48], c[:48]) if p.kind == "hs"] == [47]


@pytest.mark.parametrize("method", ["kernel", "swing"])
def test_no_look_ahead_on_random_walks(method):
    rng = np.random.default_rng(7)
    for seed in range(4):
        c = 100 * np.exp(np.cumsum(np.random.default_rng(seed).normal(0, 0.05, 700)))
        hi, lo = c * np.exp(np.abs(rng.normal(0, 0.01, 700))), c * np.exp(-np.abs(rng.normal(0, 0.01, 700)))
        df = pd.DataFrame({"open": c, "high": hi, "low": lo, "close": c})
        full = pt.detect(df, method)
        for cut in (300, 450, 699):
            part = pt.detect(df.iloc[:cut + 1], method)
            want = [(p.kind, p.detect, p.points, p.complete if p.complete is not None and p.complete <= cut else None)
                    for p in full if p.detect <= cut]
            got = [(p.kind, p.detect, p.points, p.complete) for p in part]
            assert got == want


def test_kernel_window_refit_uses_only_its_own_rows():
    rng = np.random.default_rng(3)
    c = 100 * np.exp(np.cumsum(rng.normal(0, 0.05, 400)))
    base = pt.detect_kernel(c)
    changed = c.copy()
    changed[:100] *= 3                    # rows outside every window that ends after row 137
    late = [p for p in base if p.detect >= 137 + pt.WINDOW]
    assert [p for p in pt.detect_kernel(changed) if p.detect >= 137 + pt.WINDOW] == late


def test_lmw_bandwidth_is_scale_free_and_on_the_grid():
    rng = np.random.default_rng(1)
    w = 100 * np.exp(np.cumsum(rng.normal(0, 0.04, (50, pt.WINDOW)), axis=1))
    h = pt.lmw_cv_bandwidth(w)
    assert np.allclose(h, pt.lmw_cv_bandwidth(w * 0.001))
    assert np.isin(h, pt.BW_GRID).all()
    # LMW's leave-one-out keeps the full normalisation: very small bandwidths are never chosen for prices
    assert (h > 1.0).all()


# ------------------------------------------------------------------------------------------------------- the study

def panel(n=200, coins=6, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2020-01-01", periods=n, freq="D")
    close = 10 * np.exp(np.cumsum(rng.normal(0, 0.03, (n, coins)), axis=0))
    open_ = close * np.exp(rng.normal(0, 0.005, (n, coins)))
    vol = rng.uniform(1, 100, (n, coins)) * 1e6
    return idx, close, open_, vol


def test_universe_mask_matches_crypto_universe():
    idx, close, _, vol = panel(n=260, coins=25)
    close[:150, 3] = np.nan                       # a late listing
    close[200:, 5] = np.nan                       # a coin that dies
    names = [f"C{i}" for i in range(25)]
    cdf, vdf = pd.DataFrame(close, index=idx, columns=names), pd.DataFrame(vol, index=idx, columns=names)
    mask = shs.universe_mask(close, vol)
    v30 = vdf.rolling(30, min_periods=20).mean()
    for t in (119, 120, 160, 210, 259):
        want = set(universe(cdf, v30, idx[t]))
        assert {names[i] for i in np.flatnonzero(mask[t])} == want


def test_quintiles_and_comparables():
    T, C = 40, 10
    close = np.ones((T, C))
    close[35] = np.arange(1, C + 1)              # 30-day returns 0..9 on row 35
    univ = np.ones((T, C), dtype=bool)
    univ[35, 9] = False
    q = shs.quintiles(close, univ)
    assert q[35].tolist() == [0, 0, 1, 1, 2, 2, 3, 3, 4, -1]          # 9 coins in the universe: floor(5 rank / 9)
    assert shs.comparables(q, 35, 2).tolist() == [3]
    assert (q[:30] == -1).all()                                       # no 30-day return yet


def test_forward_returns_delisting_and_period_end():
    T = 12
    close = np.tile(np.arange(1.0, T + 1)[:, None], (1, 2))
    open_ = close - 0.5
    close[8:, 1] = np.nan                         # coin 1's data ends on row 7 (inside the period)
    open_[8:, 1] = np.nan
    last, delisted = shs.life(close)
    assert last.tolist() == [11, 7] and delisted.tolist() == [False, True]
    fr = shs.forward_returns(open_, close, 3, last, delisted)
    assert fr[2, 0] == pytest.approx(close[5, 0] / open_[3, 0] - 1)
    assert np.isnan(fr[9, 0])                     # runs past the period end: no outcome
    assert fr[5, 1] == pytest.approx(close[7, 1] / open_[6, 1] - 1)  # sold at its last close
    assert np.isnan(fr[7, 1])                     # no open the next day


def test_after_tax_and_episodes():
    assert shs.after_tax([0.1, -0.1]).tolist() == pytest.approx([0.0688, -0.1])
    assert shs.episodes({0: [10, 30, 70], 1: [5]}) == 3


def test_exit_flag_state_and_trend_weights():
    idx = pd.date_range("2021-01-01", periods=140, freq="D")
    s = pd.Series(np.r_[np.linspace(100, 150, 80), np.linspace(150, 120, 30), np.linspace(120, 170, 30)], index=idx)
    flag_day = idx[85]                            # above the 50-day average and falling
    st = shs.exit_flag_state(s, {flag_day})
    assert not st.loc[: idx[84]].any() and st.loc[flag_day]
    sma = s.rolling(50).mean()
    above = s > sma
    back = next(d for d in idx[86:] if above.loc[d] and not above.shift(1).loc[d])
    assert st.loc[flag_day:back].iloc[:-1].all() and not st.loc[back]
    fn = shs.trend_weights({"BTC": st, "ETH": pd.Series(False, index=idx)})
    closes = pd.DataFrame({"BTC": s, "ETH": s})
    assert fn(idx[90], closes.loc[: idx[90]]) == {"ETH": 0.5}         # BTC held out by the flag
    assert shs.trend_weights(None)(idx[90], closes.loc[: idx[90]]) == {"BTC": 0.5, "ETH": 0.5}


def test_day_average_and_nw_summary():
    rows = np.array([5, 5, 9, 12])
    vals = np.array([1.0, 3.0, np.nan, -2.0])
    assert shs.day_average(rows, vals).tolist() == [2.0, -2.0]
    assert shs.nw_lags(10, 30) == 30
    s = shs.nw_summary(np.array([0.01, -0.02, 0.03, 0.0, 0.01]), 1)
    assert s["n_days"] == 5 and s["lags"] >= 1


def test_test_period_refuses_without_committed_prereg(monkeypatch):
    calls = []

    def refuse(test_id):
        calls.append(test_id)
        raise prereg.NotPreregistered("not committed")

    def boom(*a, **k):
        raise AssertionError("data loaded before the pre-registration check")

    monkeypatch.setattr(shs.prereg, "require_committed", refuse)
    monkeypatch.setattr(shs, "load_panel", boom)
    with pytest.raises(prereg.NotPreregistered):
        shs.main(["--crypto", "--period", "test"])
    with pytest.raises(prereg.NotPreregistered):
        shs.main(["--period", "test"])               # checked first, even before the stock stub
    assert calls == ["H9c", "H9c"]


def test_prereg_matches_script_constants():
    shs.check_spec(prereg.load("H9c"))


def synthetic_ctx(drift_after: float, jump_on_day: float = 0.0, seed: int = 0, T: int = 520, C: int = 20, n_events: int = 400):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2019-01-01", periods=T, freq="D")
    r = rng.normal(0, 0.03, (T, C))
    ev = {(int(c), int(i)) for c, i in zip(rng.integers(130, T - 40, n_events), rng.integers(0, C, n_events), strict=True)}
    for c, i in ev:
        r[c, i] += jump_on_day                       # on the completion day itself: known before entry, not an outcome
        r[c + 1: c + 31, i] += drift_after / 30       # after entry at the next open
    close = 10 * np.exp(np.cumsum(r, axis=0))
    open_ = np.vstack([close[:1], close[:-1]])       # each day opens at the previous close
    vol = np.tile(np.linspace(100, 50, C) * 1e6, (T, 1))
    arr = {"open": open_, "high": np.maximum(open_, close), "low": np.minimum(open_, close), "close": close, "volume": vol}
    ctx = shs.context(idx, [f"C{i}" for i in range(C)], arr, 0)
    shs.add_outcome_inputs(ctx)
    return ctx, [{"coin": i, "complete": c} for c, i in sorted(ev)]


def test_outcomes_find_a_planted_underperformance():
    ctx, events = synthetic_ctx(drift_after=-0.15)
    res = shs.outcomes(events, ctx, "swing-dt")
    m30 = res["30d"]["main_vs_quintile"]
    assert m30["mean"] < -0.10 and m30["t"] < -3 and m30["lags"] >= 30
    assert res["7d"]["main_vs_quintile"]["t"] < -3
    assert res["30d"]["vs_ew_top20"]["mean"] < -0.10
    assert res["30d"]["vs_same_coin_random_dates"]["share_random_sets_below_event_mean"] < 0.05
    assert res["30d"]["main_after_tax"]["mean"] < -0.08
    ok, t, mean, hb = shs.design_pass(res)
    assert t == max(res[f"{h}d"]["main_vs_quintile"]["t"] for h in shs.HORIZONS) and hb in ("1d", "7d", "30d")
    assert res["30d"]["event_book_costs_0.30%"]["max_drawdown"] < 0


def test_outcomes_ignore_the_completion_day_itself():
    ctx, events = synthetic_ctx(drift_after=0.0, jump_on_day=-0.2, seed=1)
    res = shs.outcomes(events, ctx, "kernel-hs")
    for h in shs.HORIZONS:
        assert abs(res[f"{h}d"]["main_vs_quintile"]["t"]) < 3


def test_step2_runs_and_no_flag_equals_plain_rule():
    idx = pd.date_range("2019-10-01", periods=300, freq="D")
    rng = np.random.default_rng(5)
    panel = {}
    for k in ("BTC", "ETH"):
        c = 100 * np.exp(np.cumsum(rng.normal(0.001, 0.03, len(idx))))
        panel[k] = pd.DataFrame({"open": np.r_[c[0], c[:-1]], "close": c}, index=idx)
    out = shs.step2({"BTC": set(), "ETH": set()}, panel, "2020-01-01", str(idx[-1].date()))
    plain, flag = out["rules"]["plain trend"], out["rules"]["trend + exit flag"]
    assert plain == flag and len(out["walk_forward"]) == 4
    assert shs.cb.FEE == 0.001 and shs.cb.SLIP == 0.0005             # the doubled-cost run restores the constants
    flagged = shs.step2({"BTC": {idx[120]}, "ETH": set()}, panel, "2020-01-01", str(idx[-1].date()))
    assert set(flagged["lines"]) == {"beats_plain_after_tax", "walk_forward_windows_won", "max_dd_no_deeper"}


# ------------------------------------------------------------------- the test-period path, on synthetic data only

def _fake_build(n_events: int = 40):
    """A stand-in for build(): a synthetic panel (no file is read) with fewer than 300 events for swing-dt."""
    ctx, events = synthetic_ctx(drift_after=-0.15, seed=2, n_events=n_events)
    for k in ("fr", "rand_elig"):
        ctx.pop(k)                                   # run() itself must add the outcome inputs
    ctx.update({"panel": {}, "start": str(ctx["idx"][0].date()), "end": str(ctx["idx"][-1].date()), "found": {}})
    ev = {"events": {v: (events if v == "swing-dt" else []) for v in shs.VARIANTS},
          "detected": {v: {"patterns_detected": 0, "completed_any_coin": 0} for v in shs.VARIANTS}}
    return ctx, ev


def test_test_run_computes_outcomes_below_300_events(monkeypatch):
    # a variant that passed the design line is computed in the test period whatever its test-period count
    monkeypatch.setattr(shs, "build", lambda period: _fake_build())
    res = shs.run("test", prereg.load("H9c"), only=["swing-dt"])
    out = res["variants"]["swing-dt"]
    assert out["counts"]["usable"] < shs.MIN_EVENTS and out["status"] == "outcomes computed"
    assert out["top20"]["30d"]["main_vs_quintile"]["t"] is not None
    assert res["variants"]["kernel-hs"]["status"].startswith("not run")


def test_test_lines_fail_a_horizon_with_no_events():
    design = {"variants": {"swing-dt": {"top20": {f"{h}d": {"main_vs_quintile": {"mean": -0.05, "t": -4.0}}
                                                  for h in shs.HORIZONS}}}}
    res = {"variants": {"swing-dt": {"top20": {"1d": {"main_vs_quintile": {"mean": -0.04, "t": -3.0}},
                                               "7d": {"main_vs_quintile": {"mean": -0.04, "t": -3.0}},
                                               "30d": {"events_with_outcome": 0}}}}}
    shs.test_lines(res, design)
    assert res["variants"]["swing-dt"]["pass_line_met"] is False


def test_test_period_after_too_little_data_computes_nothing(monkeypatch, tmp_path):
    design = {"variants": {v: {"status": "too little data: 3 usable events, fewer than 300; no outcome computed",
                               "pass_line_met": False} for v in shs.VARIANTS}}
    (tmp_path / "H9c_design.json").write_text(json.dumps(design))
    monkeypatch.setattr(shs, "RESULTS", tmp_path)
    monkeypatch.setattr(shs.prereg, "require_committed", lambda test_id: prereg.load(test_id))

    def boom(*a, **k):
        raise AssertionError("test-period data loaded although no variant passed the design line")

    monkeypatch.setattr(shs, "load_panel", boom)
    monkeypatch.setattr(shs.prereg, "log_trial", boom)
    assert shs.main(["--crypto", "--period", "test"]) == 0
    out = json.loads((tmp_path / "H9c_test.json").read_text())
    assert "too little data" in out["status"] and "failed" not in out["status"]
