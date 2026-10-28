# Strategy change log

Config numbers (stops, sizing, screen) change only with evidence: a backtest plus paper results. Each entry: date,
change, evidence, expected effect. Review the effect after 20+ trading days.

| Date | Change | Evidence | Expected effect |
|---|---|---|---|
| 2026-10-28 | Hybrid mode default: momentum screen picks, LLM can only veto | Deep-dive research (FINSABER, KTD-Fin, Lopez-Lira) | LLM adds value only as a red-flag filter |
| 2026-10-28 | Slow momentum book + SEPA trend template (4×ATR stop, no fixed target, 20-day hold, 10 positions) | Nifty 200 backtest Jan 2024–Oct 2026: +10.2% vs −7.0% for swing exits (not significant) | Fewer trades, lower costs, winners run |
