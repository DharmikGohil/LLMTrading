# Going live

> Real money only after evidence. The checklist below is the minimum.

## Checklist before real money

1. **Paper results over months, not days.** At least 60 trading days and 30 closed trades, with the
   LLM-reviewed account ahead of both the control account and the index after costs.
2. **Agree the fallback in advance.** If the desk does not beat the index, a Nifty index fund is the honest
   alternative.
3. **Start small.** ₹1–2 lakh in delivery equity. Below about ₹1 lakh this strategy does not work (expensive
   shares cannot be bought within a 10% slot, and the per-sale DP charge eats small gains).
4. **No leverage.** Delivery only: no margin, no intraday, no F&O until those desks have their own record.
5. **Broker-side stops.** Place every stop as a GTT order at the broker so it triggers even if the bot is down.
6. **Scale slowly.** Add money only after another few months that match paper and backtest.
7. **Tax.** Listed equity held under a year: 20% short-term capital gains. The edge must survive tax.

## Costs

`indtrader costs <price> <qty>` prints buy and sell charges and the break-even move (about 0.24% round trip
for NSE delivery).

## Brokers

| Broker | How | Notes |
|---|---|---|
| Zerodha (Kite Connect) | `broker.name: zerodha`, `KITE_API_KEY` / `KITE_API_SECRET`, daily `indtrader zerodha-login` | Personal API (orders, GTT, portfolio) is free; live and historical data is ₹500/month. No sandbox: every API order is real. |
| OpenAlgo (25+ brokers) | Self-hosted [OpenAlgo](https://github.com/marketcalls/openalgo), `OPENALGO_API_KEY`, `broker.name: openalgo` | Angel One, Dhan, Upstox, Fyers, Kotak, 5paisa, Shoonya and more. Its analyzer mode is a sandbox with virtual capital. |
| Paper | `broker.name: paper` | Simulated fills at live prices with full costs and partial fills. |

## Market data options (India)

| Source | Cost | Notes |
|---|---|---|
| Yahoo Finance (default) | free | Unofficial; occasional bad bars are dropped |
| NSE public APIs | free | Filings, results calendar, surveillance lists, live option chain |
| Upstox Analytics Token | free | Read-only, valid 1 year, no daily login and no static IP for market data (quotes, history, option chain, WebSocket) |
| Fyers API | free | Daily login; 5 years daily and 1 year intraday history |
| Zerodha Kite Connect | ₹500/month | Live WebSocket and history |
| Dhan Data API | ₹499/month | |

## SEBI retail algo rules (in force since 1 April 2026)

- API orders only from a registered app on a **whitelisted static IP** (run the bot on a VPS with a static IP).
- **Daily 2FA login**; no perpetual trading tokens.
- Orders tagged with the exchange Algo ID where the broker provides one (`KITE_ALGO_ID`).
- Under 10 orders per second keeps you a regular API user; this bot sends a handful a day.

Rules change: check your broker's current notice before going live.
