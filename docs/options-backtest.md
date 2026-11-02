# Options backtest, January 2020 to October 2026

Run on 2 November 2026 with `scripts/options_backtest_report.py` over NSE's daily F&O bhavcopy (1,688 trading days,
`scripts/download_fo_bhavcopy.py`). Rules as on the live desk: iron condors with short strikes `k` standard deviations
out (volatility implied by the at-the-money straddle), wings 200 points (Bank Nifty 500), entered `dte` trading days
before expiry; *managed* = take profit at 50% of the credit, stop when the loss equals the credit, else close the day
before expiry; *hold* = close the day before expiry. Fills at the close with slippage (2% of premium, at least 0.5
point per leg), charges with the STT and exchange rates of each date, today's lot sizes, Rs 1 lakh capital.

## Verdict

**No variant shows an edge.** 46 of 48 weekly variants lost money; the best (Bank Nifty, 1 SD, 3 days, +7.2% over
6.8 years) has a deflated Sharpe of 0.002 (0.95 = robust). The rules running live on 2 Nov (Nifty, 1 SD, 5 days,
managed) lost **-223%** of capital. Longer holding periods (10, 15, 20 days) were also negative.

The losses are not only costs. With zero slippage and zero charges the live rules still lost about 96% (managed)
and 53% (held): weekly short strikes about 1 SD out were breached by real moves often enough (January and
February 2022, the 2024 election, 2026) that the premium collected did not pay for them. Wider strikes (1.5 SD,
held) made +7% gross, which costs then erased.

| Variant | Trades | Return | Win rate | Worst trade | Max drawdown | Sharpe | Deflated Sharpe |
|---|---|---|---|---|---|---|---|
| BANKNIFTY k=1.0 dte=3 hold | 274 | +7.2% | 72% | ₹-13,352 | -30.7% | 0.06 | 0.002 |
| BANKNIFTY k=1.0 dte=3 managed | 274 | +5.0% | 71% | ₹-10,811 | -34.1% | 0.05 | 0.001 |
| BANKNIFTY k=1.25 dte=3 hold | 271 | -7.8% | 75% | ₹-13,387 | -30.3% | -0.08 | 0.0 |
| FINNIFTY k=1.5 dte=5 hold | 60 | -10.2% | 78% | ₹-13,281 | -17.5% | -0.36 | 0.002 |
| BANKNIFTY k=1.25 dte=3 managed | 271 | -12.0% | 75% | ₹-10,306 | -28.8% | -0.15 | 0.0 |
| BANKNIFTY k=0.75 dte=3 hold | 274 | -15.3% | 67% | ₹-13,279 | -42.3% | -0.11 | 0.0 |
| ... | | | | | | | |
| NIFTY k=1.0 dte=5 managed | 319 | -222.7% | 61% | ₹-9,997 | -223.8% | -1.84 | 0.0 |

Average return across variants: Nifty -150%, Bank Nifty -98%,
Fin Nifty -48% (16 variants each).

## Rs 1,000 option buying (one out-of-the-money option per expiry, 5-day trend direction)

- **NIFTY:** 291 trades, 19% winners, -20.4% of everything staked
- **BANKNIFTY:** 227 trades, 18% winners, -11.2% of everything staked
- **FINNIFTY:** 136 trades, 21% winners, -16.5% of everything staked

About one in five bets paid off; overall the buyer lost 11-22% of the money staked.

## Limits of this test

- Daily closes only: a stop can only trigger at a close, so intraday stops on the live desk can exit earlier (or
  later) than here. Untraded strikes are marked at NSE's settlement price.
- No bid/ask in daily data: slippage is an assumption. Results with zero slippage and zero charges are given above.
- The LLM event gate cannot be backtested honestly; it can only be judged on paper against the rules-only control.

## Consequence

Real money does not go into these option strategies. The paper desk may continue only as a test of whether the
LLM gate reduces the losses the rules make on their own.
