# Kronos forecasts: walk-forward test

[Kronos](https://github.com/shiyu-coder/Kronos) (Tsinghua, AAAI 2026, MIT licence) is a transformer
pre-trained on candlesticks. It samples many possible future paths for a chart. A popular recipe pairs it
with the day-trader skills: sample 1,000 paths, count how many hit the target before the stop, and trade
only when the odds look good. Before adding it to any desk, we checked whether its forecasts hold up on
our markets.

## Method

- **Model:** Kronos-small (24.7M parameters) on daily candles: 128 candles of context, 50 sampled paths,
  5 trading days ahead.
- **Test period:** a forecast every 5th trading day from 1 Sep 2025 to 23 Oct 2026, 57–58 forecasts per
  instrument and 343 in all. These dates come after the model's release, so it cannot have trained on them.
- **Instruments:** Nifty 50, Bank Nifty, Reliance, HDFC Bank, Infosys and SPY.
- **Baselines** use only data known on the forecast date:
  - a coin flip;
  - "always up";
  - the sign of the 20-day return;
  - an 80% band of ±1.28 × the 60-day volatility × √5;
  - the historical rate at which the target is hit first.
- **The race** follows the post's recipe. Each forecast is a long trade with a stop 1 × the 5-day volatility
  away and a target 2 × away. If both are touched on the same day, the stop counts as hit first.

Reproduce with `python scripts/kronos_eval.py <Kronos clone> <symbols> out.csv`, then
`python scripts/kronos_score.py out.csv`. The raw results are in
[`data/kronos-walkforward-2025-09-to-2026-10.csv`](data/kronos-walkforward-2025-09-to-2026-10.csv).

## Results

| | HDFC Bank | Infosys | Reliance | SPY | Bank Nifty | Nifty | All |
|---|---|---|---|---|---|---|---|
| Direction right (Kronos) | 65% | 60% | 56% | 52% | 56% | 46% | 56% |
| Direction right (20-day momentum) | 58% | 51% | 46% | 55% | 46% | 47% | 50% |
| Rank correlation, forecast vs actual | 0.14 | 0.12 | 0.12 | 0.14 | 0.03 | 0.01 | 0.11 |
| Actual inside Kronos's 80% band | 63% | 46% | 40% | 47% | 44% | 37% | **46%** |
| Actual inside the naive 80% band | 77% | 77% | 77% | 78% | 81% | 72% | **77%** |
| Kronos band width vs naive band | 0.55× | 0.52× | 0.53× | 0.57× | 0.47× | 0.45× | 0.52× |
| Target-first odds, Brier (Kronos) | 0.046 | 0.071 | 0.064 | 0.052 | 0.041 | 0.028 | **0.050** |
| Target-first odds, Brier (base rate) | 0.034 | 0.065 | 0.050 | 0.017 | 0.034 | 0.034 | **0.039** |

A lower Brier score is better.

## What it means

1. **The race odds are worse than useless.** Kronos's paths spread only about half as wide as real prices
   do. Its 80% band contained the outcome 46% of the time. Because the paths are too narrow, counting how
   many hit the target first gives badly mis-stated odds: on every instrument, its probabilities scored
   worse than simply assuming the historical average. This is the core step of the recipe, and on these
   markets it misleads.
2. **Index direction is a coin flip.** On Nifty and Bank Nifty, which our options desk trades, Kronos's
   forecasts are uncorrelated with the actual moves (rank correlation 0.01–0.03).
3. **There is a faint signal on single stocks.** Pooled direction was right 55.7% of the time
   (p = 0.04 against a coin flip). The rank correlation was about 0.12 on the four stocks and ETF. This is
   weak evidence for three reasons:
   - six instruments were tested, so one p = 0.03 is roughly what chance alone produces;
   - the forecasts share the same market weeks, so they are not independent;
   - it comes from one 14-month window.
4. **Trades where Kronos said "go"** averaged +0.11R, against −0.04R for all trades. That rests on 56 trades,
   24 of them SPY, before costs, so it is not evidence.
5. **Volatility:** Kronos's spread tracked the size of the next move about as well as plain historical
   volatility (0.37 vs 0.33 pooled). That is not enough to change how the options desk sets its strikes.

## Decision

Kronos is **not** added to any desk's decisions. The direction signal on single stocks is the only lead
worth watching. If it is tracked, it should be a logged shadow forecast scored after the fact, like the
LLM-off control, and adopted only if it holds up out of sample. The day-trader skills the recipe pairs it
with have been in this repository since October (`.claude/skills/trader-*`). Their Time Machine
(replays of the stock's own history) is the better-calibrated second opinion.
