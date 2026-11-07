# Open-interest build-up: does the F&O "order-flow board" predict anything?

The order-flow boards sold on Instagram, and the free open-source one at
[github.com/MrChartist/order-flow](https://github.com/MrChartist/order-flow) (PolyForm Noncommercial), sort every
F&O stock by its futures build-up. Rising price with rising open interest is long build-up (bullish), falling price
with rising open interest is short build-up (bearish), and so on. Before putting this on the desk, we checked
whether the reading predicts returns.

## Method

- **Data:** NSE F&O bhavcopy, stock futures, 2 Jan 2023 to 6 Nov 2026: 948 trading days and 178,180
  stock-days. Downloaded with `scripts/download_futstk_bhavcopy.py`.
- **Price change:** the near-month future against the same contract's previous close.
- **Open-interest change:** total open interest across all expiries against the previous day, so rollover does not
  look like unwinding in one month and build-up in the next.
- **Classification:** each stock-day falls into one of the four buckets. Moves under 0.1% in price or 0.5% in open
  interest count as neutral.
- **Outcome:** the same contract's return over the next 1 and 5 trading days, minus the average of all F&O stocks
  that day. A market-wide move therefore does not count as a signal.
- **Statistics:** t-stats are computed over daily averages.
- **Board as a trade:** long the bullish buckets and short the bearish ones, next day, with about 6 bps of
  round-trip cost per leg.

The data is end of day. The boards also update intraday, and that version cannot be tested with this archive.

Reproduce: `python scripts/download_futstk_bhavcopy.py 2023 2026`, then `python scripts/oi_buildup_study.py`.

## Results

Average excess return after each build-up, in basis points (t-stat):

| Bucket (board's side) | Next day | Next 5 days |
|---|---|---|
| Long build-up (bullish) | −5.5 (−2.7) | −7.6 (−1.8) |
| Short covering (bullish) | +2.1 (+1.4) | +1.8 (+0.5) |
| Short build-up (bearish) | −3.7 (−2.4) | −8.5 (−2.4) |
| Long unwinding (bearish) | +5.0 (+2.4) | +12.7 (+3.0) |

**Trading the board** (long bullish, short bearish, next day): about −0.2 bps a day before costs and −6.2 bps a
day after. That is −43% over four years, with a Sharpe of −3.2. The result is the same in 2023-24 and 2025-26.

## What it means

1. **The board's bull/bear split has no edge.** Its "bullish" side mixes long build-up, which lagged, with short
   covering, which beat. Its "bearish" side mixes short build-up, which lagged, with long unwinding, which beat.
   The two cancel out, and costs make the trade a steady loser.
2. **The pattern that does exist is the opposite of the story:**
   - **Rising open interest** in either direction was followed by slight underperformance.
   - **Falling open interest** was followed by slight outperformance.
   - **Long unwinding**, a "bearish" signal, was the best bucket over five days.
3. **That pattern is too small to trade.**
   - Long falling-OI and short rising-OI names earned 2.7 bps a day gross (t 4.4).
   - After costs it is −3.3 bps a day.
   - The effect shrank from 3.9 bps in 2023-24 to 1.4 bps (t 1.6) in 2025-26.

## Decision

The build-up reading is **not** a trading signal on any desk. A board can still be useful as context, showing
where open interest is piling up and near which strikes, but it should be read as a description of positioning,
not as a forecast. The open-source board is free to run on your own computer for personal use. Its licence does
not allow commercial use.
