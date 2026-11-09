# Crypto desk: how the strategy was chosen, and how the desk runs

The brief was a momentum strategy that makes money, tested honestly before any paper trading started.

## The test

- **Data:** daily Binance USDT candles, 2019 to 8 Nov 2026, for 74 coins (`scripts/download_crypto_klines.py`). The
  pool includes coins that collapsed or were delisted: LUNA, FTT, WAVES, OMG, XMR, MATIC (since renamed POL) and
  others. A ticker that was reused for a different coin (LUNA became LUNA 2.0 in May 2022) is split into two coins,
  so no return is measured across the splice.
- **Point-in-time universe:** on each rebalance day, the 20 coins with the highest 30-day traded value among those
  with at least 120 days of history. Only what was knowable that day is used.
- **Variants fixed in advance**, as listed in `scripts/crypto_momentum_study.py`:
  - cross-sectional altcoin momentum: top 3 or 5 coins by 30- or 90-day return, raw or risk-adjusted, weekly, with
    trend and BTC-regime filters
  - a core-satellite mix of BTC plus momentum
  - BTC + ETH trend
  - benchmarks: BTC buy-and-hold and the BTC 50-day trend
- **Design and test:** the variants were compared on 2020-22 (the design period), then all were reported on
  2023-26 (the test period, untouched while designing).
- **Costs and tax:** 0.1% fee plus 0.05% slippage per trade. "After tax" applies India's 31.2% on every profitable
  sale, with no loss set-off.

## Results

| Strategy | 2020-22 design | 2023-26 test | Test, after Indian tax | Test max drawdown | Test Sharpe |
|---|---|---|---|---|---|
| BTC buy and hold | +129% | +350% | **+240%** | −53% | 1.07 |
| BTC 50-day trend | +358% | **+390%** | +159% | **−27%** | **1.38** |
| BTC + ETH 50-day trend | +569% | +384% | +147% | −31% | 1.33 |
| Momentum top 5, 30-day (best in design) | **+2,274%** | +61% | −58% | −64% | 0.52 |
| Momentum top 3, 30-day | +1,770% | +107% | −53% | −66% | 0.62 |
| Risk-adjusted momentum top 3, 90-day | +419% | +145% | −25% | −53% | 0.68 |
| Momentum top 3, 90-day | +181% | −13% | −74% | −62% | 0.29 |
| Half BTC + half momentum | +251% | +143% | +1% | −43% | 0.71 |

Reproduce: `python scripts/crypto_momentum_study.py`.

## What it means

- **Altcoin momentum overfits.**
  - The variant that won the design period (+2,274%) made +61% in the test, against +350% for holding BTC.
  - After tax it lost 58%.
  - Every altcoin-momentum variant trailed BTC in the test, and every one lost money after Indian tax.
  - Its design-period returns came from the 2021 altcoin bubble.
- **Trend-following on BTC and ETH is the robust result.**
  - It made money in both periods.
  - In the test it roughly matched or beat holding BTC before tax.
  - It about halved the worst drawdown and had a higher Sharpe.
  - This is momentum in its time-series form: own an asset while its own trend is up.
- **After Indian tax, holding BTC still comes out ahead.** The trend rule realizes gains often, and losses give no
  tax relief.

## The desk

Paper money: three 10,000 USDT accounts (`indtrader/crypto.py`).

| Account | Rules |
|---|---|
| `main` | BTC + ETH 50-day trend, subject to the analyst's gate |
| `control` | The same rules, no gate |
| `hold` | BTC bought once and held: the benchmark |

**Rules:**
- Each of BTC and ETH gets half the account while its daily close is above its 50-day average; otherwise that half
  is held in USDT.
- Rebalances smaller than 5% of the account are skipped, to save costs.
- Prices come from Binance's public market-data mirror. Buys fill at the ask and sells at the bid, plus slippage
  and a 0.1% fee.

**Runs (24/7, on GitHub Actions, `.github/workflows/crypto-desk.yml`):**
- daily at 00:10 UTC: the rebalance
- every 2 hours: apply the gate and record equity

**The gate (`analyst/CRYPTO_PLAYBOOK.md`):** a scheduled Claude run before the daily rebalance checks macro events,
hacks, unlocks, delistings and market stress, then writes `indtrader crypto-gate`. The gate can only cut `main`'s
exposure or exclude a coin.

**Site:** `/crypto`, with live Binance prices, holdings, the equity chart against holding BTC, and the trade log.

**Judged on:**
- `main` against `control`: does the LLM gate add anything?
- both against `hold`, after Indian tax, out of sample, before any real money.
