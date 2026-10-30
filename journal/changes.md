# Strategy change log

Config numbers (stops, sizing, screen) change only with evidence: a backtest plus paper results. Each entry: date,
change, evidence, expected effect. Review the effect after 20+ trading days.

| Date | Change | Evidence | Expected effect |
|---|---|---|---|
| 2026-10-28 | Hybrid mode default: momentum screen picks, LLM can only veto | Deep-dive research (FINSABER, KTD-Fin, Lopez-Lira) | LLM adds value only as a red-flag filter |
| 2026-10-28 | Slow momentum book + SEPA trend template (4×ATR stop, no fixed target, 20-day hold, 10 positions) | Nifty 200 backtest Jan 2024–Oct 2026: +10.2% vs −7.0% for swing exits (not significant) | Fewer trades, lower costs, winners run |
| 2026-10-30 | Drawdown circuit breaker: no new buys while equity is 10%+ below its peak (both desks, both books) | Nifty 200 backtest Jan 2024-Oct 2026: max drawdown -18.6% -> -11.5%, return +14.2% -> +21.5%, Sharpe 0.41 -> 0.69; deflated Sharpe 0.75 over 11 variants (not significant), walk-forward 2/4 vs 3/4 | Adopted as a safety rule, not a profit claim: smaller drawdowns, fewer trades |
| 2026-10-30 | Volatility targeting tested and left off | Same backtest: 15% target cut return to +9.4% with a slightly deeper drawdown | None (off) |
