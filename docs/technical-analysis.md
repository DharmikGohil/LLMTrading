# Technical analysis: how the desk reads a chart, and what the evidence says

Each stock page on the site has a daily candlestick chart. `indtrader brief` gives the analyst the same reading as
data in its `chart` block. Both use the definitions below, implemented in `indtrader/signals/chart.py` and
`indtrader/signals/technical.py` (Python) and `web/lib/ta.js` (site).

## The evidence, in one paragraph

Trend and momentum have the strongest support:
- Price momentum over 3-12 months (Jegadeesh and Titman 1993).
- Time-series momentum across asset classes (Moskowitz, Ooi and Pedersen 2012).
- Long moving-average trend filters.

Short-term indicator rules are weaker:
- Park and Irwin's review (Journal of Economic Surveys, 2007) counted 56 positive, 20 negative and 19 mixed results
  among 95 modern studies. It also flagged that most of those studies suffer from data snooping, rules picked after
  the fact, and costs that are underestimated.
- Sullivan, Timmermann and White (Journal of Finance, 1999) corrected the classic Brock, Lakonishok and LeBaron
  (1992) moving-average results for data snooping. They found the rules lost their edge on US indices after the
  mid-1980s.
- Candlestick strategies showed no value on Dow stocks over 1992-2002 (Marshall, Young and Rose, Journal of Banking
  & Finance, 2006).
- In India, RSI rules on the Sensex over 2000-2018 failed to make money even before costs, and MACD's sell signals
  helped only in bear markets (Muruganandan, 2020).
- Chart patterns such as head-and-shoulders and double tops carry some information about the next few days' return
  distribution (Lo, Mamaysky and Wang, Journal of Finance, 2000). That is a statistical effect, not a proven
  trading profit.

**So the strategy uses trend and momentum to decide what to own, and uses everything else here to time entries and
place stops.** The desk's own studies agree. The open-interest build-up board, Kronos forecasts and altcoin
momentum all failed honest tests (`docs/oi-buildup.md`, `docs/kronos.md`, `docs/crypto-backtest.md`).

## Trend

| Tool | Definition | How traders use it |
|---|---|---|
| EMA 20 / EMA 50 | Exponential moving average, smoothing 2/(n+1) | Short and medium trend. Price above a rising EMA 50 is an uptrend; pullbacks to the EMA 20 or 50 are classic entry points in a trend. |
| SMA 200 | Simple 200-day average | The long-term trend line institutions watch. The desk's bear-regime rule (index below its SMA 200) halves new buys. |
| Trend template | Minervini's 7 conditions (price above the 50/150/200-day averages, averages stacked and rising, within 25% of the 52-week high, 30% above the low) | The screen requires it: buy only stocks already in a Stage 2 uptrend. |
| 52-week high distance | Close against the 250-day high | Stocks near their highs tend to keep outperforming (George and Hwang 2004). |

## Momentum oscillators

| Tool | Definition | How traders use it | Caution |
|---|---|---|---|
| RSI 14 | Wilder's relative strength index: average gain against average loss, smoothing 1/14 | Above 50 means momentum is up. Above 70 is overbought, below 30 oversold. In strong trends RSI stays at 70-80 for weeks, so "overbought" is not a sell signal on its own. | Above 80 after a news spike is the desk's parabolic red flag. |
| MACD 12,26,9 | EMA 12 minus EMA 26 (the line), its 9-day EMA (the signal), and their difference (the histogram) | Line above signal and above zero means bullish momentum. A shrinking histogram means momentum is fading. A bullish cross after a pullback in an uptrend is a common entry trigger. | Lags price. Crossovers in sideways markets whipsaw. |

## Volatility

| Tool | Definition | How traders use it |
|---|---|---|
| ATR 14 | Wilder's average true range | Sizes stops: the desk places stops 2-4 × ATR below entry. Also scales position size, so a volatile stock gets fewer shares for the same rupee risk. |
| Bollinger Bands 20,2 | SMA 20 ± 2 standard deviations; %B = position inside the bands; bandwidth = band width ÷ middle | %B above 1 means the close is above the upper band: strength in a trend, stretched in a range. A squeeze (bandwidth at a 6-month low) often comes before a big move, but it does not tell you the direction. |

## Support and resistance

Levels where price turned more than once. The desk finds them the way a trader eyeballs them:
1. Mark swing highs and lows: a bar whose high (or low) is the extreme of the 5 bars on each side.
2. Group swings within 0.6 × ATR of each other into one level, and require at least two touches.
3. Rank levels by touches, with recent touches counting more.

On the chart, support is drawn in green below price and resistance in red above, with the touch count. Traders use
them in three ways:
- **Stops:** go just below support, not on it, because levels attract stop-hunting wicks.
- **Targets:** go at the next resistance.
- **Breakouts:** a close above resistance on volume of at least 1.5× average is a buy trigger in the trend
  template's setups (pivot points, VCP).

A broken resistance often becomes support.

## Candlesticks

Read on the last bar, in the context of the prior 10-day trend:
- **Doji:** body at most 10% of the range. Indecision.
- **Hammer** (after a decline) and **hanging man** (after a rise): lower shadow at least 2× the body, small upper
  shadow.
- **Shooting star** (after a rise) and **inverted hammer** (after a decline): the mirror shape.
- **Bullish / bearish engulfing:** the body engulfs the prior opposite-colour body.
- **Inside bar:** the range sits inside the prior bar's range. A coiling pattern.
- **Outside bar:** range expansion.

The desk treats candlesticks as **confirmation at a level only**. A hammer on support in an uptrend is worth
noticing. A hammer in the middle of nowhere is not. The evidence above says candlestick rules on their own do not
beat buy-and-hold.

## Volume

Volume against its 50-day average. A breakout on above-average volume is more reliable than one on thin volume. A
selloff on heavy volume is distribution, and is more serious than a drift lower on light volume.

## How the analyst uses the `chart` block

The block is context for the rating, not a reason to buy:
- **Never upgrade a rating because of an indicator.** The screen decides what to buy.
- **Use it for the red-flag checklist:** RSI above 80, or closing far above the upper Bollinger band after a news
  spike, is the parabolic flag. A bearish engulfing candle on very heavy volume at resistance is worth a Hold.
- **Use it for the bear case** in the devil's-advocate step: "extended 12% above EMA 50 into resistance at X"
  is a specific, checkable risk.
- **Use levels when suggesting a stop:** just below the nearest strong support, if that is tighter than the ATR
  stop.
