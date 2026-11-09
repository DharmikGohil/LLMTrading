import numpy as np
import pandas as pd

from indtrader.signals.chart import bollinger, candle_patterns, chart_read, macd, support_resistance, swing_points


def frame(close, spread=1.0, opens=None):
    close = pd.Series(close, dtype=float)
    o = pd.Series(opens, dtype=float) if opens is not None else close.shift(1).fillna(close.iloc[0])
    idx = pd.bdate_range("2025-01-01", periods=len(close))
    return pd.DataFrame({"Open": o.values, "High": np.maximum(o.values, close.values) + spread,
                         "Low": np.minimum(o.values, close.values) - spread, "Close": close.values,
                         "Volume": 1000.0}, index=idx)


def test_macd_matches_definition():
    c = pd.Series(np.linspace(100, 150, 80))
    m = macd(c)
    ema12 = c.ewm(span=12, adjust=False).mean()
    ema26 = c.ewm(span=26, adjust=False).mean()
    assert np.allclose(m["macd"], ema12 - ema26)
    assert np.allclose(m["hist"], m["macd"] - m["signal"])
    assert m["macd"].iloc[-1] > 0                       # steady uptrend: fast EMA above slow


def test_bollinger_band_width_and_pct_b():
    c = pd.Series([100.0] * 19 + [110.0])
    b = bollinger(c, 20, 2)
    sd = c.std(ddof=0)
    assert abs(b["upper"].iloc[-1] - (c.mean() + 2 * sd)) < 1e-9
    assert b["pct_b"].iloc[-1] > 1.0                     # a 10% jump from a flat base closes above the upper band
    assert abs(b["mid"].iloc[-1] - 100.5) < 1e-9


def test_swing_points_and_levels_find_a_double_top():
    # rise to 120, fall, rise again to 120, fall: two touches of the same resistance
    path = list(np.linspace(100, 120, 20)) + list(np.linspace(120, 105, 15)) + list(np.linspace(105, 120, 15)) \
        + list(np.linspace(120, 108, 15))
    df = frame(path, spread=0.3)
    highs, lows = swing_points(df, 5)
    assert len(highs) >= 2
    lv = support_resistance(df, lookback=250, k=5)
    assert any(abs(r["price"] - 120.3) < 1.5 and r["touches"] >= 2 for r in lv["resistance"])


def test_candles_engulfing_and_hammer_in_context():
    down = list(np.linspace(120, 100, 15))
    # bullish engulfing: previous bar red (open 101 close 99), last bar green opening below 99, closing above 101
    df = frame(down[:-2] + [99.0, 102.0], spread=0.2, opens=down[:-2] + [101.0, 98.5])
    assert "bullish engulfing" in candle_patterns(df)
    # hammer after a decline: small body near the high, long lower shadow
    closes = down[:-1] + [100.2]
    opens = down[:-1] + [100.0]
    df = frame(closes, spread=0.0, opens=opens)
    df.loc[df.index[-1], ["High", "Low"]] = [100.25, 98.0]
    assert "hammer" in candle_patterns(df)


def test_chart_read_has_all_blocks():
    rng = np.random.default_rng(1)
    c = 100 * np.exp(np.cumsum(rng.normal(0.0005, 0.01, 300)))
    out = chart_read(frame(c, spread=0.8))
    assert {"macd", "bollinger", "levels", "candles", "volume_vs_50d", "rsi14"} <= set(out)
    assert set(out["levels"]) == {"support", "resistance"}
