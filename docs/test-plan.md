# Test plan: how we check chart patterns, market data and behaviour (crypto first)

*Written on 9 Nov 2026 from six research briefs and a skeptic's review of the first drafts. Everything here runs on
paper money and on historical data. No test result, pass or fail, authorises real money. The real-money gate is in
`docs/go-live-checklist.md`, and going live is always the owner's decision.*

## In short

- **Crypto comes first.** It trades 24 hours a day, 7 days a week, its data is already on disk, and the crypto
  learning loop is already running. So crypto gives the most graded evidence per week.
- **Most ideas here are expected to fail.** A failed test is still useful. It takes the idea out of the analyst's
  list of reasons, and it stops anyone trusting it with real money.
- **Every test is written down and committed before it runs.** Every try is counted, because each extra try makes
  a lucky result more likely.
- **The bar is high on purpose.** Anything new needs a t-statistic of at least 3 and a deflated Sharpe of at least
  0.95 (both explained below).
- **Even a pass only earns more paper trading.** A passed test can change the rules, but only through a dated entry in
  `journal/changes.md`, with paper evidence, never through the LLM.

Nothing in this plan has been run yet. The only numbers computed for it are event counts, made without looking at
any outcome, plus a few rechecks of figures the research briefs had already seen. Both kinds are labelled.

## Words used in this plan

| Word | Meaning here |
|---|---|
| Paper trading | Trading with pretend money at real prices. |
| LLM | Large language model: here, Claude, which reviews the desks' decisions. |
| With LLM / Without LLM | Each desk runs the same rules in two paper accounts. In "With LLM" the analyst can veto, shrink or cut risk. "Without LLM" runs the rules alone. (The code and older docs call them `main` and `control`; some docs say "LLM-reviewed".) |
| Just hold BTC | The crypto desk's third account: BTC bought once and held. It is the benchmark. |
| Design period / test period | Ideas may be tuned only on the design period. The test period is then run once, to judge. |
| Pre-registration | Writing the exact rule and the pass and fail lines into a file, and committing it to git, before any result is seen. |
| Trial | One run of one variant of one idea. Every trial is logged. |
| t (t-statistic) | How many standard errors an average is from zero. For one test with no real effect, a t at least 2 away from zero (in either direction) happens by luck about 1 time in 22, and at least 3 away about 1 time in 370. Many tests make lucky values common. |
| Newey-West t | A t-statistic corrected for overlapping periods (for example, 7-day returns measured every day). Without it, overlap makes results look stronger than they are. |
| Episode | A run of days in the same state (for example, extreme fear). Ten days in one panic are one episode, not ten independent events. |
| Brier score | For a probability forecast: the squared gap between the stated chance and what happened (1 if the price rose, 0 if not). Always saying 50% scores 0.25. Lower is better. |
| No-skill baseline | The call a forecaster with no skill would make: 50% up, with a range set by recent volatility. |
| 80% range, coverage | A price range the forecaster is 80% sure of. Coverage is the share of outcomes that land inside it. It should be about 80%. |
| Sharpe ratio | Average return divided by how much returns swing, per year. Higher is smoother. |
| Deflated Sharpe | The chance that a Sharpe ratio is real after allowing for how many variants were tried and for fat tails (Bailey & López de Prado 2014). We need 0.95 or more. |
| PBO | Probability of backtest overfitting: how often the variant that looked best in one half of the data falls below the median variant in the other half. We need 0.2 or less. |
| TRI | Total return index: an index that includes dividends. A price index leaves them out. |
| Information ratio (IR) | Average return above the benchmark divided by how much that gap swings, per year. |
| Drawdown | A fall from a previous peak. Maximum drawdown is the worst one. |
| Walk-forward windows | The test period cut into 4 consecutive parts. A real effect should hold in at least 3 of them. |
| Survivorship bias | Testing only on things that still exist today. Dead stocks and coins are missing, so results look better than reality. |
| Look-ahead | Using information that was not yet known on the day of the decision. |
| ATR | Average true range: the typical daily price movement, used as a ruler. |
| Funding rate | On crypto perpetual futures, longs pay shorts (or the reverse) every 8 hours. High positive funding means many traders hold borrowed long positions. |
| Fear & Greed index | A daily 0-100 crypto mood score from alternative.me. The repo's tags call below 25 "extreme fear" and above 75 "extreme greed" (alternative.me's own labels also put 25 itself in extreme fear). |
| Support / resistance | Price levels where the price turned before. Support is below the price, resistance above. |
| Bounce rate | Of all the times price reached a level, the share where it turned back instead of closing through it. |
| Round number | A level such as $70,000 or ₹1,000. |
| Double top / head-and-shoulders | Chart shapes read as "the rise is over". A double top has two similar peaks. A head-and-shoulders has three peaks, the middle one highest. The neckline is the low point (or line) between the peaks. The shape is "complete" when price closes below it. |
| After-tax line | The result after Indian tax, shown next to every pre-tax result. |
| R-multiple | Profit or loss divided by the amount risked to the stop-loss. |
| Event study | Measure what happened after each time a signal fired, compared with a fair comparison group. |
| bp | Basis point: 0.01%. |
| Quintile / decile | One fifth / one tenth of a list sorted by some number (for example, the top decile is the 10% with the highest value). |
| Bootstrap | Re-running a calculation on many random resamples of the data, to see how much the answer could vary by chance. |
| Kernel smoother | A method that draws a smooth line through noisy prices, so that peaks and troughs can be found by code. |
| F&O | Futures and options. |
| Open interest | The number of futures or option contracts still open at the end of a day. |
| FII / DII | Foreign / domestic institutional investors (funds, banks, insurers). |
| Slow book, SEPA template, VCP | The stock desks' current momentum set-up: the "slow book" (4×ATR stop, no fixed target, rating-driven sales wait 20 days, 10 positions) with Mark Minervini's SEPA trend template (a checklist that price and its moving averages line up in an uptrend). A VCP (volatility contraction pattern) is a base in which each pullback is shallower than the one before. |

---

## 1. Crypto first

The owner asked to "focus on crypto right now as it opens 24/7 so we can learn and improve a lot". This section comes
first for that reason, and because its data is ready. None of it needs the NSE stock data that the stock tests wait
for.

### What is already built (not proposed here)

- **The crypto desk.** It trades BTC and ETH on a 50-day trend rule, on GitHub Actions. Each coin gets half the
  account while its daily close is above its 50-day average; otherwise that half sits in USDT (a dollar
  stablecoin). The rebalance runs daily at 00:10 UTC. Three paper accounts of 10,000 USDT each: With LLM, Without
  LLM and Just hold BTC. In the With LLM account, an LLM gate can only cut exposure or exclude a coin, never add
  risk (`docs/crypto-desk.md`, `analyst/CRYPTO_PLAYBOOK.md`).
- **The learning loop** (`indtrader/crypto_learn.py`; `docs/crypto-desk.md`, "The learning loop"):
  - three forecast runs a day, at 05:05, 13:05 and 23:05 IST;
  - each run gives, for BTC and ETH, the chance that the price is higher 24 hours later and an 80% price range;
    the 05:05 run also gives a 168-hour (7-day) call;
  - each call is stored next to a no-skill baseline made at the same moment (50% up; a range of ±1.28 × daily
    volatility × √days);
  - every 2 hours, GitHub Actions grades the calls that are due: Brier score, range coverage, pinball loss (a
    score for the range), calibration, all split by market-state tag, with a Newey-West t against the baseline;
  - market-state tags come from the data (`below_50d`, `fg_extreme_fear`, `funding_high`, `vol_high`,
    `big_move_24h` and others);
  - lessons in `journal/crypto_lessons.json` have their status set by the data, not by the analyst: confirmed at
    30 or more scored calls with |t| ≥ 2 in the claimed direction, retired when the data turns against them.
- **A scorer fix, made separately from this plan.** The "market" lessons were first scored against 50% (a coin
  flip). In a rising market, most calls end "up" whatever the tag, so an "up" lesson could be confirmed by plain
  drift. The code has been changed, outside this plan, to compare the up-rate when the tag is on with the up-rate on
  the other calls of the same period, with a Newey-West t (`crypto_learn.market_stats`; `docs/crypto-desk.md`
  describes it the same way).

The first forecast was made on 9 Nov 2026 at 17:36 UTC. The first 24-hour call is graded on 10 Nov 2026. **So the
verdict rules for M-C1 and M-C2 below are written before any forecast or gate action has been graded.**

### 1.0 Rules shared by every crypto test

**Data**
- `data/crypto`: daily Binance USDT candles (open, high, low, close, volume; UTC days) for 74 coins. BTC and ETH
  run from 1 Jun 2018 to 8 Nov 2026.
- Dead and delisted coins stay in: LUNA, FTT, WAVES (its file ends in June 2024), OMG, XMR and others. LUNA's ticker
  was reused for a new coin in May 2022, so it is split into two series, as `scripts/crypto_momentum_study.py`
  already does. No return is measured across the splice.
- Fear & Greed: `data/crypto/fear_greed.csv`, daily from 1 Feb 2018 (source `api.alternative.me/fng/?limit=0`).
- Funding: `data/crypto/funding_BTC.csv` and `funding_ETH.csv`, every 8 hours from 1 Jan 2020 to 31 Oct 2026
  (source: Binance USDT-margined monthly files, `data.binance.vision/data/futures/um/monthly/fundingRate/`).
- Both are already downloaded on this machine by `scripts/download_crypto_sentiment.py`. The `data/crypto` folder
  is not in git, so rerun that script on a new machine.
- The live fact sheet reads OKX funding instead (`crypto_learn.Feeds`). Before relying on history, check that
  OKX and Binance agree on overlapping dates and report how closely.

**Design and test split**
- Design: up to 31 Dec 2022. Test: 1 Jan 2023 to 31 Oct 2026. The test period is run once.
- All historical reports end on 31 Oct 2026, the same end date as the stock reports.

**What has already been seen.** A test period is only clean if nobody has looked at its outcomes.

| Question | Outcomes already seen? | So the 2023-26 test period is |
|---|---|---|
| The BTC + ETH 50-day trend rule itself | Yes. Variants were compared on 2020-22, then all were reported on 2023-26, and the desk's rule was picked after that (`docs/crypto-desk.md`). | In-sample for that rule |
| Fear & Greed and funding, as signals or as add-ons to the trend rule | Yes, 2018-2026, in the crowd-emotion research brief's scratch scripts | Exploratory only |
| Support and resistance against random levels, round numbers, double tops and head-and-shoulders on crypto | No, as far as the repo and the research notes show | Clean, if each test is pre-registered before it runs |

Data that arrives after a test's pre-registration commit is clean for every question.

**Costs**
- 0.1% Binance fee plus 0.05% slippage on each side of a trade, as in `indtrader/crypto.py` (`FEE, SLIP = 0.001,
  0.0005`) and `scripts/crypto_backtest.py`. That is about 0.30% for a round trip (a buy and a sell).
- The live paper desk also pays the bid-ask spread (it buys at the ask and sells at the bid); the backtest does not.
  An Indian exchange may charge different fees (not checked). So every result is also run with costs doubled.

**Tax: the after-tax line on every result**
- 31.2% (30% plus 4% cess) on each profitable sale. Losses cannot be set off against gains and cannot be carried
  forward. Everything is treated as sold on the last day. This is how `scripts/crypto_backtest.py` already works.
- For a single event: a profitable event (after costs) keeps 68.8% of its gain; a losing event keeps its full loss.
- Budget 2026 kept the 30% rate and the 1% TDS (press coverage of the Feb 2026 budget; not checked against the
  Act's text; confirm with a chartered accountant).
- Not modelled, and reported next to the after-tax line:
  - surcharge, which raises the rate at higher incomes;
  - the 1% TDS (tax deducted at source) on each sale's value, above a small yearly threshold (confirm the current
    threshold with a chartered accountant). It counts toward the final tax, but the cash is held until the tax
    return is processed. A rule that trades often locks up more cash. Report the TDS deducted per year.

**Timing**
- Decide on day t's close (00:00 UTC). Act at day t+1's open.
- A Fear & Greed value is stamped 00:00 UTC, so it is known at that day's open, not before.
- Funding settles at 00:00, 08:00 and 16:00 UTC. Use settled values only.

**Statistics**
- When many coins fire on the same day, average across coins for each day first, then compute t.
- Newey-West t with lags at least equal to the horizon in days (M-C1 below sets its own, slightly larger, lags).
- Count episodes as well as days, and report both.
- Report the Sharpe ratio and the maximum drawdown next to every return.

**Trials.** Crypto variants already tried before this plan: about 29.
- 14 in `scripts/crypto_backtest.py` (`docs/crypto-backtest.md`);
- 8 more in `scripts/crypto_momentum_study.py`;
- about 7 Fear & Greed and funding add-ons in the crowd-emotion brief's scratch scripts.

All go into `research/trials.csv` before any new crypto run. The deflated Sharpe for any crypto rule uses every
crypto row.

**Benchmarks.** Just hold BTC, after tax, for anything that touches money. For add-ons to the trend rule, also the
plain rule (the Without LLM account, or the BTC + ETH 50-day trend in a backtest).

---

### M-C1. The forecast learning loop: verdict rules (running now)

**What it answers.** Do the LLM's 24-hour and 7-day calls on BTC and ETH beat a forecaster with no skill? And under
which market states are they better or worse?

**Data.** `paper/crypto/learn/forecasts.csv` and `scores.csv`. Up to 6 calls a day at 24 hours (2 coins × 3 runs)
and 2 a day at 168 hours. By day 90 that is up to about 540 and 180 calls.

**Why the code's own verdict is not enough for this plan.** The live code is right for day-to-day learning, but
three things make it too easy to pass for any wider purpose:
1. **Overlap.** Calls 8 hours apart with 24-hour horizons share most of their outcome, and BTC and ETH move
   together. Thirty 24-hour calls can come from 5 days, which is close to one market episode. The code's
   Newey-West lag was `ceil(horizon/8) − 1`, which assumed one call every 8 hours; with BTC and ETH pooled, a
   24-hour call overlaps about the next 5 rows, not 2. Fixed on 9 Nov 2026: the lag is now counted from the actual
   call times (`crypto_learn.overlap_lags`). The daily-series rule below still applies.
2. **Drift.** The baseline says 50% up. In a rising market, a forecaster who always says 53% beats it with no skill.
3. **Many tags.** The code makes about 19 tags. With two horizons and two kinds of lesson, that is about 76
   possible cells. At |t| ≥ 2, a few will "confirm" by luck.

**Verdict rules, fixed now**
- **Unit of evidence: the day.** For each horizon, average every LLM-minus-baseline Brier difference for the calls
  made on one UTC day, across both coins and all runs. Then compute a Newey-West t on that daily series: lags 2
  for 24 hours, lags 7 for 168 hours.
- **A second no-skill baseline: drift.** Computed afterwards from data the analyst had: the chance of "up" equals
  the share of up periods of the same length over the previous 365 days (the fact sheet already shows this for
  1-day moves as `up_days_365_pct`). The LLM must beat this one too, or its "skill" may only be the market's drift.
- **Checkpoints.** Verdicts are read only at day 90 (7 Feb 2027), day 180 (8 May 2027), and then every 90 days.
  The site may show running numbers, but nothing outside the loop changes between checkpoints.
- **Primary verdict (24 hours, BTC and ETH pooled):**

  | Verdict | Condition |
  |---|---|
  | Skill shown | Daily-series t ≥ 3.0 against the 50% baseline, **and** a positive Brier gain against the drift baseline, **and** the same sign for BTC and for ETH separately |
  | Worse than no skill | Daily-series t ≤ −2.0. Then the analyst stays at the baseline for that horizon (chance of "up" between 0.45 and 0.55, baseline range) until the next checkpoint. Holding the LLM back is the cautious direction, so the lower bar is enough. |
  | No evidence yet | Anything else |

- **7-day verdict:** the same rules, but read as descriptive until day 365. By day 90 there are only about 13
  non-overlapping weeks.
- **Ranges.** Coverage between 70% and 90% is fine. Below 70% means the ranges are too narrow (overconfident): the
  analyst uses at least the baseline's width until the next checkpoint. Above 90% means too wide. Pinball loss
  against the baseline is reported with its daily-series t.
- **Calibration.** Report "said" against "happened" for each probability band. Flag any band with at least 30
  days of calls where the two differ by more than 10 points.

**Lessons**
- Each lesson counts as one trial in `research/trials.csv`, under "crypto-lessons".
- The code's rule (30 calls and |t| ≥ 2) keeps governing day-to-day use: the analyst may lean at most 0.10 from
  50% on a confirmed market lesson (`analyst/CRYPTO_PLAYBOOK.md`).
- To be used for anything else (the gate, the trading rule, the go-live case, or the site calling it "learned"), a
  lesson needs all of:
  - at least 30 distinct days with the tag on;
  - at least 3 separate episodes (tag-on stretches separated by at least 7 days with the tag off);
  - daily-series t ≥ 3.0;
  - the same sign in the first and second half of the data, and for BTC and ETH separately.
- Market lessons are measured against the up-rate on the other calls of the same period, never against 50% (the
  scorer fix described at the top of this section).
- LLM lessons can never be backfilled on history: the model may remember past prices (rule 9 in section 2).

**What a verdict changes**
- "Skill shown" does not change the trading rule and does not authorise real money. It is evidence that the
  analyst reads crypto news and data usefully, which supports keeping the gate and the forecast runs.
- "Worse than no skill" sends the analyst back to the baseline for that horizon.

**Honest expectation.** BTC rose in 52.6% of 7-day windows from June 2018 to November 2026 (crowd-emotion brief;
rechecked for this plan from `data/crypto/BTC.csv`). Short-term crypto direction is close to a coin flip, so any
real edge will be small. Expect "no
evidence yet" at the first checkpoints. That is the honest answer, not a failure.

**Script.** `scripts/forecast_verdict.py` (new): reads the two CSV files, builds the daily series and the drift
baseline, prints the verdict table. It reuses `crypto_learn.nw_tstat`.

### M-C3. Bracket calls against the base rates (bracket-v1, from 11 Nov 2026)

**What it answers.** Does the analyst predict *which is hit first* (a target 1.5 d away, a stop d away, or neither,
within 24 h; d = one day's volatility) better than the coin's own measured base rates? This is closer to a trade's
result than "up or down", and the base rates are a harder, fairer yardstick than a coin flip. Adapted from the
design of zadescoxp/calibrain-harness (read on 11 Nov 2026), whose first question set lost to base rates until the
model was shown them.

**Data.** `paper/crypto/learn/brackets.csv` (analyst rows and base-rate rows, one long and one short bracket per
call), graded from Binance 1-minute candles into `bracket_scores.csv` (a candle touching both levels counts as stop
first). Mirror probes in `probes.csv`.

**Verdict rules, fixed now** (read at the M-C1 checkpoints, 7 Feb 2027 and 8 May 2027, then every 90 days)
- Score: the three-way Brier score of the analyst against the base rates, averaged per UTC day across coins and
  sides, Newey-West t with 2 lags.
- **Skill shown:** daily-series t >= 3.0, the same sign for long and for short, and a fitted blend weight above 0.
- **Worse than the base rates:** t <= -2.0. Then the analyst gives the base rates unchanged until the next checkpoint.
- **Ranks trades:** reported, not a pass line yet: does realised R rise with logged EV (Spearman, EV terciles)?
- **Mirror consistency:** mean gap between mirrored and real answers. Above 0.10 flags a direction bias.
- Logged EV never trades. Linking it to the desk needs this verdict plus the go-live checklist.

**Trials.** 1 (bracket-v1). Any wording or bracket-size change is a new version and a new trial.

### M-C2. The crypto gate: With LLM against Without LLM (running now)

**What it answers.** Does the LLM gate (cut exposure around big events, exclude a coin on a red flag) improve the
With LLM account compared with the Without LLM account?

**Data.** The desk's equity log and gate notes in `paper/crypto/`.

**Measure.**
- The daily return of With LLM minus Without LLM, with a Newey-West t (lags 5).
- The two accounts differ only because of gate actions, so the real sample is the number of gate actions, not the
  number of days. A gate action is a day with exposure below 1 or a coin excluded.
- Each action is tagged by reason type: macro event (for example FOMC or US CPI), coin red flag (hack, delisting,
  large unlock), or systemic stress. `analyst/CRYPTO_PLAYBOOK.md` already asks every gate note to start with
  `Reason: none|macro|coin|stress` and the day's Fear & Greed value. Actions taken when Fear & Greed is below 25 are
  also reported under H6.
- The after-tax line for both accounts.

**Verdict rules, fixed now (the one bar for any LLM claim, section 3)**
- "The gate adds value": t ≥ 3.0, at least 30 actions of that reason type, and only data recorded after this plan
  is committed.
- "The gate costs value": t ≤ −2.0 with at least 30 actions of a reason type. Then that reason type is removed from
  the gate, and only systemic stress remains.
- Otherwise: "no verdict yet".

**Honest expectation.** FOMC meetings (8 a year) and US CPI releases (12 a year) come about 20 times a year, so 30
macro actions take about 18 months. A gate action has no effect on a day when the trend rule already holds only
USDT, so the useful count may be lower. Coin red flags and systemic stress may never reach 30. No verdict is
likely before mid-2028.

**Script.** `scripts/gate_audit.py` (new), shared with M6.

### H8. Crypto crowd extremes: Fear & Greed and funding

The repo-testbed brief proposed this study (its item P1-10). Part H8a looks at history, which has already been
seen. Part H8b is the real test, on data that does not exist yet.

#### H8a. On history (exploratory: outcomes already seen)

**Why.** The six seeded lessons include three crowd-mood ideas: "fear rebounds", "greed pulls back" and "crowded
longs fall". History can show whether they deserve live attention. It cannot prove them, because the crowd-emotion
brief has already looked at 2018-2026, test period included.

**Step 1: make the brief's numbers reproducible.** The brief's runs live in scratch scripts outside the repo, so
nobody can check them. Until `scripts/study_crypto_sentiment.py` reproduces them, every figure below is an
"unreviewed exploratory result, not reproducible from the repo".

**What the scratch runs found (unreviewed; before Indian tax; 0.15% per side)**
- Fear & Greed is mostly price: its correlation with BTC's distance from its 50-day average was 0.79 (rechecked
  for this plan from the files on disk: 0.79 against the previous day's distance).
- After extreme fear, BTC was up 7 days later 56.7% of the time, against 52.6% on all days. The average return was
  lower than on all days.
- On the first day of the 14 episodes with Fear & Greed below 15, BTC's next 30 days averaged −3.9%, against +4.2%
  on all days.
- After crowded funding (3-day average ≥ 0.03% per 8 hours), BTC's next day was +0.16% against +0.14% on all days
  (51.9% up, 208 days). The "crowded longs fall within 24 hours" idea was not supported.
- Trend rule add-ons since 2023: plain BTC trend +390% (worst drawdown −27%); trend OR negative funding +483%
  (−38%). Going flat when funding is crowded hurt both BTC and ETH in 2020-26.
- Day counts, counted by the repo-testbed brief without looking at outcomes (and recounted for this plan from
  `data/crypto/fear_greed.csv`, same result): the design period (2018-22) has 493 extreme-fear and 185
  extreme-greed days; the test period (2023 to Nov 2026) has 186 and 97. These days cluster into a handful of
  episodes.

**Data.** `data/crypto/fear_greed.csv` (from 1 Feb 2018), `funding_BTC.csv` and `funding_ETH.csv` (Binance, from
1 Jan 2020), all already on disk (section 1.0); `data/crypto/BTC.csv` and `ETH.csv`.

**Definitions (the same as the live tags in `crypto_learn.state`)**
- Extreme fear: Fear & Greed below 25. Extreme greed: above 75.
- Funding high: the average of the last 9 settlements (3 days) above 0.03% per 8 hours. Funding negative: below 0.
- Below the 50-day average: the close is under its 50-day average.

**Questions: one per seeded market lesson, measured the fixed way**
1. `fear-rebound-7d`: the 7-day up-rate after extreme fear, against the up-rate on the other days of the same
   period (the live scorer's comparison).
2. `greed-pullback-7d`: the same after extreme greed (the lesson expects "down").
3. `crowded-longs-24h`: the 24-hour up-rate after funding high (expects "down").
4. `downtrend-continues-7d`: the 7-day up-rate below the 50-day average (expects "down").

For each, also report the average return and the worst drawdown over 7 and 30 days, and the first day of each
episode on its own. The first day is when a person feels the urge to act.

**Output.** An `evidence_history` block on each seeded lesson, labelled "history, outcomes already seen". It is
kept apart from the live evidence and **never changes a lesson's status.**

**Lines, fixed now.** An idea "deserves a forward test" only if all of these hold:
- the same sign in the design years (2018-22 for Fear & Greed, 2020-22 for funding) and in 2023-26;
- Newey-West t ≥ 2 in each half;
- at least 5 episodes in each half;
- as an add-on to the trend rule, it beats the plain rule after the 31.2% tax line in both halves.

Otherwise it gets no forward arm, and the analyst may describe the gauge but not cite it as a reason.

**Trials.** 4 lesson rows plus 2 add-on rows, marked "exploratory".

**Script.** `scripts/study_crypto_sentiment.py` (new). It reuses `scripts/crypto_backtest.simulate` (costs and the
after-tax book), `validation.deflated_sharpe` and `crypto_learn.nw_tstat`. It runs in seconds.

#### H8b. Two shadow paper arms (the real test)

**Why.** Only data that arrives after the pre-registration commit is clean for these ideas. A shadow arm is an extra
paper account that follows a fixed rule. The LLM plays no part in it.

**The arms.** These were chosen before the H8a lines above were written, from the brief's run, so H8b is judged on
forward data only.
- **Arm F+:** the desk's rule, except that each coin's half is also held while that coin's 3-day average funding
  is below 0 (trend **or** negative funding). Source: the crowd-emotion brief's scratch run.
- **Arm F−:** the desk's rule, except that a coin's half is cut to a quarter while its 7-day average funding is
  above a fixed line: the 90th percentile of that coin's Binance 7-day averages in 2020-22, computed once and
  written into the pre-registration file. A fixed line cannot peek at later data. Motivation: Schmeling,
  Schrimpf & Todorov (BIS Working Paper 1087, April 2023) found that a high crypto "carry" (the gap between futures
  and spot prices, a close relative of the funding rate) predicts future price crashes.
  Note: the brief's history run found that the stronger "go flat when crowded" version hurt.

Both arms use BTC and ETH like the desk (the brief's history used BTC alone), the same 10,000 USDT start, the same
5% rebalance threshold, and the same fills, fee and slippage. They update in the same daily 00:10 UTC GitHub
Actions job. Live funding comes from OKX, as the learning loop's fact sheet already reads it
(`crypto_learn.Feeds`), while F−'s line comes from Binance history.
So the arms start only after the OKX-against-Binance agreement check (section 1.0) has been run and reported.

**Start.** The day `research/prereg/H8b.json` is committed.

**Verdict rules, fixed now** (at 12 months, then every 6 months, on the after-tax value as if everything were sold
that day)

| Verdict | Condition |
|---|---|
| Stop | It trails the Without LLM account after tax at 12 months. |
| Keep running | It beats both Without LLM and Just hold BTC after tax, **and** its maximum drawdown is no deeper than Without LLM's. |
| Adopt | Never on 12 months alone. It needs a Newey-West t ≥ 3.0 on the daily return difference against Without LLM, on forward data, **and** a deflated Sharpe ≥ 0.95 using the full crypto trial count. Then it goes through `journal/changes.md`. |

Twelve months cannot tell skill from luck (`docs/go-live-checklist.md`, section 2). Realistically, "Adopt" would
take many years. The brief's run also showed a deeper drawdown for F+ (−38% against −27%), so F+ may fail the
drawdown line.

**Trials.** 2.

**Script.** Arms added to `indtrader/crypto.py` as extra paper accounts; the verdict is printed by
`scripts/study_crypto_sentiment.py --arms`.

### H10c. Crypto support and resistance against random levels

**Question.** Does the price turn at the levels our chart code draws more often than at random levels?

**Why.** In one study of intraday currency data, arbitrary levels "held" 56% of the time, against 61% for levels
published by trading firms (Osler 2000, FRBNY Economic Policy Review 6(2)). So "it held support" is weak evidence on
its own. Our crypto rate is unknown until this test.

**Data.**
- Main: `data/crypto` BTC and ETH, daily, 1 Jun 2018 to 31 Oct 2026.
- Second: each day's top 20 coins by 30-day traded value with at least 120 days of history (the rule in
  `indtrader/crypto.py` and `scripts/crypto_momentum_study.py`), dead coins included while they were in the top 20.

**Levels.** `chart.support_resistance` exactly as coded: a 250-bar lookback, swing points with k = 5, swings within
0.6 ATR clustered into one level, at least 2 touches, up to 4 levels on each side. Recompute every day from data up
to that day's close. A swing needs 5 bars after it, so only swings already confirmed that day count. For the
second universe, use unrounded level prices: `chart.py` rounds levels to 2 decimals, which breaks coins priced under
about $1.

**Rules, fixed now**
- **Hit:** the previous close was above a support level, and the day's low reaches the level or comes within
  0.2 × ATR(14) above it. Resistance is the mirror image. Count first hits only: the price must have been at least
  1 ATR away from the level since its last hit.
- **Bounce:** on the hit day and the next 3 days, no close more than 0.2 ATR beyond the level.
- **Bounce rate** = bounces ÷ hits.
- **Random levels:** for each coin and day, 1,000 sets with the same number of levels, placed uniformly at random
  inside the 250-day high-low range, scored by the same rules.
- **Money check (report only):** buy at the next open after a support hit, hold 3 days, minus 0.30% costs, with the
  31.2% after-tax line. Compare with the same trade at random-level hits.

**Pass, fixed now.** The bounce rate at our levels is above the 95th percentile of the random sets' rates in the
design period **and** again in the test period. Report the gap (ours minus the random median) with a bootstrap
interval.

**What the result changes.**
- Pass: levels may appear in the analyst's notes as "levels where price paused more often than chance, on our
  data". They may help place a forecast's 80% range.
- Fail: the analyst may not cite support or resistance as a reason to move a forecast or set the gate. Any crypto
  chart that shows levels says "no better than random on our data".
- Either way, this is not a trading rule. The money check is reported only.

**Trials.** 3 (BTC and ETH; the top-20 universe; the money check).

**Script.** `scripts/study_candles_levels.py --crypto` (shared with H10). It runs in seconds for BTC and ETH. The
random-level loop must be vectorised.

### H19c. Round numbers on BTC and ETH

**Levels.** For a price p, let s = 10^floor(log10 p). Major levels are multiples of s; minor levels are multiples of
s/10.
- BTC above $10,000: majors every $10,000, minors every $1,000. Below $10,000 (2018-20): majors every $1,000,
  minors every $100.
- ETH between $1,000 and $10,000: majors every $1,000, minors every $100. Between $100 and $1,000: majors every
  $100, minors every $10. Below $100 (13 days in December 2018): majors every $10, minors every $1.

**Questions**
1. **Clustering.** Do daily highs stop just below a major level (within 0.5% under it) more often than just below
   random offset levels with the same spacing? The same for lows just above.
2. **Crossing.** After a daily close crosses a major level, is the move over the next 1, 3 and 7 days, in the
   direction of the cross, larger than after crossing a random offset level? A crossing counts only if the same
   level was not crossed in the previous 10 days. The move is reported after 0.30% costs, with the 31.2% after-tax
   line.

**Why.** Osler (Journal of Finance 2003) found, at a large currency bank, that take-profit orders cluster at round
numbers and stop-loss orders just beyond them. That would explain both "reversal at the level" and "acceleration
after crossing". Urquhart (Economics Letters 2017) found that over 10% of BTC prices end in .00, but no significant
return pattern after round numbers.

**Event counts (counted for this plan, outcomes not looked at; recounted in review).** Counting coin-days on which
the daily close crossed at least one level (the scale s taken from the previous close), BTC and ETH crossed a major
level on 359 days in the design period and 207 in the test period (to 31 Oct 2026), and a minor level on 1,966 and
1,390 days. Many are the same level crossed back and forth, so independent events are far fewer. The 10-day rule
above cuts them down.

**Pass, fixed now.** Above the 95th percentile of 1,000 random offsets, in both the design and the test period.

**Use: descriptive only.** BTC and ETH alone cannot supply enough independent crossings for a trading rule.
- Pass: the analyst may note a nearby round level as context for its 80% range and gate notes. A new tag
  (`near_round`, within 0.5 ATR below a major level) could be added to the learning loop so that live data tests it.
  Adding it is a separate code change, and it counts as a new trial.
- Fail: the analyst may not cite a round number as a reason.

**Trials.** 4 (major and minor levels × the two questions).

**Script.** `scripts/study_round_numbers.py --crypto` (shared with H19).

### H9c. Double tops and head-and-shoulders on crypto

**Question.** After a completed top, do coins do worse than comparable coins? If so, would an exit flag help the
desk after tax?

**Data.** `data/crypto`, all 74 coins from June 2018. The universe on each day is the top 20 by 30-day traded value
with at least 120 days of history, with dead coins (LUNA, FTT, WAVES and others) included while they were in it.
BTC and ETH are also reported on their own, but they will have few events.

**Definitions (Lo, Mamaysky & Wang 2000), fixed now**
- **Head-and-shoulders top:** five turning points E1 to E5. E1 is a peak. The head E3 is above both shoulders E1
  and E5. The shoulders are within 1.5% of their average. The two troughs E2 and E4 are within 1.5% of their
  average.
- **Double top:** two peaks within 1.5% of their average, at least 22 days apart.
- **Complete** (our rule, added to the paper's shape definitions): a close below the neckline within 10 days after
  the last turning point is confirmed. For head-and-shoulders, the neckline is the line through E2 and E4. For a
  double top, it is the lowest close between the peaks.
- We keep the published 1.5% tolerance so the test matches the paper. Crypto moves more each day than large
  stocks, so expect fewer patterns.

**Detection methods: 2, each run on both patterns, so 4 variants**
- (a) A kernel smoother at 0.3 × the cross-validated bandwidth over 38-day windows, with a 3-day lag, refitted using
  data up to that day only.
- (b) `chart.swing_points` with k = 3, each swing usable only from bar i+3.

**Outcome.**
- The return from the next day's open over 1, 7 and 30 days, minus 0.30% costs.
- Main comparison (the one the t-statistic uses): the average return of coins in the same 30-day-return quintile on
  the same date, over the same window.
- Also reported: the event return minus the equal-weight top 20, and against the same coin on 1,000 random dates in
  the same period.
- The after-tax line: profitable events keep 68.8% of the gain.

**Count first.** Count the design-period events before looking at any outcome. Fewer than 300 means "too little
data", and the test stops there.

**Pass, fixed now**
- **Step 1, the signal exists:** design-period Newey-West t ≤ −3, and test-period t ≤ −2 with at least half the
  design effect. Average across coins for each date first.
- **Step 2, it helps the desk:** run the BTC + ETH 50-day trend with one change. A coin's half moves to USDT when a
  completed top appears and comes back at the next fresh close above the 50-day average. It must beat the plain rule
  after the 31.2% tax line in 2023-26 and in at least 3 of 4 walk-forward windows, with a maximum drawdown no
  deeper. Caveat: the plain rule was itself picked after seeing 2023-26.

**What the result changes.**
- Pass: the exit flag is proposed through `journal/changes.md` and first runs as a shadow paper arm. The analyst may
  cite a completed top in gate notes.
- Fail: the analyst may describe the shape but must not cite it as a reason to cut exposure or move a forecast.
  Pattern-book success rates (Bulkowski) are never quoted as odds.

**Evidence elsewhere.** On US stocks, Lo, Mamaysky & Wang found that the shapes change the distribution of later
returns: a statistical effect, not a profit. Savin, Weller & Zvingelis (2007) found that shorting the pattern alone
lost money in the S&P 500. The chart-patterns brief found no test on crypto.

**Trials.** 4, plus 1 if step 2 runs.

**Script.** `scripts/study_head_shoulders.py --crypto`, with the detector in `indtrader/research/patterns.py`
(shared with H9).

### Crypto order of work

**Status (9 Nov 2026).** P0-B is built (`indtrader/research/prereg.py`, `research/trials.csv`). H10c and H19c ran
once on the test period and failed in both periods; H9c stopped at "too little data"; H8a found no lesson worth a
forward test, so H8b is registered but not started. Results: [crypto-studies.md](crypto-studies.md).


1. Build the pre-registration files and the trial ledger (P0-B), and enter the about 29 past crypto trials.
   Commit the files for H8b, H9c, H10c and H19c. This document fixes the M-C1 and M-C2 rules once committed.
2. M-C1 and M-C2 are already collecting data. Read verdicts only at the checkpoints.
3. H8a: reproduce the brief's numbers inside the repo. Then start the H8b arms.
4. H10c and H19c: fast, seconds per run.
5. H9c: after `indtrader/research/patterns.py` exists (shared with the stock test H9).

None of this waits for the NSE stock data (P0-A).

---

## 2. Ground rules for every test (stocks, options and crypto)

1. **Pre-register.** Before any run, commit `research/prereg/<id>.json`. It holds:
   - the hypothesis;
   - the exact rule;
   - the universe (which stocks or coins);
   - the holding horizons;
   - the costs;
   - at most 4 variants per question (a test with several questions lists each one, and every variant counts as a
     trial);
   - the pass and fail lines.

   The test runner refuses to touch the test period unless that file is already committed (check with
   `git log -- <file>`).
2. **Count every try.** Every run, design or test, appends one row to `research/trials.csv`. The number of trials
   used in the deflated Sharpe is every row for that asset class. That includes variants tried before this plan:
   - momentum exit and config variants (`journal/changes.md`, `docs/strategy.md`, `docs/backtest-forensics.md`);
   - the 48 condor variants (`docs/options-backtest.md`);
   - the about 29 crypto variants (section 1.0).
3. **Fixed periods.** Tune only on the design period. Run the test period once.

   | Asset | Design period | Test period |
   |---|---|---|
   | Stocks | 2008-01-01 to 2018-12-31 | 2019-01-01 to 2026-10-31 |
   | Crypto | up to 2022-12-31 | 2023-01-01 to 2026-10-31 |
   | Sentiment built from options data | 2020-2022 | 2023 to 2026-10-31 |

   - **The momentum book's current settings were chosen on Jan 2024 to Oct 2026 data.** The slow book with the SEPA
     template was adopted on 28 Oct 2026 and the drawdown breaker on 30 Oct 2026, both from a Nifty 200 backtest of
     Jan 2024 to Oct 2026 (`journal/changes.md`). So for any test that uses the current book, 2024-2026 is
     in-sample. Report 2019-2023 as the clean out-of-sample period and 2024-2026 separately, labelled in-sample.
   - The same applies to crypto: 2023-26 is in-sample for the desk's trend rule (section 1.0).
   - Only data that arrives after the pre-registration commit is fully clean.
4. **One end date, and an endpoint check.**
   - All historical reports end on 31 Oct 2026. The forensics report (`docs/backtest-forensics.md`) ended on 6 Nov
     2026. Rerun it to 31 Oct and show both.
   - Why it matters: the Nifty rose 8.6% in that one week, from 23,053.1 on 30 Oct to 25,030.3 on 6 Nov 2026 (Yahoo
     `^NSEI` closes, checked by the skeptic review and again in a later review). The median F&O stock future in
     `data/futstk` rose about 6.6% over the same week (218 stocks, same-expiry contracts, computed for this plan
     and rechecked). A 2.85-year comparison can flip on its last week.
   - So every headline comparison is repeated with the end date at each month-end from 30 Jun 2025 to 31 Oct 2026,
     and the range is reported. A result that changes sign across end dates is "endpoint-dependent: no evidence
     either way".
5. **Data whose results have already been seen.** The research briefs and earlier work already looked at outcomes
   for:
   - India VIX against the Nifty, 2008-2026;
   - US VIX/VIX3M, 2009-2026;
   - the AAII survey, 1987-2026;
   - Nifty put-call ratio, 2020-2026;
   - CBOE put-call ratio, 2006-2019;
   - NSE participant open interest, 2014-2026;
   - crypto Fear & Greed, 2018-2026;
   - Binance funding rates, 2020-2026;
   - IIMA momentum factors, 1994-2025;
   - the momentum book, Jan 2024 to Nov 2026;
   - the crypto trend and momentum rules, 2020-2026.

   Historical tests on these can only be exploratory. The only clean judge is data that arrives after the
   pre-registration commit.
6. **Numbers nobody can reproduce are labelled.** Several figures in this plan come from the briefs' scratch runs,
   whose scripts are not in the repo. Each is marked "unreviewed exploratory result, not reproducible from the
   repo" until its script and output are committed under `scripts/` and `research/`.
7. **No look-ahead.**
   - Signals use data up to the close on day t and fill at the open on day t+1, as `indtrader/backtest.py` already
     does.
   - A swing point at bar i is usable only from bar i+k.
   - Smoothers are refitted on data up to day t only.
   - "Gap filled", "exhaustion" and Bulkowski's "ultimate high" are never inputs.
   - Data published after the close acts in the next session. This covers FII/DII flows, bulk deals, participant
     open interest, insider (PIT) disclosures, and results broadcast after 15:30.
8. **No survivorship.**
   - Stock tests use the point-in-time price table (P0-A), never Yahoo, for the history of who was in the universe.
   - Crypto tests keep dead coins (section 1.0).
9. **The LLM never judges historical charts or history.** LLMs remember past prices (the FinCAD paper cited in
   `docs/research.md`). Code scores the patterns; the LLM only reads the results. LLM forecasts are tested live
   only (M-C1).
10. **Statistics.**
    - Average across stocks or coins on each date first, then compute t-statistics.
    - Use Newey-West t-statistics with lags equal to the horizon, and market-adjusted returns.
    - Report confidence intervals.
    - When many events fall on the same day, use calendar-time portfolios or errors clustered by date.
    - For every timing rule (in or out of the market), report the Sharpe ratio and the maximum drawdown next to the
      yearly return. A rule meant to cut drawdowns must be judged on drawdowns too.
11. **Costs and tax.**
    - **Delivery shares:** the `CostModel` charges, which come to about 0.22% of the value for a round trip plus the
      ₹15.34 DP charge (the depository's fee) per stock sold; `CostModel.round_trip_pct` already includes that fee
      (about 0.24% in all on a ₹1 lakh trade). Add 0.05% slippage per side. Stress run: 0.2% slippage per side.
    - **Options:** STT (securities transaction tax) of 0.15% of the premium on options sold, and 0.15% of the
      intrinsic value on options exercised (held to expiry in the money).
    - **Futures:** STT of 0.05% on the sale side.
    - These derivative rates apply to trades from 1 Apr 2026 under the Finance Act 2026. Before that they were
      0.10%, 0.125% and 0.02% (NSE circular NSE/FATAX/73524, "Changes in rates of Securities Transaction Tax",
      31 Mar 2026, as quoted in Fyers' and Zerodha's notices; the circular's PDF itself returned an error). The
      delivery rate is unchanged. Tests that reach back before 1 Oct 2024 must use the older, lower rates in force on
      each trade date; `indtrader/options_backtest.stt_rate` already does this for options (0.0625% of premium
      before 1 Oct 2024).
    - `indtrader/options_backtest.py` charges STT only on sales, and it closes every position on the last trading
      day before expiry, so the exercise rate never applies there. Any test that holds options to expiry must add
      it.
    - The OI build-up study (`docs/oi-buildup.md`) assumed about 6bp of costs per leg, set before the futures STT
      rise. Rerun its 2026 period at the new rate.
    - **Tax on shares:** 20% short-term capital gains on net realised gains, with losses carried forward (which
      needs the tax return filed on time); 12.5% long-term above ₹1.25 lakh a year. Add the 4% cess (20.8% and
      13%) and note that surcharge may apply at higher incomes. Confirm with a chartered accountant.
    - **Crypto:** section 1.0.
12. **Circuit days.** When open, high, low and close are all equal at the price band, assume no fill.
13. **Tools.** Use pandas and numpy only, because pyarrow and scipy are not installed. Unit tests go next to the
    existing ones in `tests/`.

---

## 3. Pass marks

- **T1, the signal exists.**
  - After costs, the design period shows |t| ≥ 3.0.
  - The test period shows the same sign, with |t| ≥ 2.0 and at least half the design-period effect.
  - There are at least 300 events, or at least 36 independent months.
  - Fewer than 300 events in the design period: report "too little data" and draw no conclusion.
- **T2, it is worth money.** All of the following:
  - a buy-only version beats both the equal-weight universe and the right benchmark in the test period, after costs
    and tax. Benchmarks: Nifty 200 TRI for stock rules, Nifty 50 TRI for index rules, BTC buy-and-hold for crypto.
    Subtract an index-fund expense ratio from the TRI, fixed in the pre-registration file;
  - compare like with like: the bhavcopy table has no dividends, so either add the stocks' dividends from the
    corporate-actions file or compare with the price index, and say which;
  - deflated Sharpe ≥ 0.95, using the full trial count;
  - PBO ≤ 0.2 wherever 8 or more variants exist;
  - positive in at least 3 of 4 walk-forward windows;
  - still positive with every decision one day late, and with costs doubled;
  - the endpoint check (section 2, rule 4) does not flip the sign.
- **T3, it works as a filter.**
  - Adding it to the current book raises test-period excess return without lowering the Sharpe ratio, in at least 3
    of 4 windows.
  - For an "avoid" filter, the stocks it removes must also underperform the stocks it keeps.
- **Tuned rule sets and anything new: t ≥ 3.0.** A t of 2.0 is acceptable only for an untuned, pre-registered plain
  12-1 momentum rule (a well-documented factor). The desk's actual rule set is tuned (slow book, SEPA template,
  drawdown breaker, volatility filter), so it needs t ≥ 3.0 and the deflated Sharpe bar, with every logged variant
  counted.
- **Any claim that the LLM adds value: one bar.** t ≥ 3.0, at least 30 cases of each reason type, and only data
  recorded after the pre-registration commit. Restricting the LLM, which moves an account back toward its tested
  rules, needs t ≥ 2.0.

**How long proof takes against a benchmark.** The owner's question is whether a desk beats an index fund, so the
relevant number is the information ratio against the TRI, not the Sharpe ratio against zero. Years of results needed,
assuming normal returns (the same arithmetic as the Sharpe table in `docs/go-live-checklist.md`):

| Information ratio | Years for 95% one-sided confidence, (1.645/IR)² | Years for t ≥ 3, (3/IR)² |
|---|---|---|
| 0.2 | about 68 | about 225 |
| 0.3 | about 30 | about 100 |
| 0.5 | about 11 | about 36 |

This is why history (long, honest backtests) has to carry the proof, and why paper trading mostly catches bugs.

**What a result changes**

| Result | Effect |
|---|---|
| Fails | Marked "tested, no edge". The analyst may not cite it as a reason. |
| Passes T1 only | Context for a veto or a smaller position only. |
| Passes T2 or T3 | May change the rules, through a dated `journal/changes.md` entry with paper evidence. Never through the LLM. |
| Any result | Does not authorise real money. See `docs/go-live-checklist.md`. |

---

## 4. Data inventory

**Already on disk**

| Data | Coverage | Notes |
|---|---|---|
| `data/crypto` | 74 Binance USDT pairs, daily; BTC and ETH from 1 Jun 2018 to 8 Nov 2026 | Includes dead coins: LUNA, FTT, WAVES and others |
| `data/crypto/fear_greed.csv`, `funding_BTC.csv`, `funding_ETH.csv` | Fear & Greed daily, 1 Feb 2018 to 9 Nov 2026; Binance funding every 8 hours, 1 Jan 2020 to 31 Oct 2026 | From `scripts/download_crypto_sentiment.py`. `data/crypto` is not in git, so rerun it on a new machine. |
| `paper/crypto/learn/` | Forecasts and scores from 9 Nov 2026 | The M-C1 data |
| `data/futstk` | NSE stock futures, 2 Jan 2023 to 6 Nov 2026: 948 days, 295 symbols, 561,574 rows | Point-in-time F&O list. Loads in about 1 second. |
| `data/fo` | Nifty, Bank Nifty and Fin Nifty options within 45 days of expiry, plus the near-month future, 2020 to 30 Oct 2026: 1,688 days | Open interest for each strike |
| Yahoo (via `indtrader/data.py`) | Daily prices | Only today's survivors. Never use it for universe history. |
| NSE live APIs (`indtrader/nse.py`) | Filings, results calendar, surveillance lists, corporate actions | Already includes `adjustment_factor()` |

**Free to download** (the briefs checked these links on 9 Nov 2026)

| Data | From | Source |
|---|---|---|
| Crypto Fear & Greed (already downloaded, above) | 1 Feb 2018 | `api.alternative.me/fng/?limit=0` |
| Binance funding rates (BTC and ETH already downloaded, above) | Jan 2020 | `data.binance.vision/data/futures/um/monthly/fundingRate/...` |
| Binance open interest and long/short ratios | Sep 2020 | `data.binance.vision/data/futures/um/daily/metrics/...` |
| Stablecoin supply | 2017 | `stablecoins.llama.fi/stablecoincharts/all` |
| Cash-market bhavcopy (prices, every listed stock) | Jan 2000 | `nsearchives.nseindia.com/content/historical/EQUITIES/...` |
| MTO delivery files | Confirmed back to 1 Apr 2008 by the market-data brief (the repo-testbed brief says 2003) | `nsearchives.nseindia.com/archives/equities/mto/MTO_DDMMYYYY.DAT` |
| `sec_bhavdata_full` (prices plus delivery in one file) | 31 Dec 2019 (earlier dates return 404) | `nsearchives.nseindia.com/products/content/sec_bhavdata_full_DDMMYYYY.csv` |
| Symbol changes (1,080 renames); delisted list | n/a | `nsearchives.nseindia.com/content/equities/symbolchange.csv` |
| Corporate actions | 2019 confirmed | `nseindia.com/api/corporates-corporateActions` |
| Participant-wise open interest | 2 Jan 2012 | `nsearchives.nseindia.com/content/nsccl/fao_participant_oi_DDMMYYYY.csv` |
| Index closes, including India VIX | Jul 2013 | `archives.nseindia.com/content/indices/ind_close_all_DDMMYYYY.csv` |
| India VIX history | 2008 (Yahoo `^INDIAVIX`); 2015 confirmed on NSE's API | `nseindia.com/api/historicalOR/vixhistory` |
| Nifty 50 and Nifty 200 TRI | Not yet checked from this server | niftyindices.com historical data |
| 91-day T-bill auction cut-offs | Not yet checked as a history | rbi.org.in |
| Results broadcast times; board meetings | 2019 confirmed; full range unknown | `nseindia.com/api/corporates-financial-results`, `.../corporate-board-meetings` |
| Bulk and block deals | Date ranges, one year at a time | `nseindia.com/api/historicalOR/bulk-block-short-deals` |
| Insider (PIT) disclosures | One stock per call | `nseindia.com/api/corporates-pit?symbol=...` |
| Promoter pledges | Current quarter only | `nseindia.com/api/corporate-pledgedata` |
| IIMA Indian factor files | 1994 | `faculty.iima.ac.in/iffm/Indian-Fama-French-Momentum/` |

**Not available free**
- Liquidation history for USDT pairs.
- Exchange flow data (coins moving into or out of exchanges).
- History of the CNN Fear & Greed index.
- A point-in-time US stock universe that includes delisted prices.
- A historical archive of the ASM/GSM surveillance lists. It only builds up going forward, if the cache in
  `<data_dir>/nse/<date>/` is kept.
- A bulk source for SAST Regulation 29 disclosures.

**Download etiquette**
- At most about 1 request per second to NSE, with browser headers, as `indtrader/nse.py` already does.
- Every fetch fails open and never blocks a stop-loss.
- Treat downloaded files as untrusted data, kept apart from code.
- `data/cm/` needs a `.gitignore` entry, added by whoever implements this.

---

## 5. Priority list

| ID | Test | Priority | Data ready? | Expected outcome |
|---|---|---|---|---|
| M-C1 | Crypto forecast loop: verdict rules | Crypto, running | Yes, building daily | "No evidence yet" at first |
| M-C2 | Crypto gate: With LLM against Without LLM | Crypto, running | Yes, building daily | No verdict before 2028 |
| H8a | Crypto crowd extremes on history | Crypto, now | Yes | Exploratory; unreviewed runs already contradict two seeded lessons |
| H8b | Two funding shadow arms | Crypto, forward | Yes | Unresolved for years |
| H10c | Crypto support/resistance against random levels | Crypto, now | Yes | Unknown |
| H19c | Round numbers on BTC and ETH | Crypto, now | Yes | Descriptive |
| H9c | Double tops and head-and-shoulders on crypto | Crypto, next | After `patterns.py` | Likely fail or too little data |
| P0-A | Clean NSE price, delivery and corporate-action table | Foundation | Download about 2-3 h | n/a |
| P0-B | Harness, pre-registration, trial ledger | Foundation (crypto needs it too) | n/a | n/a |
| P0-C | Fix measurement problems | Foundation | Yes | n/a |
| H1 | Momentum screen on a clean universe, 2008-2026 | P1 | After P0-A | Likely fail or "no evidence either way" |
| H2 | 52-week high adds to momentum | P1 | After P0-A | Uncertain |
| H3 | MAX (lottery stock) avoid filter | P1 | After P0-A | Uncertain |
| H4 | Drift after results | P1 | After P0-A plus results dates | Uncertain |
| H5 | Buy now or wait for a base breakout (VCP, flag, cup, range) | P1 | After P0-A | Likely fail |
| H6 | Fear-state veto audit, all desks | P1, forward only | Start logging now | Unknown |
| H7 | VIX as a brake (desk filter, sizing, condor skip) | P1 | Partly | (a) likely costs return |
| H9 | Head-and-shoulders and double top as exit flags | P2 | After P0-A | Likely fail |
| H10 | Candles and support/resistance as coded; bounce test against random levels | P2 | After P0-A | Likely fail |
| H11 | Range-breakout family, as a calibration | P2 | Yes (index) | Fake winners expected |
| H12 | Stop distance and stop placement | P2 | After P0-A | Unknown |
| H13 | Sizing, loss limits, no averaging down | P2 | Yes (backtest trades) | Safety rules |
| H14 | Attention-spike filter | P2 | After P0-A | Unknown |
| H15 | Delivery % spikes | P3 | After P0-A | Likely fail |
| H16 | Indian sentiment gauges (PCR, participant OI, VIX direction) | P3 | Mostly | Exploratory only |
| H17 | Breadth as the regime brake | P3 | After P0-A | Unknown |
| H18 | Gaps with news against gaps without news | P3 | After P0-A | Unknown |
| H19 | Round-number clustering and crossings (NSE, Nifty) | P3 | After P0-A | Descriptive |
| H20 | Bulk deals after publication | P3 | API | Reversal expected |
| H21 | Insider market purchases | P3 | API | Unknown |
| H22 | Promoter pledges as a filter | P3 | Partly | Unknown |
| H23 | High-volume premium, buy-only | P3 | After P0-A | Unknown |
| H24 | Max pain as an expiry forecast | P3 | Yes (`data/fo`) | Likely fail |
| H25 | Close position in the 20-day range (the neural-network shortcut) | P3 | After P0-A | Unknown |
| H26 | Bulkowski hindsight gap (teaching demo) | P3 | After P0-A | Large gap expected |
| M1-M7 | Ongoing forward monitors | Ongoing | Paper logs | n/a |

**The trial budget.** Every trial raises the bar for every other trial in the same asset class.
- Crypto: about 29 trials already, about 20 more from section 1, plus one per lesson.
- Stocks: running every test from H1 to H26 adds about 60 or more.
- So: crypto section 1, P0 and P1 first, plus the monitors. Then the owner decides whether P2 and P3 are worth the
  extra trials.

---

## 6. Foundations

### P0-A. A survivorship-free NSE price, delivery and corporate-action table
- **Why.** Yahoo only covers today's survivors. The repo's audit found the momentum result fell from +18.5% to
  +12.6% once the stock list was taken as it stood at the start (`docs/backtest-forensics.md`). Delisting returns
  are a known bias in stock-return data (Shumway 1997, cited from memory).
- **What to build.**
  1. `scripts/download_cm_bhavcopy.py`, modelled on `scripts/download_futstk_bhavcopy.py`: resumable, a 0.25 s
     pause between files, one `data/cm/<YYYY>.csv.gz` per year.
     - Before 2020: `cm{DD}{MON}{YYYY}bhav.csv.zip` for prices, plus the MTO files for delivered quantity.
     - From 31 Dec 2019: `sec_bhavdata_full`.
     - Keep the EQ and BE series, and flag BE as trade-for-trade.
  2. `scripts/download_corp_actions.py`: monthly windows of the corporate-actions API, turned into split and bonus
     factors with `indtrader.nse.adjustment_factor`, plus `symbolchange.csv` and `delisted.csv`. Keep dividends too,
     for the like-with-like TRI comparison.
  3. `indtrader/research/panel.py`:
     - Back-adjust prices and volume by the cumulative factors, and chain renamed symbols to their old histories.
     - Drop any stock-day return where close/previous close is below 0.55 or above 1.8 with no matching corporate
       action. Never guess an adjustment.
     - `liquid_top(n, day)`: stocks with at least 252 sessions of history, ranked by median traded value over the
       previous 126 sessions.
     - `fno_list(day)`: the F&O list as it stood that day, from `data/futstk`, extended back with
       `python scripts/download_futstk_bhavcopy.py 2008 2022`.
     - A delisted stock's last trade is its exit. Run every result twice, with a 0% and with a −30% delisting
       return.
- **Checked facts.**
  - NSE's previous close is **not** adjusted on ex-dates. RELIANCE on 28 Oct 2024 (1:1 bonus): previous close
    2,655.70, close 1,334.35. TCS on 31 May 2018 (1:1 bonus): previous close 3,514.10, close 1,741.05.
  - Renames in `symbolchange.csv` include MCDOWELL-N to UNITDSPR (7 Jun 2024), L&TFH to LTF (23 Apr 2024), and
    TATAMOTORS to TMPV (24 Oct 2025, after the Tata Motors demerger).
  - Demergers such as Tata Motors': exclude the event window rather than guessing.
- **Unit tests** (`tests/test_research_panel.py`):
  - a 1:1 bonus is adjusted;
  - an unexplained −50% day is dropped;
  - a renamed symbol is chained;
  - `liquid_top(day)` uses no data after that day.
- **Runtime.** About 8,000 files for 2007-2026 take 1.5-2.5 hours, resumable and in the background (about 100-200
  MB gzipped, per the market-data brief). Corporate actions take about 5 minutes. Building the table takes 2-5
  minutes and under 1 GB of memory.

### P0-B. The harness, pre-registration and trial ledger
- Three new pieces:
  - `indtrader/research/eventstudy.py`, the event-study harness (about 200 lines). It must work on 24/7 daily crypto
    data as well as NSE sessions;
  - `research/prereg/<id>.json`, one per test;
  - `research/trials.csv`, the ledger, with an asset-class column.
- **Outcome measure.** The return from the open on day t+1 to the close on day t+h (h = 1, 5, 20, 60 for stocks;
  1, 7, 30 days for crypto), minus the equal-weight universe over the same window. Newey-West t-statistics via
  `indtrader.crypto_learn.nw_tstat`.
- **Reuse** `indtrader/validation.py`: `bootstrap_sharpe_ci`, `walk_forward`, `deflated_sharpe`.
- **Unit tests** (`tests/test_eventstudy.py`):
  - a planted effect in synthetic data is detected;
  - moving a signal one day earlier changes the result (catches look-ahead);
  - a swing point is usable only from bar i+k;
  - `trials.csv` grows by one row per run.

### P0-C. Measurement fixes, before any test is trusted
- **Crypto lesson scorer: changed separately, not part of this plan.** `market` lessons now compare the up-rate
  when a tag is on with the up-rate on the other calls of the same period, instead of 50% (a coin flip)
  (`crypto_learn.market_stats`).
- **Crypto Newey-West lag: a code check, outside this plan.** `crypto_learn.stats` and `market_stats` set the lag to
  `ceil(horizon_h/8) − 1`, which assumes one call every 8 hours. BTC and ETH calls are pooled, so 24-hour calls come
  about 6 a day and each overlaps about the next 5 rows, not 2. Too few lags make t look larger than it is. The
  168-hour lag (20) already covers its overlap. M-C1 avoids the issue by averaging per day first.
- **Sharpe above cash.** `validation._sharpe` uses raw returns. Add versions on returns above cash and above the
  Nifty 50 TRI. "Cash" is the realised return of the 91-day T-bill over the same window, built from RBI's auction
  cut-offs with their dates, not one fixed yield.
- **Information ratio.** Add the information ratio against the TRI, with its Newey-West t (section 3).
- **Track-record length.** Add `min_trl()` and keep `probabilistic_sharpe()` (Bailey & López de Prado, "The
  Sharpe Ratio Efficient Frontier", Journal of Risk, 2012). It is about 5 lines.
- **Overfitting check.** Add PBO by combinatorial cross-validation (Bailey, Borwein, López de Prado & Zhu), about 50
  lines of numpy, using stored variant equity curves.
- **Breakout volume.** Unify the 50-day (`chart.py`) and 20-day (SEPA skill) definitions. Pre-register one before H5
  and H14.
- **After-tax line.** Add one to every backtest report: section 2, rule 11, for shares; section 1.0 for crypto,
  including the yearly TDS deducted.
- **Endpoint check.** A helper that repeats a comparison at each month-end end date (section 2, rule 4).

---

## 7. Stock and options tests, priority 1

### H1. Does the desk's momentum screen beat the Nifty on a clean universe, 2008-2026?
- **Why.**
  - The go-live gates need a long point-in-time backtest. The current window is only about 2.85 years, and its
    verdict depends on its last week (section 2, rule 4).
  - The IIMA factor data suggest the buy-only part of momentum (big winners minus the market) earned only about
    0.2-0.3% a month after 2008: 0.26% (t 0.99) in 2008-18 and 0.21% (t 0.68) in 2019-25. Source: the IIMA
    2025-12 survivorship-adjusted monthly file, as computed by the repo-testbed brief and rechecked by the skeptic
    review.
- **Hypothesis.** The exact slow book plus SEPA rules in `config/india_paper.yaml`, with no tuning, beat the Nifty
  200 TRI after costs and tax.
- **Periods.** The settings were chosen on Jan 2024 to Oct 2026. So 2008-2018 and 2019-2023 are out-of-sample for
  them, and 2024-2026 is in-sample. Report the three separately. Nothing is tuned anywhere.
- **Universes.** `liquid_top(200)` and `fno_list(day)`. Run both and report both.
- **Pass.** Because the rule set is tuned (section 3), all of:
  - Newey-West t ≥ 3.0 on the monthly return above the Nifty 200 TRI over 2008-2023;
  - deflated Sharpe ≥ 0.95, with every logged momentum variant counted;
  - the rest of T2 (walk-forward, one day late, costs doubled, endpoint check).
- **Report** the information ratio and the years it would need (section 3).
- **Honest expectation.** t ≥ 3 over 16 years needs an information ratio of about 0.75 (3 ÷ √16). That is far above
  what momentum books usually show. The likely result is "no evidence either way" or a fail, not "trails by 1-2.6
  points".
- **Script.** `run_backtest(histories=panel)`, about 30-90 minutes a run, or a vectorised monthly simulator, under 5
  minutes.
- **If it fails.** The momentum desk stays a measurement of the LLM layer. What to do with real money stays the
  owner's decision under `docs/go-live-checklist.md`.

### H2. Does nearness to the 52-week high add to momentum?
- **Why.** George & Hwang 2004 (US, cited from memory). It is marginal in the large replication: t 2.02 (Hou, Xue &
  Zhang). Indian evidence is unverified (Raju, SSRN 4587697).
- **Measure.** PTH = adjusted close ÷ highest adjusted high of the last 252 sessions.
- **Variants (3).**
  - (a) A monthly cross-sectional regression (Fama-MacBeth) of next-month returns on PTH and the screen's momentum
    z-score, with Newey-West errors. The question is whether PTH adds anything beyond momentum.
  - (b) The top fifth of `liquid_top(200)` by PTH, equal-weighted, held 1 month.
  - (c) Inside the screen's top 2N names, break ties by PTH.
- **Pass.** T1 on the coefficient in (a) or on the excess return in (b). T3 for (c).
- **If it passes.** Add z(PTH) to the screen score through `journal/changes.md`.
- **If it fails.** Drop "near its highs, so bullish" from the analyst's reasoning.
- **Script.** `scripts/study_52wk_high.py`, under 2 minutes.

### H3. Lottery stocks (MAX) as an avoid filter
- **Why.** Bali, Cakici & Whitelaw 2011 found over 1% a month in the US, but it is not significant once
  value-weighted (Hou, Xue & Zhang). The direction is disputed in India, and the briefs rate it differently.
- **Measure.** MAX = the largest daily return in the previous 21 sessions. Variant: the average of the 5 largest.
- **Rule.** Monthly deciles in `liquid_top(200)` and `liquid_top(500)`. The buy-only use is excluding the top decile
  from screen candidates.
- **Pass.** T1 with a negative sign (design t ≤ −3, test t ≤ −2), after costs. Then T3 against the current screen,
  which already drops the most volatile 20% (`vol_exclude_pct = 0.2`).
- **Script.** `scripts/study_max_effect.py`.

### H4. Drift after results
- **Why.** Classic US evidence that has faded in large caps (Martineau 2022, cited from memory). Indian evidence is
  mixed. The result decides what the desk does after results, not just before them.
- **Data.** A new `scripts/download_results_dates.py`, using `broadCastDate` from the financial-results API: about
  450 two-week windows at 1 request per second, roughly 10 minutes.
  - Check pagination and how far back it goes before starting. If coverage is thin, fall back to board-meeting
    dates.
  - Day 0 is the first session at or after the broadcast. If the broadcast is after 15:30, day 0 is the next
    session.
- **Measure.** EAR (earnings announcement return) = the stock's return minus the equal-weight universe's, from day
  −1 to day +1.
- **Variants (3).**
  - (a) Quintiles of EAR, measuring excess return from the open on day +2 to the close on day +61.
  - (b) As a filter: block momentum buys for 60 sessions after a bottom-quintile EAR.
  - (c) Chan 2003: one-day moves larger than 3 standard deviations, split by whether results came out within 2
    days. Expect drift after news moves and reversal within 20 days after no-news moves.
- **Pass.** T1 for (a) and (c). T3 for (b).
- **If it passes.** Allow buys after a strong positive reaction instead of blocking them, and veto after a weak one.
  The 3-day pre-results blackout stays either way.

### H5. Buy now, or wait for a base breakout?
- **Why.** This is the desk's real pattern question. No peer-reviewed test of VCP, flags or cup-and-handle exists.
- **Arms.**
  - Arm A: buy the screen's picks at the next open (the current default).
  - Arm B: wait up to 20 bars for a pivot breakout; skip the stock if none comes.
  - Both arms: same sizing, same 4×ATR stops, Indian costs.
- **VCP definition, fixed before running** (from `.claude/skills/sepa-strategy/references/patterns.md` and
  `entry-rules.md`):
  1. All 7 trend-template checks pass, and the momentum score is at the 70th percentile or above.
  2. The base runs from the highest high of the last 65 sessions (at least 15 sessions old) to today, and is 10-35%
     deep.
  3. There are at least 3 pullbacks between confirmed swing points (`swing_points`, k = 3, usable from bar i+3).
     Each pullback is no deeper than 0.8 times the one before, with rising swing lows, and the last is at most 10%
     deep.
  4. Average volume in the last pullback is at most 0.7 times the 50-day average.
  5. The pivot is the highest high since the last pullback's swing high.
  6. Breakout: a close above the pivot, no more than 5% above it, on volume at least 1.5 times the pre-registered
     average.
  7. The Nifty is above its 200-day average.
- **Exit.** The stop, a close below the 50-day average, or 60 sessions, whichever comes first. The stop is the last
  pullback low, capped at 8% below entry.
- **Variants (4).** VCP; flat base (at most 15% deep, 5-10 weeks long); bull flag (as defined in the chart-patterns
  brief); a close above the 20- to 60-day range high.
- **Matched comparison group.** On the same days, stocks that pass step 1 but have not broken out.
- **Before looking at any outcome,** count the design-period events. Fewer than 300 means "too little data".
- **Measures.** Yearly return against the Nifty, the share of names never bought, the stop-out rate, turnover, and
  the mean R-multiple.
- **Pass.** T2 or T3, as an entry-timing rule.
- **If it fails.** The analyst stops citing "pivot" or "VCP breakout" as a reason, and the SEPA skill's output gets
  a "not supported by our test" note.
- **Script.** `scripts/study_vcp.py`, with the detector in `indtrader/research/patterns.py`. About 10-30 minutes.

### H6. Fear-state veto audit, all desks (forward only; start logging now)
- **Why.** The crowd-emotion brief found that de-risking during fear cost the index about 4-5 points a year, and
  that the first panic day had no edge (unreviewed exploratory result, not reproducible from the repo). In its
  India run, staying out while India VIX was high also cut the worst fall from −38% to −29%, so the cost bought
  some safety; both have to be weighed. LLM agents
  have also been found too cautious in bull markets and too aggressive in bear markets (FINSABER, in
  `docs/research.md`).
- **Logging, from now on.** On every veto, shrink or crypto gate action, record:
  - the India VIX 1-year percentile, the US VIX/VIX3M ratio, crypto Fear & Greed and the crypto funding percentile;
  - the reason type: company news, filing, event, chart, fear/sentiment, untested house rule, or other.
- **Hypothesis.** Vetoes and shrinks issued in fear states lower the With LLM account's return compared with the
  Without LLM account. The fear states are: India VIX at or above its 1-year 80th percentile; US VIX/VIX3M at or
  above 0.95; crypto Fear & Greed below 25.
- **Measure.** The next-20-trading-day return of vetoed candidates minus that of taken candidates, by tag, with a
  Newey-West t. Only data logged after this plan is committed. Decide at 30 or more vetoes per tag and reason type.
- **Verdict, fixed now.**
  - Vetoed candidates do better than taken ones with t ≥ 2.0: write a hard rule that fear alone is never a valid
    veto reason. This restricts the LLM, which moves the account back toward its tested rules.
  - Any claim that fear vetoes add value needs t ≥ 3.0 (section 3).

### H7. India VIX as a brake
- **Variants (3), pre-registered.**
  - (a) The momentum book with and without "no new buys when India VIX ≥ its 1-year 80th percentile", 2010-2026, on
    the P0-A table. Does de-risking in fear cost our own picks as much as the crowd-emotion brief found it cost the
    index (about 4 points a year; unreviewed exploratory result)?
  - (b) One VIX-scaled rule for new-position size: does it cut drawdown without cutting return?
  - (c) The condor desk skips entries when VIX is in its bottom fifth (premium too thin) or top tenth (crash
    regime). One variant only, not a search over thresholds.
- **Pass.**
  - (a) and (b): T3, with the Sharpe ratio and maximum drawdown reported next to the return.
  - (c): the condor desk reaches at least break-even after costs (at the 2026 STT rates) in the test period, with
    the deflated Sharpe counted over 49 trials.
- **Expectation.** (a) probably fails, which would itself be useful: it would confirm "do not de-risk on fear alone".

---

## 8. Priority 2

### H9. Head-and-shoulders and double tops as exit or avoid flags (stocks)
- **Definition.** Lo, Mamaysky & Wang 2000, with the shoulders and troughs within 1.5% of each other. Our added
  completion rule, the same as H9c: a close below the neckline within 10 sessions of the last turning point being
  confirmed.
- **Variants (4).** Two detection methods: a kernel smoother at 0.3 times the cross-validated bandwidth over a
  38-day window with a 3-day lag, and `swing_points` with k = 3. Two patterns: head-and-shoulders top and double
  top.
- **Measure.** Market-adjusted 20- and 60-day returns, against two comparison groups: the same stock on random
  dates, and stocks matched on their 12-1 month momentum decile.
- **Pass.** T1 with a negative sign. Then T3 as an exit rule on the momentum book (it can never be a short sale).
- **Evidence.** Savin, Weller & Zvingelis (2007, US, 1990-1999): shorting the pattern on its own lost money in the
  S&P 500. A hedged version (short the stock, long the index) earned 5-7% a year and broke even at 80-90bp one-way
  costs, partly because the pattern picks stocks with weak momentum. That needs short-selling, which an Indian
  retail delivery account cannot hold overnight. No India test exists.
- **Script.** `scripts/study_head_shoulders.py` (the crypto version is H9c).

### H10. The site's candles and support/resistance, exactly as coded (stocks)
- **Events.** Use `chart.py` rules exactly (`candle_patterns` with `trend_bars = 10`; `support_resistance` with k = 5
  and a 0.6 ATR tolerance), recomputed daily from confirmed swings only.
  - Bullish: a hammer or bullish engulfing candle within 0.5 ATR of support, with the close above the 50-day EMA.
  - Bearish: a shooting star or bearish engulfing candle within 0.5 ATR of resistance, on volume at least 2 times
    the 50-day average.
  - Measure 1, 5, 10 and 20 days. The rules must be vectorised: about 2 million per-day calls would be too slow.
- **Bounce test against random levels** (NSE stocks; the crypto version is H10c): the same hit, bounce and
  random-level rules as H10c.
- **Why the random comparison matters.** In one study of intraday currency data, arbitrary levels "held" 56% of the
  time, against 61% for published levels (Osler 2000). Our NSE rate is unknown until this test.
- **Pass.**
  - Candles: T1 (failure expected).
  - Levels stay as a stop-placement aid only if their bounce rate is above the 95th percentile of the random levels'
    rates.
  - If not, the site labels the levels "no better than random".
- **Script.** `scripts/study_candles_levels.py`. A pilot can run now on `data/futstk`, 2023-2026.

### H11. The range-breakout family, as a calibration
- **What.** The Sullivan-Timmermann-White rule family: 50-, 150- and 200-day breaks, a 1% band, and a 10-day hold.
  - Nifty: Yahoo `^NSEI` from 2007, or `data/fo` futures closes.
  - Stocks: the P0-A table.
- **Correction.** Apply White's Reality Check, Hansen's SPA test or Romano-Wolf (standard corrections for testing
  many rules at once) across **all** variants, and report how many "work" by chance.
- **Purpose.** To measure how many fake winners a settings sweep produces on our data. No adoption is expected.
- **Ledger.** Log these runs as "calibration" in `trials.csv`. They count toward the trial total only if one of them
  is ever proposed for adoption.

### H12. Stops
- **Variants.**
  - (a) No stop, 2×ATR and 4×ATR on the slow book (Nifty 200; S&P 100 with a survivorship caveat).
  - (b) Stops within 0.2 ATR beyond a major round number or support, against all other stops: the gap-through rate
    and slippage, from the table and from forward paper fills.
  - (c) A trendline-break exit (pivot lows at least 10 bars apart; break = a close more than 0.5 ATR below the line)
    against the 4×ATR trailing stop.
- **Pass.** T3 for (a) and (c). (b) is descriptive. If stops near obvious levels slip more, move them further away
  and cut the share count so the rupee risk stays the same.

### H13. Sizing, loss limits and averaging down (safety rules)
- **Before running,** the owner pre-sets the acceptable cost of a safety rule, for example "up to 1 point of yearly
  return for a clearly lower drawdown". That number is the owner's choice, not a research result.
- **Variants.**
  - Bootstrap the backtest's closed-trade R-multiples at 0.5%, 1% and 2% risk per trade, including gap-through-stop
    days. Report the chance of a 20% and a 30% drawdown within 12 months.
  - A weekly loss limit of 4%, 5% or 6%.
  - A pause after 3 or after 4 stop-outs in a row.
  - Blocking add-on buys below the average cost. First count how often `plan_target` already does this in the paper
    ledgers and the backtest.
- **Reporting.** The deflated Sharpe over all variants, plus maximum drawdown and trade count.

### H14. Attention-spike filter
- **Definition** (the thresholds are illustrative; pre-register one set). On the day before entry, any of:
  - volume more than 3 times the pre-registered average;
  - an absolute one-day return in the top 5% of the universe, or above 5%;
  - a headline in the day's top news.
- **Measure.** The 20- and 60-day index-relative returns of screen candidates bought on attention days against other
  days, net of costs.
- **Pass.** T3, as a "shrink or wait 5 days" rule.
- **Evidence.** Barber & Odean 2008; Barber, Huang, Odean & Schwarz 2022 (US). No India test exists.
- **Note.** The analyst's "parabolic move" shrink (RSI above 80, or more than 25% above the 50-day EMA) is an
  untested house rule until this test or a pre-registered variant of it passes.

---

## 9. Priority 3

### H15. Delivery percentage
- **Variants (2).**
  - (a) A spike: delivery % at least 2 standard deviations above the stock's own previous 60 sessions, volume at
    least 2 times the 50-day average, and the close above the previous close. Measure 5 and 20 days.
  - (b) The 20-day average delivery % minus the stock's own 250-day average, in monthly deciles, measuring the next
    21 days and checking whether it adds anything beyond momentum and abnormal volume.
- **Rules.** Exclude BE and other trade-for-trade series (delivery is always 100% there) and days with corporate
  actions. Report results by sub-period, because settlement and margin rule changes shift what normal delivery looks
  like.
- **Pass.** T1. This would be new Indian evidence either way. Until then, a "price spike on very low delivery %"
  shrink is an untested house rule.

### H16. Indian sentiment gauges (exploratory: outcomes already seen)
- **Gauges.** Nifty put-call ratio on open interest (and its 5-day z-score), from `data/fo`; the FIIs' long share of
  index futures and its 5-day change; the clients' net long share; India VIX terciles.
- **Measure.** The Nifty 50 TRI over the next 20 and 60 sessions. Two-sided tests: 6 trials.
- **Status.** Exploratory on history. Only fresh data counts as a test.
- **Pass.**
  - T1 on fresh data.
  - T2 if a rule that cuts exposure when the crowd is greediest beats buy-and-hold Nifty after tax.
  - If it fails: drop PCR and FII commentary from the briefs.

### H17. Breadth as the regime brake
- **One comparison.** The current brake ("halve new buys when the Nifty is below its 200-day average") against "% of
  Nifty 200 stocks above their 200-day average below 40%". Use point-in-time members, 2008-2026.
- **Pass.** T3, with Sharpe and maximum drawdown reported.

### H18. Gaps with news against gaps without news
- **Gaps.** Opening gaps of at least 1%, or 0.5 ATR.
- **News.** Join with NSE board-meeting and results dates.
- **Measure.** Market-adjusted 1-, 5- and 20-day returns after Indian costs. Skip crypto (it trades 24/7, so it has
  no opening gaps).
- **Pass.** T1.

### H19. Round numbers (NSE and the Nifty)
- **Questions.** The same two as H19c: clustering just below major levels, and the move after a crossing against
  random offset levels.
- **Data.** NSE stocks from the P0-A table; the Nifty at multiples of 500 and 1,000, from `data/fo` futures closes.
  (BTC and ETH are H19c.)
- **Use.** Descriptive, to inform stop placement (H12).

### H20. Bulk deals after publication
- **Sample.** Nifty 200 stocks with a published bulk buy, 2015-2026, excluding known high-frequency and proprietary
  firms.
- **Measure.** From the next day's open, 5- and 20-day returns against the index. The same for sells.
- **Expectation.** Reversal (Rajvanshi, IIM Calcutta Working Paper No. 863). If confirmed, "bulk buy after a run-up" becomes a
  logged shrink reason.

### H21. Insider market purchases
- **Sample.** Open-market purchases by promoters or directors worth over ₹1 crore, entered at the next open after
  the disclosure time. Measure 20 and 60 days, 2016-2026. The same for clustered sales.
- **Data.** About 200 per-stock API calls at 1 per second. A query with no stock symbol returned empty in testing.
- **Pass.** T1. Insider buying adds nothing to the rules unless this passes.

### H22. Promoter pledges as a filter
- **Data.** History needs quarterly shareholding filings, or daily logging from now on.
- **Cut-off.** Pre-set before running, for example more than 25% of promoter holding pledged, or pledging rising
  this quarter. That number is a choice, not evidence.
- **Measure.** Drawdowns of past screen picks with and without the filter.
- **Pass.** T3.

### H23. High-volume premium, buy-only
- **Rule.** Each month, Nifty 200 stocks whose 5-day volume ÷ 50-day volume is in the top decile, with a 5-day
  return between −5% and +5%. Measure the next 21 days against the equal-weight Nifty 200, net of costs.
- **Also check** whether high-volume winners in the current screen underperform low-volume winners (Lee &
  Swaminathan 2000).
- **Pass.** T1. If it passes, use it at most as a ranking tie-breaker.

### H24. Max pain as an expiry forecast
- **Test.** For each weekly Nifty expiry, compute max pain (the strike where option buyers in total would lose the
  most) at the previous day's close. Is the settlement closer to max pain than to the previous day's futures price?
  Compare mean absolute errors. `data/fo` holds 358 Nifty expiries from Jan 2020 to 30 Oct 2026 (counted for this
  plan, outcomes not looked at).
- **Split by market structure, because the rules changed:**
  - up to 19 Nov 2024 (256 expiries);
  - 20 Nov 2024 to 28 Aug 2025 (41 expiries): SEBI's contract changes, with weekly expiries limited to one index per
    exchange; Nifty weeklies still expired on Thursday;
  - from 2 Sep 2025 (61 expiries to 30 Oct 2026): Nifty weekly expiry moved to Tuesday, after SEBI's circular of
    26 May 2025 limiting expiries to Tuesday or Thursday. The repo's own NSE files confirm the dates: Bank Nifty and
    Fin Nifty weeklies stop in Nov 2024, the last Thursday Nifty weekly is 28 Aug 2025 and the first Tuesday one is
    2 Sep 2025. When Tuesday is a holiday, expiry moves to the previous trading day (in `data/futstk`, the monthly
    contracts of 30 Mar 2026 and 23 Nov 2026 fall on a Monday). Check NSE's current schedule before running.
  - The middle period has only 41 expiries, so treat its result as descriptive.
- **Use.** Descriptive only.

### H25. Where the close sits in its 20-day range
- **Why.** This is the simple approximation of the chart-image neural network (Jiang, Kelly & Xiu 2023).
- **Rule.** A long-only top decile, rebalanced monthly, on the P0-A table: design up to 2018, test from 2019,
  against the Nifty 200 equal-weight, with Indian costs.
- **Pass.** T2. Expect costs to dominate.

### H26. Bulkowski's hindsight gap (teaching demonstration)
- **Test.** Measure one Bulkowski statistic on NSE data, the ascending triangle, in two ways: with his "ultimate
  high" exit, and with a fixed 20-day, market-adjusted, net-of-cost exit.
- **Purpose.** The gap between the two shows how much hindsight inflates published pattern statistics. It is not a
  candidate for adoption.

---

## 10. Ongoing forward monitors

These run continuously on the paper logs. They are not tests of new rules, so they do not add trials. The crypto
monitors M-C1 and M-C2 are in section 1.

| ID | What | Data | Verdict rule |
|---|---|---|---|
| M1 | Behaviour audit: PGR minus PLR (Odean's disposition measure: the share of gains sold minus the share of losses sold) for each book, trades per month, charges as a % of gross P&L, add-on buys below cost | `paper/*/trades.csv`, `equity.csv` | Monthly. Verdict only after at least 30 closed trades per book (`docs/live-trading.md`). |
| M2 | Owner override log and scorecard: every manual action with a written reason, scored against the bot's counterfactual after 20 trading days | `journal/overrides` (new) | After 10 overrides with negative net effect, only "halt entries" remains for the owner. |
| M3 | Shadow fills: record bid/ask at order time with the free Upstox Analytics token, re-price fills at the far side, compare 09:16 against 09:45 against the close, and count orders that would be rejected (price bands, no market orders) | New collector | Gate G5 (honest fills) needs at least 20 sessions. |
| M4 | Paper against backtest on the same dates | `indtrader backtest` over the paper window | Monthly. Paper must sit inside the backtest's 5-95% bootstrap band. |
| M5 | Track-record length and probabilistic Sharpe for each desk and each account, on returns above the realised T-bill return and above the Nifty 50 TRI, plus the information ratio | Paper equity curves | Shown on the site as "years still needed". |
| M6 | LLM reasons graded by type (news, filing, event, chart, fear/sentiment, untested house rule) against the Without LLM account | `signals/`, scorecard | A value claim needs t ≥ 3.0 and at least 30 cases per reason type, on data after the pre-registration commit. Chart-based and fear-based vetoes are graded apart from news-based ones. Shrinks that cite an untested house rule (delivery-% spike, parabolic move) are graded on their own, pending H15 and H14. |
| M7 | LLM recency and loss-chasing: regress ratings on the last 5-20 day return beyond the screen's inputs, and compare veto rates after losing weeks with veto rates after winning weeks | `signals/`, ledgers | Flag it if either shows t ≥ 2 (a warning, not a value claim). |

---

## 11. Scripts and modules to add (none exist yet)

- Crypto: `scripts/forecast_verdict.py`, `scripts/gate_audit.py`, `scripts/study_crypto_sentiment.py` (with
  `--arms`), `scripts/study_round_numbers.py`; `--crypto` options for `study_candles_levels.py` and
  `study_head_shoulders.py`; the two H8b arms as extra paper accounts in `indtrader/crypto.py`.
- `scripts/download_cm_bhavcopy.py`, `scripts/download_corp_actions.py`, `scripts/download_results_dates.py`
- `indtrader/research/panel.py`, `indtrader/research/eventstudy.py`, `indtrader/research/signals.py`,
  `indtrader/research/patterns.py`
- `research/prereg/*.json`, `research/trials.csv`
- `scripts/study_52wk_high.py`, `study_max_effect.py`, `study_pead.py`, `study_vcp.py`, `study_head_shoulders.py`,
  `study_candles_levels.py`, `study_delivery_spike.py`, `study_india_sentiment.py`, `momentum_factor_check.py`,
  `behaviour_audit.py`
- `validation.py` additions: `min_trl`, an excess-return Sharpe, the information ratio, PBO, the endpoint check
- `tests/test_research_panel.py`, `tests/test_eventstudy.py`
- Later: `indtrader gate <desk>` (see `docs/go-live-checklist.md`)

## 12. Order of work

1. **Crypto, now** (section 1): P0-B first, then H8a, H8b, H10c and H19c. M-C1 and M-C2 are already collecting.
2. **Stocks:** P0-A and P0-B take about 1-2 days of coding plus about 3 hours of background downloads. P0-C
   alongside.
3. Start H6 logging and the M1-M7 monitors immediately; they cost nothing.
4. H1, then H2, H3 and H4. Then H5 and H7. H9c once `patterns.py` exists.
5. P2, then P3, only if the owner judges them worth the extra trials.

Before any test runs, the owner should agree what a pass would change. Even a T2 pass means only more months of
paper trading against an index fund (`docs/live-trading.md`). It is not permission to trade real money.

## 13. Known gaps in the evidence behind this plan

- Several papers were cited from memory because the briefs' web-search budget ran out or publisher pages returned
  errors (listed in `docs/trading-knowledge.md`, section 10). They are marked "cited from memory" above.
- The crowd-emotion and go-live briefs' own calculations are not in the repo, so their figures cannot be reproduced
  yet (section 2, rule 6).
- Whether NSE's financial-results API paginates, and how far back it goes, is unknown.
- Official Nifty 200 membership history was not rebuilt. `liquid_top` (ranked by traded value) and the historical
  F&O list are both proxies, so run both.
- The right delisting return for India is unclear: some delistings are buybacks at a premium, others forced exits
  at a loss. That is why both 0% and −30% are run.
- US pattern tests here would carry survivorship bias. Rely instead on large published replications (Chen &
  Zimmermann's openassetpricing.com), unless the owner pays for data.
- Indian crypto-exchange fees, and whether the OKX and Binance funding series agree, were not checked.
- The TRI and T-bill histories have not yet been downloaded from this server.
- The 2026 STT rates come from two broker notices (Fyers, Zerodha) that quote NSE circular NSE/FATAX/73524; the
  circular's PDF could not be opened on 9 Nov 2026. The Nifty Tuesday expiry is confirmed by the repo's own NSE
  files (`data/fo`, `data/futstk`); the SEBI circular date (26 May 2025) comes from press coverage. Crypto tax was
  checked only against press coverage of Budget 2026.

## Sources checked for this version (9 Nov 2026)

- STT from 1 Apr 2026 (futures 0.02% to 0.05%; options sale 0.10% to 0.15% of premium; exercise 0.125% to 0.15%),
  under the Finance Act 2026: Fyers notice,
  https://fyers.in/notice-board/revision-in-securities-transaction-tax-stt-effective-april-01-2026/ ; Zerodha
  bulletin, https://zerodha.com/marketintel/bulletin/445377/revision-in-stt-securities-transaction-tax-from-1st-april-2026 ;
  both quote NSE circular NSE/FATAX/73524 of 31 Mar 2026,
  https://nsearchives.nseindia.com/content/circulars/FATAX73524.pdf (the PDF returned an error from this server).
- Nifty weekly expiry on Tuesday from 2 Sep 2025: confirmed in the repo's NSE bhavcopy files (`data/fo`: last
  Thursday weekly 28 Aug 2025, first Tuesday weekly 2 Sep 2025). Background: SEBI circular of 26 May 2025 limiting
  expiries to Tuesday or Thursday (press: Moneylife,
  https://moneylife.in/article/sebi-tightens-equity-derivatives-rules-asks-exchanges-to-pick-tuesday-or-thursday/77245.html );
  Angel One, https://www.angelone.in/news/market-updates/why-nifty-expiry-changed-to-tuesday ; Business Today,
  https://businesstoday.in/markets/stocks/story/nse-revises-expiry-dates-for-index-derivatives-contracts-from-august-29-481484-2025-06-23
- Budget 2026 kept the 30% crypto tax and 1% TDS: Whale Alert summary,
  https://whale-alert.io/stories/978301d668f6a4/India-retains-30-crypto-tax-and-1-TDS-in-Budget-2026-bars-deductions-adds-reporting-penalties-and-eases-TDS-criminal-liability-to-2-years
  (press coverage, not the Act's text).
- Osler (2000), Support for Resistance, FRBNY Economic Policy Review 6(2):
  https://www.newyorkfed.org/medialibrary/media/research/epr/00v06n2/0007osle.pdf
- Schmeling, Schrimpf & Todorov (April 2023), Crypto carry, BIS Working Paper 1087 ("a high crypto carry predicts
  future price crashes"): https://www.bis.org/publ/work1087.htm
- Nifty closes on 30 Oct and 6 Nov 2026 (23,053.1 and 25,030.3): Yahoo `^NSEI`, rechecked in this review.
- Lo, Mamaysky & Wang (2000), NBER WP 7613: https://www.nber.org/papers/w7613
- Savin, Weller & Zvingelis (2007), Journal of Financial Econometrics 5(2):
  https://ideas.repec.org/a/oup/jfinec/v5yi2p243-265.html
- Urquhart (2017), Economics Letters 159: https://ideas.repec.org/a/eee/ecolet/v159y2017icp145-148.html
- Osler (2003), Journal of Finance 58(5): https://econpapers.repec.org/RePEc:bla:jfinan:v:58:y:2003:i:5:p:1791-1819
- Repo: `indtrader/crypto.py`, `indtrader/crypto_learn.py`, `indtrader/costs.py`, `scripts/crypto_backtest.py`,
  `scripts/crypto_momentum_study.py`, `scripts/download_crypto_sentiment.py`, `indtrader/signals/chart.py`,
  `indtrader/validation.py`, `indtrader/options_backtest.py`, `journal/changes.md`, `journal/crypto_lessons.json`,
  `analyst/CRYPTO_PLAYBOOK.md`, `docs/crypto-desk.md`, `docs/crypto-backtest.md`, `docs/backtest-forensics.md`,
  `docs/oi-buildup.md`, and the data in `data/crypto`, `data/fo` and `data/futstk`.
