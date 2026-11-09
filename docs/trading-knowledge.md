# Trading knowledge: charts, data, crowds, crypto and our own emotions

*A plain-English reference for the owner, merged on 9 Nov 2026 from six research briefs and a skeptic's review. It
reports what the evidence says. It is not advice to trade real money. Every desk stays on paper; real money is the
owner's decision, after the gate in `docs/go-live-checklist.md`. The tests named here (H1-H26, M1-M7, P0-A to P0-C)
are in `docs/test-plan.md`.*

---

## The short version

1. **Crypto is where we learn fastest, not where money is easiest.** It trades 24/7, so the crypto analyst makes
   about 180 small 24-hour forecasts a month, each graded against a no-skill guess. That teaches calibration
   quickly; it does not prove a trading edge quickly. Bitcoin swings about 3.5 times as much as the Nifty, and India
   taxes every crypto gain at 30% with no relief for losses (section 1).
2. **In crypto, our own test favours a plain trend rule, but holding wins after tax.** Holding BTC only while it is
   above its 50-day average roughly halved the worst fall in 2023-26. After India's 30% tax, simply holding BTC
   still came out ahead (`docs/crypto-desk.md`).
3. **Chart shapes mostly do not pay.** Head-and-shoulders, triangles, candles and the like show nothing, or a small
   tilt that costs and luck-correction remove. Of 5,806 chart rules tested on 49 country indices, India included,
   none survived that correction (Marshall, Cahan & Cahan 2010).
4. **Trend facts do better than shapes, but not much for a buy-only Indian account.** Past winners and stocks near
   their 52-week high tend to keep doing well. In India, the part a buy-only account can capture has been small and
   statistically no different from zero since 2008 (IIMA factor data). Our momentum book shows no evidence of beating
   the Nifty once survivorship, costs and timing are fixed; the gap is smaller than the noise (section 8).
5. **Most free market data describes the past.** FII flows, put-call ratios, "max pain", open-interest boards and
   delivery percentages have no solid tested edge. Their best use is as brakes.
6. **Fear gauges did not time the market.** Stepping out when fear was high cut long-run returns in India and the
   US. Holding BTC only in extreme fear made +31% from 2018, against +1,087% for holding throughout (exploratory).
7. **Human emotion is the best-documented finding of all.** People feel a loss about twice as strongly as an equal
   gain. They sell winners too early, hold losers too long and trade too much. In FY26, 87.7% of Indian individual
   F&O traders lost money after costs (SEBI). The best-supported defence is rules set while calm and carried out by
   a machine.
8. **A short record proves almost nothing.** With an information ratio of 0.3, showing with 95% confidence that a
   desk beats the index fund would take about 30 years of data (section 8).
9. **Index funds are the fallback, and they are risky too.** If nothing beats a Nifty index fund after costs and
   tax, the index fund is the honest alternative (`docs/live-trading.md`). The Nifty has fallen 60% (2008), 38%
   (2020) and about 16% this year. That suits only money not needed for five or more years, after an emergency fund
   and with no high-interest debt. This is not personal advice; the owner decides, ideally with a SEBI-registered
   adviser (section 9).

---

## How to read this guide

Each topic says what the idea is, what the evidence says (and whether it survives costs: after brokerage, taxes
and slippage, is any money left?), and ends with **What we do with it**.

**Strength ratings**
- **Strong**: large studies agree and others have repeated them.
- **Mixed**: the evidence is real, but it conflicts, has faded, or holds only in some markets.
- **Weak**: a few small or old studies, or results that could be luck.
- **None**: no independent test found; only books, vendors or forums.
- **Exploratory, not yet reproducible** (shortened to *exploratory*): quick runs made during the research on 9 Nov
  2026, on data whose outcomes were already seen. Their scripts are not yet in the repo. Leads, not findings.

**Words used throughout (each explained once)**
- *Backtest*: running a fixed rule over past prices. *In-sample / out-of-sample*: data used to choose a rule /
  data kept aside to judge it once.
- *Survivorship bias*: testing only on companies or coins that still exist, which flatters results. *Look-ahead
  bias*: accidentally using information not available on the day.
- *Data snooping*: trying many rules and keeping the best; some look good by luck. *Pre-registration*: committing
  the exact rule and pass mark to git before seeing any result.
- *t-statistic (t)*: a result divided by its own noise. About 2 is the classic "5% chance of luck" bar; Harvey,
  Liu & Zhu (2016) argue for 3, because so many ideas have been tried. *Newey-West t* is a version that allows for
  overlapping observations.
- *Sharpe ratio*: yearly return above cash divided by how much returns swing. 0.5 is decent; 1.0 is very good.
- *Information ratio (IR)*: the same idea measured against an index: return above the index divided by how much
  that gap swings. It answers "does this beat the index fund?"
- *TRI (total return index)*: an index that includes reinvested dividends. A *price index* (like Yahoo's ^NSEI)
  leaves them out.
- *Drawdown* (or worst fall): the drop from a peak to a later low. *Basis point (bp)*: 0.01%. *Round trip*: a buy
  plus a sell. *Slippage*: the gap between expected and actual fill. *Gross / net*: before / after costs.
- *ATR (average true range)*: how much a stock typically moves in a day.
- *Long-short*: buying one group and short-selling another. Indian retail delivery accounts cannot hold a short
  overnight, so many long-short results cannot be copied here.

**The two accounts.** Each desk runs the same rules in two accounts: **With LLM** (the analyst may veto or shrink a
trade) and **Without LLM** (no analyst). Older files call these `main`/"LLM-reviewed" and `control`/"rules-only".
The crypto desk also has **Just hold BTC** as its benchmark.

---

## 1. Crypto: the current focus

### 1.1 What is different about crypto
- **It never closes.** Prices move every hour, every day. Binance's daily candle closes at 00:00 UTC (05:30 IST);
  the desk rebalances at 00:10 UTC (`docs/crypto-desk.md`). Large moves happen while you sleep.
- **It swings much more.** Bitcoin's yearly volatility was 46% since 2023 (62% since mid-2018) and Ether's 62%
  (`data/crypto`); the Nifty's was 13% (Yahoo ^NSEI). A normal Bitcoin day moves about as much as a bad Nifty day.
- **Falls are deep and long.** Bitcoin fell 77% from Nov 2021 to Nov 2022 and regained its old high only in March
  2024. On 8 Nov 2026 it was 40% below its 6 Oct 2025 peak, and Ether 56% below its Aug 2025 peak (repo data).
- **Weekends** were calmer on average in our data (BTC's typical daily move, the standard deviation, was 2.3% on
  Saturdays and Sundays against 3.6% on weekdays, mid-2018 to Nov 2026), but not safe: the Oct 2025 crash (1.3)
  ran from Friday evening, US time, into Saturday.

**What we do with it.** Paper only, spot only, no leverage. The learning loop (1.9) is the main way the desk improves.

### 1.2 Funding rates (how crowded the leveraged bets are)
- **What it is.** A *perpetual future* is a crypto future that never expires. To keep its price near the spot
  price, longs pay shorts (or the reverse) a *funding rate*, usually every 8 hours. Positive funding means leveraged
  buyers are crowded. 0.01% per 8 hours is about 11% a year.
- **Evidence: mixed, and our own run disagrees with the common story.**
  - Crypto "carry" (futures priced above spot) averages above 10% a year and can reach about 60%. Small investors
    chasing leverage drive it, and high carry predicts crashes (Schmeling, Schrimpf & Todorov 2023, BIS WP 1087).
  - "Funding arbitrage" is not risk-free (He, Manela, Ross & von Wachter).
  - Exploratory, Binance BTC, 0.15% cost per side, before tax:

    | Rule | From Mar 2020 | Since Jan 2023 |
    |---|---|---|
    | 50-day trend (the desk's rule) | +1,783%, worst fall −58%, Sharpe 1.28 | +390%, −27%, 1.38 |
    | Same, but out when 3-day funding ≥ 0.03% per 8h | +1,183%, −61%, 1.26 | +369%, −26%, 1.39 |
    | Same, or in when funding is negative | +2,904%, −63%, 1.36 | +483%, −38%, 1.45 |

    Cutting when longs were crowded did not help. Adding when funding was negative raised returns but deepened the
    worst fall. One of about four variations tried, on seen data, before tax. Crowding is also rare: the 3-day
    average topped 0.03% per 8 hours on about 2% of days since 2023 (about 7% since Mar 2020).
- **What we do with it.** A fact in the fact sheet and a loop tag (`funding_high` above 0.03%, `funding_negative`
  below 0, from OKX's last nine rates). Never a reason to add leverage; the gate may only cut. H8b proposes "cut
  when crowded" and "add when negative" as shadow paper arms, judged after tax on fresh data only.

### 1.3 Liquidation cascades
- **What it is.** When a leveraged position's margin runs out, the exchange force-sells it. That pushes the price
  further and forces the next sale. A *cascade* is a chain of these.
- **Example.** On 10-11 Oct 2025, over $19 billion of positions were liquidated in about a day, mostly longs, after
  a US tariff announcement (CoinGlass figures, press coverage; CoinGlass said the true total was probably higher).
- **Evidence as a predictor: none.** It measures stress after the fact. The lesson: leverage turns a bad day into
  a total loss, and a stop-loss is not a guaranteed price; in a cascade the price jumps past it.
- **What we do with it.** No leverage on any crypto desk. The gate's "systemic stress" row (for example BTC −15% in
  24 hours) sets exposure to zero. The loop's `big_move_24h` tag (a move above 5%) checks whether the analyst
  chases big moves.

### 1.4 The Crypto Fear & Greed index
- **What it is.** alternative.me's 0-100 score (0 = extreme fear). Inputs: volatility 25%, momentum and volume 25%,
  social media 15%, surveys 15% (paused), Bitcoin's share of the crypto market 10%, Google searches 10%
  (alternative.me, checked 9 Nov 2026). Most of it is built from price.
- **Evidence: none as a trading signal.** All figures below are exploratory.
  - It correlates 0.79 with Bitcoin's distance from its 50-day average (0.70 for Ether): mostly the trend restated.
  - On the first day of each of 14 deep-fear episodes (index below 15, well inside "extreme fear", which starts
    below 25), Bitcoin fell 3.9% over the next 30 days on average, against +4.2% on all days.
  - Over all days, Bitcoin's next 30 days averaged +2.5% when the index was below 25 and +12.9% when above 75,
    against +4.2% overall. Neither gap is statistically clear (t −0.74 and 1.30).
  - Jul 2018 to Nov 2026, 0.15% per side: holding only when the index was below 25 made +31% (worst fall −54%,
    Sharpe 0.28); holding throughout +1,087% (−77%, 0.79); the 50-day trend +2,847% (−58%, 1.17).
  - Retail traders who act as contrarians in stocks chase momentum in crypto (Kogan et al. 2024).
- **What we do with it.** Shown as mood, labelled "mostly price trend; no tested edge". It sets the loop's tags
  (`fg_extreme_fear` below 25, `fg_fear` 25-44, `fg_neutral` 45-55, `fg_greed` 56-75, `fg_extreme_greed` above
  75). The seeded lessons "fear rebounds" and "greed pullbacks" start out against this history; the loop will
  settle them. H6 logs the index next to every veto.

### 1.5 Other crypto data
- **Open interest and long/short ratios: none.** No published evidence that they predict returns.
- **Coins moving into or out of exchanges: weak.** Intraday studies, paid data, labels revised later (Chi, Chu &
  Hao). Not used.
- **Stablecoin supply: weak.** It peaked at $187.4B on 2 Apr 2022 and shrank to $122.6B by Aug 2023 while Bitcoin
  fell: it followed the price (DefiLlama).
- **Round numbers.** Over 10% of Bitcoin prices end in .00, with no return pattern after (Urquhart 2017).
- **What we do with it.** Context at most. Never a reason to add exposure.

### 1.6 What our own crypto backtest found
- **Altcoin momentum overfits.** The best design-period variant made +2,274% in 2020-22, then +61% in the 2023-26
  test (−58% after Indian tax), against +350% for holding BTC (`docs/crypto-desk.md`).
- **BTC and ETH trend-following is the robust result.** In the 2023-26 test: BTC 50-day trend +390% (worst fall
  −27%, Sharpe 1.38); BTC + ETH trend +384% (−31%, 1.33); holding BTC +350% (−53%, 1.07).
- **After 31.2% tax, holding wins**: +240% for holding against +159% for BTC trend and +147% for BTC + ETH trend.
  The trend rule takes gains often, and losses give no tax relief.
- **Weak points.** One test period, mostly rising; about 24 variants tried across two studies (14 in
  `docs/crypto-backtest.md`, 10 in `scripts/crypto_momentum_study.py`); the TDS cash drag (1.7) not modelled.
- **What we do with it.** The desk trades the BTC + ETH trend rule, judged With LLM against Without LLM (does the
  gate add anything?) and both against Just hold BTC, after tax, out of sample.

### 1.7 Crypto tax in India
- **30% on every gain** (31.2% with the 4% cess; surcharge can add more at higher incomes). Nothing can be deducted
  except the cost of buying. A crypto loss cannot be set off against any other income or other crypto gains, and
  cannot be carried forward (Union Budget 2022-23 speech; Finance Act 2022).
- **Example.** Gain ₹50,000 on BTC and lose ₹50,000 on ETH in the same year: you made nothing, but owe about
  ₹15,600 (31.2% of ₹50,000).
- **1% TDS** (tax deducted at source) is withheld on sales above small yearly thresholds. It counts toward your tax
  and any excess is refunded after you file, but the cash waits until then. A rule that sells its holding about ten
  times a year (the trend rule's rough pace in our exploratory run) keeps about a tenth of that holding's value
  waiting as TDS credit. Our backtests ignore this (`docs/crypto-backtest.md`).
- **The rules carried over** into the Income-tax Act 2025 from 1 Apr 2026 with new section numbers (sources
  disagree on which), and Budget 2026 left the rates unchanged (coverage). Crypto goes in Schedule VDA.
- **Budget 2026 proposed penalties** (₹200 a day for not filing; ₹50,000 for wrong details) on whoever must file
  the "statement on transaction of crypto-assets" under s.509 of the Income-tax Act 2025, from 1 Apr 2026 (Budget
  2026-27 speech, Part B). Those filers are reporting entities such as exchanges, not individual traders. We did not
  check whether the final Finance Act 2026 kept it unchanged. Confirm with a chartered accountant (CA).
- **What we do with it.** Every crypto result is reported after 31.2% tax with no set-off. P0-C adds an after-tax
  line to every backtest, with the yearly TDS deducted reported next to it.

### 1.8 Exchange and custody risk
- **Exchanges fail and get hacked.** On 18 Jul 2024, about $235 million was stolen from Indian exchange WazirX,
  close to half of the roughly $500 million it had reported holding a month earlier. Users could not withdraw for
  over a year. A Singapore court approved a restructuring on 13 Oct 2025; the exchange restarted later that month
  and users got back about 85% of their claims, plus "recovery tokens" that may pay more later. The stolen coins
  themselves were not recovered (Wikipedia, coverage). FTX collapsed in Nov 2022; its token FTT is among the dead
  coins kept in `data/crypto`.
- **Registration is not protection.** Crypto service providers serving Indians must register with the Financial
  Intelligence Unit (FIU-IND) under anti-money-laundering law (since March 2023). FIU fined Binance ₹18.82 crore
  (June 2024) and sent notices to 25 offshore platforms (Oct 2025) (coverage). Registration checks money-laundering
  compliance; it does not guarantee your coins. As of Nov 2026 India has no dedicated crypto law (coverage;
  confirm), and crypto exchanges are not SEBI-regulated, so SEBI's complaint system does not cover them.
- **Self-custody** (holding your own keys) swaps exchange risk for the risk of losing the keys.
- **What we do with it.** The desk holds no keys and uses public data only. If the owner ever goes live: an
  FIU-registered exchange, holding there no more than he could lose entirely.

### 1.9 The learning loop: how the crypto desk learns
Built and running (`indtrader/crypto_learn.py`; `docs/crypto-desk.md`, "The learning loop";
`analyst/CRYPTO_PLAYBOOK.md`):
- **Forecasts.** At 05:05, 13:05 and 23:05 IST the analyst gives, for BTC and ETH, the probability that the price
  is higher in 24 hours (and in 7 days, at 05:05) and an 80% range, after reading a fact sheet: price changes,
  distance from the 50- and 200-day averages, RSI, volatility, Fear & Greed, OKX funding and market-state tags.
- **A no-skill baseline** is stored next to every call: 50% up, and a range of ±1.28 × daily volatility × √(days).
- **Grading every 2 hours** on GitHub Actions: the *Brier score* (squared error of the probability; 0.25 for a coin
  flip; lower is better), range coverage (target 80%), calibration (do 60% calls come true 60% of the time?), all
  also by tag. The analyst-minus-baseline gap gets a Newey-West t; under 30 calls it says "too few to tell".
- **Lessons** (`journal/crypto_lessons.json`). An `llm` lesson says the analyst is worse or better than the
  baseline under a tag; a `market` lesson says the price went up or down more often under a tag. The analyst writes
  the words; the data sets the status: confirmed at 30+ calls and |t| ≥ 2, retired when it turns. Six hypotheses
  are seeded: fear rebounds, greed pullbacks, crowded longs, downtrends persist, overconfidence in high volatility,
  chasing big moves.
- **A recent fix.** The `market` scorer now compares the up-rate under a tag with the up-rate on the other calls
  of the same period, not with 50% (`indtrader/crypto_learn.py`, `market_stats`). BTC was higher after 7 days in
  52.6% of 7-day windows since mid-2018 (repo data), so in a rising year "up more often than not" is true under
  almost any tag.

**How long will a lesson take? Rough arithmetic, not a test.**
- Calls 8 hours apart on a 24-hour horizon overlap, and BTC and ETH move together (daily correlation 0.83, repo
  data). Count about one independent outcome a day for 24-hour lessons and one a week for 7-day lessons.
- Telling a 60% up-rate from 50% at t ≈ 2 needs about 100 independent outcomes under the tag. Extreme fear was on
  about 13% of days since 2023 (exploratory): about two years for a 24-hour lesson, more than a decade for a 7-day
  one. A rare tag such as `funding_high` may get its 30 calls from two or three episodes.
- So 30 calls is a floor, not proof. `llm` lessons may settle sooner, because comparing each call with a baseline
  on the same outcome removes much of the noise.
- The scorer's t may also look stronger than it is. Its Newey-West correction assumes one call every 8 hours, but
  BTC and ETH calls are pooled, so 24-hour calls come about six a day (flagged for the main session in
  `docs/test-plan.md`, P0-C).
- A better Brier score is not profit. Money still has to survive costs and 31.2% tax.

**What we do with it.** Read the loop monthly. Backfill the seeded lessons on 2018-2026 history, labelled
exploratory (H8a). Keep the playbook's emotion checks (recency, anchoring, herding, overconfidence) on every
call; they are the biases of section 6.

---

## 2. Chart patterns

**How a computer finds a pattern.** Lo, Mamaysky & Wang (2000) smooth the price line, mark its turning points, and
define each pattern by exact rules on them. The repo's `chart.py` uses "swing points": a day higher than the k days
on each side. A swing point is only known k days later; using it earlier is look-ahead bias.

### 2.1 Head and shoulders (and the inverse)
- **What it is.** Three peaks, the middle one highest; a close below the "neckline" joining the two dips is read as
  a top. The inverse is the same shape at a bottom.
- **Evidence: mixed. It does not survive costs as a trade on its own.**
  - US stocks, 1962-1996: returns after the pattern differed from ordinary days (Lo, Mamaysky & Wang 2000): a
    statistical difference, not a profit test.
  - US, 1990-1999: shorting the pattern on its own lost money in the S&P 500. A hedged version (short the stock,
    long the index) earned 5-7% a year and broke even at 80-90bp one-way costs, partly because the pattern picks
    stocks with weak momentum. Raw small-cap versions broke even only below 6, 26 or 39.5bp for 20-, 40- and 60-day
    holds (Savin, Weller & Zvingelis 2007). It needs short-selling. No India test.
  - Volume jumps when the pattern appears, but acting on it does not help (Osler 1998; Bender, Osler & Simon 2013).
- **What we do with it.** No buy or sell signal. A completed top can be a bear-case line, only together with other
  red flags. Never upgrade on an inverse head-and-shoulders. Exit-flag test: H9.

### 2.2 Double tops and bottoms, triangles, wedges
- **Evidence: weak to none.** US 1962-1996: returns after double tops differed from normal (p = 0.021), after
  double bottoms not (p = 0.393); triangles were not significant (Lo, Mamaysky & Wang 2000). No profit test after
  costs anywhere. Wedges: no test at all.
- **What we do with it.** Description only. Never buy a "double bottom" in a stock that fails the trend template.

### 2.3 Flags, cup-and-handle and base breakouts (VCP)
- **What they are.** A *flag* is a sharp rise, then a short tight pause, then a breakout. A *cup and handle* is a
  U-shaped dip back to the old high, a small pullback, then a breakout. Minervini's *volatility contraction pattern
  (VCP)* is a base with ever-shallower pullbacks on drying volume, bought on a heavy-volume breakout above the
  "pivot" (the repo's SEPA skill).
- **Evidence: weak to none.**
  - Bull-flag "templates" worked on the NYSE Composite (Leigh et al. 2002) and Nasdaq and Taiwan indices (Wang &
    Chan 2007): indices, tuned on the same data. Flags in single stocks after costs: untested.
  - Cup and handle: no independent test. A large machine-learning study found the opposite tendency at weekly
    horizons: a close near the *low* of the recent range predicted higher returns (Jiang, Kelly & Xiu 2023).
  - VCP: no peer-reviewed test; circulating figures come from vendors with hidden methods.
- **What we do with it.** Entry timing only, never a source of names. H5 tests "buy at the next open" against "wait
  for the breakout" on the same screened stocks. The LLM must never judge a VCP by eye.

### 2.4 Range breakouts
- **What it is.** Buying a close above a recent range, such as a new 20- or 55-day high.
- **Evidence: mixed as statistics, no after costs.**
  - Worked on the Dow from 1897 to 1986 (Brock, Lakonishok & LeBaron 1992); gone after the mid-1980s once data
    snooping was controlled (Sullivan, Timmermann & White 1999; Bajgrowicz & Scaillet 2012).
  - 49 countries, 2001-2007, 5,806 rules: none survived the snooping adjustment. In India, 592 rules looked
    significant one by one; the best had an adjusted p-value of 0.794 and made 0.55% per trade before costs,
    about Indian delivery costs (Marshall, Cahan & Cahan 2010; the India figures are unverified, see section 10).
- **What we do with it.** No standalone use. H11 runs the family once to show how many "fake winners" a settings
  sweep produces. Long-horizon trend following (`docs/technical-analysis.md`) is a different, better-supported idea.

### 2.5 Gaps
- **What it is.** A day that opens well away from the last close. Folklore says gaps "get filled".
- **Evidence: weak.** US indices 1928-2018: prices tend to keep going the gap's way for a while; "gaps get filled"
  was contradicted (Plastun et al. 2020). US stocks: news moves drift, no-news moves reverse, mostly in small
  stocks (Chan 2003). Effects last about a day, when costs are highest. "Filled" and "exhaustion" are known only
  afterwards and must never be rule inputs.
- **What we do with it.** Context and risk only. H18 tests news gaps against no-news gaps.

### 2.6 Support, resistance and round numbers
- **What they are.** Price levels where a stock turned before (the repo groups swing points within 0.6 ATR into one
  level), and round prices like ₹1,000 or $100,000.
- **Evidence: mixed. They show where orders sit, not where returns come from.**
  - In one study of intraday currency data, 1996-98, arbitrary levels "held" 56% of the time, against 61% for
    levels published by forecasters (Osler 2000). That is not a rate for NSE daily charts; ours is unknown until H10.
  - Take-profit orders cluster at round numbers and stop-losses just beyond them, which explains both "price turns
    at the level" and "price speeds up through it" (Osler 2003). NSE prices and trade sizes cluster too (Mishra &
    Tripathy 2018). As trading rules, India included: no profit after the snooping correction (Marshall et al. 2010).
- **What we do with it.** Levels for stops and targets, not for picking. No stop just beyond an obvious level;
  paper sell targets just below round numbers (₹998, not ₹1,000). H10 tests our levels against random ones; H19
  studies round numbers. **On crypto, done:** our levels held *less* often than random levels in both 2018-22 and
  2023-26 (H10c), and round numbers showed nothing (H19c); see [crypto-studies.md](crypto-studies.md).

### 2.7 Candlesticks, trendlines and breakout volume
- **Candlesticks: weak.** Dow stocks 1992-2002, 28 signals, none predictive (Marshall, Young & Rose 2006); Japan
  1975-2004, none (Marshall, Young & Cahan 2008).
- **Trendlines: none.** Moving-average trend following has support (Park & Irwin 2007); drawing lines does not.
- **Breakout volume: mixed.** High volume was followed by higher returns over the next month in the US (Gervais,
  Kaniel & Mingelgrin 2001), but high-volume winners also reverse faster (Lee & Swaminathan 2000).
- **What we do with it.** Candles: confirmation at a level at most; H10 tests the repo's exact rules. No
  trendlines in analyst write-ups; the 4×ATR trailing stop is the mechanical version. Volume: a "don't chase a thin
  breakout" guard, after fixing the 50-day (`chart.py`) against 20-day (SEPA skill) mismatch (P0-C).

### 2.8 Machine-learned chart images
- **Evidence: strong in the US, failed in India.** A neural network trained on price-bar pictures reached a gross
  Sharpe of up to 7.2 in the US (1993-2019), about 4.0 after costs, long-short with about 700% monthly turnover,
  mostly by learning short-term reversal. In India the US-trained model scored −1.30, one trained on Indian data
  2.52, gross (Jiang, Kelly & Xiu 2023).
- **What we do with it.** Not tradable here. Log where each candidate's close sits in its 20-day range (H25).

### 2.9 Pattern "success rates" from books
- **Evidence: none, as odds.** Bulkowski's patterns were picked by eye, after the fact, mostly in bull markets, with
  hindsight exits and no costs. His own breakout failure rate rose from 11% in 1991 to 44% in 2007.
- **What we do with it.** Never quote a book or website success rate as a probability. H26 measures the hindsight gap.

---

## 3. Trend facts

### 3.1 Momentum
- **What it is.** Stocks that rose most over the past 6-12 months (skipping the latest month) tend to keep
  outperforming for a while. The desks' screen ranks on this.
- **Evidence: strong as a long-short premium, weak for a buy-only Indian account.** From the IIMA Indian factor
  file (`2025-12_FourFactors_and_Market_Returns_Monthly_SurvivorshipBiasAdjusted.csv` and the size-momentum file,
  Agarwalla, Jacob & Varma), before costs (exploratory: recomputed from the public file; script not yet in the repo):
  - Winners minus losers earned 1.09% a month over 1994-2025 (Newey-West t 2.78).
  - Big winners minus the market, the part a buy-only account can capture: 1.00% a month in 1994-2007 (t 2.65),
    0.26% in 2008-2018 (t 0.99), 0.21% in 2019-2025 (t 0.68). That is about 2.5-3% a year before costs and tax,
    statistically no different from zero.
  - Momentum crashes in sharp rebounds after falls (Daniel & Moskowitz 2016). India's worst months: Nov 2001
    (−27.6%), May 2009 (−25.0%), Apr 2000 (−21.1%); Dec 2008 was −20.3%.
  - Our book: no evidence of beating the Nifty once survivorship, costs and timing are fixed
    (`docs/backtest-forensics.md`; section 8 explains why the gap is within the noise). Its settings were chosen on
    Jan 2024-Oct 2026 data, so that period is in-sample; 2019-2023 is the clean out-of-sample period.
- **What we do with it.** Treat the momentum desk as a way to measure the LLM layer, not as a proven edge. H1 tests
  the exact rules on a survivorship-free universe (P0-A).

### 3.2 The 52-week high
- **What it is.** How close a stock is to its one-year high. People anchor on that high and are slow to bid above
  it, so stocks near it keep drifting up.
- **Evidence: mixed.** It explained much of momentum's profit in the US, 1963-2001 (George & Hwang 2004); the
  large replication finds 0.57% a month, t 2.02, below the t 3 bar (Hou, Xue & Zhang 2020). Significant in 10 of
  20 markets, mostly not after costs (Liu, Liu & Ma 2011). India: one unverified working paper.
- **What we do with it.** Already in the trend template. Never call a stock "too expensive" because it is near its
  high (that is the anchoring error itself), and do not count a new high twice. H2 tests whether it adds anything.

---

## 4. Data beyond price

Almost all of this is free from NSE's and Binance's archives. Most of it describes what already happened.

### 4.1 India VIX
- **What it is.** NSE's index of the Nifty volatility expected over 30 days, from option prices. VIX ÷ 16 ≈ the
  typical daily Nifty move in %.
- **Evidence: strong for how much the market will move, not which way.** It beat standard statistical models at
  forecasting Nifty volatility (Thenmozhi & Chandra 2013). It sat above the Nifty's later actual volatility 79% of
  the time in 2015-2026 (`docs/research.md`), yet selling that gap with iron condors failed: 46 of 48 variants lost
  (`docs/options-backtest.md`).
- **"Buy the fear" fails as timing.** On the first day of each of 20 episodes when VIX passed its 1-year 95th
  percentile, the day you would act, the Nifty's next 20 days averaged −0.03%, against +1.11% on all days
  (exploratory). Timing rules, 2010-2026, price indices, 0.1% per side (US 0.05%), exploratory:

  | Rule | Yearly return | Worst fall | Sharpe |
  |---|---|---|---|
  | Nifty buy and hold | 10.0% | −38% | 0.66 |
  | Out of the market while VIX ≥ its 1-year 80th percentile | 6.0% | −29% | 0.53 |
  | Same, from 2018 only: hold / step out | 10.7% / 7.9% | −38% / −29% | 0.69 / 0.71 |
  | US: S&P 500 buy and hold / hold only when VIX < VIX3M | 11.8% / 6.7% | −34% / −35% | 0.74 / 0.55 |

  Stepping out cut returns and, in India, the worst fall; the Sharpe was lower or about the same. In the US it was
  worse on all three.
- **What we do with it.** Log VIX on every journal entry. Use it only to size new positions down, if H7 supports it.
  "Fear is high" alone is not a veto reason (H6).

### 4.2 Breadth, put-call ratio and max pain
- **Breadth (stocks rising against falling): weak.** Sentiment-type measures move with returns but predict little
  (Brown & Cliff 2004). H17 tests it once as a replacement regime brake.
- **Put-call ratio: weak.** Nifty returns drive the ratio more than the reverse (Jena, Tiwari & Mitra 2019). It
  moved with the past 20-day return (correlation +0.41) and did not predict the next 5 or 20 days (exploratory).
- **Max pain** (the strike where option buyers collect least): **weak for the Nifty.** Pinning near strikes exists
  in US single stocks (Ni, Pearson & Poteshman 2005); an Indian practitioner test found closes rarely near max pain
  (Capitalmind 2014). Options traded on their own expiry day rose from 38% of index-option turnover in FY22 to 70%
  in FY25, and fell back to 59% in FY26 after SEBI limited weekly expiries to one index per exchange (SEBI FY25-FY26
  study, section 6.13). Nifty weekly options moved from Thursday to Tuesday expiry from 1 Sep 2025 (NSE circular
  NSE/FAOP/68747 of June 2025, via broker coverage; reports differ on its exact date).
- **What we do with it.** None is a reason to trade. Max pain is never a target; close short options before expiry
  day. H16, H17 and H24 test them.

### 4.3 Open-interest boards and participant positions
- **Stock-futures "build-up" board: none, and it loses.** The repo labelled 178,180 stock-days, Jan 2023 to Nov
  2026. Before costs the board earned about zero (−0.2bp a day). Trading it daily at about 6bp of costs turned that
  into about −43% over four years (`docs/oi-buildup.md`). Lesson: no edge, and daily turnover compounds costs. Its
  cost model predates the rise in futures STT to 0.05% from 1 Apr 2026 (section 7), so recent costs are understated.
- **FII / Pro / Client positions: none.** The FIIs' long share of index futures did not predict the Nifty over 5
  or 20 days, 2014-2026 (exploratory). SEBI's FY26 data: proprietary traders made about
  ₹44,000 crore gross and FPIs about ₹14,000 crore, 99% of it by entities that placed at least one algorithmic
  order in the year (SEBI's definition). Our inference, untested: much of it likely comes from speed and intraday
  market-making, which an end-of-day file cannot capture.
- **FII/DII cash flows: weak.** FIIs chase past returns (Batra 2003); predictive results used private data (Froot,
  O'Connell & Seasholes 2001).
- **What we do with it.** Context, labelled "untested". If ever used, only to shrink new longs.

### 4.4 Delivery %, volume, bulk deals and insiders
- **Delivery percentage: none as a predictor.** Every delivered share has a buyer and a seller, so high delivery
  does not mean buyers outnumber sellers. "High delivery means accumulation" has no published test.
- **Volume shocks: mixed** (2.7). A possible ranking tie-breaker if H23 passes.
- **Bulk and block deals: mixed, and chasing them loses.** NSE 2010-2019: for buy deals, prices rise from about 7
  days before, peak around the deal day and fall from day 2 after publication (Rajvanshi 2021).
- **Insider trades (SEBI PIT): mixed.** US "opportunistic" insider trades earned about 0.82% a month above normal,
  routine ones about zero (Cohen, Malloy & Pomorski 2012). No Indian test of the post-2015 rules.
- **What we do with it.** A spike on very low delivery is an untested house rule for shrinking, pending H15; high
  delivery is never a buy reason. A big bulk buy after a run-up is a reason to wait (H20). Clustered promoter
  selling is a reason to shrink; insider buying adds nothing unless H21 passes.

### 4.5 Promoter pledges, results and surveillance lists
- **Promoter pledges: mixed, the best of the Indian items.** Heavy pledging worsens volatility and firm value
  across 1,452 firms (Chauhan, Mishra & Spahr 2021) and predicts crash risk in BSE 500 firms, 2011-2020 (Kalia 2024).
- **Results and post-earnings drift: mixed.** US drift replicates (t 3.4-5.9; Hou, Xue & Zhang) but faded outside
  the tiniest stocks by 2006 (Martineau 2022). India: drift in 2002-2011 (Sehgal & Bijoy 2015), none in 2014-2018
  for 100 NSE firms (Gupta & Dhusia 2021).
- **ASM/GSM surveillance lists: weak but pointing the right way.** Returns fell after inclusion, 2018-2019 (Chari &
  Inamdar 2021). A listed stock has usually already had its run.
- **What we do with it.** Pledges: candidate hard filter (H22). Results: keep "no new buys within 3 days before
  results"; H4 tests what to do after. Surveillance lists: kept as a hard filter.

---

## 5. Crowd emotion and sentiment

- **CNN Fear & Greed and the AAII survey (US): weak.** CNN's index predicted returns statistically in 2011-2020,
  less so later, with no trading test (Farrell & O'Connor 2025); it repeats trend and volatility data. The AAII
  survey has little short-run power (Brown & Cliff 2004, 2005).
- **Baker-Wurgler sentiment: mixed.** After high sentiment, small, young, unprofitable stocks do worse (Baker &
  Wurgler 2006; in India, Mathur & Rastogi 2018). It tells which stocks suffer, not when to time the market.
- **Google searches: weak.** Profitable before costs, not after (Bijl et al. 2016); no next-day effect for Bitcoin
  (Urquhart 2018). **Twitter mood: none** out of sample (Lachanski & Pav 2017).
- **News read by an LLM: mixed, real but small and fading.** A daily long-short strategy built from GPT-4's reading
  of overnight headlines on 4,123 US stocks (Oct 2021-May 2024) earned 0.34% a day before costs. It needs shorting,
  was strongest in small stocks, lost money at 20bp round-trip costs, and its Sharpe fell from 6.54 to 1.22 by
  early 2024. Bad news mattered more than good (Lopez-Lira & Tang). Before a model's training cutoff, much apparent
  skill is memory (Glasserman & Lin).
- **The main lesson.** Most gauges are price in disguise, and their good-looking averages include days you only
  recognise in hindsight. Always test the first day of a signal, not the average day in a state.
- **What we do with it.** The LLM may only veto or shrink. A veto that cites specific negative company news has
  research support; one that cites general fear does not (H6, M6). In frothy periods, never loosen quality filters
  toward small, young or unprofitable companies.

---

## 6. Human emotions and biases

### 6.1 How emotions create market patterns
The same biases that cost traders money leave faint tracks in prices:
- **Loss aversion and the disposition effect** make people slow to sell losers and quick to sell winners, so good
  news gets into prices slowly. That is one explanation for momentum (3.1) and post-results drift (4.5).
- **Anchoring** on the 52-week high makes buyers hesitate there (3.2).
- **Attention** sends individuals into stocks that are in the news or had a huge day; those stocks then lag. The
  stocks Robinhood users bought most fell 4.7% over the next 20 days (Barber, Huang, Odean & Schwarz 2022).
- **Lottery preference** makes people overpay for a small chance of a huge win: cheap volatile stocks and
  out-of-the-money options (Kumar 2009; Bali, Cakici & Whitelaw 2011). The stock effect is weak in the large
  replication (−0.34% a month, t −1.14; Hou, Xue & Zhang), and Indian studies disagree on its direction.
- **Herding and fear** cluster stops at obvious levels (2.6) and feed liquidation cascades (1.3).
- **Overreaction**: big 3-year losers beat big winners over the next 3 years in old US data (De Bondt & Thaler
  1985); the replication puts it at the borderline (t −1.98). A fall alone does not make a stock cheap.

With realistic weighting, recent data and costs, most of these tracks are small or gone. Their real use here is
in rules for behaviour.

### 6.2 How emotions hurt traders
- **Loss aversion: strong.** People feel a loss about twice as strongly as an equal gain (Tversky & Kahneman 1992,
  about 2.25; meta-analysis: 1.955 from 607 estimates in 150 articles, Brown, Imai, Vieider & Camerer 2024).
  Professional traders show it too (Coval & Shumway 2005).
- **Disposition effect: strong.** US accounts sold 14.8% of available gains but only 9.8% of losses, and the
  winners sold beat the losers kept by 3.4 points over the next year (Odean 1998).
- **Overconfidence and overtrading: strong.** 66,465 US households earned 16.4% a year against 17.9% for the
  market; the most active 11.4% (Barber & Odean 2000). Our own swing book made 646 trades and paid ₹12,965 in
  charges for a −7.0% result (`docs/strategy.md`).
- **Revenge trading and "getting back to even": mixed.** Traders with morning losses took more risk in the
  afternoon (Coval & Shumway 2005). After losses, people prefer bets that might get them back to even (Thaler &
  Johnson 1990).
- **Sunk cost and averaging down: mixed.** Investors buy more of their losers (Odean 1998). Our strategy code can
  do it too: the India paper desk added to fallen positions (LAURUSLABS, FEDERALBNK in `paper/india/trades.csv`).
- **Recency and learning from noise: strong.** People expect recent returns to continue (Greenwood & Shleifer
  2014). Indian investors randomly allotted a rising IPO applied for more IPOs and traded more (Anagol,
  Balasubramaniam & Ramadorai 2021). Our ₹1,000 option test grew to ₹8,675 after two lucky exits under a rule that
  re-staked everything; the owner capped the stake (`journal/changes.md`).
- **Checking too often (myopic loss aversion): strong.** People given the most frequent feedback took the least
  sensible risks and earned the least (Thaler, Tversky, Kahneman & Schwartz 1997; Gneezy & Potters 1997). A 24/7
  market makes this worse: there is always a price to look at.
- **Paper does not rehearse real fear: strong in the lab.** Raising imaginary stakes barely changed choices; real
  stakes made people much more cautious (Holt & Laury 2002). People drop an algorithm after one visible mistake,
  even when it beats them, unless they keep a small bounded say (Dietvorst, Simmons & Massey 2015, 2018).

### 6.3 What happens to retail traders
- **India F&O (SEBI): strong.**
  - About 93% of individual traders lost money over FY22-FY24, more than ₹1.8 lakh crore in all.
  - FY26: 87.7% lost after costs and 82.1% before costs. Loss-makers lost ₹1.47 lakh on average. Options were 92%
    of individual losses, and 93% of individuals traded only options. 89% of traders under 30 lost.
  - SEBI's measures (STT rise from 1 Oct 2024; contract changes phased in from 20 Nov 2024 to April 2025) were
    followed by an 18% drop in active traders and a 3.2-point fall in the loss share, to 87.7% in FY26. That is
    still nearly 9 in 10. SEBI says the drop in traders cannot be put down to its measures alone, and warns that a
    lower loss share with fewer traders does not necessarily mean better outcomes (SEBI FY25-FY26 study).
- **India intraday cash, FY23: strong.** 71% lost; 80% of those making over 500 trades a year; 76% of under-30s.
  Costs added 57% to the losses of loss-makers (SEBI 2024).
- **Elsewhere: strong.** Fewer than 1% of Taiwan's day traders could predictably earn money after fees (Barber,
  Lee, Liu & Odean 2014).

### 6.4 What actually helps
- **Mechanical rules beat judgement: strong.** Formulas beat human experts substantially in 33-47% of studies;
  humans won in 6-16% (Grove et al. 2000). Managers who overrode a hiring test hired worse (Hoffman, Kahn & Li
  2018). An Indian robo-adviser reduced users' disposition effect (D'Acunto, Prabhala & Rossi 2019).
- **Automatic stops: mixed.** In the lab, automatic stop-losses reduced the disposition effect; reminders did not
  (Fischbacher, Hoffmann & Schudy 2017). If prices move randomly, stops lower expected return; they help when there
  is momentum (Kaminski & Lo 2014).
- **Small fixed risk per trade: weak as to the number.** Betting too much is far worse than betting too little
  (Thorp 2006; MacLean, Thorp & Ziemba 2010). No study proves 1% or 2% is best.
- **Loss limits: weak as to the thresholds.** The repo's 10% drawdown breaker cut the worst fall from −18.6% to
  −11.5%, not significantly (deflated Sharpe 0.75 over 11 variants; `journal/changes.md`).
- **Journaling: weak.** No study shows a journal itself raises returns. Its value is making overrides visible.

**What we do with it (all of section 6).** Exits and sizing come only from rules in code (20-day minimum hold,
20-day re-entry cooldown, daily order cap, loss limits). The LLM should not see a position's profit against its buy
price or the account's recent results. H13 tests "no add-on buy below average cost" and loss limits, H14 an
attention-spike filter, H3 a lottery-stock filter. M1 audits our own disposition effect and trading, M2 scores
every owner override, M7 checks the LLM for recency and loss-chasing. The owner gets one bounded knob (new-entry
size from 0 to 100%) instead of free overrides, and one headline number, "against the index since the start",
reviewed weekly. Real money stays out of F&O, intraday trading and option buying, and never follows tips.

---

## 7. Costs and tax (shares and F&O)

Crypto tax is in 1.7.
- **Delivery shares.** The repo's cost model (`indtrader/costs.py`) charges about 0.22% per round trip in taxes and
  fees (STT 0.1% each side, stamp duty 0.015% on buys, exchange fees, GST). The ₹15.34 DP (depository) charge on
  each sale adds about 0.015% on a ₹1 lakh sale, making 0.24% in all (the figure in `docs/live-trading.md`), but
  0.15% on a ₹10,000 sale. With 0.05% slippage per side, a ₹1 lakh round trip costs about 0.34%. Many edges in the
  research are about this size (2.4).
- **Share tax.** Held up to 12 months: 20% short-term gains tax since 23 Jul 2024. Longer: 12.5% on gains above
  ₹1.25 lakh a year (Union Budget 2024-25 speech). Plus 4% cess, and surcharge at higher incomes.
- **F&O.** Profits are business income, taxed at slab rates. The Finance Act 2026 (assent 30 Mar 2026) raised STT
  from 1 Apr 2026: futures 0.02% → 0.05%, options premium 0.1% → 0.15%, options exercise 0.125% → 0.15% (Budget
  2026-27 speech, para 140; NSE circular NSE/FATAX/73524 of 31 Mar 2026, via broker and press coverage).
  `indtrader/options.py` models the 0.15% premium rate; the futures rate is not yet in the OI study's cost model.
- **Cash is a real competitor.** The audited momentum book earned 4.2-4.8% a year (`docs/backtest-forensics.md`).
  The latest 91-day Treasury bill cut-off on rbi.org.in was 5.897% (seen 9 Nov 2026, undated), and yields were
  higher in 2024, when the RBI's repo rate was 6.5%, so cash probably beat the book. The right yardstick is the
  realised T-bill return over the same dates (P0-C).
- **What we do with it.** Every backtest reports an after-tax line (P0-C), a stress run with 0.2% slippage per side,
  and results against both cash and the index. Confirm all tax points with a chartered accountant before real money;
  details per desk are in `docs/go-live-checklist.md`.

---

## 8. Luck versus skill

- **The real question is the information ratio against the Nifty TRI.** "Is the Sharpe above zero?" is easy.
  "Does the desk beat an index fund?" is the owner's question. Years of daily results needed for 95% confidence
  (one-sided), if returns are roughly normal: years ≈ (1.645 ÷ ratio)² (Bailey & López de Prado 2012):

  | Sharpe above cash, or IR above the index | Years needed | t ≥ 3 bar |
  |---|---|---|
  | 0.2 | 68 | 225 |
  | 0.3 | 30 | 100 |
  | 0.5 | 10.8 | 36 |
  | 1.0 | 2.7 | 9 |

  Our audited momentum backtests have Sharpe ratios of 0.44-0.50 before subtracting cash. Information ratios of
  0.2-0.4 are often quoted as typical for active managers (unverified). At those levels no paper record can prove
  skill; only long, honest backtests can help, discounted for every variant tried.
- **One year tells you little.** With roughly normal returns, a Sharpe-0.5 strategy ends a year ahead of cash about
  69% of the time; a strategy with no edge, 50%.
- **The end date matters.** `docs/strategy.md` gives the Nifty +4.6% from Jan 2024 to late October 2026;
  `docs/backtest-forensics.md` gives +15.1% to 6 November. Both are right for their end dates: the Nifty rose 8.6%
  between 30 Oct and 6 Nov 2026 (Yahoo ^NSEI closes 23,053.1 and 25,030.3; the repo's Nifty futures match the
  end-October level). The as-published book was about 5.6 points ahead at end-October and 3.4 points ahead on 6
  November, while the audited variants trail by 0.8-2.6 points. A gap that one week can move by several points is
  "no evidence either way".
- **Price index or TRI.** Every repo benchmark uses the Nifty price index, with no dividends. The Nifty 50's
  dividend yield was about 1.2-1.4% in 2026 (factsheet figures quoted by Bajaj AMC and Trendlyne). The book's stock
  prices load from Yahoo with `auto_adjust=True` (`indtrader/data.py`), which, on our reading of the code, folds
  dividends into past prices. If so, every comparison leans toward the book by roughly the index's dividend yield,
  about 3.5-4 points over 2.85 years.
- **Count every try.** The *deflated Sharpe ratio* corrects for picking the best of many variants (Bailey & López
  de Prado 2014). The best condor variant scored 0.002, where 0.95 is the bar (`docs/options-backtest.md`). The
  expected live haircut is not a flat half: for Sharpe ratios below about 0.4 it is almost always more than 50% and
  can approach 100%; above 1.0 it is at most 25% (Harvey & Liu 2015).
- **Edges shrink once found.** Of 452 published US anomalies, 65% fail even t ≥ 1.96 when tests are built
  carefully (Hou, Xue & Zhang 2020); the average one is worth about 8bp a month after costs (Chen & Velikov 2023).
- **What we do with it.** P0-C adds returns above the realised T-bill and above the Nifty 50 TRI, the track-record
  length and the deflated Sharpe. H1 reruns the momentum book against the TRI with rolling month-end end dates
  (from mid-2025) and reports the spread. M5 shows "years still needed" for each desk on the site. The full gate is
  in `docs/go-live-checklist.md`.

---

## 9. Before any real money: the owner's own basics

None of this is personal advice. It is the standard order of steps that comes before any investing.
- **Prerequisites.** An emergency fund of several months of expenses (six is a common rule of thumb). No
  high-interest debt such as credit-card balances. Health and term-life insurance in place. Money for trading or
  index funds should be money not needed for five years or more.
- **Index funds fall too.** Nifty 50 price index, Yahoo daily closes, checked 9 Nov 2026:

  | Fall | Peak to low | Back to the old peak |
  |---|---|---|
  | 2008 | −60% (Jan to Oct 2008) | Nov 2010 |
  | 2015-16 | −22% (Mar 2015 to Feb 2016) | Mar 2017 |
  | 2020 | −38% (Jan to Mar 2020) | Nov 2020 |
  | 2024-25 | −16% (Sep 2024 to Mar 2025) | Jan 2026 |
  | 2026 | −16% (Jan to Oct 2026) | not yet, on 6 Nov 2026 |

  An index fund also has a small yearly fee (expense ratio) and tracks the index imperfectly.
- **Adviser or finfluencer.** A SEBI-registered investment adviser must give advice suited to you and is
  accountable to SEBI; registration numbers start with "INA" (research analysts: "INH"). Check the number on SEBI's
  website under recognised intermediaries. Most social-media "finfluencers" are neither. Since SEBI's circular of
  22 Oct 2024, SEBI-regulated firms may not work with unregistered people who give advice or claim returns (press
  coverage). SEBI has banned unregistered "trading gurus" and impounded their money (for example ₹546 crore in its
  interim order of 4 Dec 2025 against Avadhut Sathe and his trading academy, coverage).
- **Scam patterns.** Telegram or WhatsApp "VIP" tip groups; "algo platforms" promising guaranteed monthly returns;
  pump-and-dump (a small stock or coin hyped online while insiders sell into the buying); fake broker apps and
  impersonated advisers; anyone asking for your login, OTP, API key or a power of attorney over your demat account.
  A promise of guaranteed trading returns is itself the warning sign.
- **Where to complain.** SEBI's SCORES portal (scores.sebi.gov.in; version 2.0 since April 2024) handles complaints
  against SEBI-registered entities such as brokers and advisers. Complain to the firm itself first; then file on
  SCORES within one year of the problem (SCORES FAQ). It does not cover
  crypto exchanges or unregistered tipsters; for fraud, use the national cybercrime portal (cybercrime.gov.in) or
  helpline 1930.
- **What we do with it.** The owner's emotional rehearsal (what to do at −10%, −20% and −30%) belongs in
  `docs/go-live-checklist.md`. Rule: broker passwords and API keys never go into the repo; keys stay in environment
  variables, as `docs/live-trading.md` already does for Kite.

---

## 10. Open items and things to check

**Still unverified or disputed**
- Cited from memory because publisher pages blocked access: George & Hwang, Martineau, Chan 2003, Gervais et al.,
  Baker & Wurgler, Holt & Laury, Dietvorst, Thaler & Johnson. Marshall, Cahan & Cahan's headline (5,806 rules, 49
  indices, 2001-2007, none significant after the correction) matches published summaries; its India figures (592
  rules, adjusted p 0.794, 0.55% per trade) are unverified. Indian evidence on the 52-week high, lottery stocks,
  post-earnings drift and delivery % was not verified.
- Disputed between briefs: lottery stocks (rated mixed here) and crypto funding (the BIS paper suggests cutting when
  crowded; our run found cutting hurt; H8b settles it).
- Crypto tax section numbers under the Income-tax Act 2025, and the reach of s.509, need a CA.
- The SEBI figures in section 6.3 were checked against SEBI's own PDFs; re-quote any other SEBI figure from the
  primary PDF before relying on it.
- The exploratory scripts (Fear & Greed, funding, VIX timing, IIMA) should be committed under `research/` with
  their outputs, so those figures become reproducible.

**Things the research flags in our own setup** (nothing was changed; for the owner to decide)
- `indtrader halt` blocks every order, including stop-loss exits (`engine._send`); `resume` takes effect instantly.
- No weekly loss limit; the daily loss switch and drawdown breaker only block buys.
- Broker-side GTT stops are recommended in `docs/live-trading.md` but not built.
- `config/config.yaml` (the live template) still holds the old swing settings (2×ATR stop, 3-day minimum hold) and
  1% risk per trade; the paper desks use the slow book and 2%.
- `validation._sharpe` does not subtract cash; benchmarks are price indices, not TRI (section 8).
- The crypto backtest ignores the TDS cash drag (1.7); the OI study's costs predate the 2026 STT rise (4.3).

---

## 11. Sources

Repo files are cited inline. Links are given for official data, working papers and hard-to-find sources; other
papers are listed by journal. "Coverage" means press coverage, used where the primary page could not be opened.

**Crypto**
- Schmeling, Schrimpf & Todorov 2023, BIS WP 1087: https://www.bis.org/publ/work1087.pdf
- He, Manela, Ross & von Wachter, perpetual futures: https://arxiv.org/abs/2212.06888
- alternative.me Fear & Greed, method and data: https://alternative.me/crypto/fear-and-greed-index/
- Oct 2025 liquidations (CoinGlass data), coverage: https://www.tradingview.com/news/newsbtc:a4b7d8789094b:0-crypto-crash-19-5-billion-wiped-out-in-record-breaking-liquidation-event
- Chi, Chu & Hao: https://arxiv.org/abs/2411.06327 ; DefiLlama stablecoins: https://stablecoins.llama.fi/stablecoincharts/all
- Urquhart 2017, Economics Letters 159; Kogan, Makarov, Niessner & Schoar 2024, NBER WP 31317
- WazirX hack and the Oct 2025 restructuring: https://en.wikipedia.org/wiki/2024_WazirX_hack ; coverage: https://www.medianama.com/2025/10/223-wazirx-singapore-hc-amended-debt-repayment-plan/
- FIU-IND: Binance penalty, coverage: https://www.theweek.in/wire-updates/business/2024/06/20/del33-fiu-binance.html ; notices to 25 offshore platforms: https://www.medianama.com/2025/10/223-fiu-ind-notices-25-offshore-crypto-platforms-pmla-violation/
- Crypto tax unchanged in Budget 2026, coverage: https://coingape.com/indias-crypto-taxation-unchanged-as-the-existing-30-tax-retains

**Chart patterns and trend facts**
- Lo, Mamaysky & Wang 2000, NBER WP 7613: https://www.nber.org/system/files/working_papers/w7613/w7613.pdf
- Savin, Weller & Zvingelis 2007: https://www.biz.uiowa.edu/faculty/gsavin/papers/HSrevision_paw_10%2019%2006.pdf
- Osler 1998, FRBNY SR 42; Bender, Osler & Simon 2013, Review of Finance 17(2); Osler 2003, JF 58(5)
- Osler 2000, FRBNY EPR 6(2): https://www.newyorkfed.org/medialibrary/media/research/epr/00v06n2/0007osle.pdf
- Marshall, Cahan & Cahan 2010, SSRN 1181367: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1181367
- Jiang, Kelly & Xiu 2023, "(Re-)Imag(in)ing Price Trends", JF 78(6)
- Leigh et al. 2002, ESWA 23(2); Wang & Chan 2007, ESWA 33; Brock, Lakonishok & LeBaron 1992, JF 47(5); Sullivan,
  Timmermann & White 1999, JF 54(5); Bajgrowicz & Scaillet 2012, JFE 106(3); Plastun et al. 2020, NAJEF 52; Chan
  2003, JFE 70(2); Mishra & Tripathy 2018, QREF 68; Marshall, Young & Rose 2006, JBF 30(8); Marshall, Young &
  Cahan 2008, RQFA 31(2); Park & Irwin 2007, J. Economic Surveys 21(4); Gervais, Kaniel & Mingelgrin 2001, JF
  56(3); Lee & Swaminathan 2000, JF 55(5)
- Bulkowski failure rates: https://thepatternsite.com/FailureRates.html
- IIMA Indian factor data (Agarwalla, Jacob & Varma): https://faculty.iima.ac.in/iffm/Indian-Fama-French-Momentum/
- Daniel & Moskowitz 2016, NBER WP 20439; George & Hwang 2004, JF 59(5); Liu, Liu & Ma 2011, JIMF 30(1)
- Hou, Xue & Zhang 2020, RFS 33(5); NBER WP 23394: https://www.nber.org/papers/w23394

**Data beyond price and crowd emotion**
- Thenmozhi & Chandra 2013, NSE WP 9: https://nsearchives.nseindia.com/research/content/res_WorkingPaper9.pdf
- Chari & Inamdar 2021, NSE-NYU ASM paper: https://nsearchives.nseindia.com/s3fs-public/inline-files/Effectiveness%20of%20additional%20surveillance%20measures_WhitePaper.pdf
- Rajvanshi 2021, IIM Calcutta WP 863: https://studentlive.iimcal.ac.in/sites/all/files/pdfs/wp_863.pdf
- Capitalmind 2014, max pain: https://premium.capitalmind.in/2014/08/optionalysis-reliability-of-max-pain-on-the-day-before-expiry/
- Nifty weekly expiry moved to Tuesday, coverage: https://www.angelone.in/news/market-updates/nifty-weekly-expiry-today-see-what-changed-on-sept-1-2025
- Jena, Tiwari & Mitra 2019, Economies 7(1); Ni, Pearson & Poteshman 2005, JFE 78(1); Batra 2003, ICRIER WP 109;
  Froot, O'Connell & Seasholes 2001, JFE 59(2); Cohen, Malloy & Pomorski 2012, JF 67(3); Chauhan, Mishra & Spahr
  2021, Financial Management 50(1); Kalia 2024, JAMR; Martineau 2022, Critical Finance Review; Sehgal & Bijoy 2015,
  Vision 19(1); Gupta & Dhusia 2021, Trends Economics and Management
- Brown & Cliff 2004, J. Empirical Finance 11, and 2005, J. Business 78(2); Farrell & O'Connor 2025, FRL 72;
  Baker & Wurgler 2006, JF 61(4); Mathur & Rastogi 2018, AAJFA 8(1); Bijl et al. 2016, IRFA 45; Urquhart 2018,
  Economics Letters; Lachanski & Pav 2017, Econ Journal Watch
- Lopez-Lira & Tang: https://arxiv.org/abs/2304.07619 ; Glasserman & Lin: https://arxiv.org/abs/2309.17322

**Psychology and behaviour**
- Tversky & Kahneman 1992, J. Risk and Uncertainty 5: https://doi.org/10.1007/BF00122574
- Brown, Imai, Vieider & Camerer 2024, JEL 62(2): https://www.aeaweb.org/doi/10.1257/jel.20221698
- Odean 1998: https://faculty.haas.berkeley.edu/odean/papers%20current%20versions/areinvestorsreluctant.pdf
- Barber & Odean 2000: https://faculty.haas.berkeley.edu/odean/Papers%20current%20versions/Individual_Investor_Performance_Final.pdf
- Barber, Lee, Liu & Odean 2014, day traders: https://faculty.haas.berkeley.edu/odean/papers/day%20traders/Day%20Trading%20Skill%20110523.pdf
- Anagol, Balasubramaniam & Ramadorai 2021, summary: https://cepr.org/voxeu/columns/learning-noise-evidence-indias-ipo-lotteries
- Coval & Shumway 2005, JF 60(1); Barber, Huang, Odean & Schwarz 2022, JF 77(6); Kumar 2009, JF 64(4); Bali, Cakici
  & Whitelaw 2011, JFE 99(2); De Bondt & Thaler 1985, JF 40(3); Thaler & Johnson 1990, Management Science 36(6);
  Greenwood & Shleifer 2014, RFS 27(3); Thaler, Tversky, Kahneman & Schwartz 1997, QJE 112(2); Gneezy & Potters
  1997, QJE 112(2); Holt & Laury 2002, AER 92(5); Dietvorst, Simmons & Massey 2015, J. Experimental Psychology:
  General 144, and 2018, Management Science 64(3); Grove et al. 2000, Psychological Assessment 12(1); Hoffman, Kahn
  & Li 2018, QJE 133(2); D'Acunto, Prabhala & Rossi 2019, RFS 32(5); Fischbacher, Hoffmann & Schudy 2017, RFS 30(6);
  Kaminski & Lo 2014, J. Financial Markets 18; Thorp 2006, "The Kelly Criterion"; MacLean, Thorp & Ziemba 2010

**SEBI, tax, market data and personal finance**
- SEBI FY25-FY26 F&O study (Aug 2026): https://www.sebi.gov.in/sebi_data/attachdocs/aug-2026/1787233506209.pdf
- SEBI intraday study (Jul 2024): https://www.sebi.gov.in/sebi_data/attachdocs/jul-2024/1721818140715.pdf
- Union Budget speeches: 2026-27 https://www.indiabudget.gov.in/doc/budget_speech.pdf ; 2024-25 https://www.indiabudget.gov.in/doc/bspeech/bs2024_25.pdf ; 2022-23 https://www.indiabudget.gov.in/budget2022-23/doc/Budget_Speech.pdf
- STT from 1 Apr 2026 under the Finance Act 2026, coverage: https://www.freepressjournal.in/business/stt-hike-from-april-1-fo-traders-face-higher-costs-as-options-stt-rises-to-015 ; https://fyers.in/notice-board/revision-in-securities-transaction-tax-stt-effective-april-01-2026/
- RBI home page (91-day T-bill): https://www.rbi.org.in/ ; Yahoo Finance ^NSEI daily closes, retrieved 9 Nov 2026
- Nifty 50 dividend yield, 2026: https://www.bajajamc.com/knowledge-centre/nifty-50-dividend-yield ; https://trendlyne.com/equity/DIV/NIFTY/1887/nifty-50/
- SEBI SCORES: https://investor.sebi.gov.in/sebi_scores.html ; SCORES FAQ (one-year limit): https://scores.sebi.gov.in/en/faqs ; finfluencer circular, coverage: https://www.outlookbusiness.com/markets/sebi-directs-regulated-entities-to-sever-ties-with-finfluencers-in-3-months ; Avadhut Sathe order, coverage: https://www.storyboard18.com/amp/how-it-works/sebi-bans-finfluencer-avadhut-sathe-impounds-rs-546-crore-for-running-unregistered-advisory-85392.htm

**Luck versus skill**
- Bailey & López de Prado 2012: https://www.davidhbailey.com/dhbpapers/sharpe-frontier.pdf ; 2014 (deflated Sharpe): https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf
- Harvey, Liu & Zhu 2016: https://www.nber.org/system/files/working_papers/w20592/w20592.pdf ; Harvey & Liu 2015: https://people.duke.edu/~charvey/Research/Published_Papers/P120_Backtesting.PDF
- Chen & Velikov: https://www.federalreserve.gov/econres/feds/zeroing-in-on-the-expected-returns-of-anomalies.htm
