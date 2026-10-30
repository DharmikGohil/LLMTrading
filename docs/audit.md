# Audit: what was taken from each project, and why

Status as of 30 October 2026. Every item is checked against the code. "Adopted" means it is in the code
and covered by tests or playbooks; "planned" is on the [roadmap](roadmap.md); "skipped" gives the reason.
An audit cannot make a strategy profitable. It checks that the system does what it claims, that the
good ideas from these projects are in it, and that the risky ones were left out on purpose.

## TradingAgents (TauricResearch, Apache-2.0, dependency)

| Idea | Status | Where / why |
|---|---|---|
| Multi-agent analysis (analysts, bull/bear debate, trader, risk team, PM) | Adopted, optional | `indtrader/signals/llm_agent.py`, `indtrader analyze`, `llm.signal_source: tradingagents` |
| Portfolio context, cached decisions, stop/target parsing | Adopted | same module, tests in `tests/test_opinions.py` and `tests/test_strategy_risk.py` |
| Majority vote over several runs (non-determinism) | Adopted | `llm.runs` |
| The LLM as the stock picker | Skipped as default | Controlled studies show no reliable stock-picking edge; the desks use the LLM as a veto (see [research](research.md)) |

## Vibe-Trading (HKUDS, MIT)

| Idea | Status | Where / why |
|---|---|---|
| Investment-committee swarm as a second opinion | Adopted, optional | `indtrader/vibe/` read-only India preset, `indtrader/signals/vibe_opinion.py`, own virtualenv |
| Backtest validation (bootstrap, walk-forward) | Adopted | `indtrader/validation.py` |
| File kill switch | Adopted | `indtrader halt` / `resume` |
| Alpha zoo, paper simulator | Skipped | No NSE universe; its simulator does not cover India |

## ai-hedge-fund (virattt, MIT)

| Idea | Status | Where / why |
|---|---|---|
| Keep the LLM away from execution | Adopted | The engine executes; ratings are inputs only |
| Scorecard per signal source | Adopted | `indtrader scorecard` |
| Kill switch, risk limits, costs | Adopted | `indtrader/risk.py`, `costs.py`, `halt` |
| Point-in-time honesty in backtests | Adopted | Backtests decide on the previous day's data and trade at the open |
| Post-earnings announcement drift (PEAD) model | Planned | A documented anomaly: after a clear beat, prices tend to keep drifting. Candidate rule: do not veto a candidate whose results were a clear beat and raise (the LLY case, 29 Oct) |
| Append-only, hash-chained paper ledger | Planned | A tamper-evident track record. Git history is the record today |
| Investor personas (Buffett, Munger, Graham, Lynch, Druckenmiller) | Skipped | No out-of-sample evidence that persona prompts add skill |

## finance-skills (himself65, MIT)

| Idea | Status | Where / why |
|---|---|---|
| SEPA trend template (Minervini) | Adopted | `indtrader/screen.py` (`trend_template`), `indtrader brief`; skill in `.claude/skills/sepa-strategy` |
| Earnings preview, estimate revisions | Adopted | `.claude/skills/earnings-preview`, `estimate-analysis`; used by the US review |
| Correlation, liquidity | Adopted | `.claude/skills/stock-correlation`, `stock-liquidity`; weekly correlation check at the close |
| Options payoff | Adopted | `.claude/skills/options-payoff`, for the options desk |
| Social sentiment (Adanos API), social readers | Skipped | Needs a paid API; social chatter says little about most Indian stocks |

## day-trader-skill (Jakeschincariol, MIT)

| Idea | Status | Where / why |
|---|---|---|
| SEC news and 8-K feed, filed earnings facts, Congress trades | Adopted | `.claude/skills/trader-news`, `trader-analyst`, `trader-pelosi`; in the US review |
| Scanner, entry, exit, budget, risk, alerts, broker | Adopted as tools | Available for a US intraday paper desk; the swing desks keep `indtrader`'s own risk engine |
| Time machine (replay a setup's own history) | Planned | Rebuilt for Nifty options before each entry |

## QuantJourney backtester (Apache-2.0)

| Idea | Status | Where / why |
|---|---|---|
| Deflated Sharpe ratio | Adopted | `indtrader/validation.py`, `indtrader backtest --trials` |
| Drawdown circuit breaker | Adopted, **on** | `risk.max_drawdown_pct: 0.10`; backtest: max drawdown −18.6% → −11.5% (`journal/changes.md`) |
| Volatility targeting | Adopted, **off** | Tested: lowered returns on Nifty 200 2024–2026 |
| Drift bands / turnover budget | Planned | Trade only when a position drifts past a band, to cut costs |
| Purged and anchored walk-forward | Planned | Today: consecutive windows without purging |
| Inverse-volatility and risk-parity sizing | Covered | Positions are already sized by risk to an ATR stop |
| Futures trend (Donchian, ATR contracts) | Skipped | One Nifty lot needs about ₹1.8–2 lakh margin; above the desk's capital |

## Research and other projects

FinRobot (numbers in code, narrative by the LLM), marketcalls/AutoAgent (the LLM may only scale risk down),
FINSABER, StockBench, LiveTradeBench, LiveOption and the SEBI F&O studies shaped the design; see
[research](research.md).
