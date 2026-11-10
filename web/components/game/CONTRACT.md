# Candle City: interfaces between the game's parts

An original open-world trading-practice game at `/game`. You drive a car around a small 3D city at dusk. Mission
markers open **missions**: a real past chart with its name and dates hidden; you buy, sell or stay out, set a stop,
then reveal the candles one at a time. A **tilt meter** rises with the classic emotional mistakes. Game cash only:
no real money, no real orders. Not a copy of any existing game: no names, characters, maps, art, music or logos
from other games.

Plain JavaScript (ES modules, no TypeScript). Next.js 15 app router, React 19, `three@0.186.1`. Use the site's CSS
tokens (`var(--bg)`, `var(--panel)`, `var(--ink)`, `var(--accent)`, `var(--up)`, `var(--down)`, `var(--grad)`, ...)
so the game follows the light/dark theme. Each part has its own CSS module; do not edit `app/globals.css`.

## 1. Data: `web/public/game/series.json` (built by `scripts/build_game_data.py`)
```json
{ "version": 1, "built": "2026-11-10", "end": "2026-10-31",
  "series": [
    { "id": "btc", "name": "Bitcoin", "symbol": "BTC/USDT", "market": "crypto", "district": "docks", "cur": "$",
      "cost": 0.0015, "t": [17683, ...], "o": [...], "h": [...], "l": [...], "c": [...] }
  ] }
```
- `t` = days since 1970-01-01 (UTC), one per candle; `o/h/l/c` rounded to 4 significant digits (at least 2 decimals
  under 10). `cost` = one-side cost as a fraction (crypto 0.0015 = fee + slippage; NSE stocks 0.0012).
- Series: crypto (district `docks`): BTC, ETH, SOL, BNB, XRP from `data/crypto/<COIN>.csv` (from 2018 or listing);
  India (district `market`): Nifty 50 (`^NSEI`), RELIANCE, TCS, HDFCBANK, INFY, ICICIBANK (yfinance, auto-adjusted,
  from 2012). All end on 2026-10-31. Target size: under 1.2 MB.

## 2. Engine: `web/lib/game/engine.js` (pure, no DOM, no React; tested by `node --test web/lib/game/`)
```js
export const VISIBLE = 90, FUTURE = 30;
export function rng(seed)                       // mulberry32 -> () => [0,1)
export function pickRound(series, rand)         // -> Round (random window with VISIBLE + FUTURE candles)
// Round = { seriesId, i0, i1, i2, candles: [{t,o,h,l,c}] (VISIBLE+FUTURE), atr, ctx: { ret10, ret30, rsi14, vsSma50 } }
//   i0 first visible index, i1 = i0+VISIBLE (first hidden), i2 = i1+FUTURE; atr = ATR(14) at the last visible candle
export function planTrade(round, { side, stopAtr, targetR }) // side "long"|"short"|"skip"; stopAtr 1..3; targetR 1|2|3|null
// -> Trade = { side, entry (open of the first hidden candle), stop, target|null, risk (|entry-stop|), cost (series.cost),
//              stopAtr, targetR, moves: [], bars: 0, status: "open" }
export function stepTrade(trade, candle, action) // action "hold"|"close"|{ moveStop: price }; applies the candle:
// gap through stop/target fills at the open; stop checked before target when both are touched in one candle.
// -> new Trade with status "open"|"stopped"|"target"|"closed"|"timeout"(after FUTURE bars), exit, r (net of 2x cost, in R)
export function coinFlipR(round, plan)          // average net R of long and short with the same stop/target, no moves
export function sizeUnits(cash, riskPct, risk)  // units so that hitting the stop loses riskPct% of cash
export function detectMistakes(history, decision, trade) // -> [{ kind, severity 1..3, title, message, lesson }]
// kinds: "fomo" (long after ret10 > 15% or RSI > 75), "panic" (short after ret10 < -15% or RSI < 25),
// "revenge" (no skip and a wider stop or a new trade straight after a loss), "early-profit" (closed a winner
// below +1R when the target was 2R+), "moved-stop" (moved a stop further away), "overtrading" (no skip in the
// last 10 decisions), "chasing" (entered after 3+ same-direction candles each > 1 ATR); positive "discipline"
// (skipped a stretched chart, or let the stop and target work untouched)
export function tilt(history)                    // 0..100 from recent mistakes, decaying with clean decisions
export function stats(history)                   // { rounds, trades, skips, winRate, avgR, coinFlipAvgR, edgeR, t, cashStart, cash }
```
`history` = array of finished missions: `{ seriesId, side, stopAtr, targetR, r, coinR, mistakes, cashBefore, cashAfter, at }`.

## 3. Mission UI: `web/components/game/Mission.js` (+ `Mission.module.css`), client component
Props: `{ data, seed, history, cash, tilt, onDone(result), onExit() }`. It loads nothing itself (`data` is the parsed
series.json). Flow: hidden-name chart (canvas, 90 candles, optional 50-day line) → decision panel (Buy / Sell / Stay
out, stop 1-3 ATR, target 1R/2R/3R/none, risk fixed at 1% of game cash) → reveal one candle at a time (Next, Auto,
Close now, Stop to breakeven, Move stop) → result card: R, cash change, coin-flip comparison, mistakes and lessons,
and the reveal ("Bitcoin, 3-11 Mar 2020"). `onDone(result)` returns the history entry. Works on a 390 px phone.

## 3b. The Strip: `web/lib/game/strip.js` + `web/components/game/StripMission.js` (written by the main session)
A neon casino-style district whose missions teach the **house edge**. Each mission sells a "lottery ticket": a cheap
out-of-the-money Nifty option (call or put, 1-3% away, expiring tomorrow or in 5 trading days) priced the way the
market prices it (implied volatility above realised, plus a spread), then reveals the real Nifty path day by day like
spinning reels. The result card shows the payout, the ticket's fair value against what you paid (the house edge),
the odds of it paying off, and your running total on the Strip, next to SEBI's finding that about 9 in 10 F&O
traders lose money. Props: `{ data, seed, history, cash, tilt, onDone(result), onExit() }`, the same as Mission;
`result` is a history entry with `kind: "strip"` plus `{ stake, payout, fair, edgePct }` and the mistakes
`"lottery"` (buying far out-of-the-money) and `"chasing-losses"` (playing again straight after a loss with a bigger
stake). The shell routes markers whose `district` is `"strip"` to `StripMission`.

## 4. World: `web/components/game/World.js`, client component, three.js
Props: `{ markers: [{ id, district, label, x, z, color }], tilt, paused, onEnterMarker(id), onReady() }`. A small
low-poly city (instanced buildings, roads, a harbour on one side for the Crypto Docks, a market square for Nifty
Market, a park for Cool-down Park, and **the Strip**: a wide boulevard of tall neon-lit towers and glowing signs with
casino-style names of our own, e.g. "The Lucky Strike", "Expiry Palace", "Theta Lounge", never real casino or game
brands), dusk lighting in the site's violet palette, an arcade car, chase camera,
keyboard (WASD/arrows, Space brake) and a touch joystick on phones, glowing marker pillars that call
`onEnterMarker` when the car stops inside one, and a minimap. Tilt above 60 adds a red vignette and camera shake.
Disposes everything on unmount. Caps pixel ratio at 1.5; no shadows on phones. Exports `DISTRICTS` (ids `docks`, `market`, `park`, `strip`) and
`defaultMarkers()`.

## 5. Shell: `web/app/game/page.js` + `web/components/game/GameShell.js` (+ `GameShell.module.css`)
Fetches `/game/series.json`, holds state (game cash starting at $10,000, history, tilt, seed) in `localStorage`
key `candle-city-v1` (wrapped in try/catch; works without it), shows the intro (controls, "practice with game cash:
no real money"), the HUD (cash, rounds, edge vs coin flip, tilt meter), switches World ↔ Mission (markers in district `"strip"` open `StripMission` from `./StripMission`), runs Cool-down
Park (tilt falls while parked; a short lesson card), the stats screen, and Reset. Adds "Play" to the site nav.
