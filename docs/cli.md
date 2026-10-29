# CLI reference

Every command takes `--config/-c` (default `config/config.yaml`, or `$INDTRADER_CONFIG`). Run
`indtrader <command> --help` for all options.

## Analysis

| Command | What it does |
|---|---|
| `indtrader screen` | Momentum + low-volatility + trend screen: today's candidate stocks. |
| `indtrader brief` | Print a JSON fact sheet (price, technicals, relative strength, fundamentals) per stock. |
| `indtrader analyze` | Run TradingAgents on each symbol (plus the optional Vibe-Trading second opinion) and cache the decisions. |
| `indtrader submit-signal` | Validate and store an externally produced rating (used by the Claude analyst). |
| `indtrader recent-picks` | Symbols rated Buy/Overweight recently (likely still held): the analyst must keep rating them. |
| `indtrader vibe-check` | Check the Vibe-Trading install and preset (no LLM calls). |

## Trading

| Command | What it does |
|---|---|
| `indtrader trade` | Rebalance once from the latest ratings (main account and shadow arms). |
| `indtrader monitor` | Check stop-loss / take-profit once (main account and shadow arms). |
| `indtrader eod` | End of day: intraday square-off (MIS only) and the daily equity record for every account. |
| `indtrader run` | Daily scheduler (IST): analysis -> execution -> monitoring -> EOD. Ctrl+C to stop. |
| `indtrader status` | Show funds, bot positions and today's counters. |
| `indtrader halt` | Kill switch: block every order until `indtrader resume`. Works while `run` is live. |
| `indtrader resume` | Remove the kill switch. |
| `indtrader is-trading-day` | Exit 0 if the date (default today, IST) is an NSE trading day, else 1. |
| `indtrader zerodha-login` | Daily Kite Connect login: prints the login URL, then exchanges the request token. |

## Review and learning

| Command | What it does |
|---|---|
| `indtrader review` | Close-of-day facts: orders, vetoes and graded analyst calls -> journal/daily/<date>-<market>.md. |
| `indtrader lessons` | Active lessons, confirmed first. Analyst runs read these before reviewing stocks. |
| `indtrader lesson` | The desk's lesson book (journal/lessons.json). |
| `indtrader scorecard` | Grade all stored ratings (LLM, second opinion, screen) against Nifty-relative outcomes. |
| `indtrader compare` | Main account vs shadow arms vs the index, from each equity.csv (written daily at EOD). |

## Research and reporting

| Command | What it does |
|---|---|
| `indtrader backtest` | Backtest the strategy with Indian transaction costs. |
| `indtrader costs` | Estimate round-trip charges for a trade. |
| `indtrader export-dashboard` | Write the dashboard's data (accounts, positions, trades, decisions, analyst calls, equity) as JSON. |

## Common recipes

```bash
indtrader screen --save                      # candidates, saved for the analyst
indtrader brief LAURUSLABS,DIVISLAB          # facts the analyst reviews
indtrader submit-signal HAL --rating Overweight --confidence 57 --thesis "... (source, date)"
indtrader trade --dry-run                    # see the plan without orders
indtrader monitor && indtrader eod && indtrader review
indtrader compare                            # LLM-reviewed vs control vs index
indtrader backtest --start 2024-01-01 --out state/bt.csv
```
