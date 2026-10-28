from datetime import date

from typer.testing import CliRunner

from indtrader import data as market_data
from indtrader.cli import app
from indtrader.engine import Engine
from indtrader.signals.llm_agent import LLMSignal, SignalStore

runner = CliRunner()


def _cfg(tmp_path):
    cfg = tmp_path / "config.yaml"
    cfg.write_text(f"data_dir: {tmp_path / 'state'}\nsignals_dir: {tmp_path / 'signals'}\nuniverse: [AAA]\n")
    return str(cfg)


def test_submit_signal_validation(tmp_path, ohlcv, monkeypatch):
    hist = ohlcv(100, drift=0.0, seed=5)
    monkeypatch.setattr(market_data, "recent_history", lambda *a, **k: hist)
    close = float(hist["Close"].iloc[-1])
    cfg = _cfg(tmp_path)
    thesis = "Breakout above 50-day average on rising volume; results beat; main risk is a weak market."
    ok = runner.invoke(app, ["submit-signal", "AAA", "--rating", "buy", "--confidence", "70", "--thesis", thesis,
                             "--stop", f"{close * 0.95:.2f}", "--target", f"{close * 1.1:.2f}",
                             "--date", "2026-10-27", "-c", cfg])
    assert ok.exit_code == 0, ok.output
    sig = SignalStore(tmp_path / "signals").get("AAA", "2026-10-27")
    assert (sig.rating, sig.confidence, sig.source) == ("Buy", 70.0, "claude-analyst")
    bad = runner.invoke(app, ["submit-signal", "AAA", "--rating", "Strong Buy", "--confidence", "120",
                              "--thesis", "short", "--stop", f"{close * 1.01:.2f}", "--date", "2026-10-27", "-c", cfg])
    assert bad.exit_code == 1
    assert "rating must be" in bad.output and "confidence" in bad.output and "stop" in bad.output


def test_is_trading_day_cmd(tmp_path):
    cfg = _cfg(tmp_path)
    assert runner.invoke(app, ["is-trading-day", "--date", "2026-10-29", "-c", cfg]).exit_code == 0
    assert runner.invoke(app, ["is-trading-day", "--date", "2026-11-10", "-c", cfg]).exit_code == 1   # Diwali Balipratipada


def test_external_source_skips_tradingagents(settings, monkeypatch):
    settings.llm.signal_source = "external"
    settings.universe = ["AAA", "BBB"]
    SignalStore(settings.signals_root).put(LLMSignal("AAA", "2026-10-27", "Buy", confidence=65, source="claude-analyst"))

    class Boom:
        def analyze(self, *a, **k):
            raise AssertionError("TradingAgents must not run in external mode")

    class B:
        name = "paper"

        def funds(self):
            return 1e5

    eng = Engine(settings, B(), analyzer=Boom())
    found = eng.analyze_universe(date(2026, 10, 28))
    assert list(found) == ["AAA"]
