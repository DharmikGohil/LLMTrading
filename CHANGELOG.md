# Changelog

All notable changes are listed here. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Desk activity (trades, reviews) is not listed; it is in `paper/`, `journal/` and on the site.

## [Unreleased]

### Added
- Kronos walk-forward test (`scripts/kronos_eval.py`, `scripts/kronos_score.py`, `docs/kronos.md`): not adopted;
  its 80% bands held 46% of outcomes and its target-first odds scored worse than the base rate.
- Chart reading: `indtrader/signals/chart.py` (MACD, Bollinger Bands, support/resistance from swing points,
  candlestick patterns) feeds a `chart` block into `indtrader brief`; each stock page on the site has a daily
  candlestick chart with EMA 20/50, SMA 200, Bollinger, levels, volume, RSI, MACD and a plain-English chart read
  (`web/components/PriceChart.js`, `web/lib/ta.js`, `/api/ohlc`); `docs/technical-analysis.md` documents each tool
  and the evidence for it.
- Crypto backtest (`scripts/download_crypto_klines.py`, `scripts/crypto_backtest.py`, `docs/crypto-backtest.md`):
  altcoin momentum was a 2021 effect and loses after Indian tax since 2023; BTC 50-day trend halves drawdowns but
  trails buy-and-hold BTC after tax.
- Backtest forensics (`scripts/backtest_forensics.py`, `docs/backtest-forensics.md`): on a point-in-time universe,
  with higher costs or with one day's delay, the momentum backtest trails the Nifty (+12.5% to +13.4% vs +15.1%);
  the README's results section now cites the audited figures.
- Analyst calibration (`scripts/analyst_calibration.py`), tip-sheet scoring (`scripts/score_tips.py`) and a
  devil's-advocate bear case on every Buy/Overweight in the playbooks.
- Open-interest build-up study (`scripts/download_futstk_bhavcopy.py`, `scripts/oi_buildup_study.py`,
  `docs/oi-buildup.md`): the order-flow board's bull/bear split has no edge, and its long/short loses 6 bps a day
  after costs; not adopted.
- Options page: invested, value and return per account, P&L charts, and the live Nifty against open strikes.

### Changed
- The Rs 1,000 options test stakes at most Rs 1,000 per trade (`LOTTO_STAKE`) and keeps its winnings; it no longer
  re-stakes its whole balance.
- The India open run moved from 09:35 to 09:16 IST and starts the one-minute options monitor first, so positions
  are watched from the opening minute.

## [0.3.0] - 2026-10-30

### Fixed
- Order safety after an independent review: no re-sent orders after timeouts, no double-booked fills,
  split/bonus shares respected, stale stop exits re-priced, capital changes handled, the control account
  uses the same exit levels as the LLM book, plus logging and cost details (see `docs/audit.md`).

### Changed
- Licence: all rights reserved (was MIT for a few hours on 29 October 2026).

### Added
- Volatility targeting, a drawdown circuit breaker and the deflated Sharpe ratio. The 10% drawdown breaker is on.
- finance-skills tools (earnings preview, estimate revisions, correlation, liquidity, options payoff) and a
  coverage audit of every source project (`docs/audit.md`).
- India paper desk capital set to Rs 1 lakh.
- Project documentation in `docs/`, licence, contribution and security policies, CI, issue and PR templates.
- All eleven day-trader-skill skills in `.claude/skills/`; the US review uses its SEC news, filings and
  Congress-trade tools.

## [0.2.0] - 2026-10-29

### Added
- Public site (Next.js, Vercel): overview, desks, history ledger and blotter, activity log, analyst calls,
  per-stock pages, journal, research; dark terminal theme with a light theme; keyboard navigation.
- Live quotes on the site every 15 seconds while a market is open (`/api/quotes`, CDN-cached).
- US paper desk ($10,000, S&P 100) next to the India desk.

### Changed
- Work moved to the `main` branch; commits authored as the repository owner.
- The claude.ai dashboard was retired in favour of the site.

### Fixed
- Same-day NSE board meetings missing from the event calendar; NaN Yahoo bars; scheduler monitor timing
  after a fresh start; placeholder take-profit values shown in order notes.

## [0.1.0] - 2026-10-28

### Added
- `indtrader`: NSE calendar and ticks, Indian and US costs, momentum screen with SEPA trend template,
  hybrid LLM veto, slow momentum book, risk limits, paper / Zerodha / OpenAlgo brokers, backtester with
  bootstrap and walk-forward validation, NSE surveillance and results checks, corporate actions.
- TradingAgents integration, Vibe-Trading second opinion, Claude analyst playbooks (no API key).
- Shadow "LLM off" accounts, scorecard, graded daily reviews and lesson book.
