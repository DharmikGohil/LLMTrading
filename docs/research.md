# Research

The design follows the evidence. This page summarises it (October 2026) and credits the projects it borrows from.

## LLMs and stock selection

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

## LLMs and options (2026)

- **LiveOption** ([arXiv 2609.33470](https://arxiv.org/abs/2609.33470)): LLM agents trading options (portfolio
  overlays, earnings trades, 0DTE intraday) mostly fail to earn competitive returns.
- **Unbounded Losses, Unchecked Inputs** ([arXiv 2610.24289](https://arxiv.org/abs/2610.24289)): of 26 LLM
  options-trading systems, 13 could reach unbounded loss and only 10 of 22 order-capable systems enforce a
  pre-trade limit outside the model.
- **LLM + Bayesian network for the wheel strategy** ([arXiv 2512.01123](https://arxiv.org/abs/2512.01123)): an LLM
  that shapes a structured, rule-based model beat both a pure LLM and plain rules on drawdown and Sharpe.
- **SEBI FY25 study:** over 91% of individual F&O traders lost money (₹1.06 lakh crore after costs), while
  algorithmic proprietary traders and foreign investors took the profits.
- **Nifty volatility risk premium (our check, 2015–2026):** India VIX exceeded the Nifty's realised volatility
  over the following month 79% of the time (mean 16.6% vs 14.1%), positive in every year but thin in 2024
  and 2026. Option sellers earn it, with crash risk, so any short option must be hedged.

Consequence for the planned options desk: rules trade defined-risk structures, hard loss limits sit in code
outside the model, and the LLM only gates entries around events.

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
- **day-trader-skill** (Jakeschincariol, MIT): SEC filing and news tools for the US review, and the
  "time machine" idea of replaying a setup's own history before risking money.

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

## Known limitations
- TradingAgents' Social analyst reads StockTwits/Reddit, which say little about
  most Indian stocks. Consider `analysts: [market, news, fundamentals]` to save cost.
- Yahoo daily data is fine for swing trading; for live prices the engine uses the broker LTP.
- Stops are monitored by the bot (every 5 min). For CNC positions you can also add
  broker-side GTT orders as a backstop in case the bot is down.
- Update `NSE_HOLIDAYS` in `indtrader/market.py` each December from the
  [NSE holiday page](https://www.nseindia.com/resources/exchange-communication-holidays).
- F&O (NIFTY/BANKNIFTY options) is not implemented. LLM analysis takes minutes,
  which suits daily swing decisions, not intraday option scalping.
