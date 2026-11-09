# Backtest forensics: how much of the momentum backtest is real?

The momentum strategy that both stock desks trade was audited for look-ahead bias, survivorship bias, cost realism
and fragility to execution timing. The idea came from the "Backtest Forensics Lab" bot in the hft.md Grok-bot
directory; the checks themselves are standard.

Window: 1 Jan 2024 to 6 Nov 2026. Benchmark: Nifty 50, **+15.1%** over the window. Script:
`python scripts/backtest_forensics.py 2024-01-01 2026-11-06` (needs `data/futstk`, see
`scripts/download_futstk_bhavcopy.py`).

## Look-ahead
Passes by design. `indtrader/backtest.py` decides on the previous close and fills at the next open. When a day's bar
touches both the stop and the target, the stop counts. Each fill includes 0.05% slippage and full Indian charges.

## Results

| Run | Stocks | Return | CAGR | Max drawdown | Sharpe | vs Nifty |
|---|---|---|---|---|---|---|
| As published: today's Nifty 200 | 200 | **+18.5%** | 6.1% | −11.6% | 0.63 | +3.4 pts |
| Today's F&O stock list (survivors only) | 218 | +14.3% | 4.8% | −11.4% | 0.50 | −0.8 pts |
| F&O list as it stood on 1 Jan 2024 (point in time) | 183 (175 with data) | **+12.6%** | 4.3% | −12.1% | 0.50 | −2.5 pts |
| Nifty 200, charges ×2 and slippage ×4 | 200 | +13.4% | 4.5% | −13.3% | 0.47 | −1.7 pts |
| Nifty 200, every decision one day late | 200 | +12.5% | 4.2% | −12.9% | 0.44 | −2.6 pts |

## What it means

1. **Survivorship bias is real and favours the published result.**
   - The same universe rule gives +14.3% on today's list and +12.6% on the list as it actually stood in January
     2024. Since then, 50 stocks have left the F&O segment, including ACC, ZEEL, MRF, IRCTC and BATAINDIA.
   - Eight of the January-2024 names have no Yahoo data because they were renamed, merged or demerged (for
     example IDFC, L&TFH, MCDOWELL-N, TATAMOTORS). The point-in-time run therefore still flatters slightly.
2. **The result is fragile.**
   - Executing one day late cuts the return by 6 points.
   - Realistic higher costs cut it by 5 points.
   - A robust edge would not move this much from a one-day timing change.
3. **No honest version beats simply holding the Nifty.** Only the as-published run, with today's members, normal
   costs and perfect timing, is ahead. Every audited variant trails the index by 1 to 2.6 points, with Sharpe
   ratios of 0.44 to 0.50.

## Decision

- The README's "Results so far" now cites the audited figure, not the flattering one.
- The stock desks keep running in paper mode as a measurement of the LLM layer against its control. That
  comparison is what the experiment tests.
- Neither desk has evidence of beating an index fund. Before any real money goes into the stock strategy, it has
  to beat a Nifty index fund out of sample, after costs, on a point-in-time universe.
