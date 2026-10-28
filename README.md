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
                     cached in state/signals/<date>/<SYMBOL>.json
09:30 IST  trade     rating + technical filter -> target qty -> risk checks -> LIMIT orders
every 5m   monitor   stop-loss / take-profit exits
15:20 IST  eod       MIS square-off (if intraday), daily summary (Telegram)
```

| Module | What it does |
|---|---|
| `indtrader/signals/llm_agent.py` | Wraps `TradingAgentsGraph`: `.NS` tickers, Nifty benchmark, Indian macro news queries, Yahoo fundamentals (SEC EDGAR is US-only), passes your holdings as portfolio context, caches decisions, parses the Trader's stop-loss and the PM's price target |
| `indtrader/strategy.py` | Long-only mapping: Buy/Overweight may **add** (only if close > EMA50 and RSI < 75); Underweight/Sell may only **trim**; Hold/REVIEW/stale = no change. Size = min(20% allocation, 1%-risk-to-stop) |
| `indtrader/risk.py` | Daily-loss kill switch, max open positions, exposure/position caps, cash, max orders/day, min order value, "price ran away from analysed close" guard |
| `indtrader/costs.py` | STT, stamp duty, exchange txn, SEBI fee, GST, DP charge, brokerage (delivery vs intraday) |
| `indtrader/market.py` | IST session times, 2026 NSE holidays, special sessions, tick rounding, symbol mapping |
| `indtrader/brokers/` | `paper` (simulated with costs), `zerodha` (Kite Connect), `openalgo` (Angel One, Dhan, Upstox, Fyers, Kotak, 5paisa, Shoonya, ...) |
| `indtrader/engine.py` | Orchestration, order fill tracking, trailing stops, re-entry cooldown, trade journal (`state/trades.csv`) |
| `indtrader/backtest.py` | Daily portfolio backtest with the same sizing/risk code and Indian costs |

**Safety by design:** the bot only sells shares it bought itself (tracked in
`state/bot_state.json`), so your long-term holdings in the same demat account
are never touched. It only uses `risk.capital` even if the account holds more.
It sends marketable LIMIT orders, never naked market orders, and has a
`--dry-run` mode.

## Setup

```bash
git clone <this repo> && cd LLMTrading
python -m venv .venv && source .venv/bin/activate      # Python 3.11+
pip install -e ".[dev]"                 # installs TradingAgents v0.7.1 too
pip install -e ".[zerodha]"             # or ".[openalgo]" for live trading

cp .env.example .env                    # add your LLM API key (Anthropic/OpenAI/Google/...)
cp config/config.example.yaml config/config.yaml   # universe, capital, risk, broker
pytest                                  # 16 tests, no network/LLM needed
```

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

Useful ways to combine them: use Vibe-Trading for research (e.g. its
`equity_research_team` swarm or backtests on `.NS` symbols), and this repo to
execute. Ideas borrowed here: statistical validation of backtests, and a
file-based kill switch.

## Related open-source projects
- [TradingAgents](https://github.com/TauricResearch/TradingAgents): the multi-agent LLM analyst/trader used here
- [OpenAlgo](https://github.com/marketcalls/openalgo): unified API for Indian brokers
- [pykiteconnect](https://github.com/zerodha/pykiteconnect): official Zerodha client
- [jugaad-data](https://github.com/jugaad-py/jugaad-data) / [nsepython](https://github.com/aeron7/nsepython): NSE data (bhavcopy, F&O, indices)
- [FinRL](https://github.com/AI4Finance-Foundation/FinRL), [FinGPT](https://github.com/AI4Finance-Foundation/FinGPT): RL / LLM finance research
- [vectorbt](https://github.com/polakowo/vectorbt), [backtrader](https://github.com/mementum/backtrader): general backtesting
