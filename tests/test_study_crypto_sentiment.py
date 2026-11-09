import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from indtrader.crypto import above
from indtrader.crypto_learn import hac_slope_t
from indtrader.research import prereg

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("study_crypto_sentiment", ROOT / "scripts" / "study_crypto_sentiment.py")
scs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(scs)


def _rates(start="2020-01-01", n=60, values=None):
    t = pd.date_range(start, periods=n, freq="8h")
    v = np.arange(n, dtype=float) if values is None else np.asarray(values, float)
    return pd.Series(v, index=t)


def test_funding_avg_leaves_out_the_midnight_settlement_at_the_decision():
    r = _rates()                                   # 0, 1, 2, ... every 8 hours from 2020-01-01 00:00
    days = pd.date_range("2020-01-01", "2020-01-06", freq="D")
    f = scs.funding_avg(r, 9, days)
    # day 2020-01-03: window ends with that day's 16:00 settlement (index 8): mean of 0..8
    assert np.isnan(f["2020-01-02"]) and f["2020-01-03"] == pytest.approx(4.0)
    # include_midnight (the live 00:10 UTC run): the window ends one settlement later, at 00:00 of day t+1
    g = scs.funding_avg(r, 9, days, include_midnight=True)
    assert np.isnan(g["2020-01-02"]) and g["2020-01-03"] == pytest.approx(5.0)


def test_funding_avg_needs_consecutive_settlements_and_a_fresh_one():
    r = _rates(n=30).drop(_rates(n=30).index[12])       # one settlement missing
    days = pd.date_range("2020-01-01", "2020-01-12", freq="D")
    f = scs.funding_avg(r, 9, days)
    assert np.isnan(f["2020-01-05"])                       # its window spans the gap
    assert np.isnan(f["2020-01-11"])                       # data ended: no fresh settlement


def test_outcomes_enter_next_open_and_measure_the_window():
    days = pd.date_range("2021-01-01", periods=6, freq="D")
    df = pd.DataFrame({"open": [10, 11, 12, 13, 14, 15.0], "high": 20.0, "low": [9, 10, 8, 12, 13, 14.0],
                       "close": [11, 12, 13, 14, 15, 16.0]}, index=days)
    o = scs.outcomes(df, 2)
    assert o["ret"].iloc[0] == pytest.approx(13 / 11 - 1)       # close(t+2) / open(t+1) - 1
    assert o["mae"].iloc[0] == pytest.approx(8 / 11 - 1)        # lowest low of t+1..t+2
    assert o["ret"].iloc[-2:].isna().all()


def test_after_tax_keeps_68_8_percent_of_a_gain_and_all_of_a_loss():
    assert scs.after_tax([0.10, -0.05, 0.0]).tolist() == pytest.approx([0.0688, -0.05, 0.0])


def test_dk_slope_equals_hac_slope_t_with_one_row_per_day():
    rng = np.random.default_rng(1)
    n = 400
    d = (rng.random(n) < 0.3).astype(float)
    y = 0.5 + 0.1 * d + rng.standard_normal(n)
    day = np.arange(n) + 18000
    b, t = scs.dk_slope(day, d, y, 7)
    assert b == pytest.approx(y[d == 1].mean() - y[d == 0].mean())
    assert t == pytest.approx(hac_slope_t(y, d, 7))


def test_compare_averages_coins_per_day_first():
    days = pd.date_range("2021-01-01", periods=10, freq="D")
    rows = []
    for i, day in enumerate(days):
        rows.append({"day": day, "coin": "BTC", "d": 1.0 if i % 2 else 0.0, "ret": 0.02 if i % 2 else 0.0, "mae": -0.01})
        rows.append({"day": day, "coin": "ETH", "d": 1.0 if i % 2 else 0.0, "ret": 0.04 if i % 2 else 0.0, "mae": -0.01})
    ev = pd.DataFrame(rows)
    ev["up"] = (ev["ret"] > 0).astype(float)
    for m in (1, 2):
        ev[f"net{m}"] = ev["ret"] - m * 0.003
        ev[f"at{m}"] = scs.after_tax(ev[f"net{m}"])
    gm = scs.group_means(ev)
    assert len(gm) == 10                                   # one row per day: both coins share the tag here
    c = scs.compare(gm, 1)
    assert c["ret"]["on"] == pytest.approx(3.0) and c["ret"]["off"] == pytest.approx(0.0)
    assert c["up"]["diff"] == pytest.approx(100.0)
    assert c["days_on"] == 5 and c["nw_lags"] >= 1


def test_episodes_need_seven_days_off_to_split():
    on = pd.to_datetime(["2021-01-01", "2021-01-02", "2021-01-09", "2021-01-18"])
    eps = scs.episodes(on)
    # 01-02 -> 01-09: 6 days off (merged); 01-09 -> 01-18: 8 days off (new episode)
    assert [(a.day, b.day) for a, b in eps] == [(1, 9), (18, 18)]
    assert len(scs.episodes(on, gap=1)) == 3


def test_ct_portfolio_single_event():
    days = pd.date_range("2021-01-01", periods=5, freq="D")
    df = pd.DataFrame({"open": [100, 100, 110, 121, 121.0], "high": 200.0, "low": 50.0,
                       "close": [100, 110, 121, 121, 121.0]}, index=days)
    ev = pd.DataFrame({"day": [days[0]], "coin": ["BTC"]})
    r, n = scs.ct_portfolio({"BTC": df}, ev, 2, days[0], days[-1], 0.0015)
    assert n.tolist() == [0, 1, 1, 0, 0]
    assert r.iloc[1] == pytest.approx(110 / 100 - 1 - 0.0015)     # entered at the open of day 1
    assert r.iloc[2] == pytest.approx(121 / 110 - 1 - 0.0015)     # held, sold at day 2's close


def test_sim_signals_match_the_desks_trend_test():
    rng = np.random.default_rng(3)
    days = pd.date_range("2020-01-01", periods=120, freq="D")
    close = pd.Series(100 * np.exp(np.cumsum(0.02 * rng.standard_normal(120))), index=days)
    px = {"BTC": pd.DataFrame({"open": close, "high": close, "low": close, "close": close})}
    sig = scs.sim_signals(px, {})
    for day in days[40:]:
        assert sig["BTC"]["above"][day] == above(close.loc[:day], 50)
    assert np.isnan(sig["BTC"]["f3"][days[60]])


def test_hold_rules():
    assert scs.hold_rule("or_negative", False, -0.0001) and not scs.hold_rule("or_negative", False, np.nan)
    assert not scs.hold_rule("flat_high", True, 0.0004) and scs.hold_rule("flat_high", True, 0.0003)
    assert not scs.hold_rule("flat_high", True, 0.0003, inclusive=True)
    assert scs.hold_rule("flat_high", True, np.nan)            # no funding data: the plain rule


def test_cost_level_restores_the_backtest_costs():
    fee = scs.cb.FEE
    with scs.cost_level(2):
        assert pytest.approx(2 * fee) == scs.cb.FEE
    assert fee == scs.cb.FEE


def test_f_minus_line_uses_only_complete_2020_22_windows_at_midnight():
    t = pd.date_range("2019-12-25", "2023-01-10", freq="8h")
    r = pd.Series(np.where(t < pd.Timestamp("2023-01-01"), 0.0001, 0.01), index=t)
    r[(t >= pd.Timestamp("2021-06-01")) & (t < pd.Timestamp("2021-06-11"))] = 0.002
    res = scs.f_minus_line(r)
    assert res["first_window_end"].startswith("2020-01-08 00:00")
    assert res["last_window_end"].startswith("2022-12-31 00:00")
    assert res["max"] < 0.003                                  # nothing from 2019 or 2023 entered
    assert res["n_values"] == (pd.Timestamp("2022-12-31") - pd.Timestamp("2020-01-08")).days + 1


def test_compare_funding_matches_settlements():
    t = pd.date_range("2026-09-20", "2026-10-31 16:00", freq="8h")
    b = pd.Series(0.0001, index=t)
    o = pd.Series(0.00012, index=t[1:])
    res = scs.compare_funding(b, o, "2026-10-01", "2026-10-31", line=0.00011)
    assert res["matched"] == 93 and res["only_binance"] == []
    assert res["mean_diff_okx_minus_binance_pct"] == pytest.approx(0.002)
    assert res["avg7d_at_00utc"]["above_f_minus_line"]["agree_share"] == 0.0
    df = scs.okx_frame([{"fundingTime": "1793462400000", "fundingRate": "0.0001", "realizedRate": "0.00009"}])
    assert df.index[0] == pd.Timestamp("2026-10-31 16:00") and df["realized"].iloc[0] == pytest.approx(0.00009)


def test_matches_uses_the_precision_the_brief_printed():
    assert scs._matches(0.786, 0.79) and not scs._matches(0.784, 0.79)
    assert scs._matches(389.996, 390) and scs._matches(-26.79, -27) and not scs._matches(-26.4, -27)
    assert scs._matches(208, 208) and not scs._matches(207, 208)           # counts exactly
    assert scs._matches(0.14475, 0.14) and not scs._matches(4.277, 4.2)
    assert scs._matches(True, True) and not scs._matches(False, True)
    assert not scs._matches(None, 1.0) and not scs._matches(float("nan"), 1.0)


def test_reproduction_status_labels_each_brief_figure():
    rep = {
        "corr_fg_vs_btc_distance_from_50d": {"brief": 0.79, "previous_day_distance": 0.786},
        "btc_7d_after_extreme_fear": {
            "brief": {"up_pct_fear": 56.7, "up_pct_all": 52.6, "mean_fear_below_all": True},
            "close_to_close": {"up_pct_fear": 55.4, "up_pct_all": 52.8, "mean_pct_fear": 0.7, "mean_pct_all": 0.9},
            "next_open_to_close": {"up_pct_fear": 56.66, "up_pct_all": 52.64, "mean_pct_fear": 0.7, "mean_pct_all": 0.9}},
        "btc_30d_after_first_day_fg_below_15": {"brief": {"episodes": 14, "mean_pct_first_days": -3.9, "mean_pct_all": 4.2},
                                                "mean_pct_all_days": 4.28, "consecutive_runs": {"episodes": 45, "mean_pct_first_days": 2.4},
                                                "gap_7_days": {"episodes": 20, "mean_pct_first_days": 5.3}},
        "btc_next_day_after_crowded_funding": {
            "brief": {"mean_pct_crowded": 0.16, "mean_pct_all": 0.14, "up_pct": 51.9, "days": 208},
            "window_to_day_t_16utc": {"days": 208, "mean_pct_crowded": 0.157, "up_pct_crowded": 51.92,
                                      "mean_pct_all_days_with_funding": 0.1448},
            "window_to_t_plus_1_00utc": {"days": 207, "mean_pct_crowded": 0.07, "up_pct_crowded": 51.2,
                                         "mean_pct_all_days_with_funding": 0.1448}},
        "btc_trend_addons_since_2023": {"brief": {"plain_pct": 390, "plain_max_dd_pct": -27, "or_negative_pct": 483,
                                                  "or_negative_max_dd_pct": -38},
                                        "plain": {"pre_tax_return_pct": 389.99, "max_dd_pct": -26.79},
                                        "trend_or_negative_funding": {"pre_tax_return_pct": 483.2, "max_dd_pct": -36.0}},
        "flat_when_crowded_2020_26": {"BTC": {"hurt": True}, "ETH": {"hurt": True}},
        "fear_greed_day_counts": {"brief": {"design_fear": 493, "design_greed": 185, "test_fear": 186, "test_greed": 97},
                                  "design_2018_22": {"fear": 493, "greed": 185}, "test_to_2026_10_31": {"fear": 186, "greed": 97},
                                  "test_to_file_end": {"fear": 188, "greed": 97}},
    }
    st = scs.reproduction_status(rep)
    yes = {k for k, v in st.items() if v["reproduced"]}
    assert yes == {"corr_fg_vs_btc_distance_from_50d", "btc_7d_after_extreme_fear", "btc_next_day_after_crowded_funding",
                   "flat_when_crowded_2020_26", "fear_greed_day_counts"}
    assert st["btc_trend_addons_since_2023"]["label"] == scs.NOT_REPRODUCED          # one number off (-36 against -38)
    assert st["btc_30d_after_first_day_fg_below_15"]["label"] == scs.NOT_REPRODUCED


def test_arms_verdict_rules():
    days = pd.date_range("2027-01-01", periods=600, freq="D")
    rng = np.random.default_rng(0)
    base = pd.Series(np.cumprod(1 + 0.001 + 0.02 * rng.standard_normal(600)), index=days)
    v = pd.DataFrame({"control": base, "hold": base * 0.9, "fplus": base * np.linspace(1, 0.8, 600)})
    assert scs.arms_verdict(v.iloc[:300], "fplus", 40)["verdict"].startswith("no verdict yet")
    res = scs.arms_verdict(v, "fplus", 40)
    assert res["months"] == 18 and res["verdict"] == "stop" and not res["beats_control"]
    v["fminus"] = base * np.linspace(1, 1.3, 600)
    assert scs.arms_verdict(v.iloc[:400], "fminus", 40)["verdict"] in ("keep running", "stop")


def test_test_period_refuses_before_reading_data(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("data read before the pre-registration check")

    monkeypatch.setattr(scs, "load_prices", boom)

    def refuse(test_id):
        raise prereg.NotPreregistered(f"{test_id} not committed")

    monkeypatch.setattr(scs.prereg, "require_committed", refuse)
    with pytest.raises(prereg.NotPreregistered):
        scs.main(["--period", "test"])
    with pytest.raises(prereg.NotPreregistered):
        scs.main(["--arms"])


def _synthetic_data(folder: Path) -> None:
    rng = np.random.default_rng(7)
    days = pd.date_range("2019-09-01", "2022-12-31", freq="D")
    for coin, p0 in (("BTC", 10000.0), ("ETH", 200.0)):
        close = p0 * np.exp(np.cumsum(0.03 * rng.standard_normal(len(days))))
        openp = np.r_[p0, close[:-1]]
        pd.DataFrame({"date": days.date, "open": openp, "high": np.maximum(openp, close) * 1.01,
                      "low": np.minimum(openp, close) * 0.99, "close": close, "volume": 1e6}).to_csv(folder / f"{coin}.csv", index=False)
        t = pd.date_range("2020-01-01", "2022-12-31 16:00", freq="8h", tz="UTC")
        pd.DataFrame({"time": [x.isoformat() for x in t], "rate": 0.0003 * rng.standard_normal(len(t)) + 0.0001}).to_csv(
            folder / f"funding_{coin}.csv", index=False)
    fg = pd.DataFrame({"date": days.date, "value": rng.integers(5, 95, len(days)), "label": "x"})
    fg.to_csv(folder / "fear_greed.csv", index=False)


def test_design_run_on_synthetic_data(tmp_path, monkeypatch):
    _synthetic_data(tmp_path)
    logged = []
    monkeypatch.setattr(scs, "DATA", tmp_path)
    monkeypatch.setattr(scs, "RESULTS", tmp_path / "results")
    monkeypatch.setattr(scs.prereg, "log_trial", lambda *a, **k: logged.append((a, k)))
    monkeypatch.setattr(scs.prereg, "trial_count", lambda asset="crypto": 42)
    assert scs.main(["--period", "design"]) == 0
    assert len(logged) == 6 and all(k["kind"] == "design" for _, k in logged)
    import json
    res = json.loads((tmp_path / "results" / "H8a_design.json").read_text())
    assert res["data_end"] == "2022-12-31" and "test" not in res["lessons"]["fear-rebound-7d"]
    fr = res["lessons"]["fear-rebound-7d"]["design"]
    assert fr["headline"]["days_on"] > 50 and fr["headline"]["t"] is not None
    assert res["addons"]["design"]["costs_x1"]["plain"]["trades"] > 0
    first = fr["by_horizon"]["30"]["first_day_of_episode"]
    assert {"costs_x1_pre_tax", "costs_x2_pre_tax"} <= set(first["portfolio"])         # Sharpe and drawdown next to it
    assert "max_dd_pct" in first["portfolio"]["costs_x1_pre_tax"]
