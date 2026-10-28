"""indtrader command line.

  indtrader analyze            # TradingAgents ratings for the universe
  indtrader trade              # turn latest ratings into orders (once)
  indtrader monitor            # check stop-loss / targets (once)
  indtrader run                # full daily scheduler (analysis, execution, monitoring)
  indtrader backtest --start 2024-01-01 --end 2026-09-30
  indtrader status
"""

from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path

import typer

from indtrader.config import Settings, load_settings
from indtrader.market import is_market_open, is_trading_day, now_ist, previous_trading_day

app = typer.Typer(add_completion=False, help="LLM (TradingAgents) algo trading for NSE/BSE.")


def _setup(config: str | None, broker: str | None = None, dry_run: bool = False) -> Settings:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    s = load_settings(config)
    if broker:
        s.broker.name = broker  # type: ignore[assignment]
    s.dry_run = s.dry_run or dry_run
    return s


def _engine(s: Settings):
    from indtrader.brokers import make_broker
    from indtrader.engine import Engine

    return Engine(s, make_broker(s))


ConfigOpt = typer.Option(None, "--config", "-c", help="config.yaml path")
BrokerOpt = typer.Option(None, "--broker", help="paper | zerodha | openalgo (overrides config)")


@app.command()
def analyze(
    config: str = ConfigOpt,
    on: str = typer.Option(None, "--date", help="analysis data date YYYY-MM-DD (default: previous trading day)"),
    symbols: str = typer.Option(None, help="comma-separated symbols (default: universe)"),
    force: bool = typer.Option(False, help="re-run even if a cached decision exists"),
    second_opinion: bool = typer.Option(None, "--second-opinion/--no-second-opinion",
                                        help="also ask the Vibe-Trading committee (default: config)"),
):
    """Run TradingAgents on each symbol (plus the optional Vibe-Trading second opinion) and cache the decisions."""
    from indtrader.signals.llm_agent import TradingAgentsAnalyzer
    from indtrader.strategy import BULLISH, combine_opinions

    s = _setup(config)
    if second_opinion is not None:
        s.second_opinion.enabled = second_opinion
    as_of = date.fromisoformat(on) if on else previous_trading_day(now_ist().date(), s.holidays)
    analyzer = TradingAgentsAnalyzer(s)
    vibe = None
    if s.second_opinion.enabled:
        from indtrader.signals.vibe_opinion import VibeTradingAnalyzer

        vibe = VibeTradingAnalyzer(s)
    for sym in symbols.split(",") if symbols else s.universe:
        sig = analyzer.analyze(sym.strip().upper(), as_of, force=force)
        line = f"{sig.symbol:<12} {sig.as_of}  TradingAgents={sig.rating:<11} stop={sig.stop_loss} target={sig.price_target}"
        if vibe and (sig.rating in BULLISH or not s.second_opinion.only_when_bullish):
            try:
                second = vibe.analyze(sig.symbol, as_of, force=force)
                final, note = combine_opinions(sig.rating, second, s.second_opinion)
                line += f"  Vibe={second.rating}({second.confidence})  -> {final}: {note}"
            except Exception as exc:
                line += f"  Vibe=FAILED ({exc})"
        typer.echo(line)


@app.command()
def trade(config: str = ConfigOpt, broker: str = BrokerOpt,
          dry_run: bool = typer.Option(False, "--dry-run", help="log orders, do not send"),
          force: bool = typer.Option(False, help="trade even when the market is closed (paper testing)")):
    """Rebalance once from the latest cached ratings."""
    s = _setup(config, broker, dry_run)
    if not force and not is_market_open(extra_holidays=s.holidays):
        typer.echo("market is closed (use --force for paper testing)")
        raise typer.Exit(1)
    typer.echo(json.dumps(_engine(s).rebalance(now_ist().date()), indent=2))


@app.command()
def monitor(config: str = ConfigOpt, broker: str = BrokerOpt, dry_run: bool = typer.Option(False, "--dry-run")):
    """Check stop-loss / take-profit once."""
    s = _setup(config, broker, dry_run)
    typer.echo(json.dumps(_engine(s).monitor(), indent=2))


@app.command()
def status(config: str = ConfigOpt, broker: str = BrokerOpt):
    """Show funds, bot positions and today's counters."""
    s = _setup(config, broker)
    typer.echo(json.dumps(_engine(s).status(), indent=2, default=str))


@app.command()
def run(config: str = ConfigOpt, broker: str = BrokerOpt, dry_run: bool = typer.Option(False, "--dry-run")):
    """Daily scheduler (IST): analysis -> execution -> monitoring -> EOD. Ctrl+C to stop."""
    from indtrader.scheduler import Scheduler

    s = _setup(config, broker, dry_run)
    Scheduler(_engine(s), s).run_forever(now_ist)


@app.command()
def brief(symbols: str = typer.Argument(..., help="comma-separated, e.g. RELIANCE,TCS"),
          on: str = typer.Option(None, "--date", help="data up to this date (default: previous trading day)"),
          config: str = ConfigOpt):
    """Print a JSON fact sheet (price, technicals, relative strength, fundamentals) per stock."""
    from indtrader.brief import build_brief

    s = _setup(config)
    as_of = date.fromisoformat(on) if on else previous_trading_day(now_ist().date(), s.holidays)
    out = []
    for sym in symbols.split(","):
        try:
            out.append(build_brief(sym.strip(), as_of, s.exchange, s.strategy.regime_index))
        except Exception as exc:
            out.append({"symbol": sym.strip().upper(), "error": str(exc)})
    typer.echo(json.dumps(out, indent=2, default=str))


@app.command("submit-signal")
def submit_signal(
    symbol: str,
    rating: str = typer.Option(..., help="Buy | Overweight | Hold | Underweight | Sell"),
    confidence: float = typer.Option(..., help="0-100"),
    thesis: str = typer.Option(..., help="2-6 sentences: why, key evidence, main risk"),
    stop: float = typer.Option(None, help="stop-loss price (below current price)"),
    target: float = typer.Option(None, help="price target"),
    on: str = typer.Option(None, "--date", help="analysis data date (default: previous trading day)"),
    source: str = typer.Option("claude-analyst"),
    config: str = ConfigOpt,
):
    """Validate and store an externally produced rating (used by the Claude analyst)."""
    from indtrader.signals.llm_agent import RATINGS, LLMSignal, SignalStore

    s = _setup(config)
    rating = rating.strip().capitalize()
    errors = []
    if rating not in RATINGS:
        errors.append(f"rating must be one of {RATINGS}")
    if not 0 <= confidence <= 100:
        errors.append("confidence must be 0-100")
    if len(thesis.strip()) < 40:
        errors.append("thesis too short: give the evidence")
    as_of = date.fromisoformat(on) if on else previous_trading_day(now_ist().date(), s.holidays)
    if stop is not None or target is not None:
        from indtrader.data import recent_history

        last = float(recent_history(symbol, as_of, lookback_days=30, exchange=s.exchange)["Close"].iloc[-1])
        if stop is not None and not (last * (1 - s.strategy.max_stop_pct) <= stop < last):
            errors.append(f"stop {stop} must be below close {last:.2f} and within {s.strategy.max_stop_pct:.0%}")
        if target is not None and target <= last:
            errors.append(f"target {target} must be above close {last:.2f}")
    if errors:
        typer.echo("REJECTED: " + "; ".join(errors))
        raise typer.Exit(1)
    sig = LLMSignal(symbol=symbol.upper(), as_of=as_of.isoformat(), rating=rating, stop_loss=stop,
                    price_target=target, summary=thesis.strip(), confidence=confidence, source=source)
    SignalStore(s.signals_root).put(sig)
    typer.echo(f"stored {sig.symbol} {sig.as_of} {rating} ({confidence:.0f}%) -> {s.signals_root}")


@app.command("is-trading-day")
def is_trading_day_cmd(on: str = typer.Option(None, "--date"), config: str = ConfigOpt):
    """Exit 0 if the date (default today, IST) is an NSE trading day, else 1."""
    s = _setup(config)
    d = date.fromisoformat(on) if on else now_ist().date()
    ok = is_trading_day(d, s.holidays)
    typer.echo(f"{d} {'is' if ok else 'is NOT'} a trading day; analysis date = {previous_trading_day(d, s.holidays) if ok else '-'}")
    raise typer.Exit(0 if ok else 1)


@app.command("vibe-check")
def vibe_check(config: str = ConfigOpt):
    """Check the Vibe-Trading install and preset (no LLM calls)."""
    from indtrader.signals.vibe_opinion import VibeTradingAnalyzer

    s = _setup(config)
    res = VibeTradingAnalyzer(s).check()
    typer.echo(json.dumps(res, indent=2))
    raise typer.Exit(0 if res.get("ok") else 1)


@app.command()
def halt(config: str = ConfigOpt, reason: str = typer.Option("manual", help="why")):
    """Kill switch: block every order until `indtrader resume`. Works while `run` is live."""
    s = _setup(config)
    s.path("HALT").write_text(f"{now_ist().isoformat()} {reason}\n")
    typer.echo(f"halted ({s.path('HALT')}). Open orders at the broker are NOT cancelled; check your broker app.")


@app.command()
def resume(config: str = ConfigOpt):
    """Remove the kill switch."""
    s = _setup(config)
    s.path("HALT").unlink(missing_ok=True)
    typer.echo("resumed")


@app.command()
def backtest(
    config: str = ConfigOpt,
    start: str = typer.Option(..., help="YYYY-MM-DD"),
    end: str = typer.Option(None, help="YYYY-MM-DD (default today)"),
    signals: str = typer.Option("technical", help="technical | llm (uses cached TradingAgents decisions)"),
    out: str = typer.Option(None, help="write trades CSV here"),
):
    """Backtest the strategy with Indian transaction costs."""
    from indtrader.backtest import llm_rating_fn, run_backtest, technical_rating

    s = _setup(config)
    fn = llm_rating_fn(s) if signals == "llm" else technical_rating
    from indtrader.validation import bootstrap_sharpe_ci, walk_forward

    res = run_backtest(s, date.fromisoformat(start), date.fromisoformat(end) if end else now_ist().date(), fn)
    report = {**res.stats, "sharpe_95ci": bootstrap_sharpe_ci(res.equity), "walk_forward": walk_forward(res.equity, 4, res.benchmark)}
    typer.echo(json.dumps(report, indent=2))
    if out:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        res.trades.to_csv(out, index=False)
        typer.echo(f"trades -> {out}")


@app.command("zerodha-login")
def zerodha_login(request_token: str = typer.Option(None, help="request_token from the redirect URL")):
    """Daily Kite Connect login: prints the login URL, then exchanges the request token."""
    from indtrader.brokers import zerodha

    _setup(None)
    if not request_token:
        typer.echo("Open this URL, log in, and copy `request_token` from the redirect URL:\n" + zerodha.login_url())
        request_token = typer.prompt("request_token")
    zerodha.exchange_request_token(request_token)
    typer.echo("access token saved to state/kite_access_token")


@app.command()
def costs(price: float, qty: int, product: str = "CNC", config: str = ConfigOpt):
    """Estimate round-trip charges for a trade."""
    s = _setup(config)
    cm = s.cost_model
    b, sl = cm.charges("BUY", qty, price, product), cm.charges("SELL", qty, price, product)
    typer.echo(f"buy Rs {b:.2f}  sell Rs {sl:.2f}  round trip Rs {b + sl:.2f} "
               f"({100 * cm.round_trip_pct(price, qty, product):.3f}% -> breakeven move)")


if __name__ == "__main__":
    app()
