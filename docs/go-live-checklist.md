# Go-live checklist: the gate between paper and real money

*Status on 9 Nov 2026: **every desk fails this gate. All desks stay on paper.***

This document sets the conditions under which the owner *could* consider real money. Passing every item makes the
owner eligible to decide. It does not decide for them. Nothing here places or authorises any order. Real money is
the owner's decision alone, ideally after talking to a SEBI-registered investment adviser.

It replaces the weaker checklist in `docs/live-trading.md` (60 trading days and 30 closed trades), for the reasons in
section 2. The crypto desk comes first, because it is the current focus. Where a cut-off is a judgement call rather
than a research result, it says so. The test rules behind each line are in `docs/test-plan.md`.

**In short**
- No desk is ready for real money. The crypto desk is the best place to learn, not yet a place for money.
- The crypto trend rule's benefit is smaller falls, not more money. After Indian tax, just holding BTC did better.
- Proving an edge takes years of data or a very large edge. A few months of paper mostly catches bugs and cost
  surprises.
- Before any desk: an emergency fund, no high-interest debt, and the owner's own written plan for falls (section 3).

---

## Status today (9 Nov 2026)

| Desk | Beats the cheap alternative after costs and tax? | Statistical proof | Paper record | Safety plumbing | Verdict |
|---|---|---|---|---|---|
| **Crypto** (BTC + ETH 50-day trend) | **No.** 2023-26: +147% after Indian tax, against +240% for just holding BTC. That period is also in-sample for this rule. | **No.** Its daily return above holding BTC is indistinguishable from zero (see 1.2). | Started 9 Nov 2026. The first forecast is graded on 10 Nov 2026. | Runs on GitHub Actions. No exchange account, API key, TDS records or kill switch for real money. | **FAIL** |
| India stocks (momentum + SEPA) | **No evidence either way.** See the note below. | Sharpe 0.44-0.50 before subtracting cash returns. Even at that level, 95% confidence needs about 11-14 years of results, and the gate's t ≥ 3 about 36-46 years (section 2). | About 7 trading days, 0 closed trades | GTT stops, the split HALT and the loss stops are not built | **FAIL** |
| US stocks (S&P 100) | Not tested on a point-in-time universe | None | About 7 trading days, 1 closed trade | Same gaps | **FAIL** |
| Nifty options | **No.** 46 of 48 condor variants lost. Buying options lost 11-22% of the money staked. | Best deflated Sharpe 0.002 | Paper only, since 2 Nov 2026 | n/a | **FAIL**, and never live (rule R11) |

**Note on the India result.**
- The audited momentum variants trailed the Nifty by 0.8 to 2.6 points over 1 Jan 2024 to 6 Nov 2026
  (`docs/backtest-forensics.md`).
- But the Nifty rose 8.6% in the last week of that window, from 23,053.1 on 30 Oct to 25,030.3 on 6 Nov 2026 (Yahoo
  `^NSEI` closes, checked for this document). At the end of October, the as-published book was ahead
  (`docs/strategy.md`). So the sign of the gap depends on one week's end date.
- Both sides use the Nifty *price* index, which leaves out dividends. The gate asks for the total return index
  (TRI), which includes them.
- Honest reading: no evidence that the book beats the index, and no evidence that it trails. Test H1 in
  `docs/test-plan.md` reruns it against the TRI with many end dates.
- The audited yearly return of 4.2-4.8% is also below the latest 91-day Treasury bill yield (5.897%, rbi.org.in,
  read 9 Nov 2026; the page gives no auction date). Yields were higher in 2024, so cash probably earned more than
  that over the same dates. The realised T-bill return has not been computed yet.

Sources: `docs/crypto-desk.md`, `docs/backtest-forensics.md`, `docs/strategy.md`, `docs/options-backtest.md`,
`paper/*/equity.csv`, `paper/*/trades.csv`, `paper/crypto/learn/forecasts.csv`.

---

## Words used here

| Word | Meaning here |
|---|---|
| Paper trading | Trading with pretend money at real prices. |
| With LLM / Without LLM | Each desk runs the same rules in two paper accounts. In With LLM, the analyst (Claude) can veto, shrink or cut risk. Without LLM runs the rules alone. (The code calls them `main` and `control`; older docs say "LLM-reviewed" and "control" or "rules-only".) |
| Just hold BTC | The crypto desk's third account: BTC bought once and held. It is the benchmark. |
| Benchmark / cheap alternative | What the owner could do instead with no skill: hold an index fund, hold BTC, or keep cash. |
| Sharpe ratio | Yearly return above cash, divided by how much returns swing. Higher means smoother gains. |
| Information ratio (IR) | Yearly return above the benchmark, divided by how much that gap swings. This answers "does it beat the index fund?". |
| t-statistic (t) | How many standard errors an average is from zero. For one test, t = 2 happens by luck about 1 time in 22, and t = 3 about 1 time in 370. Many tries make lucky values common. |
| Newey-West t | A t-statistic corrected for overlapping or related observations. |
| Deflated Sharpe | The chance that a Sharpe ratio is real after allowing for every variant tried. We need 0.95 or more. |
| PBO | Probability of backtest overfitting: how often the best-looking variant in one half of the data falls below the median variant in the other half. We need 0.2 or less. |
| Pre-registration | Writing the rule and the pass and fail lines into a file and committing it to git before seeing any result. |
| In-sample | Data that was already looked at when the rule was chosen. A result on it flatters the rule. |
| Point-in-time universe | The list of stocks or coins as it really stood on each past date, including ones that later failed. |
| Walk-forward windows | The test period cut into 4 consecutive parts. A real effect should hold in at least 3 of them. |
| Bootstrap band | Reshuffle the backtest's own daily returns thousands of times; the 5-95% band is where the middle 90% of those runs end. A paper result outside it means paper and backtest disagree. |
| Shadow fills | Recording the real bid and ask at the moment of each paper order, to see what a real order would have paid. |
| Kill switch | A rule or button that stops new trading at once. |
| STT | Securities transaction tax, charged on share and F&O trades in India. |
| R | The amount risked on one trade: the distance from entry to stop, times the quantity. A trade that makes 2R made twice what it risked. |
| Drawdown | A fall from a previous peak. |
| Brier score | For a probability forecast: the squared gap between the stated chance and what happened. Always saying 50% scores 0.25. Lower is better. |
| TRI | Total return index: an index that includes dividends. |
| TDS | Tax deducted at source: the exchange keeps 1% of each crypto sale and pays it to the tax department. |
| GTT | Good-till-triggered order: a stop order held by the broker, which fires even if our bot is down. |
| DDPI | Demat Debit and Pledge Instruction: a limited permission that lets the broker take shares out of your demat account to settle your own sales. |
| FIU-IND | Financial Intelligence Unit-India. Crypto exchanges serving Indians must register with it as reporting entities under anti-money-laundering law. |
| bp | Basis point: 0.01%. |
| API, API key | The connection a program uses to send orders to a broker or exchange, and the password-like key that unlocks it. |
| TPIN, OTP | A PIN from the depository (CDSL) that approves a sale of your shares, and a one-time code sent to your phone. |
| Form 26AS / AIS | The tax department's yearly statements of tax already deducted or paid on your behalf. |
| FOMC, CPI | The US Federal Reserve's interest-rate meetings (8 a year) and the monthly US inflation release. Both move crypto prices. |
| T-bill | Treasury bill: a short loan to the government. Its yield is what plain cash can earn. |

---

## 1. The crypto gate (current focus)

Crypto trades 24 hours a day, 7 days a week, so it is the fastest place to learn. Learning fast is not the same as
proving an edge. This gate says what the crypto desk and its learning loop must show before any real money.

### 1.1 What is already built

- **The desk.** BTC and ETH on a 50-day trend rule. Each coin gets half the account while its daily close is above
  its 50-day average; otherwise that half sits in USDT (a dollar stablecoin). It rebalances daily at 00:10 UTC on
  GitHub Actions. Three paper accounts of 10,000 USDT: With LLM, Without LLM and Just hold BTC. The LLM gate can only
  cut exposure or exclude a coin, never add risk (`docs/crypto-desk.md`, `analyst/CRYPTO_PLAYBOOK.md`).
- **The learning loop** (`indtrader/crypto_learn.py`; "The learning loop" in `docs/crypto-desk.md`):
  - three forecast runs a day, at 05:05, 13:05 and 23:05 IST;
  - for BTC and ETH: the chance the price is higher 24 hours later, and an 80% price range; the 05:05 run also
    makes a 168-hour (7-day) call;
  - each call is stored next to a no-skill baseline made at the same moment (50% up, and a range from recent
    volatility);
  - every 2 hours, GitHub Actions grades the calls that are due: Brier score, range coverage, calibration, a
    Newey-West t against the baseline, and the same split by market-state tag;
  - lessons in `journal/crypto_lessons.json` get their status from the data: confirmed at 30 scored calls and
    |t| ≥ 2 in the claimed direction.
  - "Market" lessons (claims about the price itself) are now scored against the up-rate on the other calls of the
    same period, not against 50% (`crypto_learn.market_stats`). In a rising market most calls end "up" whatever
    the tag, so 50% was the wrong yardstick.

### 1.2 Where the crypto desk stands

- **Before tax**, the trend rule roughly matched holding BTC in 2023-26 (+384% against +350%) and cut the worst fall
  from −53% to −31% (`docs/crypto-desk.md`).
- **After Indian tax**, holding BTC wins: +240% against +147%. The trend rule sells often and pays 31.2% on every
  profitable sale, and its losing sales give no tax relief.
- **Rough check for this document.** BTC + ETH 50-day trend against holding BTC, daily close-to-close returns,
  0.15% cost per trade, from `data/crypto/BTC.csv` and `ETH.csv`. An independent rerun for this review gave the
  same figures, but it is not yet a repo script, so treat it as unreviewed:
  - 2023 to 8 Nov 2026: information ratio about −0.07, Newey-West t about −0.15;
  - 2020 to 8 Nov 2026: information ratio about 0.18, t about 0.54. At an IR of 0.18, reaching t ≥ 3 would take
    about 280 years, from (3/0.18)².
- **In plain words:** the rule's benefit is smaller falls, not more money. Holding less crypto also gives smaller
  falls, with no extra tax events. So a gate built on "beats holding BTC after tax" will very likely keep this desk on
  paper. That is the honest result, not a flaw in the gate.
- **The 2023-26 test period is in-sample for this rule.** The rule was picked after all variants were reported on
  it (`docs/test-plan.md`, section 1.0). Only data recorded after a pre-registration commit is a clean judge.

### 1.3 The crypto gate: every line must pass

The earliest the whole gate could pass is 9 Nov 2027, after 12 months of paper (CG5), or 12 months after the
pre-registration commit if that comes later (CG1 counts only data recorded after it). Realistically it is not in
sight, because CG2 needs t ≥ 3 and the rule shows no excess return over holding BTC.

**CG1. Beats Just hold BTC after Indian tax.**
- History (exploratory only, because 2023-26 is in-sample): with costs doubled and every decision one day late, the
  rule ends above Just hold BTC after tax, and in at least 3 of 4 walk-forward windows.
- Forward (the real judge): on paper data recorded after the pre-registration commit, over at least the 12 months of
  CG5, the Without LLM account's after-tax value ends above Just hold BTC's after-tax value.
- Tax treatment: 31.2% on each profitable sale, no relief for losses (section 12). Just hold BTC is taxed once, when
  it is finally sold. The 1% TDS cash drag is included (CG5).
- Today: **FAIL** (+147% against +240%).

**CG2. Not luck.**
- The rule's daily return above Just hold BTC has a Newey-West t ≥ 3.0. The bar is 3.0, not 2.0, because the rule was
  chosen from about 29 crypto variants (`docs/test-plan.md`, section 1.0).
- Deflated Sharpe ≥ 0.95, counting every crypto variant ever tried.
- Today: **FAIL** (t about −0.15 since 2023, rough check above).

**CG3. The learning-loop scorecard (forecasts).** The scorecard is a fast early warning. It can take the LLM's
role away early. It can never, on its own, approve real money.
- Verdicts are read only at checkpoints: day 90 (7 Feb 2027), day 180 (8 May 2027), then every 90 days.
- They use the daily-series method in `docs/test-plan.md` (test M-C1), not the live scorer's running t:
  - all LLM-minus-baseline Brier differences made on one UTC day are averaged (both coins, all runs) into one number;
  - the Newey-West t uses that daily series (lags 2 for 24-hour calls, 7 for 168-hour calls).
- Why not the live scorer's t: it treats BTC and ETH calls made in the same run as separate observations, and its
  lag window counts rows, not hours. In a quick simulation for this document (a forecaster with no skill, BTC and
  ETH moving together), that roughly doubled false "beats the baseline" readings: about 7% at t ≥ 2, against about
  4% with one observation per run.
- **What it must show before the LLM touches real money ("Skill shown"):**
  - 24-hour calls: daily-series t ≥ 3.0 against the 50% baseline;
  - and a Brier gain against a drift baseline (the share of "up" periods in the previous 365 days), so that skill
    is not just the market's trend;
  - and the same sign for BTC and for ETH separately;
  - range coverage between 70% and 90%;
  - no probability band with at least 30 days of calls where "said" and "happened" differ by more than 10 points.
- **What takes the LLM out:** daily-series t ≤ −2.0 ("worse than no skill"). Then the LLM has no role in any
  real-money crypto desk, and its calls go back to the baseline until the next checkpoint (test M-C1).
  Restricting the LLM is the cautious direction, so the lower bar is enough.
- **Lessons.** A confirmed lesson (30 calls, |t| ≥ 2) is for day-to-day learning only. About 19 tags, 2 horizons
  and 2 kinds of lesson give about 76 cells, so a few will "confirm" by luck. To matter for money, a lesson needs the
  stricter bar of test M-C1: at least 30 distinct days with the tag on, at least 3 separate episodes, t ≥ 3.0, and
  the same sign in each half of the data and for each coin. Any trading rule built from a lesson is a new rule. It
  goes through CG1 and CG2 as a new trial.
- **How long "Skill shown" takes.** Our simulation (24-hour calls every 8 hours on two coins that move together,
  one observation per run, 400 paths each; assumptions are rough):

  | Forecaster | After 6 months | After 1 year | After 2 years |
  |---|---|---|---|
  | Right 55% of the time, leans 5 points from 50% | t ≥ 3 in 9% of paths | 23% | 65% |
  | Right 60% of the time, leans 10 points from 50% | 62% | 95% | 100% |
  | Right 55% of the time, leans 10 points from 50% | about 0% | about 0% | about 0% |

  Why the last row almost never passes: the average Brier gain per call is about
  lean × (2 × hit rate − 1) − lean². At a 55% hit rate, a 10-point lean only breaks even with the coin flip, and a
  bigger lean loses to it. So the lean must stay smaller than the edge, which is why the playbook keeps most calls
  between 0.40 and 0.60. Short-term crypto direction is close to a coin flip, so a 60% hit rate would be
  remarkable. Expect "no evidence yet" at the early checkpoints.

**CG4. The LLM gate itself (With LLM against Without LLM).** One bar, the same for every desk:
- t ≥ 3.0 on the daily return difference, at least 30 gate actions of each reason type (macro event, coin red flag,
  systemic stress), and only data recorded after the pre-registration commit (test M-C2).
- Otherwise any real money follows the Without LLM rules.
- If a reason type shows t ≤ −2.0 over 30 actions, that reason type is removed from the gate.
- Honest expectation: about 20 FOMC meetings and US CPI releases a year, so 30 macro actions take about 18 months.
  No verdict is likely before mid-2028 (`docs/test-plan.md`).

**CG5. Paper matches plan, at real Indian prices.**
- At least 12 months of paper trading on the live code. The earliest date is 9 Nov 2027.
- The rule exits a coin about 19 times a year (BTC 10.4, ETH 8.6 a year in 2023-26; count for this document from
  `data/crypto`), so 12 months gives about 19 round trips. That is enough to check fills and costs, not to prove an
  edge (CG2 does that).
- The paper return sits inside the 5-95% bootstrap band of the backtest run on the same dates.
- Realised turnover and costs are no more than 1.25 times the model's.
- **Shadow fills:** on at least 20 rebalance days, record the real bid and ask on the chosen FIU-registered Indian
  exchange, in rupees, with its fees, at each paper order time. Price the fills at the far side. The desk must still
  pass CG1 at those prices. Today the desk prices from Binance, which is not what an Indian account would pay.
- **TDS cash drag is modelled.** Each exit sells about half the account, so 1% TDS withholds roughly 9-10% of the
  account's value a year (19 exits × half the account × 1%). It counts toward the year's tax, or comes back as a
  refund, only when the tax return is processed. In a flat or losing year, that cash is out of the strategy for
  many months. The backtests ignore it today.
- **Rupees, not USDT, for the cash half.** Buying a coin back with USDT is itself a crypto sale (of the USDT). For
  crypto-for-crypto trades on an exchange, CBDT Circular 13/2022 has the exchange deduct 1% on both legs (as
  summarised by tax sites; not read in the original). Holding the cash half in USDT could therefore roughly double
  the drag. Model the exchange's real pairs and confirm with a chartered accountant.

**CG6. Crypto operations.**
- **Exchange.** Registered with FIU-IND (section 12). Registration is an anti-money-laundering filing, not a licence
  and not a safety guarantee.
- **Custody.** Only the pilot amount ever sits on the exchange. Plan for a freeze: WazirX lost about $230-235 million
  in a hack in July 2024, froze withdrawals and reopened only in October 2025 after a Singapore court approved a
  restructuring (news reports).
- **API key:** trade-only, withdrawals switched off, whitelisted to one fixed IP address, used by this desk only,
  stored only in environment variables, and replaced at once if it may have leaked (section 9).
- **Not on GitHub Actions for real money.** GitHub says scheduled runs "can be delayed during periods of high
  loads" and that "some queued jobs may be dropped". In a public repository, scheduled workflows are switched off
  after 60 days with no repository activity. Standard GitHub-hosted runners also have no fixed IP address to
  whitelist. A live desk needs its own server with a fixed IP, and alerts.
- **Kill switch** split into "freeze" (no new buys; sells still allowed) and "flatten". Exits are never blocked.
- **20 consecutive days** of the live code in dry-run against the real exchange, with zero duplicate, orphan or
  unreconciled orders.
- **Daily reconciliation** of exchange balances against the desk's books, with a phone alert on any break.
- **Tax records:** for each sale, the rupee value, cost, fee and TDS. TDS should appear in Form 26AS / AIS.
  Gains go in Schedule VDA of the return.

**CG7. The owner is ready.** Everything in section 3 is done, including the written plan for falls and the signed
owner rules (section 7).

### 1.4 If every line passes: a tiny crypto start

Only after CG1-CG7 all pass, and only if the owner decides to.

- **Pilot cap fixed in advance: at most ₹25,000.** This is a judgement call. Size it as if it could go to zero
  (an exchange failure), not as if the worst case were the backtest's −31%.
- **Two calendar steps, not a reward for results:** ₹10,000 first; the remaining ₹15,000 after 4 weeks, only if the
  plumbing is clean (no reconciliation breaks, TDS recorded correctly, fills inside the shadow-fill band), and
  whatever the profit or loss.
- **The Without LLM rules**, unless CG4 has passed.
- **Paper keeps running** on the same signals, so live and paper can be compared every week.
- **Stop rules.** Any one sends the desk back to paper. Restarting needs a written post-mortem and a fresh pass of
  CG5 and CG6.
  - A 25% fall from the live account's peak: no new buys, and an owner review.
  - A 35% fall: exit to cash and end the pilot. (Judgement calls: crypto swings about three times as much as the
    stock desks, and the rule's worst fall in 2023-26 was −31%. Replace both with the crypto backtest's own 1-year
    drawdown percentiles once they are computed; no test in `docs/test-plan.md` does this yet.)
  - Live trails paper by more than 1.5 points over any 3 months, counting TDS withheld as cash.
  - Realised costs above 1.25 times the model over any 3 months.
  - Any duplicate or orphan order, reconciliation break, or manual action outside the written rules.
  - The exchange freezes withdrawals or loses its FIU-IND registration: stop, and withdraw if possible.
- **No increase before the 24-month verdict.** At 24 months: if the live desk trails Just hold BTC after tax, it
  stops. It may grow only if CG2 holds on forward data and live results stay inside the backtest band, and only up to
  an absolute rupee cap the owner writes down in advance.

Whether to own any crypto at all, outside this desk, is a personal-finance decision (section 3). This desk has not
earned it. BTC has fallen 77% (2020-26) and 53% (2023-26) from a peak (`docs/crypto-backtest.md`).

---

## 2. Why a few months of paper cannot prove skill

**Years needed to be 95% sure the true Sharpe ratio is above zero** (daily data, normal returns; Bailey & López de
Prado 2012; formula: years ≈ (1.645 / Sharpe)²). The right-hand column uses the gate's stricter bar for anything
tuned or new, t ≥ 3, from years ≈ (3 / Sharpe)² (Harvey, Liu & Zhu 2016).

| Sharpe ratio | Years for 95% one-sided | Years for t ≥ 3 (the gate's bar) |
|---|---|---|
| 0.3 | 30.1 | 100 |
| 0.5 | 10.8 | 36 |
| 0.7 | 5.5 | 18 |
| 1.0 | 2.7 | 9 |
| 1.5 | 1.2 | 4 |
| 2.0 | 0.7 | 2.25 |

Negative skew and fat tails make these longer.

**The real question is the information ratio, not the Sharpe ratio.** The owner wants to know whether a desk beats an
index fund (or holding BTC). That depends on the return *above the benchmark*. Active strategies usually have
information ratios of 0.2-0.4 against their index (the skeptic review's estimate), which takes far longer:

| Information ratio | Years for 95% one-sided, (1.645/IR)² | Years for t ≥ 3, (3/IR)² |
|---|---|---|
| 0.2 | about 68 | about 225 |
| 0.3 | about 30 | about 100 |
| 0.5 | about 11 | about 36 |
| 1.0 | about 2.7 | about 9 |

**One year cannot tell skill from luck.** In a simulation (15% yearly volatility), a strategy with a Sharpe of 0.5 is
up after 12 months in 69% of paths. A strategy with no edge is up in 50% (research brief 5).

**How many trades prove an edge per trade.** Formula: trades needed ≈ (z × σ / edge)², where σ is how much one trade's
result swings, in R. Here σ = 1.7R, the swing of a strategy that wins 40% of the time at +2.5R and loses 1R
otherwise. Replace it with the backtest's own closed-trade σ when test H13 bootstraps the closed trades.
z = 1.645 for 95% one-sided, 3 for the gate's bar.

| Edge per trade | Trades for 95% one-sided | Trades for t ≥ 3 (the gate's bar) |
|---|---|---|
| +0.40R (very large) | about 49 | about 163 |
| +0.22R | about 162 | about 537 |
| +0.12R | about 543 | about 1,806 |
| +0.05R (realistic if any) | about 3,130 | about 10,400 |

So 30 trades can only show an edge of about 0.5R per trade at 95%, and about 0.9R at t ≥ 3. The old checklist's 30
trades proves almost nothing.

**Backtests shrink when traded live.**
- Harvey & Liu (2015) show the right discount is not a flat half. It depends on the Sharpe ratio and on how many
  variants were tried. For Sharpe ratios below about 0.4, the discount is "almost always more than and sometimes much
  larger than 50%". Above 1.0 it is at most 25%. They call the flat 50% rule "a serious mistake". With Sharpe ratios
  of 0.44-0.50 and dozens of variants tried, plan for a discount of more than half.
- The average published anomaly is worth about 8bp a month after trading costs and the decline that follows
  publication (Chen & Velikov 2023: "a measly 8 bps per month").
- Anomaly returns are about 58% lower after publication (McLean & Pontiff 2016; the paper could not be opened for
  this review, so this figure is unverified).

**So:** proof of an edge has to come from a long, honest, point-in-time backtest, discounted for every variant tried.
Paper trading is for catching bugs, cost surprises and behaviour problems.

---

## 3. Your own readiness, before any desk

None of this is research about trading. It is the ground under it. It is general information, not personal advice.
A SEBI-registered investment adviser can give personal advice.

### 3.1 Money basics first

Common planning rules of thumb (not research results):
- **An emergency fund** that covers several months of expenses (6 months is a common rule of thumb), kept in safe,
  easy-to-reach places such as a savings account or liquid fund.
- **No high-interest debt.** Credit-card and personal-loan interest costs more than any desk could hope to earn.
  Pay it off first.
- **Health insurance, and term life insurance if anyone depends on your income.**
- **Money needed within about 5 years stays out of shares and crypto.**
- **Only then**, and only with money whose total loss would not change your life, consider any pilot.

### 3.2 Index funds are the fallback, and they are risky too

The repo's fallback, if no desk beats the index after tax, is an index fund. That is a comparison, not a
recommendation to buy one now. Index funds fall too:

| Fall | Nifty 50 price index (Yahoo `^NSEI` closes, computed for this document) |
|---|---|
| 8 Jan 2008 to 27 Oct 2008 | −59.9%. It got back to the January 2008 level only in November 2010. |
| 14 Jan 2020 to 23 Mar 2020 | −38.4% |
| 2 Jan 2026 to 8 Oct 2026 | −15.6% |

- The Nifty 50 TRI returned −7.09% in the year to 30 Sep 2026, and 6.05% a year over 3 years (Tata Nifty 50 ETF
  factsheet, 30 Sep 2026).
- BTC is far bumpier: −77% from its peak at worst in 2020-26, −53% in 2023-26 (`docs/crypto-backtest.md`), and a
  fall of at least 20% within every calendar year in the data, mid-2018 to 2026 (`data/crypto/BTC.csv` daily
  closes, computed for this document; the mildest year, 2023, fell exactly 20.0%).
- Costs are small but real. Direct plans of Nifty 50 index funds and ETFs charge from about 0.07% a year (Tata Nifty
  50 ETF, direct plan) to 0.24% (Franklin India NSE Nifty 50 Index Fund, direct plan base expense ratio), both as of
  30 Sep 2026. Tracking error, the gap between the fund and its index, ran 0.05-0.13% a year in the factsheets checked
  (Axis, Franklin, Tata). SEBI caps it at 2% for equity index funds and ETFs (May 2022 circular, from news reports;
  not read in the original).

### 3.3 Who to listen to, and scams to recognise

- **A SEBI-registered investment adviser (RIA)** is registered, must act in your interest, and can be checked at
  sebi.gov.in/intermediaries.html. A "finfluencer" usually is not registered. A SEBI circular of October 2024
  bars brokers, exchanges and other regulated firms from working with unregistered finfluencers who give advice
  or claim returns, and gave them three months to end existing ties (news report of 24 Oct 2024; the circular
  was not read).
- **Scam patterns** (SEBI press release 65/2026, 22 Oct 2026; NSE investor warnings, 2026):
  - invitation-only WhatsApp or Telegram groups giving "free" stock tips, often from overseas numbers;
  - members who post fake profits and praise for the "expert" (SEBI calls this astroturfing);
  - "our group was banned, join the new one" messages;
  - trading apps or platforms suggested inside such groups;
  - "guaranteed" or "assured" returns, which exchanges say are illegal in the stock market;
  - anyone asking for your login ID, password, TPIN or OTP.
- **Where to complain:** your broker first, then SEBI's complaint system SCORES (scores.sebi.gov.in). SEBI does not
  regulate crypto exchanges, so SCORES does not cover them. For online fraud: cybercrime.gov.in or helpline 1930.

### 3.4 Your written plan for falls

The bot's behaviour in a fall is written in code. The owner's behaviour needs writing too. Before any real money,
the owner writes and signs, in `journal/owner_plan.md`, what they will do at each level. Below is a starting
template only; the owner writes their own words.

| Fall from the peak | What it usually means | Example wording for "what I will do" | What I will not do |
|---|---|---|---|
| −10% | Normal. The Nifty fell 10% or more within the year in 15 of the 19 years 2008-2026. BTC closed 10% or more below its highest close of the past week on about 1 day in 12 (mid-2018 to 2026; about 1 in 30 since 2023). | Nothing. I read this plan once. | Check prices more often. Change any setting. |
| −20% | A real fall. The stock pilot's stop rule ends the pilot here (section 5); the crypto pilot stops at −35% (section 1.4). BTC fell at least 20% within every calendar year in the data (mid-2018 to 2026). | Wait 5 trading days before any decision. Re-read section 2. Write one line in the journal: "what changed apart from the price?" | Buy more to "average down". Raise risk to win it back. |
| −30% | A bad fall. 2008 and 2020 went further. | Check that my emergency fund and income are intact. Any change goes through the 5-day wait in rule R3. | Sell everything in one day because of the fall alone. Borrow. |

- The figures in the table come from Yahoo `^NSEI` closes and `data/crypto/BTC.csv`, computed for this document.
- Rehearse it: once a quarter, read the plan and the 2008 and 2020 rows above, and imagine the account at −30%.
- Paper losses do not train fear. In experiments, people became markedly more cautious as real stakes grew, but not
  as pretend stakes grew (Holt & Laury 2002; text not re-read for this review). Expect to feel worse than the paper
  desks suggest.

---

## 4. The gate for the stock and options desks

Every item must pass, for each desk. The criteria are written down before looking at results.

**G1. Beats the cheap alternative.**
- Test conditions: a point-in-time universe, costs doubled, every decision executed one day late.
- Required result: the after-tax return beats the alternative over the untouched test period, and in at least 3 of 4
  walk-forward windows, and the sign holds at every month-end end date from 30 Jun 2025 to 31 Oct 2026 (the endpoint
  check in `docs/test-plan.md`).
- The alternatives, after their own costs and tax:
  - India: the Nifty 50 TRI minus 0.10% a year for a direct-plan index fund's cost (section 3.2), taxed at 12.5%
    on long-term gains above ₹1.25 lakh a year when sold after more than 12 months;
  - US: an S&P 500 fund, with the tax and remittance costs in section 12;
  - options: cash.
- Whether a momentum index fund (for example a Nifty200 Momentum 30 fund) is the fairer benchmark for the momentum
  desk is an open question (section 15).

**G2. Not luck.**
- Deflated Sharpe ≥ 0.95, counting every variant ever tried.
- Newey-West t on the daily return above the benchmark:
  - **t ≥ 3.0 for the desk's actual rule set.** It is tuned (slow book, SEPA template, which is a chart-trend
    checklist, drawdown breaker, volatility filter), with variants logged in `journal/changes.md`. The same bar
    applies to anything new: chart-pattern rules, condor tweaks.
  - t ≥ 2.0 only for an untuned, pre-registered plain 12-1 momentum rule (a long-documented factor), over at least
    10 years. This is not a loophole for the desk's rules.
- PBO ≤ 0.2 wherever 8 or more variants exist.
- Every Sharpe ratio is measured on returns above the realised T-bill return.

**G3. Paper matches the plan.**
- At least 12 months (about 250 trading days) and at least 100 closed round trips. These check fills, costs and
  behaviour. They cannot prove an edge (section 2).
- The paper return sits inside the 5-95% bootstrap band of the backtest run on the same dates.
- Realised turnover and costs are no more than 1.25 times the model's.

**G4. The LLM.** One bar, as in CG4: the With LLM account needs t ≥ 3.0 on its benefit over Without LLM, at least 30
vetoes of each reason type, and only data recorded after the pre-registration commit. Otherwise any pilot uses the
Without LLM rules.

**G5. Honest fills.**
- At least 20 sessions of shadow fills, priced at the far side of the real bid and ask at order time (test M3).
- The desk still passes G1 at those prices.

**G6. Operations (section 8).**
- A broker-side GTT stop on every position, and DDPI or a working daily authorisation so that the stop can actually
  sell (section 9).
- HALT split into "freeze" and "flatten", with exits always allowed.
- A weekly 5% and a hard 20% loss stop in code.
- 20 consecutive sessions of the live code in dry-run or sandbox mode, with zero duplicate, orphan or unreconciled
  orders.
- A static-IP server registered at the broker, and a working daily login.
- Phone alerts.
- A written runbook for "bot down with positions open".
- A live config identical to the paper config.

**G7. Personal.** Section 3 done. The owner has signed the rules in section 7. Tax records are set up. No leverage and
no F&O.

**Exact cut-offs.** The statistics behind G1-G2 are strong. The exact numbers (0.95, 0.2, 1.25×, 100 trades,
12 months) are judgement calls taken from the research briefs and `docs/test-plan.md`.

---

## 5. Staged start for the stock desks

- **S0 Paper (now).** The desks stay here until G1-G7 all pass.
- **S1 Pilot.** Only if the owner decides to, with a rupee cap fixed in advance:
  - India: ₹1-2 lakh in delivery shares. Below about ₹1 lakh the strategy cannot buy expensive shares within its 10%
    slots, and the DP charge eats small gains (`docs/live-trading.md`).
  - US: at most $2,000.
  - Options: never.

  Risk at most 1% per trade and at most 8% of capital at risk across all open positions (section 6). The pilot runs
  with paper trading alongside, on the same signals.
- **S1 stop rules.** Any one sends the desk back to S0. Restarting needs a written post-mortem and a fresh pass of G5
  and G6.
  - A 15% fall from the peak: no new buys, and an owner review.
  - A 20% fall: exit to cash and end the pilot.
  - Live trails paper by more than 1.5 points over any 3 months.
  - Realised costs above 1.25 times the model over any 3 months.
  - Any duplicate or orphan order, missed stop, or reconciliation break.
  - Any manual action outside the written rules.

  The existing 3% daily loss switch already blocks new buys for the day. The proposed 5% weekly limit would block
  them for the week.
- **No increase before the 24-month verdict.** Section 2 shows that 6 or 12 good months cannot tell skill from luck.
  Doubling after a good half-year would reward luck.
- **12-month check (can only stop).** If the live desk trails the index fund after costs and tax, stop it. One year
  cannot prove skill, so this check can stop the desk but never prove it.
- **24-month verdict.** To keep going, the desk must still beat the benchmark after tax. To grow beyond the pilot:
  - the G2 backtest evidence still holds;
  - live results stay inside the backtest's band;
  - the bootstrap 95% interval of the after-tax excess return sits above zero;
  - and growth stops at an absolute rupee cap written down in advance, never more than 10-20% of the owner's
    investable money.

---

## 6. Position sizing

- **Risk per trade.** Size each trade so that hitting the stop loses a fixed share of capital:
  shares = (capital × risk%) / (entry − stop).
  - Pilot: **1%** per trade, with the same 10% position cap.
  - Paper stays at 2%, so the paper accounts remain comparable with their history (`config/india_paper.yaml`,
    `config/us_paper.yaml`; `analyst/PLAYBOOK.md` states the same 2%).
- **Total open risk** across all positions: at most 8%. Ten momentum stocks can fall together, so 10 positions at 2%
  each is really about 20% at risk if every stop is hit at once, and more if prices gap through the stops.
- **The crypto desk does not size by R.** It holds up to the whole account in BTC and ETH and exits on the 50-day
  average, not on a stop. Its pilot is sized in rupees (section 1.4).
- **Simulation.** 200 trades, 20,000 paths. Winners pay +2.5R and losers −1R. Trades are independent, which
  understates risk, because real stops tend to hit together. Research brief 5's script, rerun with a small-edge case
  for this document.

  **No desk has shown any positive edge, so the no-edge column is the relevant one.**

  | Risk per trade | No edge (28.6% winners): chance of a 20%+ / 50%+ fall | Small edge, +0.05R (30% winners): 20%+ / 50%+ | Large edge, +0.40R (40% winners): 20%+ / 50%+ |
  |---|---|---|---|
  | 2% | 98% / 25% | 97% / 15% | 47% / 0.05% |
  | 1% | 60% / 0.2% | 47% / 0.07% | 2% / 0 |
  | 0.5% | 7% / 0 | 4% / 0 | 0 / 0 |

  Losing streaks over 200 trades: with no edge (28.6% winners at +2.5R), the median longest streak is 13 losses in a
  row, and there is a 30% chance of 15 or more. With +0.05R it is 24%; with +0.40R, 4%.
- **Kelly betting (the maths of the growth-maximising bet size).** Use it only as a ceiling: at most a quarter of
  the Kelly fraction, computed from the lower 95% bound of the edge.
  - If that bound is zero or below, the allocation is zero.
  - Full Kelly gives a 1-in-2 chance of ever halving your money; half Kelly 1 in 8 (Thorp 2006).
  - Kelly is very sensitive to errors in the estimated edge, so bets "should be reduced" (MacLean, Thorp & Ziemba
    2010).
  - Our desks' estimated edge over their benchmark is zero or negative, so Kelly says: nothing beyond the benchmark.
- **Volatility targeting** (scaling exposure so the portfolio's swings stay near a target).
  - Not a return booster here: in our 2024-2026 test, a 15% target cut the return to +9.4% (`docs/audit.md`,
    `journal/changes.md`).
  - Wider evidence is mixed: Barroso & Santa-Clara 2015 and Moreira & Muir 2017 found gains; Cederburg et al. 2020
    found none in real time (none of the three re-read for this review).
  - At most, use it as a risk cap: smaller new buys when India VIX or the 20-day realised volatility is in its top
    tenth, alongside the existing 200-day regime filter.
- **The owner and the LLM can only scale size down**, never up.

---

## 7. Owner rules: binding the human the way the code binds the LLM

These are proposed rules for the owner to sign. No study tests this exact rulebook. Each rule guards against a
documented habit (psychology research brief): mechanical rules beat in-the-moment judgement (Grove et al. 2000;
Hoffman, Kahn & Li 2018); automatic stops beat reminders (Fischbacher, Hoffmann & Schudy 2017); losses push people
to take extra risk (Coval & Shumway 2005); people "learn" from lucky streaks (Anagol, Balasubramaniam & Ramadorai
2021; the summary page could not be opened for this review); checking too often makes it worse (Thaler, Tversky,
Kahneman & Schwartz 1997).

- **R1. One-way overrides.** The owner may only halt new entries, scale new-entry size between 0 and 100%, or close a
  position early. The owner may never add a trade or raise size; widen, lower or remove a stop; re-buy a stock during
  its stop cooldown; or edit risk settings during market hours.
- **R2. Logged and scored.**
  - Every manual action goes through a command that requires a written reason. It is logged in `journal/overrides`
    and scored against the bot after 20 trading days (test M2).
  - After 10 or more overrides with a negative net effect, only "halt entries" remains available.
  - Any action other than reducing risk waits 24 hours, except an emergency exit.
- **R3. Config freeze.** Any change that loosens risk (more capital, higher risk %, bigger positions, looser loss
  limits):
  - takes effect only after 5 trading days;
  - needs a dated `journal/changes.md` entry with backtest and paper evidence;
  - is never made within 10 trading days of a big win or loss.

  Apart from the pilot's own pre-set steps inside its cap (section 1.4), capital is added only on a calendar set
  in advance, never within 3 months of a new equity high, never after a loss, and never before the 24-month
  verdict (sections 1.4 and 5).
- **R4. Loss limits** as in section 8. Exits are never blocked.
- **R5. The panic button is "halt entries".** Every stock position has a GTT stop at the broker.
- **R6. No averaging down.** No add-on buy when the price is below the position's average cost, and no manual buying
  of losers. (The India paper desk has already added to falling positions, for example LAURUSLABS and FEDERALBNK in
  `paper/india/trades.csv`; test H13 covers it.)
- **R7. Stops only rise.** Already enforced in code (`apply_fill`; verified in `docs/audit.md`).
- **R8. Check less.** Weekly and monthly reports against the benchmark. No intraday profit-and-loss alerts, except
  kill-switch events.
- **R9. One-line journal.** Before any manual action, write: "What just happened (a loss? news? a tip?), and would I
  do this if I had no position?" The LLM reads the line and flags danger signs: acting right after a loss, a stock in
  the news, moving a stop, sizing up after a win, buying more of a loser. It can only warn, never approve.
- **R10. Pre-registered verdict** as in sections 1.4 and 5. If a desk trails its benchmark after costs and tax, the
  desk stops. The fallback is the benchmark (an index fund, or for crypto holding BTC). That fallback is risky too:
  falls of 15-60% have happened in the Nifty and over 75% in BTC (sections 1.4 and 3.2). It suits only money not needed for
  5 or more years, after an emergency fund and with no high-interest debt. This is not personal advice; the owner
  decides, ideally with a SEBI-registered adviser.
- **R11. No real money** in F&O, intraday trading or option buying.
- **R12. Only money the owner can afford to lose.** No top-ups to win back losses, no borrowing, no margin.
- **R13. The written plan for falls** (section 3.4) is signed before any real money and re-read every quarter.

---

## 8. Loss limits, kill switches and operations

**Already in place on the stock desks** (`indtrader/risk.py`, `indtrader/engine.py`, config):
- a 3% daily loss switch (blocks buys only);
- a 10% drawdown breaker (no new buys);
- a daily order cap of 30;
- stops only rise;
- a 20-day minimum hold and a 20-day re-entry cooldown on the paper desks.

**To build before any live money** (thresholds are judgement calls, to be costed in test H13):
1. **Split HALT.** "Freeze" blocks new orders while exits and broker GTT stops stay active; this is the default panic
   button. "Flatten" is for broker or API faults only. Today `indtrader halt` blocks every order, including
   stop-loss exits (`engine._send`).
2. **A GTT stop at the broker for every position** before a buy counts as done, with an alert if any position lacks
   one. Whether a missing GTT should also block new buys is for the owner to decide.
3. **A weekly loss of 5%** blocks new entries until the next week.
4. **Three stop-outs in a row** pause entries for 2 days.
5. **A 15% fall** means no new buys and an owner review. **A 20% fall** stops the desk; `resume` then needs a written
   post-mortem and 10 trading days. (Crypto: 25% and 35%, section 1.4.)
6. **`indtrader resume` refuses to run within 24 hours of a halt**, unless the halt was for a technical fault.
7. **An orders-per-second guard** in code (for example at most 2 per second), far below broker and SEBI limits.
8. **Phone alerts** on any rejection, missing GTT, or reconciliation break.
9. **None of these may ever block a stop or a sell.**

**Why it matters.** At Knight Capital, old code left on one of eight servers was switched back on. In about 45
minutes it sent about 4 million executions and lost more than $460 million. The SEC found that Knight lacked the
risk controls that would have stopped it (SEC 2013). SEBI calls the kill switch "the last level of defence
against any Algorithm malfunction" (SEBI circular, 4 Feb 2025).

**Operations checklist**
- Run the live bot on a server with a static IP registered at the broker (section 10).
- Automate nothing that bypasses the daily two-factor login.
- The Kite access token expires at 6 AM each day. NSE requires API sessions to be logged out daily.
- Use LIMIT orders only, with the existing 0.3% buffer, whatever a broker allows (section 10).
- Reconcile against the broker every day.
- Chaos drills in paper or dry-run mode: kill the process mid-order, expire the token, drop the network, duplicate
  a signal. Then check there are no duplicate or orphan orders (start from `tests/test_order_safety.py`). Two
  live-only duplicate-order bugs were already found and fixed (`docs/audit.md`).
- Run the live code path for 20 or more sessions in dry-run mode, or in OpenAlgo's analyzer mode (a sandbox with
  virtual capital).
- Generate the live config from the exact paper config, with a diff check that fails on any difference. Today
  `config/config.yaml` holds the old swing settings (a stop at 2×ATR, where ATR is the average daily price range;
  a 2.5R target; 20% positions; a 5-day cooldown), the variant that lost 7% in the backtest. The paper desks run
  the slow book from `config/india_paper.yaml`. `docs/operations.md` says ₹10 lakh while the India desk is ₹1 lakh.
- Keep a written runbook for "bot down with positions open".

---

## 9. Keys, DDPI and account security

**Broker API keys**
- Keys and secrets live only in environment variables or `.env`, never in git. Scan the git history for leaked keys
  before going live.
- One key per desk, with the smallest permissions available.
- Orders are accepted only from the registered static IP. At Zerodha: "effective 1 April 2026, you must have a static
  IP for API-based order placement"; up to two IPs; one change per calendar week. Market data, order book and
  positions still work from any IP (Zerodha support page). So a stolen key cannot place orders from another IP,
  unless the thief can also change the registered IP.
- If a key may have leaked: revoke it at once, generate a new one, and check the order book and holdings.
- Never share the trading login, password, TPIN or OTP with anyone, any app, or any "algo platform". NSE has warned
  about Telegram channels that ask for exactly these (NSE investor warnings, 2026).

**DDPI and power of attorney (POA)**
- SEBI introduced DDPI in 2022 to replace the broad POA that brokers used to hold. DDPI only lets the broker debit
  shares to settle your own sales, and for pledges and a few listed uses you ask for (broker explanations of the 2022
  SEBI circulars; circular text not read for this review). Never sign a broad POA.
- **Without DDPI, automatic stops may not work.** Each sale then needs CDSL TPIN and OTP authorisation. At Zerodha,
  sell GTT orders on an account without POA or DDPI must be pre-authorised with the TPIN; "the authorisations are
  valid for only one day", and must be redone each trading day after 7 AM (Zerodha support page). A GTT stop that
  fires without that authorisation can fail.
- **The trade-off is the owner's to make:**
  - with DDPI, broker-side stops work unattended, but anyone who gets into the trading login can sell holdings
    without an OTP;
  - without DDPI, every sale needs the owner's TPIN and OTP, so the bot's stops need a daily authorisation step.
  - Either way: strong unique passwords, two-factor login on a device only the owner uses, and no shared logins.

**Crypto exchange keys:** trade-only, withdrawals switched off, IP-whitelisted, plus a withdrawal-address whitelist and
two-factor login on the exchange account itself.

---

## 10. SEBI and broker rules (checked Nov 2026)

- **SEBI circular of 4 Feb 2025** (retail algorithmic trading):
  - brokers are responsible for algo orders;
  - every API algo order carries an exchange-issued identifier;
  - no open APIs: access only through a client-specific API key and a static IP whitelisted by the broker, with
    OAuth and two-factor login;
  - algos a retail investor writes for themselves need exchange registration only above a set orders-per-second
    threshold, and may be used only for self and family ("self, spouse, dependent children and dependent parents").
  - It was first due to apply from 1 Aug 2025. SEBI then postponed it, to 1 Oct 2025 and again by a circular of
    30 Sep 2025 (news and broker reports; those circulars were not read).
- **NSE implementation standards** (NSE/INVG/67858, 5 May 2025):
  - the threshold is 10 orders per second per exchange; below it, no registration is needed;
  - a static IP is mandatory for API access; a primary and a secondary IP may be registered, changed at most once a
    calendar week, and mapped to one client (family may share);
  - API sessions must be logged out every day.
- **Status.** In force since 1 April 2026 (Zerodha support page; Upstox community post of 31 Mar 2026; Fyers
  notice). No later relaxation was found as of 9 Nov 2026. The SEBI circulars that moved the start date were not
  retrieved. Check the chosen broker's current notice.
- **Market orders.** Upstox's post of 31 Mar 2026 says "Market Orders are no longer permitted", with market-price
  protection on by default. Its trading-API product page still lists market orders, so Upstox's own pages disagree.
  Our rule stays LIMIT-only, whatever any broker allows.
- **Broker APIs** (prices change; check before choosing):

  | Broker | Order API | Limits and notes |
  |---|---|---|
  | Zerodha Kite Connect | Personal plan free (orders, GTT, alerts). Data and streaming ₹500 a month. | 10 orders a second, 400 a minute, 5,000 a day; token expires 6 AM. Fits the existing `indtrader/brokers/zerodha.py`. |
  | Upstox | Trading and data APIs free; promotional ₹10 per order for API set-ups until 31 Dec 2026 | Static IP; see the market-order note above |
  | Dhan | Trading APIs free; data APIs extra (`docs/live-trading.md` lists ₹499 a month) | 10/s, 250/min, 1,000/hour, 7,000/day; token valid 24 hours; whitelisted IP fixed for 7 days |
  | Angel One SmartAPI | Pricing not verified | n/a |

  For market data, the free Upstox Analytics token avoids paying for data.

---

## 11. Nifty F&O today (paper only)

The options desk stays on paper for good (rule R11). These facts matter for honest paper results. Most come from
broker and news summaries of NSE and SEBI circulars, not from the circulars themselves.

- **Weekly expiry.** Since 20 Nov 2024, each exchange may offer weekly options on only one index (SEBI FY25-FY26
  study). On NSE that is the Nifty 50. Since September 2025 it expires on **Tuesday** (it was Thursday); SEBI now
  allows only Tuesday or Thursday, and BSE's Sensex expires on Thursday. If Tuesday is a holiday, expiry moves to the
  previous trading day.
- **Lot size.** The Nifty lot is **65** (it was 75) from the January 2026 contracts; the first weekly expiry at the
  new size was 6 Jan 2026 (NSE circular FAOP70616, via Upstox and Angel One notices). The repo already uses 65
  (`indtrader/options.py`). NSE revises lot sizes from time to time, so check before relying on it.
- **Contract size and margins** (SEBI measures from 20 Nov 2024 to April 2025, SEBI FY25-FY26 study):
  - minimum contract value raised to ₹15-20 lakh;
  - option buyers pay the premium upfront;
  - no calendar-spread margin benefit on expiry day;
  - an extra 2 percentage points of extreme-loss margin on short options on expiry day.
- **Position limits** are now monitored during the day, on a delta (futures-equivalent) basis, from 2025. The limits
  are set for large firms (for example ₹5,000 crore intraday net per entity), far above a retail account.
- **STT** (securities transaction tax) from 1 April 2026: futures 0.05% (was 0.02%); options sold 0.15% of the
  premium (was 0.1%); options exercised 0.15% (was 0.125%). Proposed in the Budget 2026-27 speech (para 140) and
  in force for trades from 1 April 2026 under the Finance Act 2026 (NSE circular NSE/FATAX/73524 of 31 Mar 2026,
  as summarised by brokers and the press; neither the circular's PDF nor the Act's text was read).
- **Expiry-day trading** fell back after these measures: options traded on their own expiry day were 70% of index
  option turnover in FY25 and 59% in FY26 (SEBI FY25-FY26 study).

---

## 12. Tax notes

Confirm all of this with a chartered accountant. The Income-tax Act 2025 replaced the 1961 Act from 1 April 2026
(Budget 2026-27 speech), so section numbers have changed. The rules below are as reported for the 2025 Act; where a
point comes from the 1961 Act and was not checked against the new one, it says so.

**Crypto (virtual digital assets)**
- **30% on each gain**, with no deduction except the cost of buying (Budget 2022-23 speech). Add 4% cess: 31.2%.
  Surcharge applies only above ₹50 lakh of total income. Whether the 15% surcharge cap for share gains also covers
  crypto is disputed between sources; ask a CA if it ever matters.
- **No relief for losses.** A crypto loss cannot be set off against any other income, including gains on other
  crypto, and cannot be carried forward. This is why the trend rule loses to holding BTC after tax.
- **1% TDS on each sale** above a small yearly threshold (₹10,000 in total, or ₹50,000 for "specified persons", which
  covers most individuals without business income). It was section 194S of the 1961 Act; from 1 April 2026 it sits in
  section 393 of the 2025 Act at the same 1% (tax firms' summaries, not the Act's text). Tax sites disagree on
  whether the 2025 Act kept the yearly thresholds, so plan as if every sale has 1% withheld. The TDS shows in
  Form 26AS / AIS and is credited against the year's tax. **The cash drag** for this desk is about 9-10% of the
  account a year, and about double that if the cash half sits in USDT (CG5).
- **No section 87A rebate** on special-rate income (Finance Act 2025 proviso, per tax firms; the start year is
  reported differently by different sources). Crypto gains and share gains are special-rate income.
- **Reporting:** gains go in Schedule VDA of the income-tax return.
- **Penalties in Budget 2026** (₹200 a day for not filing, ₹50,000 for inaccurate particulars, section 509 of the 2025
  Act) apply to **reporting entities such as exchanges** that file the statement of crypto transactions, not to the
  owner. The owner's duties are the 30% tax, the TDS records and Schedule VDA.
- **FIU-IND registration.** Crypto exchanges serving Indians, including offshore ones, must register with FIU-IND
  under the anti-money-laundering law (PMLA). FIU-IND does not publish an official list. Reported counts: 49 by
  March 2025 (45 Indian, 4 offshore; FIU-IND's 2024-25 report, via PTI) and 54 by 9 Mar 2026 (a government reply in
  Parliament, via a copy reproduced by an exchange; the official record was not read). On 9 Sep 2026 FIU-IND sent
  notices to 15 platforms and sought to block their apps and websites (news reports). Check an exchange's
  status with the exchange and in official notices before opening an account.
- **Custody and hacks.** Coins held at an exchange can be frozen or stolen (WazirX, July 2024; section 1.3, CG6).

**Indian shares (delivery)**
- Held up to 12 months: 20% short-term capital gains tax, since 23 July 2024. Held longer: 12.5% on long-term gains
  above ₹1.25 lakh a year (Budget 2024-25 speech). With 4% cess: 20.8% and 13%. Surcharge, above ₹50 lakh of income,
  is capped at 15% on these gains.
- No section 87A rebate on these gains (above).
- **Set-off and carry-forward** (1961 Act rules; confirm under the 2025 Act): short-term losses can be set off against
  short-term or long-term gains; long-term losses only against long-term gains. Unused losses carry forward for 8
  years, but only if the return is filed by its due date.
- A momentum book with a 20-day minimum hold realises most gains at 20% every year. An index fund held over a year
  pays 12.5% above the exemption. That gap is part of G1.
- **Capital gains or business income?** Frequent delivery trading may be treated as business income, depending on
  the facts. CBDT guidance (Circular 6/2016, as recalled in the brief; not re-read) lets taxpayers choose for shares
  held over 12 months and expects consistency. Ask a CA before the first trade, not after.
- **Return form and advance tax:** capital gains usually go on ITR-2; business income (including F&O) on ITR-3.
  Advance tax is due in instalments when the year's tax after TDS is ₹10,000 or more; capital gains can be paid in the
  instalments after they arise (1961 Act rules; form names and sections under the 2025 Act not checked).

**US shares held by an Indian resident**
- Treated as unlisted foreign shares: long-term only after 24 months; before that, taxed at slab rates (research
  brief 5's reading).
- TCS (tax collected at source, refundable against your tax) applies on money sent abroad under the Liberalised
  Remittance Scheme (LRS) above ₹10 lakh a year (Budget 2025-26).
- Schedule FA (the return's list of foreign assets) and US dividend withholding also apply.
- None of this has been modelled yet.

**F&O**
- Non-speculative business income at slab rates. No real money here in any case (R11).

**Every backtest and every performance note shows the after-tax line.**

---

## 13. Base rates the owner should keep in view

**India F&O, re-quoted from the SEBI FY25-FY26 study PDF (Aug 2026):**
- 87.7% of individual traders made net losses in FY26, against 90.9% in FY25 and 91.1% in FY24 (p.47).
- Before trading costs, 82.1% made losses in FY26. Costs alone pushed about 5.6 points more of traders into loss
  (p.47).
- The average loss **among loss-makers** was ₹1.47 lakh; the average profit among profit-makers was ₹1.22 lakh
  (p.5). The average loss **per individual trader**, counting everyone, was ₹1.17 lakh (p.5). These two figures
  measure different groups, which explains the briefs' different numbers.
- Options caused 92% of individual losses (p.6). Individuals lost about ₹3.85 lakh crore in total over FY22-FY26
  (p.47).
- The FY26 improvement came with about 18-20% fewer active traders (the report gives both figures). SEBI warns that a
  lower loss share "does not necessarily mean trading outcomes have genuinely improved" (p.47).
- 99% of the profits of foreign portfolio investors (FPIs) and proprietary traders (firms trading their own money)
  went to "algo entities", which SEBI defines as entities that placed
  **at least one** algorithmic order in the year (p.6, footnote 5). Our inference, untested: much of that profit
  likely comes from speed and intraday market-making, which an end-of-day bot cannot copy.

**Other evidence:**
- India intraday cash trading (SEBI study, FY23): 71% of individual traders lost money; 80% of those making more
  than 500 trades a year.
- US households, 1991-96: the most active fifth earned 11.4% a year against the market's 17.9% (Barber & Odean
  2000).
- Brazil: 97% of people who day-traded for more than 300 sessions lost money (Chague, De-Losso & Giovannetti, as
  cited by SEBI; the paper was not opened).

---

## 14. The `indtrader gate` command (proposed)

- `indtrader gate <desk>` prints each line (CG1-CG7 for crypto, G1-G7 for the others) as PASS or FAIL with its
  number. The site shows the same output. `indtrader gate crypto` comes first.
- The LLM analyst reads it daily but can never mark a line as passed. Only code can.
- Even when every line says PASS, going live is the owner's decision.

---

## 15. Open questions and unverified items

1. **Crypto: smaller falls as a reason.** Is the trend rule better than simply holding a smaller fixed amount of BTC
   with the same worst fall, after tax? Not tested. It needs its own pre-registration before it can count.
2. **Crypto: the rough IR, exit count and TDS-drag figures** in section 1 come from scratch scripts, not repo
   scripts. A second, independent scratch run for this review gave the same figures. Commit a script under
   `scripts/` before relying on them.
3. **Crypto: the live scorer's t-statistic** pools BTC and ETH rows and counts its lag window in rows (test P0-C
   lists it as a code check). Until it is fixed, use the daily-series method of test M-C1.
4. **Crypto: Indian exchange fees, spreads and INR conversion** are not measured, nor whether the exchange's BTC and
   ETH rupee pairs are liquid enough to avoid USDT (and its second TDS leg). They need the shadow fills in CG5.
5. **Crypto tax:** surcharge on crypto income, the 87A start year, and the 2025 Act's section numbers come from tax
   firms' summaries, not the Act.
6. **Benchmark for G1.** Nifty 50 TRI, or a momentum index fund? Not checked.
7. **Static IP.** Each broker's exact current wording. Check the chosen broker's notice.
8. **Angel One SmartAPI.** Pricing and terms not verified.
9. **Real slippage at 09:16.** Not measured; needs the bid/ask collector (test M3).
10. **Does the LLM add value?** Not yet testable on any desk: fewer than 30 actions of any reason type.
11. **Business-income treatment** of frequent delivery trades. Ask a chartered accountant.
12. **US desk after-tax modelling.** Not done (TCS, Schedule FA, 24-month rule, dividend withholding).
13. **G2 for momentum.** Cannot be evaluated until the 2008-2026 point-in-time backtest exists (test H1).
14. **F&O facts** (Tuesday expiry, lot size 65, position-limit rules) come from broker and news summaries of NSE and
    SEBI circulars.
15. **Not opened for this review:** McLean & Pontiff; Anagol et al. (VoxEU); Chague et al.; Holt & Laury; Barroso &
    Santa-Clara; Moreira & Muir; Cederburg et al.; the SEBI 2022 DDPI circulars; the SEBI 2022 passive-fund circular;
    the Finance Act 2026 text; NSE circular NSE/FATAX/73524; CBDT Circular 13/2022; the SEBI circulars that
    postponed the algo rules; the October 2024 finfluencer circular; the Parliament reply on FIU-IND counts.

---

## Sources

**Statistics and sizing**
- Bailey & López de Prado 2012, Sharpe Ratio Efficient Frontier: https://www.davidhbailey.com/dhbpapers/sharpe-frontier.pdf
- Bailey & López de Prado 2014, Deflated Sharpe Ratio: https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf
- Bailey, Borwein, López de Prado & Zhu, Probability of Backtest Overfitting: https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf
- Harvey, Liu & Zhu 2016: https://www.nber.org/system/files/working_papers/w20592/w20592.pdf
- Harvey & Liu 2015, Backtesting (pp. 12-13 on the nonlinear haircut): https://people.duke.edu/~charvey/Research/Published_Papers/P120_Backtesting.PDF
- McLean & Pontiff 2016 (not opened): https://doi.org/10.1111/jofi.12365
- Chen & Velikov: https://www.federalreserve.gov/econres/feds/zeroing-in-on-the-expected-returns-of-anomalies.htm
- Thorp 2006: https://web.williams.edu/Mathematics/sjmiller/public_html/341/handouts/Thorpe_KellyCriterion2007.pdf
- MacLean, Thorp & Ziemba 2010: https://www.stat.berkeley.edu/~aldous/157/Papers/Good_Bad_Kelly.pdf
- Barroso & Santa-Clara 2015: https://doi.org/10.1016/j.jfineco.2014.11.010
- Moreira & Muir 2017: https://doi.org/10.1111/jofi.12513
- Cederburg, O'Doherty, Wang & Yan 2020: https://doi.org/10.1016/j.jfineco.2020.04.015
- Own simulations for this document (drawdowns with a +0.05R case; forecast-skill timing; scorer false-positive
  rate; crypto IR, exit count): scratch scripts, not yet in the repo (open question 2).

**Behaviour**
- Grove et al. 2000: https://experts.umn.edu/en/publications/clinical-versus-mechanical-prediction-a-meta-analysis/
- Hoffman, Kahn & Li 2018: https://econpapers.repec.org/RePEc:oup:qjecon:v:133:y:2018:i:2:p:765-800.
- Fischbacher, Hoffmann & Schudy 2017: https://econpapers.repec.org/RePEc:oup:rfinst:v:30:y:2017:i:6:p:2110-2129.
- Coval & Shumway 2005: https://ideas.repec.org/a/bla/jfinan/v60y2005i1p1-34.html
- Anagol, Balasubramaniam & Ramadorai 2021 (not opened): https://cepr.org/voxeu/columns/learning-noise-evidence-indias-ipo-lotteries
- Thaler, Tversky, Kahneman & Schwartz 1997: https://econpapers.repec.org/RePEc:oup:qjecon:v:112:y:1997:i:2:p:647-661.
- Holt & Laury 2002 (not re-read): https://www.aeaweb.org/articles?id=10.1257/000282802762024700
- Barber & Odean 2000: https://faculty.haas.berkeley.edu/odean/papers%20current%20versions/individual_investor_performance_final.pdf
- Chague, De-Losso & Giovannetti (as cited by SEBI): https://econpapers.repec.org/RePEc:fgv:eesptd:525

**Regulators, exchanges and brokers**
- SEBI FY25-FY26 F&O study (Aug 2026), PDF: https://www.sebi.gov.in/sebi_data/attachdocs/aug-2026/1787233506209.pdf ;
  page: https://www.sebi.gov.in/reports-and-statistics/research/aug-2026/study-profitability-of-individual-traders-in-the-equity-derivatives-segment-fy25-fy26-_103835.html
- SEBI intraday study (Jul 2024): https://www.sebi.gov.in/reports-and-statistics/research/jul-2024/study-analysis-of-intraday-trading-by-individuals-in-equity-cash-segment_84946.html
- SEBI circular, 4 Feb 2025: https://www.sebi.gov.in/legal/circulars/feb-2025/safer-participation-of-retail-investors-in-algorithmic-trading_91614.html
- NSE/INVG/67858, 5 May 2025: https://nsearchives.nseindia.com/content/circulars/INVG67858.pdf
- SEBI press release 65/2026 (22 Oct 2026), WhatsApp stock-tip groups: https://www.sebi.gov.in/sebi_data/attachdocs/oct-2026/1792675550417.pdf
- SEBI registered intermediaries: https://www.sebi.gov.in/intermediaries.html ; SCORES: https://scores.sebi.gov.in
- SEC 2013, Knight Capital order: https://www.sec.gov/litigation/admin/2013/34-70694.pdf
- Zerodha, static IP: https://support.zerodha.com/category/trading-and-markets/general-kite/kite-api/articles/static-ip
- Zerodha, sell GTT without POA/DDPI: https://support.zerodha.com/category/trading-and-markets/kite-features/gtt/articles/why-was-my-sell-gtt-order-rejected
- Zerodha API: https://zerodha.com/products/api/ ; Kite docs: https://kite.trade/docs/connect/v3/user/ and https://kite.trade/docs/connect/v3/exceptions/
- Upstox, rules live (31 Mar 2026): https://community.upstox.com/t/important-update-regulatory-changes-for-api-and-algo-trading-are-now-live/14874 ; Upstox API: https://upstox.com/trading-api/
- Fyers notice: https://fyers.in/notice-board/new-sebi-framework-for-retail-algo-trading-from-april-01-2026/
- DhanHQ docs: https://dhanhq.co/docs/v2/authentication/ and https://dhanhq.co/docs/v2/
- Angel One SmartAPI (not verified): https://smartapi.angelbroking.com/
- Nifty lot size 65 (NSE FAOP70616): https://upstox.com/announcements/updates/important-update-changes-in-lot-size-of-derivative-contracts ;
  https://www.angelone.in/news/market-updates/nse-revises-lot-sizes-for-index-derivatives-from-december-2025-nifty-lot-size-to-reduce-to-65
- Nifty expiry moved to Tuesday: https://www.angelone.in/news/market-updates/why-nifty-expiry-changed-to-tuesday ;
  https://www.5paisa.com/news/nse-marks-historic-expiry-shift-as-tuesday-becomes-new-expiry-day
- Intraday position limits: https://www.business-standard.com/amp/markets/news/sebi-stricter-intraday-position-limits-options-market-regulation-125090200971_1.html
- STT from 1 April 2026: https://www.businesstoday.in/markets/story/stt-hike-on-fo-trades-to-take-effect-from-april-1-trading-costs-to-rise-522428-2026-03-26 ;
  NSE/FATAX/73524 (not opened): https://nsearchives.nseindia.com/content/circulars/FATAX73524.pdf
- GitHub Actions schedule event: https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows
- RBI home page (91-day T-bill 5.897%): https://www.rbi.org.in/

**Tax**
- Union Budget speeches: 2022-23 https://www.indiabudget.gov.in/budget2022-23/doc/Budget_Speech.pdf ; 2024-25
  https://www.indiabudget.gov.in/doc/bspeech/bs2024_25.pdf ; 2025-26 https://www.indiabudget.gov.in/doc/bspeech/bs2025_26.pdf ;
  2026-27 https://www.indiabudget.gov.in/doc/budget_speech.pdf
- Crypto TDS under the 2025 Act and Budget 2026: https://www.patronaccounting.com/blog/crypto-vda-taxation-income-tax-act-2025-rules ;
  https://www.kucoin.com/news/flash/india-2026-budget-maintains-30-crypto-tax-and-1-tds-introduces-fines-for-non-compliance
- TDS under section 393(1) of the 2025 Act (tax site; thresholds disputed between sites):
  https://blog.tdsman.com/2026/08/tds-on-virtual-digital-assets-section-3931-194s/
- CBDT Circular 13/2022 (TDS on both legs of crypto-for-crypto trades), as summarised; not read in the original:
  https://studycafe.in/tds-on-crypto-transactions-cbdt-issues-clarifications-on-newly-introduced-section-194s-138945.html
- Schedule VDA: https://www.koinx.com/tax-guides/file-crypto-taxes-on-schedule-vda
- Section 87A and special-rate gains: https://taxguru.in/income-tax/section-87a-rebate-stcg-111a-tax-planning-fy-2025-26.html
- Surcharge and crypto: https://www.taxmann.com/post/blog/opinion-all-about-section-115bbh-taxation-of-virtual-digital-assets/
- FIU-IND registrations and notices (54 by 9 Mar 2026: a Parliament reply as reproduced in CoinSwitch's compendium,
  https://coinswitch.co/building-blocks/wp-content/uploads/2026/05/P-Public-Policy-Compendium-of-Que-and-Ans-Final-Version.pdf ,
  seen only through a search summary): https://www.outlookbusiness.com/news/49-crypto-currency-exchanges-registered-with-fiu-during-2024-25-fiscal-report ;
  https://www.outlookmoney.com/invest/fiu-ind-issues-notices-to-15-crypto-platforms-seeks-takedown-of-apps-urls ;
  https://cryptoslate.com/crypto-laws/india-pmla-vda-service-provider-aml-cft-regime/
- WazirX hack and restart: https://decrypt.co/345632/wazirx-to-resume-trading-and-withdrawals-more-than-a-year-after-234m-hack ;
  https://cointelegraph.com/news/wazirx-users-approve-new-restructuring-plan-after-hack

**Index funds**
- Tata Nifty 50 ETF factsheet, 30 Sep 2026: https://www.tatamutualfund.com/system/files/2026-10/TATA%20NIFTY%2050%20EXCHANGE%20TRADED%20FUND.pdf
- Franklin India NSE Nifty 50 Index Fund factsheet, 30 Sep 2026: https://www.franklintempletonindia.com/static/factsheet/Innerpage/Franklin-India-NSE-Nifty-50-Index-Fund.html
- Axis Nifty 50 Index Fund factsheet, Aug 2026: https://www.axismf.com/efactsheet/Aug-2026/Innerpage/NIFTY-50-INDEX-FUND.html
- SEBI 2% tracking-error cap (news report): https://moneylife.in/article/sebi-tracking-error-of-equity-etfs-and-index-funds-cannot-exceed-2-percentage/67279.html
- Finfluencer circular (news report): https://www.outlookbusiness.com/markets/sebi-directs-regulated-entities-to-sever-ties-with-finfluencers-in-3-months

**Repo:** `docs/crypto-desk.md`, `docs/crypto-backtest.md`, `docs/test-plan.md`, `docs/live-trading.md`,
`docs/backtest-forensics.md`, `docs/strategy.md`, `docs/options-backtest.md`, `docs/audit.md`,
`analyst/CRYPTO_PLAYBOOK.md`, `indtrader/crypto_learn.py`, `indtrader/options.py`, `journal/changes.md`,
`config/config.yaml`, `config/india_paper.yaml`, `indtrader/engine.py`, `indtrader/risk.py`, `paper/*/trades.csv`,
`data/crypto/`.
