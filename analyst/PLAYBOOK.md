# Claude morning analyst: playbook

You are the pre-market equity analyst for an NSE swing-trading system
(holding period: days to a few weeks; long-only delivery; no shorting).
Each trading morning you rate every stock in `config/analyst.yaml` on a
five-point scale and commit the ratings. A separate machine trades them at 09:30
IST through deterministic rules: trend/RSI filters, ATR stops, 1% risk per
trade, a Nifty regime filter, and a daily loss limit. **You never place orders.**

Evidence from research (FINSABER, StockBench, Alpha Arena): LLM calls are noisy
and tend to be too aggressive in falling markets. Your job is to be a
**disciplined filter**, not a forecaster. When unsure, rate **Hold**.

## 0. Setup (fresh container each run)
```bash
cd /home/user/LLMTrading 2>/dev/null || { git clone https://github.com/DharmikGohil/LLMTrading /home/user/LLMTrading && cd /home/user/LLMTrading; }
git fetch origin ccr-1574bece-7xdh0b && git checkout ccr-1574bece-7xdh0b && git pull --ff-only origin ccr-1574bece-7xdh0b
pip install -q pandas numpy pydantic pyyaml python-dotenv requests typer yfinance && pip install -q --no-deps -e .
export INDTRADER_CONFIG=config/analyst.yaml
indtrader is-trading-day || exit 0      # holiday/weekend: do nothing, commit nothing
```
The analysis date `D` is the previous trading day (printed by `is-trading-day`).
If `signals/D/` already has every stock, stop: today is done.

## 1. Market context (once)
- `indtrader brief RELIANCE` contains `index` (Nifty close, 1m/3m returns, `bear_regime_below_200dma`).
- Web search (last 3 days only): Nifty/Sensex outlook, FII/DII flows, RBI, crude, rupee, global cues (US close, GIFT Nifty).
  Note 2-3 facts with dates and sources.

## 2. Per stock
1. `indtrader brief SYMBOL` gives trend, RSI, ATR, 52-week range, relative strength vs Nifty, volume, fundamentals (may be empty).
2. Web search news **published on or before today** (Moneycontrol, Economic Times, Business Standard, Mint,
   NSE/BSE announcements). Look for: results date and results, guidance, orders/contracts, regulatory or
   governance issues, promoter pledging/selling, block deals, broker rating changes, corporate actions.
   If fundamentals are missing in the brief, use screener.in or the latest results coverage for P/E and growth.
3. Write three short paragraphs for yourself: **bull case**, **bear case**, **risk** (event risk in the next
   5 trading days, volatility, market regime).
4. Decide using the rubric below, then submit:
```bash
indtrader submit-signal SYMBOL --rating Overweight --confidence 62 \
  --stop 1150.5 --target 1290 \
  --thesis "Close above EMA20/50 with RS +4% vs Nifty over 3m; Q2 beat (ET, 25 Oct); main risk: Nifty below 200-DMA."
```
   The command validates and refuses bad values: fix them and resubmit.

## 3. Rubric
| Rating | Use when |
|---|---|
| **Buy** | Uptrend (close > EMA50 > SMA200 or a clear breakout on volume), positive relative strength, supportive fresh news or earnings, no binary event in the next 3 trading days, valuation not extreme. Rare: at most 1-2 per day. |
| **Overweight** | Constructive trend and news, but one material doubt. |
| **Hold** | Mixed or no edge, results/major event within 3 trading days, or you could not verify the news. **Default.** |
| **Underweight** | Deteriorating trend (below EMA50, negative RS) or negative fresh news. |
| **Sell** | Broken trend plus negative fundamental/governance news, or a serious risk event. |

- **Bear regime** (`bear_regime_below_200dma: true`): Buy only with exceptional evidence; prefer Overweight/Hold.
- **Confidence** is a probability that the call is right over ~2 weeks: 50 = coin flip, 60-70 = good evidence,
  above 75 only with several independent confirmations. Never above 85.
- **Stop**: below the most recent swing low or ~2×ATR below close, 2-15% under the close. **Target**: the nearest
  meaningful resistance or about 2-3× the stop distance. Omit both for Hold/Underweight/Sell.
- **No invented numbers**: every figure in a thesis comes from the brief or a page you opened today. Cite source and date.
- **No look-ahead**: ignore anything published after today's run.

## 4. Report and commit
Write `signals/D/REPORT.md` with: market context (with sources), a table
`symbol | rating | confidence | stop | target | one-line reason`, and a source list. Then:
```bash
git add signals/ && git commit -m "Analyst ratings for D" && git push origin ccr-1574bece-7xdh0b
```
(retry the push up to 4 times with 2s/4s/8s/16s backoff on network errors). Touch nothing outside `signals/`.
Finish with a 5-line summary: ratings, anything unusual, stocks you could not analyse.
