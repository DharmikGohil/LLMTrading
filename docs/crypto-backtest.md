# Crypto backtest: is there a rule worth paper trading?

Before building a crypto desk, we tested simple, low-frequency rules on Binance daily candles. Overtrading is what
sank most models in Alpha Arena (Nof1, Oct-Nov 2025), so every rule here trades a few times a week at most.

## Setup

- **Data:** Binance spot USDT pairs, daily candles, June 2018 to 8 Nov 2026, from the public archive at
  data.binance.vision (`scripts/download_crypto_klines.py`). The Binance API is geo-blocked from this server; the
  archive is not.
- **Execution and costs:** decide on a day's close, fill at the next day's open. Each trade pays a 0.1% fee plus
  0.05% slippage. A coin that stops trading is sold at its last close: XMR was delisted in Feb 2024, and EOS's
  ticker ends in May 2025 with its rename.
- **India after tax:** 31.2% (30% plus cess) on every profitable sale. Losses give no relief: they cannot be set
  off or carried forward. Everything is sold on the last day. The 1% TDS is creditable, so it is ignored.
- **Universes:**
  - *Point in time:* the 15 large Binance coins of January 2020, including ones that later faded: EOS, NEO, XMR,
    XTZ and ETC.
  - *Today's survivors:* today's large coins, such as SOL, DOGE and AVAX. They were picked with hindsight, so this
    universe flatters every rule.
- **Statistics:** the deflated Sharpe accounts for all 14 variants tried.
- **Reproduce:** `python scripts/crypto_backtest.py 2020-01-01`.

## Results, 1 Jan 2020 to 8 Nov 2026

| Rule | Return | Max drawdown | Sharpe | India after tax |
|---|---|---|---|---|
| BTC buy and hold | +938% | −77% | 0.88 | +644% |
| BTC trend: hold above the 50-day average | +2,142% | −59% | 1.31 | +571% |
| BTC trend: 100-day average | +1,048% | −39% | 1.06 | +377% |
| BTC trend: 200-day average | +565% | −64% | 0.86 | +246% |
| Momentum, top 3 by 30 days, weekly (point in time) | +12,593% | −49% | 1.39 | +906% |
| Momentum, top 5 by 90 days, weekly (point in time) | +4,451% | −46% | 1.24 | +683% |
| Equal-weight hold, point in time | +612% | −82% | 0.77 | +288% |

These full-period numbers are misleading, as the checks below show.

## The checks

**1. Fresh start on 1 Jan 2023.** This removes the 2021 altcoin bubble from the record.

| Rule | Return | Max drawdown | Sharpe | India after tax |
|---|---|---|---|---|
| BTC buy and hold | +350% | −53% | 1.07 | **+240%** |
| BTC trend, 50-day | +390% | −27% | 1.38 | +159% |
| BTC trend, 200-day | +211% | −32% | 0.97 | +112% |
| Momentum top 3, 30-day (point in time) | +1% | −59% | 0.27 | **−58%** |
| Momentum top 3, 90-day (point in time) | +30% | −57% | 0.39 | −39% |
| Momentum top 3, 90-day (today's survivors) | +186% | −61% | 0.76 | +19% |

**2. Decisions one day late, 2020-26.**
- Point-in-time momentum (top 3, 30-day) falls from +12,593% to +1,871%. A weekly rule that loses 85% of its result
  from a one-day delay is fragile.
- BTC trend, 50-day, holds up: +2,142% becomes +1,842%.

**3. Costs doubled, 2020-26.** Every rule stays roughly where it was, so costs are not what decides these results.

## What it means

1. **Altcoin momentum was a 2021 bubble effect, not an edge.** All of its outperformance comes from 2020-22. Since
   2023, on a point-in-time universe, it made 1-30% before tax and lost 39-61% after Indian tax. It also collapses
   under a one-day delay.
2. **The BTC 50-day trend rule is the only robust result, but it is risk control, not extra return.** Since 2023 it
   roughly halves the worst drawdown (−27% against −53%) and has a better Sharpe (1.38 against 1.07). Its return is
   only slightly above holding.
3. **Indian tax decides it: after tax, nothing beat holding BTC.** Every active rule realises gains often and pays
   31.2% on each one, while its losses earn no tax relief. Since 2023, BTC trend after tax is +159% against +240%
   for buy and hold.

## Decision

- **Real money:** no active crypto rule tested here beats buy-and-hold BTC after Indian tax. A small, long-term
  BTC allocation is the honest benchmark to beat.
- **A paper crypto desk is worth running only as a measurement of the LLM.** The candidate setup has three
  accounts:
  - BTC 50-day trend with an LLM event gate that can only make it safer (skip or reduce around events, like the
    options gate)
  - the same rule without the gate (the control)
  - BTC buy and hold (the benchmark)

  It must beat the benchmark after tax, out of sample, before any real money goes in.
