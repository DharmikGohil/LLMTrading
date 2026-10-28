# LLMTrading — TradingAgents algo trading for the Indian market (NSE/BSE)

An end-to-end algorithmic trading system for Indian equities. It uses
[TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents)
(multi-agent LLM analysis) as the signal and adds what TradingAgents
deliberately does not include: Indian market calendar, position sizing, risk
limits, Indian transaction costs, broker execution (Zerodha / 25+ brokers via
OpenAlgo / paper), stop-loss monitoring, a scheduler and a backtester.

> **Risk warning.** This is research software. LLM ratings are non-deterministic
> and unproven as an edge. Most retail F&O and intraday traders in India lose
> money (SEBI studies). Backtest, then paper trade for months, then go live with
> money you can afford to lose. Nothing here is investment advice.

## How it works

```
08:30 IST  analyze   TradingAgents on each stock in the universe (data up to previous close)
                     Market + Social + News + Fundamentals analysts
                     -> Bull vs Bear debate -> Trader -> Risk team -> Portfolio Manager
                     -> rating: Buy / Overweight / Hold / Underweight / Sell (+ stop, target)
                     (optional: N runs + majority vote)  -> state/signals/<date>/<SYMBOL>.json
           2nd opinion  (optional) Vibe-Trading "India investment committee" swarm on the
                     stocks TradingAgents wants to buy: bull vs bear -> CRO -> PM verdict
                     -> state/signals_vibe/<date>/<SYMBOL>.json
09:30 IST  trade     ratings combined (2nd opinion can only veto/shrink buys)
                     + trend/RSI filter + market regime (Nifty vs 200-DMA)
                     -> target qty -> risk checks -> LIMIT orders
every 5m   monitor   stop-loss / take-profit exits
15:20 IST  eod       MIS square-off (if intraday), daily summary (Telegram)
```

| Module | What it does |
|---|---|
| `indtrader/signals/llm_agent.py` | Wraps `TradingAgentsGraph`: `.NS` tickers, Nifty benchmark, Indian macro news queries, Yahoo fundamentals (SEC EDGAR is US-only), passes your holdings as portfolio context, caches decisions, parses the Trader's stop-loss and the PM's price target |
| `indtrader/strategy.py` | Long-only mapping: Buy/Overweight may **add** (only if close > EMA50 and RSI < 75); Underweight/Sell may only **trim** (not within `min_hold_days` of entry); Hold/REVIEW/stale = no change. Size = min(20% allocation, 1%-risk-to-stop), halved when Nifty is below its 200-day average. `combine_opinions` merges the second opinion |
| `indtrader/signals/vibe_opinion.py` + `indtrader/vibe/` | Vibe-Trading bridge: our read-only India committee preset (no shell, no trading tools), a runner executed in Vibe-Trading's own virtualenv, verdict parsing and caching |
| `indtrader/risk.py` | Daily-loss kill switch, max open positions, exposure/position caps, cash, max orders/day, min order value, "price ran away from analysed close" guard |
| `indtrader/costs.py` | STT, stamp duty, exchange txn, SEBI fee, GST, DP charge, brokerage (delivery vs intraday) |
| `indtrader/market.py` | IST session times, 2026 NSE holidays, special sessions, tick rounding, symbol mapping |
| `indtrader/brokers/` | `paper` (simulated with costs), `zerodha` (Kite Connect), `openalgo` (Angel One, Dhan, Upstox, Fyers, Kotak, 5paisa, Shoonya, ...) |
| `indtrader/engine.py` | Orchestration, order fill tracking, trailing stops, re-entry cooldown, trade journal (`state/trades.csv`) |
| `indtrader/backtest.py` | Daily portfolio backtest with the same sizing/risk/regime code and Indian costs; compares with Nifty and equal-weight buy-and-hold of the same stocks |
| `indtrader/validation.py` | Block-bootstrap confidence interval for Sharpe, walk-forward windows vs Nifty |

**Safety by design**
- **Only its own shares:** the bot sells only shares it bought itself (tracked in
  `state/bot_state.json`), so your long-term holdings in the same demat account are never touched.
- **Own cash ledger:** capital + realised P&L − open positions − charges. It never spends more
  than `risk.capital` (plus profits), even if the account holds more, and the daily-loss kill
  switch sees the bot's real P&L.
- **Pending orders:** while an order is working at the broker, no second order is sent for that
  stock, so there are no duplicate buys or exits. Partial fills are tracked, and an order whose
  placement timed out is looked up in the broker's order book before anything else happens.
- **Orders:** marketable LIMIT orders on NSE's price-band tick grid (0.01 / 0.05 / 0.10 / 0.50 / 1 / 5),
  never naked market orders. Stops only move up. `--dry-run` mode and `indtrader halt` kill switch.
- **Scheduler:** each step has its own error handling, analysis runs in the background so
  stop-loss monitoring never pauses, and progress is saved so a restart never repeats the day's trades.
- **Zerodha:** the morning `zerodha-login` token is picked up by a running scheduler automatically.

## Setup

```bash
git clone <this repo> && cd LLMTrading
python -m venv .venv && source .venv/bin/activate      # Python 3.11+
pip install -e ".[dev]"                 # installs TradingAgents v0.7.1 too
pip install -e ".[zerodha]"             # or ".[openalgo]" for live trading

cp .env.example .env                    # add your LLM API key (Anthropic/OpenAI/Google/...)
cp config/config.example.yaml config/config.yaml   # universe, capital, risk, broker
pytest                                  # 62 tests, no network/LLM needed
```

### Optional: Vibe-Trading second opinion
Vibe-Trading must live in its **own virtualenv** (it and TradingAgents both ship
a top-level `cli` package, so they would overwrite each other):

```bash
scripts/install_vibe.sh                 # -> ~/vibe-venv, validates our preset
indtrader vibe-check                    # re-check any time (no LLM calls)
```
Then set `second_opinion.enabled: true` in `config/config.yaml` and the model
for Vibe-Trading in `.env` (`LANGCHAIN_PROVIDER`, `LANGCHAIN_MODEL_NAME`, API key).
`indtrader analyze --second-opinion` shows both verdicts and the combined result.

| `second_opinion.mode` | TradingAgents Buy/Overweight is executed when Vibe-Trading says |
|---|---|
| `veto` (default) | anything except confident Underweight/Sell (a confident Hold turns Buy into Overweight) |
| `confirm` | confident Buy/Overweight only |

Sells and holds are never changed by the second opinion. If it fails,
`on_missing: hold` skips new buys that day. **Never use it for backtests**: its
data tools always return today's data (the code refuses past dates).

## Option A: Claude as your morning analyst (no API key)

Instead of running TradingAgents with a paid API key, a scheduled Claude Code
session on your Claude plan does the analysis every trading morning at
**07:40 IST**, following [`analyst/PLAYBOOK.md`](analyst/PLAYBOOK.md):
- `indtrader screen --save` produces the day's momentum candidates.
- `indtrader brief A,B,C` gives it real price and technical data, plus NSE filings, results dates and surveillance status.
- It searches the web for India news and checks each candidate against a red-flag list.
- It submits ratings through `indtrader submit-signal`, which validates them.
- It commits `signals/<date>/*.json` plus a `REPORT.md` with sources.

Your trading machine (laptop or VPS) pulls those ratings and trades them with
all the normal rules. In `config/config.yaml`:

```yaml
screen: {index: nifty200, top_n: 12}   # same as config/analyst.yaml
strategy: {signal_mode: hybrid}
shadow_arms: [factor]
signals_dir: signals
signal_sync: git          # git pull before using signals
llm:
  signal_source: external # do not run TradingAgents here
broker:
  name: paper             # start with paper!
```
Then `indtrader run`: at 08:30 it pulls and reports the ratings, and at 09:30 it trades them.

**Vibe-Trading on your Claude login (option B):** in `.env` set
`LANGCHAIN_PROVIDER=claude-cli` and `LANGCHAIN_MODEL_NAME=claude-opus-5-5`. With the
`claude` command logged in on that machine, the second-opinion committee needs no API key.

## Recommended path to live trading

1. **Understand costs:** `indtrader costs 2500 40` prints buy+sell charges and the
   break-even move (~0.24% round trip for delivery).
2. **Backtest the plumbing** (free, technical signals):
   `indtrader backtest --start 2024-01-01 --out state/bt.csv`
3. **Generate LLM signals** for a day: `indtrader analyze` (each stock = one full
   multi-agent run, a few minutes and some LLM cost). For an LLM backtest, run
   `indtrader analyze --date YYYY-MM-DD` for past dates, then
   `indtrader backtest --start ... --signals llm`.
4. **Paper trade** for 1-3 months with real-time decisions:
   `indtrader run --broker paper` (leave running on a server/VM in IST hours),
   check with `indtrader status` and `state/trades.csv`.
5. **Go live small:** `broker.name: zerodha` (or `openalgo`), small `risk.capital`,
   first day with `--dry-run`.

One-off commands: `indtrader trade [--dry-run] [--force]`, `indtrader monitor`,
`indtrader status`. Emergency stop: `indtrader halt` (creates `state/HALT`; the
running scheduler sends no orders until `indtrader resume`).

Every backtest also prints a **bootstrap 95% confidence interval for Sharpe**
and a **walk-forward** split (excess return vs Nifty per window). Treat a
strategy as unproven unless `edge_shown` is true and most windows beat Nifty.

### Zerodha (Kite Connect)
Create an app at developers.kite.trade (paid API subscription), set
`KITE_API_KEY`/`KITE_API_SECRET`, then every morning run `indtrader zerodha-login`
(Kite tokens expire daily; SEBI's framework requires daily 2FA anyway).

### Other brokers (OpenAlgo)
Run [OpenAlgo](https://github.com/marketcalls/openalgo) (self-hosted, open
source), log in to your broker there, set `OPENALGO_API_KEY` and
`broker.name: openalgo`.

## SEBI retail algo rules (in force since 2026)

The SEBI retail algo framework (full implementation deadline extended to
1 April 2026) requires, via your broker:
- API orders only from a **registered app on a whitelisted static IP** (run the
  bot on a VPS with a static IP and register it in your broker's developer console),
- **daily 2FA login** (no perpetual tokens),
- orders tagged with an exchange **Algo ID** (set `KITE_ALGO_ID` if your broker gives one),
- staying **under 10 orders/second** keeps you a regular API user (this bot sends
  a handful of orders per day).

Check your broker's current notice before going live. These rules change.

## What the evidence says about LLM trading (and what we did about it)

Research summary (October 2026):
- **FINSABER** (KDD 2026, 20 years of S&P 500 including delisted stocks): published
  LLM agents (FinMem, FinAgent) did **not** beat buy-and-hold. They were too cautious in
  bull markets and too aggressive in bear markets
  ([arXiv 2505.07078](https://arxiv.org/abs/2505.07078)).
- **StockBench** ([arXiv 2510.02209](https://arxiv.org/abs/2510.02209)): best models made
  +1.9–2.5% vs buy-and-hold +0.4% over 4 months, with large run-to-run variance; no agent
  beat buy-and-hold in the downturn. **LiveTradeBench** ([arXiv 2511.03628](https://arxiv.org/abs/2511.03628)):
  general LLM leaderboard rank does not predict trading results.
- **nof1 Alpha Arena**: most models lost money. The worst traders overtraded.
- **Look-ahead**: LLMs memorise past prices and news, so backtests on dates before the
  model's training cutoff are inflated ([FinCAD, arXiv 2605.24564](https://arxiv.org/abs/2605.24564)).

A deeper review (Oct 2026: benchmark papers read in full, code of the top repos,
practitioner reports, NSE rules) sharpened this. In properly controlled tests
no study shows LLMs reliably picking stocks. A 2026 China study found 9 of 10
agents had negative stock-selection skill. Two things do have evidence:
**rule-based momentum/low-vol stock selection in India** (NSE factor indices beat
the Nifty since 2005), and **LLMs catching negative news and red flags**.

Design choices that follow from this:
1. **Hybrid mode (default):** a Nifty 200 momentum + low-volatility + trend screen
   (`indtrader screen`) proposes the stocks. The LLM review can only **veto or shrink**
   them, never add a stock. `signal_mode: llm` (the LLM drives) and `factor` (screen only) remain available.
2. **Measure it:** a paper "LLM off" shadow account (`shadow_arms: [factor]`) trades alongside;
   `indtrader compare` and `indtrader scorecard` (hit rate, bullish/bearish spread and rank IC vs Nifty)
   show whether the LLM earns its cost.
3. **India safety data from NSE:** skip ASM/GSM and trade-for-trade stocks, no buys just before results,
   rescale positions on splits and bonuses, cap positions per sector.
4. A **regime filter** shrinks new buys when Nifty is below its 200-day average.
5. **Non-determinism**: `llm.runs: 3` gives a majority vote; disagreement means Hold.
6. **Several independent reviewers** (Claude analyst or TradingAgents, plus optional Vibe-Trading) can each veto a buy.
7. **Anti-overtrading**: minimum holding period, re-entry cooldown after stops, sector cap, and costs in every backtest.
8. **Honest evaluation**: compare against Nifty *and* equal-weight buy-and-hold, require a Sharpe CI above 0,
   and judge LLM signals on **paper trading after the model's training cutoff**, not on old backtests.

## Backtests (Jan 2024 – Oct 2026, Nifty 200, Indian costs)

| Variant | Return | Max drawdown | Trades | Charges | Windows beating Nifty |
|---|---|---|---|---|---|
| Momentum screen, swing exits (2×ATR stop, 2.5R target) | −7.0% | −21% | 646 | ₹12,965 | 1/4 |
| … + SEPA trend template | −10.4% | −28% | 721 | ₹14,584 | 2/4 |
| Slow momentum book (4×ATR stop, no target, 20-day hold) | −1.5% | −23% | 357 | ₹5,356 | 2/4 |
| **Slow book + SEPA (current default)** | **+10.2%** | −20% | 473 | ₹7,199 | 3/4 |
| Nifty 50 buy-and-hold | +4.6% | | | | |

Today's index members are used throughout, so survivorship bias flatters every row. None of these
shows a statistically proven edge (all Sharpe 95% ranges cross zero). The LLM layer cannot be
backtested honestly at all, so it is judged on forward paper trading against the "LLM off" control.

## Known limitations / ideas
- TradingAgents' Social analyst reads StockTwits/Reddit, which say little about
  most Indian stocks. Consider `analysts: [market, news, fundamentals]` to save cost.
- Yahoo daily data is fine for swing trading; for live prices the engine uses the broker LTP.
- Stops are monitored by the bot (every 5 min). For CNC positions you can also add
  broker-side GTT orders as a backstop in case the bot is down.
- Update `NSE_HOLIDAYS` in `indtrader/market.py` each December from the
  [NSE holiday page](https://www.nseindia.com/resources/exchange-communication-holidays).
- F&O (NIFTY/BANKNIFTY options) is not implemented. LLM analysis takes minutes,
  which suits daily swing decisions, not intraday option scalping.

## How this compares with Vibe-Trading (HKUDS)

[Vibe-Trading](https://github.com/HKUDS/Vibe-Trading) (MIT) is a large LLM
research workspace: chat agent, 29 multi-agent "swarm" presets, 29 data
sources, 478-alpha factor zoo, backtests with Monte Carlo/bootstrap/walk-forward,
MCP server and web UI. For **Indian live trading** it does not fit:
- Its Zerodha, Dhan, Shoonya and mStock connectors are **paper-only or read-only
  by design**: there is no live order path for any Indian broker.
- Its paper-trading simulator covers China A-shares, Hong Kong and the US only, not India.
- The alpha-zoo benchmark is limited to CSI300, S&P 500 and BTC-USDT (no NSE universe).
- It does have an India daily backtest engine (delivery costs, T+1, circuit bands), and
  `india_broker` historical data from Zerodha, Shoonya or Dhan.

How we combine them: Vibe-Trading's committee is wired in as an optional second
opinion (above), running in its own virtualenv with read-only tools. This repo
does the execution. Ideas borrowed: statistical validation of backtests and a
file-based kill switch.

## Ideas borrowed from other projects
- **ai-hedge-fund v2** (virattt): keep the LLM away from execution; grade every signal source with a scorecard.
- **finance-skills** (himself65, MIT): Minervini's SEPA trend template (`screen.trend_template`, and in `indtrader brief`).
- **FinRobot**: "numbers are code-calculated, narratives are LLM-assisted" (the brief computes, the analyst interprets).
- **marketcalls/AutoAgent**: the LLM may only scale risk down, never up.
- **Vibe-Trading**: backtest validation and a file kill switch.

## Related open-source projects
- [TradingAgents](https://github.com/TauricResearch/TradingAgents): the multi-agent LLM analyst/trader used here
- [Vibe-Trading](https://github.com/HKUDS/Vibe-Trading): the second-opinion committee
- [AI-Trader](https://github.com/HKUDS/AI-Trader), [ai-hedge-fund](https://github.com/virattt/ai-hedge-fund), [FinRobot](https://github.com/AI4Finance-Foundation/FinRobot): other LLM trading agents
- [Agentic-Trader](https://github.com/marketcalls/Agentic-Trader): LLM agent trading NSE through OpenAlgo
- [OpenAlgo](https://github.com/marketcalls/openalgo): unified API for Indian brokers
- [pykiteconnect](https://github.com/zerodha/pykiteconnect): official Zerodha client
- [jugaad-data](https://github.com/jugaad-py/jugaad-data) / [nsepython](https://github.com/aeron7/nsepython): NSE data (bhavcopy, F&O, indices)
- [FinRL](https://github.com/AI4Finance-Foundation/FinRL), [FinGPT](https://github.com/AI4Finance-Foundation/FinGPT): RL / LLM finance research
- [vectorbt](https://github.com/polakowo/vectorbt), [backtrader](https://github.com/mementum/backtrader): general backtesting
