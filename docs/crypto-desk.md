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

## The learning loop

The desk trades about once a day, which is too rarely to learn from. So the analyst also makes small, checkable
forecasts at 05:05, 13:05 and 23:05 IST (`indtrader crypto-forecast`): the probability that BTC and ETH are higher
24 hours later (and 7 days later at 05:05), and an 80% price range. Code: `indtrader/crypto_learn.py`; data:
`paper/crypto/learn/`.

- **Fact sheet** (`indtrader crypto-brief`): price, 24h/7d/30d change, distance from the 50- and 200-day averages,
  RSI, volatility, the Fear & Greed index (alternative.me), OKX perpetual funding, and market-state **tags**
  computed from the data (`below_50d`, `fg_extreme_fear`, `funding_high`, `vol_high`, `big_move_24h`, ...).
- **Baseline:** every call is stored next to a no-skill call made at the same moment: 50% up, and a range of
  ±1.28 × daily volatility × √(days). Skill means beating it.
- **Scoring** (every 2 hours on GitHub Actions, `indtrader crypto-score`): the price at the due time from Binance's
  1-minute bars; the Brier score (squared error of the probability; lower is better; 0.25 for a coin flip), range
  coverage (should be about 80%), the pinball loss of the range, calibration, and the same broken down by tag.
- **Significance:** the LLM-minus-baseline Brier difference gets a Newey-West t-statistic, because calls 8 hours apart
  with a 24-hour horizon overlap. Under 30 calls the verdict is "too few to tell".
- **Lessons** (`journal/crypto_lessons.json`): each lesson names one tag, a horizon and what it expects: `llm`
  lessons claim the analyst is `worse` or `better` than the baseline under that tag; `market` lessons claim the
  price went `up` or `down` more often under that tag than on the other calls of the same period (not more often than
  50%: in a rising year most calls end up whatever the tag). That is a regression of the up/down outcome on the tag,
  with a Newey-West t-statistic. `indtrader crypto-learn` recounts the evidence from the
  scores and sets the status: confirmed at 30+ calls and |t| ≥ 2 in the claimed direction, retired when it turns
  the other way. The analyst writes the words; the data decides the status. Seeded with six hypotheses: fear
  rebounds, greed pullbacks, crowded longs, downtrends persisting, overconfidence in high volatility, chasing big
  moves.

### Bracket calls (bracket-v1, from 11 Nov 2026)

Each run also asks "which is hit first within 24 hours: a target 1.5 d away, a stop d away, or neither?" for a long
and a short on BTC and ETH (d = one day's volatility). The fact sheet shows the coin's measured base rates for that
exact bracket (about 80 days of hourly candles), the baseline the analyst must beat. The tool blends the analyst
with the base rates (weight fitted on graded calls, Brier score; it falls to 0 for an analyst who adds nothing), logs
the expected value in R after costs (never traded), grades every call from 1-minute candles, and runs a mirror probe
(flipped fact sheet) twice a week. Code: `indtrader/crypto_bracket.py`; verdict rules: `docs/test-plan.md` M-C3.
Ideas adapted from the design of zadescoxp/calibrain-harness; no code copied.

