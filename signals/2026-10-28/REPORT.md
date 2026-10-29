# India analyst review: data to 28 Oct 2026, trading 29 Oct

## Market context
- Nifty 50 closed at 22,698.85, **below its 200-day average** (1m -1.9%, 3m -5.4%): bear regime, so the engine halves new buys.
- With the SEPA trend template on, only 9 of 192 Nifty 200 stocks qualified. Leadership is narrow (pharma, a private
  bank, autos, platforms, defence).
- Earnings season: 4 of the 9 candidates report within ~7 trading days. One reports today.

## Ratings
| Symbol | Screen rank | Rating | Confidence | Reason / red flags |
|---|---|---|---|---|
| LAURUSLABS | 1 | **Underweight (veto)** | 80 | Results board meeting **today** (NSE intimation); call 5pm; +12% above EMA50 at 52w high |
| DIVISLAB | 2 | Hold | 55 | Yahoo's 28 Oct bar missing, technicals unverifiable; results 7 Nov |
| BOSCHLTD | 3 | Overweight | 58 | SEPA 7/7, RS +21% (3m); results 6 Nov; no red flags |
| FEDERALBNK | 4 | **Buy** | 66 | Q2 record profit +45%, NPA at decade lows (16 Oct); event risk passed |
| NYKAA | 5 | Hold | 58 | Results 4 Nov, inside the first week |
| ZYDUSLIFE | 6 | Hold | 58 | USFDA approval (21 Oct) but results 4 Nov |
| ADANIPORTS | 7 | Hold | 55 | Q2 filed 28 Oct; numbers and reaction not yet verifiable |
| ETERNAL | 8 | Hold | 55 | Q2 profit +92% but missed estimates, stock -3.5% (21 Oct) |
| HAL | 9 | Overweight | 57 | SEPA 7/7, results 12 Nov; routine director change |

## Data issues found
- NSE's `event-calendar` no longer lists **today's** board meetings (LAURUSLABS missing), so the engine's results blackout
  would have missed it. NSE's `corporate-board-meetings` endpoint still shows it. Code fix to follow.
- Yahoo returned an empty (NaN) last bar for DIVISLAB. Code fix to follow (drop empty bars).

## Sources
- NSE board-meeting intimation, Laurus Labs, 13 Oct 2026 (nseindia.com corporate-board-meetings); [ScanX: Laurus Q2 call on 29 Oct](https://scanx.trade/stock-market-news/companies/laurus-labs-schedules-q2-fy27-earnings-call-october-29/53439146)
- [Upstox: Federal Bank Q2 results](https://upstox.com/news/market-news/earnings/federal-bank-q2-results-net-profit-soars-45-yo-y-to-1-386-crore-asset-quality-improves/article-201993/), [Free Press Journal: Federal Bank Q2](https://www.freepressjournal.in/business/federal-bank-q2-profit-surges-4510-to-138609-crore-npa-at-decadal-lows)
- [Kotak Neo: Eternal Q2 FY27](https://www.kotakneo.com/news/stocks/eternal-q2-results-profit-rises-revenue-growth-blinkit-adds-stores/), [IndMoney: Eternal Q2 analysis](https://www.indmoney.com/blog/stocks/eternal-q2-results-analysis)
- NSE filings via `indtrader brief`: Adani Ports outcome of board meeting (28 Oct), Zydus USFDA press release (21 Oct), HAL director change (28 Oct); NSE event calendar for results dates (Bosch 6 Nov, Nykaa 4 Nov, Zydus 4 Nov, Divi's 7 Nov, HAL 12 Nov)
