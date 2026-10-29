# Roadmap

## Now

- [x] India and US paper desks with LLM-reviewed and control accounts
- [x] Public site with live quotes, history, analyst calls, journal
- [x] SEC filing and news tools for the US review
- [ ] Decide the next phase (scheduled runs paused meanwhile)

## Next: Nifty options desk (paper)

- [ ] Backtest weekly and monthly Nifty iron condors on NSE F&O bhavcopy data, 2020 onwards, with full costs
      (STT 0.15% on option sales, exchange charges, stamp duty, GST, brokerage) and bid/ask fills
- [ ] Paper desk on NSE's live option chain: defined-risk structures only, profit at 50% of credit, stop at
      2× credit, close the day before expiry
- [ ] LLM event gate (RBI, budget, Fed, CPI, heavyweight results): trade, skip, shrink or widen, never enlarge
- [ ] Rules-only control account, as on the stock desks
- [ ] "Time machine" odds check: replay Nifty's own moves to expiry before each entry
- [ ] Hard limits in code outside the model: max lots, max loss per trade, daily loss kill switch
- [ ] Options page on the site: payoff, Greeks, maximum loss, LLM vs control

## Later

- [ ] Nifty futures as a portfolio hedge in bear regimes
- [ ] Upstox Analytics Token as the India data source (official quotes, no daily login)
- [ ] Broker-side GTT stops for live trading
- [ ] Optional US intraday paper desk on the day-trader-skill pipeline

Items move only with evidence: a backtest, then paper results logged in
[`journal/changes.md`](../journal/changes.md).
