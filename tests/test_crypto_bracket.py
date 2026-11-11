import numpy as np
import pytest

from indtrader.crypto_bracket import RR, base_rates, brier3, ev_r, first_touch, fit_w, mirror


def test_first_touch_and_the_cautious_tie_rule():
    e, d = 100.0, 0.02                                  # long: target 103, stop 98
    assert first_touch([(101, 99), (103.5, 100)], e, "long", d) == "target"
    assert first_touch([(101, 97.5)], e, "long", d) == "stop"
    assert first_touch([(104, 97)], e, "long", d) == "stop"          # both in one candle: stop first
    assert first_touch([(101, 99)], e, "long", d) == "neither"
    assert first_touch([(102.5, 99)], e, "short", d) == "stop"       # short: stop 102, target 97
    assert first_touch([(101, 96.5)], e, "short", d) == "target"


def test_base_rates_sum_to_one_and_ev_includes_costs():
    rng = np.random.default_rng(0)
    c = 100 * np.exp(np.cumsum(rng.normal(0, 0.004, 600)))
    br = base_rates(c * 1.002, c * 0.998, c, 0.02)
    for s in ("long", "short"):
        assert sum(br[s].values()) == pytest.approx(1, abs=1e-3)
    assert br["windows"] == 600 - 24 - 1
    assert ev_r(0.4, 0.4, 0.02) == pytest.approx(0.4 * RR - 0.4 - 0.003 / 0.02)
    assert base_rates(c[:100], c[:100], c[:100], 0.02) is None      # too little history


def test_blend_weight_goes_to_zero_for_an_analyst_who_adds_nothing():
    base = {"target": 0.2, "stop": 0.3, "neither": 0.5}
    noisy = {"target": 0.6, "stop": 0.1, "neither": 0.3}            # confident and unrelated to outcomes
    outs = ["neither"] * 20 + ["stop"] * 12 + ["target"] * 8
    res = fit_w([(noisy, base, o) for o in outs])
    assert res["fitted"] and res["w"] == 0.0 and res["skill_vs_base_pct"] < 0
    good = [({"target": 0.9 if o == "target" else 0.05, "stop": 0.9 if o == "stop" else 0.05,
              "neither": 0.9 if o == "neither" else 0.05}, base, o) for o in outs]
    assert fit_w(good)["w"] == 1.0
    assert brier3(base, "neither") == pytest.approx(0.04 + 0.09 + 0.25)


def test_mirror_flips_the_fact_sheet_and_swaps_the_brackets():
    coin = {"facts": {"ret_24h_pct": -2.0, "ret_7d_pct": -5, "ret_30d_pct": -9, "vs_sma50_pct": -8, "vs_sma200_pct": 1,
                      "rsi14": 30, "fear_greed": {"value": 25}, "funding": {"last_pct": 0.01, "avg3d_pct": 0.005, "annual_pct": 5},
                      "up_days_365_pct": 48},
            "bracket": {"base_rates": {"long": {"target": 0.1}, "short": {"target": 0.2}, "p_up_24h": 0.45}}}
    m = mirror(coin)
    assert m["facts"]["ret_24h_pct"] == 2.0 and m["facts"]["rsi14"] == 70 and m["facts"]["fear_greed"]["value"] == 75
    assert m["facts"]["funding"]["avg3d_pct"] == -0.005 and m["facts"]["up_days_365_pct"] == 52
    assert m["bracket"]["base_rates"]["long"]["target"] == 0.2 and m["bracket"]["base_rates"]["p_up_24h"] == 0.55


def test_score_grades_a_due_bracket_from_minute_candles(tmp_path):
    from datetime import UTC, datetime, timedelta

    from indtrader.crypto_bracket import BR_COLS
    from indtrader.crypto_learn import Learner, _append

    class API:
        def _get(self, path, **p):                      # price climbs 0.01% a minute: +2.9% by the 290th minute
            return [[p["startTime"] + i * 60_000, 0, 100 * (1 + 0.0001 * (k := i + (1000 if p["limit"] == 440 else 0))),
                     100 * (1 + 0.0001 * k) - 0.01, 0] for i in range(p["limit"])]

    ln = Learner(tmp_path, api=API(), feeds=None, lessons=tmp_path / "l.json")
    made = datetime.now(UTC) - timedelta(hours=25)
    rows = [{"id": "x", "made": made.isoformat(), "due": (made + timedelta(hours=24)).isoformat(), "source": src, "qset": "bracket-v1",
             "coin": "BTC", "spot": 100, "d_pct": 2.0, "side": side, "p_target": pt, "p_stop": 0.3, "p_neither": round(0.7 - pt, 4),
             "w": 0.5, "ev_r": 0, "note": ""} for src, pt in (("llm", 0.5), ("rate", 0.1)) for side in ("long", "short")]
    _append(ln.brackets.br, BR_COLS, rows)
    out = {(r["source"], r["side"]): r["outcome"] for r in ln.brackets.score()}
    assert out[("llm", "long")] == "target" and out[("llm", "short")] == "stop"
    assert ln.brackets.score() == []                    # graded once only
    assert ln.brackets.summary()["all"]["n"] == 2
