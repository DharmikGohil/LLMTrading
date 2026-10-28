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
import time as _time
from datetime import date, datetime
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
):
    """Run TradingAgents on each symbol and cache the decision."""
    from indtrader.signals.llm_agent import TradingAgentsAnalyzer

    s = _setup(config)
    as_of = date.fromisoformat(on) if on else previous_trading_day(now_ist().date(), s.holidays)
    analyzer = TradingAgentsAnalyzer(s)
    for sym in symbols.split(",") if symbols else s.universe:
        sig = analyzer.analyze(sym.strip().upper(), as_of, force=force)
        typer.echo(f"{sig.symbol:<12} {sig.as_of}  {sig.rating:<11} stop={sig.stop_loss} target={sig.price_target}")


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
    from indtrader.notify import notify

    s = _setup(config, broker, dry_run)
    eng = _engine(s)
    sch = s.schedule
    done: dict[str, str] = {}
    last_monitor = 0.0
    notify(f"[indtrader] scheduler started: broker={s.broker.name} dry_run={s.dry_run} universe={s.universe}")

    def due(key: str, hhmm: str, now: datetime) -> bool:
        return now.strftime("%H:%M") >= hhmm and done.get(key) != now.date().isoformat()

    while True:
        now = now_ist()
        today = now.date()
        try:
            if is_trading_day(today, s.holidays):
                if due("analysis", sch.analysis_time, now):
                    eng.analyze_universe(today)
                    done["analysis"] = today.isoformat()
                if due("execution", sch.execution_time, now) and is_market_open(now, s.holidays):
                    eng.rebalance(today)
                    done["execution"] = today.isoformat()
                if is_market_open(now, s.holidays) and _time.monotonic() - last_monitor >= sch.monitor_interval_min * 60:
                    eng.monitor()
                    last_monitor = _time.monotonic()
                if due("eod", sch.eod_time, now):
                    eng.square_off_intraday()
                    st = eng.status()
                    notify("[indtrader] EOD: funds Rs {:,.0f}, positions: {}".format(
                        st["funds"], ", ".join(f"{p['symbol']} {p['qty']} ({p['unrealized']:+,.0f})" for p in st["positions"]) or "none"))
                    done["eod"] = today.isoformat()
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            logging.exception("scheduler step failed")
            notify(f"[indtrader] ERROR: {exc}")
        _time.sleep(30)


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
    res = run_backtest(s, date.fromisoformat(start), date.fromisoformat(end) if end else now_ist().date(), fn)
    typer.echo(json.dumps(res.stats, indent=2))
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
