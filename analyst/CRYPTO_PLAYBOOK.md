# Crypto desk: playbook for the scheduled analyst runs

The crypto paper desk trades by itself on GitHub Actions (`.github/workflows/crypto-desk.yml`):
- daily at 00:10 UTC (05:40 IST): the rebalance check
- every 2 hours: apply today's gate, record equity, **grade every forecast whose time has come**

You run three times a day (05:05, 13:05 and 23:05 IST). You never place orders and never edit code. Paper money only.

| Account | Rules |
|---|---|
| `main` (With LLM) | BTC and ETH, each held (half the account) while its daily close is above its 50-day average, otherwise that half sits in USDT. Subject to your gate. |
| `control` (Without LLM) | The same rule, no gate |
| `hold` (Just hold BTC) | BTC bought once and held: the benchmark |

You have two jobs:
1. **Forecasts (every run).** Small, checkable calls that are graded automatically. This is how the desk learns
   quickly: hundreds of graded calls a month instead of one trade a day.
2. **The gate (05:05 run only).** It can only make `main` safer: cap the share in coins (`--exposure`, 0-1) or
   exclude a coin (`--exclude`). It can never add risk.

## 0. Setup
```bash
cd /home/user/LLMTrading 2>/dev/null || { git clone https://github.com/DharmikGohil/LLMTrading /home/user/LLMTrading && cd /home/user/LLMTrading; }
git fetch origin main && git checkout main && git pull --ff-only origin main
git config user.name "dharmikgohil" && git config user.email "gohildharmik2020@gmail.com"
pip install -q pandas numpy pydantic pyyaml python-dotenv requests typer yfinance && pip install -q --no-deps -e .
indtrader crypto-status
indtrader crypto-brief          # the fact sheet: read all of it before forecasting
```

## 1. Read the fact sheet and the lesson book first
`indtrader crypto-brief` prints, for BTC and ETH:
- price, 24h/7d/30d change, distance from the 50- and 200-day averages, RSI, daily volatility
- Fear & Greed (crowd emotion, 0 = extreme fear, 100 = extreme greed) and perpetual funding (how crowded the
  leveraged longs are)
- **tags**: the market state, computed from the data (for example `below_50d`, `fg_fear`, `vol_high`)
- **the baseline call** for 24h and 168h: 50% up, and an 80% range from recent volatility. This is what a forecaster
  with no skill would say. You are scored against it. At its checkpoints, test M-C1 also scores you against the
  market's own drift (the share of up periods over the past year; the fact sheet's `up_days_365_pct` for 1 day), so
  leaning up every day in a rising market is not skill.
- **the scorecard so far** (Brier score, lower is better; skill % against the baseline; range coverage; calibration;
  the same split by tag) and **the lesson book** (`journal/crypto_lessons.json`)

Apply the lessons:
- A **confirmed** `llm` lesson ("my calls are worse than the baseline when the tag X is on"): when X is on today, stay
  at or very near the baseline (p_up within 0.45-0.55, baseline range).
- A **confirmed** `market` lesson ("under tag X the price rose (or fell) more often than on the other calls of the
  same period"; the scorer compares with that up-rate, not with 50%): you may lean that way when X is on, by at
  most 0.10 from 0.5 unless other evidence agrees.
- **Hypotheses** are unproven: do not lean on them.

## 2. Check the next 24-48 hours for events (web search, cite sources and dates)
- **Macro:** FOMC decisions and minutes, US CPI/PCE, US jobs report, large options expiries (Deribit monthly and
  quarterly).
- **Coin-specific:** exchange or protocol hacks, large token unlocks (over 2% of supply), Binance delisting or
  monitoring tags, SEC/CFTC actions, stablecoin de-pegs, chain halts, founder or insider selling.
- **Market stress:** a move of more than 8% in 24h, funding at extremes, a large liquidation cascade.

## 3. Forecasts (every run)
For **BTC and ETH**, 24 hours ahead, every run; and 168 hours (7 days) ahead at the **05:05 run only**:
```bash
indtrader crypto-forecast --coin BTC --horizon 24 --p-up 0.55 --lo 73200 --hi 76900 \
  --note "Below the 50-day average (trend down) but fear at 29 and funding normal; no macro event before <date> (Fed calendar). Bull case: ... Bear case: ..."
```
- `--p-up` is your probability that the price is **higher** at the horizon than now. `--lo`/`--hi` is the range
  you are 80% sure of: 10% chance below `lo`, 10% chance above `hi`. The range must contain the current price.
- **Start from the baseline and move only for a stated reason.** Most calls should sit between 0.40 and 0.60.
  Beyond 0.30-0.70 needs strong, specific evidence (a scheduled event, an extreme reading that a confirmed lesson
  covers). Never 0.01 or 0.99.
- **Range size:** if the scorecard's coverage is below 70%, your ranges are too narrow (overconfident): widen them.
  Above 90%, they are too wide: tighten them. Aim for 80%.
- **Emotion checks before submitting** (these are the mistakes that cost human traders money):
  - *Recency:* am I just extending the last 24 hours? A big move is not a reason by itself.
  - *Anchoring:* am I repeating my previous call instead of re-reading today's facts?
  - *Herding/FOMO:* am I following the crowd's mood? Fear & Greed is a fact to weigh, not a feeling to share.
  - *Overconfidence:* would I really bet at these odds? Write the bull case **and** the bear case in the note.
  - *Results-chasing:* is a good or bad week for the accounts or the scorecard changing my calls? It should not.
- **Chart claims are not reasons.** Our pre-registered tests on BTC/ETH (2018-2026, `docs/crypto-studies.md`):
  support/resistance from our chart code held *less* often than random levels (H10c, failed in both periods); round
  numbers showed nothing (H19c); double tops and head-and-shoulders were too rare to test (H9c). So never move
  `--p-up`, the range or the gate because of a level, a round number or a pattern; you may mention one as
  description only, saying "no better than random on our data". Never quote a pattern book's "success rate" as odds.
- One call per coin and horizon every 6 hours at most (the tool refuses repeats). Never delete or edit a forecast.

## 4. The gate (05:05 run only)
| Situation | Gate |
|---|---|
| Nothing material | `--exposure 1` (no limit) |
| A major macro event in the next 24 hours (FOMC, CPI) | `--exposure 0.5` |
| A coin-specific red flag (hack, delisting notice, unlock over 5%, regulatory action) | `--exclude COIN` |
| Systemic stress (an exchange failure, a stablecoin de-peg, BTC −15% in 24h) | `--exposure 0` |

```bash
indtrader crypto-gate --exposure 1 --exclude "" --note "Reason: none. Fear & Greed <value> (alternative.me, <date>). No material events in the next 24-48h: next FOMC <date> (Fed calendar), no unlocks over 2% for BTC/ETH."
```
Every note cites its sources and dates. **No invented facts.** If you cannot verify an event, do not act on it.
Extreme fear or greed is a mood, not a gate row: on its own it never lowers `--exposure` (test H6 audits gate
actions taken in fear). Start each gate note with `Reason: none|macro|coin|stress` and today's Fear & Greed value,
so test M-C2 can grade each reason type.

## 5. Lesson review (Sunday's 05:05 run)
```bash
indtrader crypto-learn          # updates each lesson's evidence from the scores, then prints the scorecard
```
- The evidence and the status of each lesson are set **by the data only**: a lesson is confirmed when its tag has
  at least 30 scored calls and |t| ≥ 2 in the claimed direction, and retired when the data turns against it.
  Never edit `evidence` or `status` by hand.
- You may add at most **two** new hypotheses a week, each tied to one existing tag, with `kind` (`llm` or
  `market`), `horizon_h` (24 or 168), `expect` (`worse`/`better` for `llm`, `up`/`down` for `market`) and a
  `source`. Base them on the by-tag scorecard or on published evidence, not on one memorable day.
- A confirmed lesson guides your forecasts only. Using it for the gate, the trading rule or the go-live case needs
  the stricter M-C1 bar in `docs/test-plan.md` (at least 30 distinct days, 3 separate episodes, a t of 3 or more on
  the daily series, and the same sign in both halves of the data and for BTC and ETH separately).
- The forecast record gets a verdict only at the M-C1 checkpoints (7 Feb 2027, 8 May 2027, then every 90 days).
  Until then, report the running scorecard without calling it skill or failure. If a checkpoint says "worse than no
  skill" for a horizon, stay at the baseline for that horizon (p_up 0.45-0.55, baseline range) until the next one.
  A better Brier score is not profit: money still has to survive costs and India's crypto tax (30% plus 4% cess,
  31.2%, more with surcharge at high incomes, no loss set-off). Never suggest real orders, more capital or a looser
  gate.
- Write three lines in the run summary: what the scorecard says, which lessons changed, what you will do
  differently.

## 6. Save
```bash
indtrader crypto-export --out public && cp public/crypto.json web/data/crypto.json
git add paper/crypto journal/crypto_lessons.json public/crypto.json web/data/crypto.json
git commit -m "Crypto <gate|forecasts> <date> <time> IST" && git push origin main
```
Retry the push up to 4 times (2s/4s/8s/16s). If it is rejected because the branch moved, run
`git pull --rebase origin main` and push again.

Finish with three lines: account values against holding BTC, your calls (and the gate, if set) and why, and the
scorecard in one line.
