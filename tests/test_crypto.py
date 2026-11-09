import numpy as np
import pandas as pd
import pytest

from indtrader import crypto
from indtrader.crypto import FEE, CryptoBook, CryptoDesk, target_weights


def panel(days=200):
    idx = pd.date_range("2026-01-01", periods=days, freq="D")
    t = np.arange(days)
    closes = pd.DataFrame({
        "BTC": 50000 * (1 + 0.002 * t),            # steady uptrend: regime on
        "AAA": 10 * (1 + 0.010 * t),               # strongest momentum
        "BBB": 10 * (1 + 0.006 * t),
        "CCC": 10 * (1 + 0.004 * t),
        "DDD": 10 * (1 - 0.002 * t),               # falling: excluded (below trend, negative return)
    }, index=idx)
    value30 = pd.DataFrame(1e9, index=idx, columns=closes.columns)
    return closes, value30


def test_target_weights_picks_top_momentum_above_trend():
    closes, v = panel()
    w = target_weights(closes, v, closes.index[-1], {**crypto.STRATEGY, "top_k": 2})
    assert set(w) == {"AAA", "BBB"} and abs(sum(w.values()) - 1) < 1e-9


def test_target_weights_goes_to_cash_when_btc_below_regime_average():
    closes, v = panel()
    closes["BTC"] = closes["BTC"].iloc[::-1].to_numpy()     # BTC now falling
    assert target_weights(closes, v, closes.index[-1]) == {}


class FakeAPI:
    def __init__(self, prices):
        self.p = prices

    def quotes(self, coins):
        return {c: {"bid": self.p[c] * 0.999, "ask": self.p[c] * 1.001, "last": self.p[c], "change_pct": 0.0}
                for c in coins if c in self.p}

    def liquid_coins(self, n=45):
        return ["AAA", "BBB", "CCC", "DDD"]

    def panel(self, coins, limit=400):
        closes, v = panel()
        return closes[[c for c in coins if c in closes]], v[[c for c in coins if c in v]]


def test_rebalance_charges_fees_and_never_overspends(tmp_path):
    b = CryptoBook(tmp_path / "b.json", 10000)
    rows = []
    q = FakeAPI({"AAA": 12.0, "BBB": 11.0}).quotes(["AAA", "BBB"])
    b.rebalance({"AAA": 0.5, "BBB": 0.5}, q, "t", rows.append)
    assert b.data["cash"] >= 0 and b.data["fees"] == pytest.approx(sum(r["fee"] for r in rows), abs=1e-3)
    assert sum(r["value"] for r in rows) * FEE == pytest.approx(b.data["fees"], abs=0.01)
    # selling everything returns cash minus spread and fees
    b.rebalance({}, q, "t", rows.append)
    assert not b.data["pos"] and 9900 < b.data["cash"] < 10000


def test_desk_gate_only_reduces_risk_and_hold_buys_btc_once(tmp_path):
    prices = {"BTC": 50398.0, "AAA": 29.9, "BBB": 21.9, "CCC": 17.9, "DDD": 6.0, "ETH": 3000.0}
    desk = CryptoDesk(tmp_path, FakeAPI(prices))
    desk.set_gate(0.5, ["AAA"], "test: FOMC tonight")
    out = desk.run()
    main = desk.books["main"].data["pos"]
    ctrl = desk.books["control"].data["pos"]
    assert "AAA" in ctrl and "AAA" not in main                      # the gate excluded a coin from main only
    q = desk.api.quotes(sorted(set(main) | set(ctrl)))
    in_coins = sum(p["qty"] * q[c]["last"] for c, p in main.items())
    assert in_coins <= 0.5 * desk.books["main"].value(q) + 1       # exposure capped at 50%
    assert set(desk.books["hold"].data["pos"]) == {"BTC"}
    desk.run()                                                     # not due again for a week, benchmark not re-bought
    assert sum(1 for r in (tmp_path / "trades.csv").read_text().splitlines() if ",hold," in r or r.startswith("hold,")) == 1
    assert out["equity"]["control"] > 0 and not desk.due("control")
