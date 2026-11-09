# Crypto studies: do chart levels, round numbers, patterns and crowd mood work on BTC and ETH?

The first pre-registered tests from the [test plan](test-plan.md) ("Crypto first"). Each test's rules, data,
variants and pass/fail lines were committed to `research/prereg/` before any 2023-26 outcome was computed
(commit `f0cbd68`); the scripts refuse to run the test period otherwise. Each study was built by one agent and
audited by another, who reproduced the design-period numbers with separate code. Every run is in
`research/trials.csv`, and every result is in `research/results/`. Paper research only.

**Short version: none of these is a reason to trade or to move a forecast.**

| Test | Question | Design 2018-22 | Test 2023-26 | Verdict |
|---|---|---|---|---|
| H10c | Does price turn at our chart's support/resistance more often than at random levels? | Less often (BTC+ETH 39.1% vs 47.0%) | Less often (40.7% vs 50.5%) | **Fail** |
| H19c | Do round numbers ($70,000, $3,000) attract highs/lows, or speed up moves after a cross? | Nothing beats random offsets | Nothing beats random offsets | **Fail** |
| H9c | Do double tops and head-and-shoulders predict weaker returns? | 2-23 events against a floor of 300 | Not run | **Too little data** |
| H8a | Do fear, greed, crowded funding and downtrends predict the next 1-7 days? (exploratory) | No lesson reaches t ≥ 2 in its claimed direction | Same | **No forward test** |

Common rules: daily Binance candles; decide at the close, act at the next open; 0.1% fee plus 0.05% slippage per
side (also doubled); an after-tax line at India's 31.2% on each profitable sale with no loss set-off; Newey-West
t-statistics; dead coins kept (LUNA, FTT, WAVES); design up to 2022, test 2023 to 31 Oct 2026, run once.

## H10c. Support and resistance against random levels

**Rule.** Levels exactly as `indtrader/signals/chart.py` draws them (250-bar lookback, swing points, swings within
0.6 ATR clustered, at least 2 touches), recomputed each day from data up to the day before. A *hit* is the first
touch of a level; it *holds* if no close goes more than 0.2 ATR through it over the next 3 days. The same rules
were scored on 1,000 sets of random levels placed inside each day's 250-day range. Pass: our hold rate above the
95th percentile of the random sets, in both periods.

| | Design: hits | Ours held | Random median (95th pct) | Our percentile | Test: hits | Ours held | Random median (95th pct) | Our percentile |
|---|---|---|---|---|---|---|---|---|
| BTC + ETH | 210 | 39.1% | 47.0% (53.2%) | 1.6 | 248 | 40.7% | 50.5% (56.3%) | 0.3 |
| Top-20 coins | 1,917 | 50.0% | 50.9% (53.1%) | 24.2 | 2,395 | 52.1% | 54.7% (56.7%) | 1.3 |

In 2023-26 the gap is below zero with 95% confidence in both universes (BTC+ETH −9.8 points, interval −15.2 to
−5.1; top-20 −2.5 points, −4.3 to −0.8).

**Money check (report only).** Buying BTC/ETH at the next open after a support hit and holding 3 days:
- design: −1.35% a trade after costs, −2.08% after tax; the book lost 49% while holding BTC gained 385%;
- test: −0.31% a trade after costs, −0.95% after tax; the book made −4% (−30% after tax) while holding BTC gained
  366%.

**Reading.** Our levels are not better than chance; price broke through them more often than through random
levels. One explanation fits the order-flow research: traders put stop-loss orders just beyond obvious levels, so
reaching one tends to trigger a push through it (Osler 2003). That is a hypothesis, not something this test shows,
and the random levels are spread evenly while ours sit near recent turning points, so part of the gap may come from
where the levels are.

**What changes.** The crypto analyst may not cite support or resistance as a reason for a forecast, a range or the
gate (`analyst/CRYPTO_PLAYBOOK.md`). The stock version (H10) is still to come.

## H19c. Round numbers on BTC and ETH

**Rule.** Major levels are multiples of the leading power of ten (every $10,000 for BTC above $10,000; every $1,000
for ETH between $1,000 and $10,000); minor levels are a tenth of that. Two questions, each against 1,000 random
offsets with the same spacing: (1) do daily highs stop just below, and lows just above, a level more often? (2) after
a close crosses a level (not crossed in the previous 10 days), is the move over 1, 3 and 7 days larger?

**Result.** No variant beats the 95th percentile of random offsets in either period. In the design years the
nearest miss was minor-level highs (20.40% against a 95th percentile of 20.43%); in 2023-26 the same measure sat at
the median (19.93% against 19.86%). Moves after a cross were matched by random levels in both periods: whatever
drift there was is trend, not round numbers. After tax, every crossing horizon lost money in 2023-26 (−0.53% to
−0.63% a trade).

**What changes.** Round numbers are description only, not a reason (crypto playbook). No `near_round` tag is added
to the learning loop.

## H9c. Double tops and head-and-shoulders

**Rule.** Lo, Mamaysky and Wang's definitions (shoulders and troughs within 1.5%), two detectors (a kernel smoother
on 38-day windows, and the chart code's swing points), completion on a close below the neckline within 10 days, on
the daily top-20 coins with dead coins included. The plan required at least 300 design-period events before any
outcome is looked at.

**Result.** Usable design-period events: 3 and 2 for the kernel detector (head-and-shoulders, double top), 17 and 23
for the swing detector. Looser readings of the rules give at most 146. Far below 300, so the study stopped without
computing any return, and the test period was not run.

**What changes.** These shapes are too rare on the coins we trade to test, let alone trade. Pattern-book success
rates are never quoted as odds.

## H8a. Crowd mood and trend (exploratory: history had already been seen)

The research brief behind the test plan had already looked at 2018-2026, so this is not a clean test. It checks the
six seeded lessons in `journal/crypto_lessons.json` with the live scorer's comparison: the up-rate when the tag is
on, against the other days of the same period. The results are stored on each lesson as `evidence_history`; they do
not change any lesson's status, which only live forecasts can do.

| Lesson | Claim | Design: up-rate on vs off (t) | 2023-26: on vs off (t) |
|---|---|---|---|
| fear-rebound-7d | After extreme fear, higher a week later | 54.0% vs 51.2% (0.6) | 53.5% vs 51.8% (0.3) |
| greed-pullback-7d | After extreme greed, lower a week later | 63.0% vs 50.6% (2.1), the opposite | 52.6% vs 52.0% (0.1) |
| crowded-longs-24h | After crowded funding, lower a day later | 52.3% vs 52.1% (0.0) | 51.4% vs 50.6% (0.1) |
| downtrend-continues-7d | Below the 50-day average, lower a week later | 46.8% vs 52.9% (−1.7) | 51.2% vs 52.4% (−0.3) |

- **Add-ons to the trend rule, 2020-22, after tax:** plain BTC+ETH 50-day trend +218%; "trend or negative funding"
  +199%; "flat when funding is high" +29%; just holding BTC +89%. Neither add-on beats the plain rule after tax, so,
  by the plan's own lines, neither gets a forward paper account: H8b is registered but not started
  (`research/prereg/H8b.json`).
- **The first day of extreme fear** (exploratory): over 23 design-period episodes, BTC and ETH averaged −6.6% over
  the next 30 days against +5.8% on other days (Newey-West t −2.86). Buying on the first day of panic was, if
  anything, early. It is a hint for the learning loop, not a rule.
- **Funding feeds agree.** The live fact sheet reads OKX; history comes from Binance. Over October 2026 their 3- and
  7-day averages correlated at 0.84-0.94 (BTC and ETH), with average gaps of 0.0001-0.0008% per 8 hours.

## What this means for real money

Nothing here gives the crypto desk a new edge, and two popular chart ideas did worse than chance on BTC and ETH.
This is the useful kind of result: it removes reasons to trade. The desk keeps its simple trend rule; the analyst's
forecasts are judged by the learning loop; nothing goes live until the [go-live checklist](go-live-checklist.md)
passes.

## Reproduce

```bash
python scripts/download_crypto_klines.py         # data/crypto candles (git-ignored)
python scripts/download_crypto_sentiment.py      # Fear & Greed and funding history
python scripts/study_candles_levels.py --crypto --period design|test
python scripts/study_round_numbers.py --crypto --period design|test
python scripts/study_head_shoulders.py --crypto --period design
python scripts/study_crypto_sentiment.py --exploratory
```
