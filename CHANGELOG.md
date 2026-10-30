# Changelog

All notable changes are listed here. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Desk activity (trades, reviews) is not listed; it is in `paper/`, `journal/` and on the site.

## [Unreleased]

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
