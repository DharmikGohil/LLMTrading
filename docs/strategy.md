# Strategy

## The question

Controlled studies find no reliable stock-picking skill in LLMs on their own once they are tested after the
model's training cutoff, over long periods, with costs (see [research](research.md)). Two things do have
evidence: rule-based momentum and low-volatility selection, and LLMs catching negative news and red flags.
So the desk combines them, and measures the LLM's contribution with a control account.

## Signal modes

| `strategy.signal_mode` | Who decides |
|---|---|
| `hybrid` (default) | The screen proposes; the LLM can only veto (Underweight/Sell at confidence ≥ 55%) or shrink (Hold). A candidate without a review is not bought (`llm_missing: hold`). |
| `factor` | Screen only (the control arm). |
| `llm` | The LLM's rating drives the trade (TradingAgents mode). |

## Screen

`indtrader screen` ranks the index (Nifty 200 or S&P 100) by risk-adjusted 6- and 12-month momentum
(skipping the last month), z-scored, after removing the most volatile names, illiquid stocks and anything
below its 200-day average. With `trend_template: true` a stock must also pass Minervini's SEPA trend
template (7 checks). The top 10 are candidates.

## Position management (slow momentum book)

| Setting | Value | Why |
|---|---|---|
| Positions | up to 10, 10% each, at most 3 per sector | Diversified, sector-capped |
| Risk per trade | 2% of capital to the stop | Sizing is the smaller of allocation and risk-to-stop |
| Stop | 4 × ATR, clamped to 8–25% below entry, only moves up | Wide enough for momentum to breathe |
| Target | none (placeholder 100R) | Let winners run |
| Minimum hold | 20 days; 20-day cooldown after a stop | Prevents churn |
| Regime filter | new buys halved when the index is below its 200-day average | Less exposure in bear markets |

## India-specific checks

No new buys in ASM/GSM or trade-for-trade (non-EQ) stocks, or within 3 days of a results board meeting
(NSE event calendar plus per-symbol board meetings, which catch same-day meetings the calendar drops).
Splits and bonuses rescale positions and stops automatically.

## Analyst review

The analyst (a scheduled Claude session, or TradingAgents with an API key) rates each candidate:
Buy / Overweight / Hold / Underweight / Sell with a confidence and a sourced thesis. Red flags include
results within 3 trading days, regulatory actions, guidance cuts, downgrade clusters, promoter or insider
selling, auditor resignations and surveillance listings. The rules are in
[`analyst/PLAYBOOK.md`](../analyst/PLAYBOOK.md) and [`analyst/DESK_PLAYBOOK.md`](../analyst/DESK_PLAYBOOK.md).

## Backtests (Nifty 200, January 2024 to October 2026, Indian costs)

| Variant | Return | Max drawdown | Trades | Charges | Windows beating Nifty |
|---|---|---|---|---|---|
| Momentum screen, swing exits (2×ATR stop, 2.5R target) | −7.0% | −21% | 646 | ₹12,965 | 1/4 |
| … + SEPA trend template | −10.4% | −28% | 721 | ₹14,584 | 2/4 |
| Slow momentum book (4×ATR stop, no target, 20-day hold) | −1.5% | −23% | 357 | ₹5,356 | 2/4 |
| **Slow book + SEPA (current default)** | **+10.2%** | −20% | 473 | ₹7,199 | 3/4 |
| Nifty 50 buy-and-hold | +4.6% | | | | |

Today's index members are used throughout, so survivorship bias flatters every row, and every Sharpe 95%
interval crosses zero. The LLM layer is judged only on forward paper trading against the control account.

## Learning loop

The model is not retrained; it learns in context:

1. `indtrader review` writes a graded close review to `journal/daily/<date>-<market>.md`: orders, each veto's
   outcome against the index, and analyst calls after 1 and 5 days. The analyst adds a reflection.
2. Patterns go into the lesson book (`journal/lessons.json`): a hypothesis needs a concrete case, becomes
   confirmed after 3 supporting cases and is retired when contradicted.
3. Every analyst run reads `indtrader lessons` first. Lessons sharpen judgement; they never loosen risk limits.
4. Config numbers change only with backtest plus paper evidence, logged in
   [`journal/changes.md`](../journal/changes.md).
