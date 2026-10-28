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
    """Rebalance once from the latest ratings (main account and shadow arms)."""
    s = _setup(config, broker, dry_run)
    if not force and not is_market_open(extra_holidays=s.holidays):
        typer.echo("market is closed (use --force for paper testing)")
        raise typer.Exit(1)
    for name, eng in _all_books(s).items():
        if s.llm.signal_source == "external" and name == "main":
            eng.sync_signals()
        typer.echo(f"== {name}")
        typer.echo(json.dumps(eng.rebalance(now_ist().date()), indent=2))


@app.command()
def monitor(config: str = ConfigOpt, broker: str = BrokerOpt, dry_run: bool = typer.Option(False, "--dry-run")):
    """Check stop-loss / take-profit once (main account and shadow arms)."""
    s = _setup(config, broker, dry_run)
    for name, eng in _all_books(s).items():
        typer.echo(f"== {name}: " + json.dumps(eng.monitor()))


@app.command()
def eod(config: str = ConfigOpt, broker: str = BrokerOpt):
    """End of day: intraday square-off (MIS only) and the daily equity record for every account."""
    s = _setup(config, broker)
    today = now_ist().date()
    for name, eng in _all_books(s).items():
        eng.square_off_intraday()
        typer.echo(f"== {name}: " + json.dumps(eng.record_equity(today)))


def _all_books(s: Settings) -> dict:
    main = _engine(s)
    return {"main": main, **_shadow_arms(s, main)}


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
    main = _engine(s)
    Scheduler(main, s, _shadow_arms(s, main)).run_forever(now_ist)


def _shadow_arms(s: Settings, main) -> dict:
    """Paper accounts with other signal modes, sharing the main engine's data (screen, NSE, signals)."""
    from indtrader.brokers.paper import PaperBroker
    from indtrader.data import last_price
    from indtrader.engine import Engine

    arms = {}
    for mode in s.shadow_arms:
        if mode == s.strategy.signal_mode and s.broker.name == "paper":
            continue   # the main account already is this arm
        a = s.model_copy(deep=True)
        a.data_dir = str(Path(s.data_dir) / "arms" / mode)
        a.signals_dir = str(s.signals_root)
        a.strategy.signal_mode = mode
        a.dry_run = False
        a.broker.name = "paper"
        a.broker.paper_state_file = str(Path(a.data_dir) / "paper_account.json")
        a.shadow_arms = []
        eng = Engine(a, PaperBroker(a.broker.paper_state_file, a.risk.capital, a.cost_model, price_fn=last_price))
        eng.screen_table = main.screen_table
        eng._nse = main.nse
        arms[mode] = eng
    return arms


@app.command()
def scorecard(horizon: int = typer.Option(10, help="trading days after the signal"),
              out: str = typer.Option(None, help="write every graded signal to this CSV"),
              config: str = ConfigOpt):
    """Grade all stored ratings (LLM, second opinion, screen) against Nifty-relative outcomes."""
    from indtrader.scorecard import run_scorecard

    s = _setup(config)
    graded, summary = run_scorecard({"tradingagents": s.signals_root, "vibe-trading": s.path("signals_vibe", "_").parent},
                                    horizon, s.strategy.regime_index)
    if summary.empty:
        typer.echo("no signals stored yet")
        raise typer.Exit(0)
    typer.echo(summary.to_string(index=False))
    typer.echo(f"\nexcess = stock minus Nifty over {horizon} trading days after the next open. "
               "Meaningful after ~100+ graded calls; a positive bullish-minus-bearish spread and rank IC are the goal.")
    if out:
        graded.to_csv(out, index=False)


@app.command("export-dashboard")
def export_dashboard(out: str = typer.Option("public", help="output folder for the JSON row files"), config: str = ConfigOpt):
    """Write the dashboard's data (accounts, positions, trades, decisions, analyst calls, equity) as JSON."""
    from indtrader import data as market_data
    from indtrader.export import export

    s = _setup(config)
    res = export(s, Path(out), lambda sym: market_data.last_price(sym, s.exchange))
    for r in res["summary"]:
        typer.echo(f"{r['market']:6} {r['book']:7} equity {r['equity']:>12,.2f} {r['currency']}  "
                   f"return {r['return_pct']:+.2f}%  positions {r['open_positions']}  trades {r['trades']}")
    typer.echo(f"wrote {len(res)} files to {out}/")


@app.command()
def compare(config: str = ConfigOpt):
    """Main account vs shadow arms vs the index, from each equity.csv (written daily at EOD)."""
    import pandas as pd

    s = _setup(config)
    books = {"main": Path(s.data_dir) / "equity.csv"}
    books.update({m: Path(s.data_dir) / "arms" / m / "equity.csv" for m in s.shadow_arms})
    rows = []
    for name, f in books.items():
        if not f.exists():
            continue
        df = pd.read_csv(f)
        if len(df) < 1:
            continue
        r = {"book": name, "since": df["date"].iloc[0], "days": len(df),
             "return_pct": round(100 * (df["equity"].iloc[-1] / df["equity"].iloc[0] - 1), 2),
             "realized_pnl": df["realized_pnl"].iloc[-1]}
        idx = pd.to_numeric(df["index_close"], errors="coerce").dropna()
        if len(idx) > 1:
            r["nifty_pct"] = round(100 * (idx.iloc[-1] / idx.iloc[0] - 1), 2)
        rows.append(r)
    if not rows:
        typer.echo("no equity history yet (written at end of day by `indtrader run`)")
        raise typer.Exit(0)
    typer.echo(pd.DataFrame(rows).to_string(index=False))
    typer.echo("\nJudge the LLM only after months of data: compare 'main' (hybrid) with 'factor' (LLM off).")


@app.command()
def brief(symbols: str = typer.Argument(..., help="comma-separated, e.g. RELIANCE,TCS"),
          on: str = typer.Option(None, "--date", help="data up to this date (default: previous trading day)"),
          config: str = ConfigOpt):
    """Print a JSON fact sheet (price, technicals, relative strength, fundamentals) per stock."""
    from indtrader.brief import build_brief

    s = _setup(config)
    as_of = date.fromisoformat(on) if on else previous_trading_day(now_ist().date(), s.holidays)
    from indtrader.nse import NSEData, NullNSE

    nse = NSEData(s.path("nse", "_").parent, now_ist().date()) if s.nse_checks else NullNSE()
    out = []
    for sym in symbols.split(","):
        sym = sym.strip().upper()
        try:
            b = build_brief(sym, as_of, s.exchange, s.strategy.regime_index)
        except Exception as exc:
            out.append({"symbol": sym, "error": str(exc)})
            continue
        upcoming = sorted(d for d in nse.results_dates().get(sym, []) if d >= now_ist().date())
        series = nse.series().get(sym)
        b["nse"] = {"upcoming_results": [str(d) for d in upcoming[:2]],
                    "surveillance": nse.surveillance().get(sym),
                    "series_band": list(series) if series else None,
                    "recent_filings": nse.announcements(sym, 8)}
        out.append(b)
    typer.echo(json.dumps(out, indent=2, default=str))


@app.command()
def screen(
    on: str = typer.Option(None, "--date", help="data up to this date (default: previous trading day)"),
    index: str = typer.Option(None, help="nifty50 | nifty100 | nifty200 | nifty500 (default: config)"),
    top: int = typer.Option(None, help="number of candidates (default: config screen.top_n)"),
    save: bool = typer.Option(False, help="write <signals_dir>/<date>/_screen.json"),
    config: str = ConfigOpt,
):
    """Momentum + low-volatility + trend screen: today's candidate stocks."""
    from datetime import timedelta

    from indtrader.screen import download_closes, index_members, score_universe

    s = _setup(config)
    sc = s.screen
    index, top = index or sc.index, top or sc.top_n
    as_of = date.fromisoformat(on) if on else previous_trading_day(now_ist().date(), s.holidays)
    members = index_members(index, s.path("universe", "_").parent)
    table = score_universe(download_closes(members, as_of - timedelta(days=420), as_of), as_of,
                           min_traded_value_cr=sc.min_traded_value_cr,
                           vol_exclude_pct=sc.vol_exclude_pct, trend_template_required=sc.trend_template)
    picks = table[table["eligible"]].head(top)
    typer.echo(picks.to_string(index=False))
    typer.echo(f"\n{int(table['eligible'].sum())} of {len(table)} {index} stocks eligible; top {top} shown (data to {as_of})")
    if save:
        out = s.signals_root / as_of.isoformat() / "_screen.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"as_of": as_of.isoformat(), "index": index, "top_n": top,
                                   "candidates": picks["symbol"].tolist(),
                                   "table": table.head(3 * top).to_dict(orient="records")}, indent=2, default=str))
        typer.echo(f"saved {out}")


@app.command("recent-picks")
def recent_picks(days: int = typer.Option(20, help="look back this many calendar days"), config: str = ConfigOpt):
    """Symbols rated Buy/Overweight recently (likely still held): the analyst must keep rating them."""
    from datetime import timedelta

    from indtrader.signals.llm_agent import SignalStore

    s = _setup(config)
    store = SignalStore(s.signals_root)
    since = (now_ist().date() - timedelta(days=days)).isoformat()
    picks = set()
    for d in sorted(p.name for p in s.signals_root.iterdir() if p.is_dir() and p.name >= since):
        for sym in store.symbols_on(d):
            sig = store.get(sym, d)
            if sig and sig.rating in ("Buy", "Overweight"):
                picks.add(sym)
    typer.echo(",".join(sorted(picks)))


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
    signals: str = typer.Option("technical", help="technical | llm (cached decisions) | momentum (factor arm on screen.index)"),
    out: str = typer.Option(None, help="write trades CSV here"),
):
    """Backtest the strategy with Indian transaction costs."""
    from datetime import timedelta

    from indtrader.backtest import llm_rating_fn, momentum_rating_fn, run_backtest, technical_rating
    from indtrader.validation import bootstrap_sharpe_ci, walk_forward

    s = _setup(config)
    d0, d1 = date.fromisoformat(start), date.fromisoformat(end) if end else now_ist().date()
    histories = benchmark = None
    if signals == "momentum":
        from indtrader import data as market_data
        from indtrader.screen import download_closes, index_members

        members = index_members(s.screen.index, s.path("universe", "_").parent)
        histories = download_closes(members, d0 - timedelta(days=420), d1)
        typer.echo(f"momentum arm on {len(histories)} {s.screen.index} stocks "
                   "(today's members: survivorship bias flatters this)", err=True)
        fn = momentum_rating_fn(histories, s)
        benchmark = market_data.history(s.strategy.regime_index, d0 - timedelta(days=400), d1)["Close"]
    else:
        fn = llm_rating_fn(s) if signals == "llm" else technical_rating
    res = run_backtest(s, d0, d1, fn, histories=histories, benchmark=benchmark)
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
