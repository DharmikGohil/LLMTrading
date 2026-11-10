// Candle City game engine: the rules of a practice trade. Pure ES module (no DOM, no React), so the same code runs
// in the browser and under `node --test`. The interfaces follow web/components/game/CONTRACT.md, section 2.
//
// A round is a real past chart cut into VISIBLE candles the player can see and FUTURE candles that stay hidden.
// The player buys ("long"), sells ("short": a bet that the price falls) or stays out ("skip"). A trade enters at
// the open of the first hidden candle, with a stop a few ATRs away and an optional target in multiples of that
// risk. Results are in R (1R = the planned loss if the stop is hit), net of costs on both sides, and every result
// is compared with a coin flip: the average of buying and selling the same chart with the same stop and target.
// Game cash only: nothing here touches real money or real orders.

export const VISIBLE = 90;
export const FUTURE = 30;
export const WINDOW = VISIBLE + FUTURE;
export const START_CASH = 10000; // the shell's starting game cash
export const RISK_PCT = 1; // the Mission risks 1% of game cash per trade

const ATR_N = 14;
const RSI_N = 14;
const STRETCH_RET10 = 0.15; // a 15% move in 10 candles counts as stretched
const RSI_HOT = 75;
const RSI_COLD = 25;
const CHASE_RUN = 3; // 3+ big candles in a row in the trade's direction
const OVERTRADE_RUN = 10; // 10 decisions in a row with no skip
const REVENGE_MS = 2 * 60 * 1000; // "straight back in": a new trade within 2 minutes of a loss
const TILT_PER_POINT = 10; // tilt added per point of mistake severity
const TILT_DECAY = 0.6; // a clean mission keeps 60% of the tilt ...
const TILT_CLEAN_DROP = 4; // ... minus a few points (8 when it also earned a "discipline" note)
const TILT_WINDOW = 40; // only the most recent missions count
const EPS = 1e-9;

// ---------------------------------------------------------------------------------------------------------------
// Random numbers

/** FNV-1a hash, so a text seed (e.g. "monday") gives a repeatable number seed. */
function hashString(s) {
  let h = 0x811c9dc5;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  return h >>> 0;
}

/** mulberry32: a small, fast seeded generator. rng(seed) returns () => a number in [0, 1). Same seed, same run. */
export function rng(seed = 0) {
  let a = typeof seed === "number" && Number.isFinite(seed) ? Math.floor(seed) >>> 0 : hashString(String(seed));
  return function next() {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), a | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** A random index in [0, n), safe against a generator that returns exactly 1. */
const pickIndex = (next, n) => Math.min(n - 1, Math.floor(next() * n));

// ---------------------------------------------------------------------------------------------------------------
// Indicators (Wilder smoothing). Inputs are oldest first; outputs line up with them and are null while warming up.

/**
 * Wilder's Average True Range. The true range of candle i needs the close of candle i-1, so the first candle has
 * none; the first ATR (at index n) is the plain average of the true ranges of candles 1..n, and after that
 * ATR = (previous ATR x (n-1) + today's true range) / n.
 */
export function wilderAtr(candles, n = ATR_N) {
  const out = new Array(candles.length).fill(null);
  let sum = 0;
  let atr = null;
  for (let i = 1; i < candles.length; i++) {
    const { h, l } = candles[i];
    const pc = candles[i - 1].c;
    const tr = Math.max(h - l, Math.abs(h - pc), Math.abs(l - pc));
    if (i < n) sum += tr;
    else if (i === n) atr = (sum + tr) / n;
    else atr = (atr * (n - 1) + tr) / n;
    if (atr != null) out[i] = atr;
  }
  return out;
}

/**
 * Wilder's RSI. The first average gain and loss (at index n) are plain averages of the first n close-to-close
 * changes; after that avg = (previous avg x (n-1) + today's) / n. RSI = 100 - 100 / (1 + avgGain / avgLoss);
 * 100 when there were no losses, 50 when nothing moved at all.
 */
export function wilderRsi(closes, n = RSI_N) {
  const out = new Array(closes.length).fill(null);
  let g = 0;
  let l = 0;
  for (let i = 1; i < closes.length; i++) {
    const d = closes[i] - closes[i - 1];
    const up = d > 0 ? d : 0;
    const dn = d < 0 ? -d : 0;
    if (i <= n) {
      g += up;
      l += dn;
      if (i === n) {
        g /= n;
        l /= n;
      }
    } else {
      g = (g * (n - 1) + up) / n;
      l = (l * (n - 1) + dn) / n;
    }
    if (i >= n) out[i] = l === 0 ? (g === 0 ? 50 : 100) : 100 - 100 / (1 + g / l);
  }
  return out;
}

/**
 * How many big candles in a row, ending at the last one, went in direction dir (1 up, -1 down). A big candle has a
 * true range above the ATR before it (bigger than an average candle at the time, measured the way ATR measures)
 * and closes in that direction both from its own open and from the previous close.
 */
function runAtEnd(visible, atrSeries, dir) {
  let n = 0;
  for (let k = visible.length - 1; k >= 1; k--) {
    const ref = atrSeries[k - 1];
    const { o, h, l, c } = visible[k];
    const pc = visible[k - 1].c;
    const tr = Math.max(h - l, Math.abs(h - pc), Math.abs(l - pc));
    if (ref == null || !(tr > ref && dir * (c - o) > 0 && dir * (c - pc) > 0)) break;
    n++;
  }
  return n;
}

/** ATR and context of the visible candles only (nothing from the hidden future leaks in). */
function analyse(visible) {
  const n = visible.length;
  const closes = visible.map((b) => b.c);
  const last = closes[n - 1];
  const atrSeries = wilderAtr(visible, ATR_N);
  const ret = (k) => (n > k ? last / closes[n - 1 - k] - 1 : null);
  let sma50 = null;
  if (n >= 50) {
    let s = 0;
    for (let i = n - 50; i < n; i++) s += closes[i];
    sma50 = s / 50;
  }
  return {
    atr: atrSeries[n - 1] ?? null,
    atrSeries,
    ctx: {
      ret10: ret(10), // change over the last 10 candles, as a fraction (0.15 = +15%)
      ret30: ret(30),
      rsi14: wilderRsi(closes, RSI_N)[n - 1] ?? null,
      vsSma50: sma50 ? last / sma50 - 1 : null, // last close against its 50-candle average, as a fraction
    },
  };
}

/**
 * What the chart looked like at the moment of the decision: { ctx, atr, upRun, downRun }. upRun/downRun count the
 * big candles (range above 1 ATR, closing that way) in a row at the end of the visible chart.
 */
export function chartSetup(round) {
  const visible = round.candles.slice(0, VISIBLE);
  const a = analyse(visible);
  return {
    ctx: round.ctx ?? a.ctx,
    atr: round.atr ?? a.atr,
    upRun: runAtEnd(visible, a.atrSeries, 1),
    downRun: runAtEnd(visible, a.atrSeries, -1),
  };
}

// ---------------------------------------------------------------------------------------------------------------
// Rounds

/**
 * Longest calendar gap between neighbouring candles that still counts as normal. Crypto trades every day, so more
 * than 3 days means missing data; markets with weekends and holidays get 7 days (the longest NSE break in the
 * data, Dussehra plus a weekend, is 6).
 */
export function gapLimitDays(series) {
  return series?.market === "crypto" ? 3 : 7;
}

function okCandle(s, j) {
  const o = s.o[j];
  const h = s.h[j];
  const l = s.l[j];
  const c = s.c[j];
  for (const v of [o, h, l, c]) if (typeof v !== "number" || !Number.isFinite(v) || v <= 0) return false;
  return Number.isFinite(s.t[j]) && h >= Math.max(o, c) && l <= Math.min(o, c);
}

const startsCache = new WeakMap();

/**
 * Every start index i0 whose window [i0, i0 + WINDOW) has only sane candles and no big gap in time between
 * neighbours, so a round never jumps across missing data. Cached per series object.
 */
export function windowStarts(s) {
  if (s && typeof s === "object" && startsCache.has(s)) return startsCache.get(s);
  const out = [];
  const n = s && Array.isArray(s.t) ? Math.min(s.t.length, s.o?.length ?? 0, s.h?.length ?? 0, s.l?.length ?? 0, s.c?.length ?? 0) : 0;
  if (n >= WINDOW) {
    const limit = gapLimitDays(s);
    let from = 0; // earliest start whose window is clean up to candle j
    for (let j = 0; j < n; j++) {
      if (!okCandle(s, j)) {
        from = j + 1;
        continue;
      }
      if (j > 0) {
        const step = s.t[j] - s.t[j - 1];
        if (!(step > 0 && step <= limit)) from = j; // out of order, duplicate or a big gap: start again here
      }
      if (j - from + 1 >= WINDOW) out.push(j - WINDOW + 1);
    }
  }
  if (s && typeof s === "object") startsCache.set(s, out);
  return out;
}

/** The round that starts at candle i0 of a series (used by pickRound; handy for replays and tests). */
export function makeRound(series, i0) {
  const i1 = i0 + VISIBLE;
  const i2 = i0 + WINDOW;
  if (!Number.isInteger(i0) || i0 < 0 || i2 > series.t.length) throw new RangeError(`makeRound: no ${WINDOW}-candle window at ${i0}`);
  const candles = [];
  for (let j = i0; j < i2; j++) candles.push({ t: series.t[j], o: series.o[j], h: series.h[j], l: series.l[j], c: series.c[j] });
  const a = analyse(candles.slice(0, VISIBLE));
  return { seriesId: series.id, i0, i1, i2, candles, atr: a.atr, ctx: a.ctx, cost: Number.isFinite(series.cost) ? series.cost : 0 };
}

/**
 * A random round. `series` may be the array of series, the whole series.json object, or one series. Each series
 * that has at least one clean window gets the same chance (a long history does not crowd out a short one), then a
 * window is drawn uniformly from that series' clean windows. `rand` is a () => [0,1) function or a seed. Optional
 * filters: { district, market }.
 * Round = { seriesId, i0, i1, i2, candles, atr, ctx: { ret10, ret30, rsi14, vsSma50 }, cost }.
 */
export function pickRound(series, rand = Math.random, { district, market } = {}) {
  let list = Array.isArray(series) ? series : Array.isArray(series?.series) ? series.series : series ? [series] : [];
  if (district) list = list.filter((s) => s.district === district);
  if (market) list = list.filter((s) => s.market === market);
  const next = typeof rand === "function" ? rand : rng(rand);
  const pool = list.filter((s) => windowStarts(s).length > 0);
  if (!pool.length) throw new Error(`pickRound: no series has ${WINDOW} clean candles in a row`);
  for (let tries = 0; tries < 50; tries++) {
    const s = pool[pickIndex(next, pool.length)];
    const starts = windowStarts(s);
    const round = makeRound(s, starts[pickIndex(next, starts.length)]);
    if (round.atr > 0) return round; // a window of frozen prices has no ATR: draw again
  }
  throw new Error("pickRound: could not find a window that moves");
}

// ---------------------------------------------------------------------------------------------------------------
// Trades

const dirOf = (side) => (side === "long" ? 1 : side === "short" ? -1 : 0);

/** Net R of closing the trade at `price`: the price move minus the cost of both sides, over the initial risk. */
function netR(trade, price) {
  const dir = dirOf(trade.side);
  return (dir * (price - trade.entry) - trade.cost * (trade.entry + price)) / trade.risk;
}

/**
 * Plan a trade on a round. side "long" | "short" | "skip"; stopAtr 1..3 (clamped); targetR a positive number
 * (1, 2 or 3 in the game) or null for no target.
 * Trade = { side, entry, stop, target, risk, cost, stopAtr, targetR, moves, bars, status, exit, r, ... } where
 * entry = open of the first hidden candle and risk = |entry - stop|. Extra fields: stop0 (the stop as planned),
 * last (the last price seen), exitBar (which hidden candle it ended on) and setup (the chart context, for
 * detectMistakes). While open, r is the result if closed at the last price; a skip has status "skipped" and r 0.
 */
export function planTrade(round, { side = "skip", stopAtr = 2, targetR = 2 } = {}) {
  const first = round?.candles?.[VISIBLE];
  if (!first) throw new Error("planTrade: the round has no hidden candles");
  const entry = first.o;
  const k = Math.min(3, Math.max(1, Number.isFinite(Number(stopAtr)) ? Number(stopAtr) : 2));
  const tR = targetR == null || !(Number(targetR) > 0) ? null : Number(targetR);
  const trade = {
    side,
    entry,
    stop: null,
    stop0: null,
    target: null,
    risk: 0,
    cost: Number.isFinite(round.cost) ? round.cost : 0,
    stopAtr: k,
    targetR: tR,
    moves: [],
    bars: 0,
    status: "open",
    exit: null,
    exitBar: null,
    r: 0,
    last: entry,
    setup: chartSetup(round),
  };
  if (side === "skip") return { ...trade, status: "skipped" };
  const dir = dirOf(side);
  if (!dir) throw new Error(`planTrade: side must be "long", "short" or "skip", not ${JSON.stringify(side)}`);
  if (!(round.atr > 0)) throw new Error("planTrade: the round has no ATR");
  trade.risk = k * round.atr;
  trade.stop = trade.stop0 = entry - dir * trade.risk;
  trade.target = tR == null ? null : entry + dir * tR * trade.risk;
  trade.r = netR(trade, entry); // closing at once would cost the fees on both sides
  return trade;
}

/** Whether a stop can be moved to `price` now: it must stay on the losing side of the last price seen. */
export function canMoveStop(trade, price) {
  const dir = dirOf(trade?.side);
  if (!dir || trade.status !== "open") return false;
  if (typeof price !== "number" || !Number.isFinite(price) || price <= 0 || price === trade.stop) return false;
  return dir * (trade.last - price) > 0;
}

function finish(t, price, status, bar) {
  t.exit = price;
  t.status = status;
  t.exitBar = bar;
  t.last = price;
  t.r = netR(t, price);
  return t;
}

/**
 * Apply the next hidden candle to an open trade and return a new trade (the input is not changed).
 * action "hold" | "close" | { moveStop: price }:
 * - "close" exits at this candle's open: the first price you could trade at after deciding.
 * - { moveStop } moves the stop before the candle is applied. Every move is recorded in `moves` as
 *   { bar, from, to, wider }; wider = further from the price, i.e. more risk. A move to the wrong side of the last
 *   price is ignored (check with canMoveStop).
 * Then the candle: a gap through the stop or the target fills at the open; if one candle touches both, the stop is
 * assumed to come first (a daily candle cannot tell which came first, so the cautious choice); after FUTURE bars
 * the trade times out at that candle's close.
 */
export function stepTrade(trade, candle, action = "hold") {
  if (!trade || trade.status !== "open" || !candle) return trade;
  const t = { ...trade, moves: trade.moves.slice() };
  const dir = dirOf(t.side);
  const bar = t.bars;
  t.bars = bar + 1;
  if (action === "close") return finish(t, candle.o, "closed", bar);
  if (action && typeof action === "object" && "moveStop" in action) {
    const to = Number(action.moveStop);
    if (canMoveStop(trade, to)) {
      t.moves.push({ bar, from: t.stop, to, wider: dir * (t.stop - to) > 0 });
      t.stop = to;
    }
  }
  const { o, h, l, c } = candle;
  const stop = t.stop;
  const target = t.target;
  if (dir * (o - stop) <= 0) return finish(t, o, "stopped", bar); // opened at or beyond the stop
  if (target != null && dir * (o - target) >= 0) return finish(t, o, "target", bar); // opened at or beyond the target
  if (dir > 0 ? l <= stop : h >= stop) return finish(t, stop, "stopped", bar); // stop first when both are touched
  if (target != null && (dir > 0 ? h >= target : l <= target)) return finish(t, target, "target", bar);
  t.last = c;
  t.r = netR(t, c);
  if (t.bars >= FUTURE) return finish(t, c, "timeout", bar);
  return t;
}

/** The finished trade if the plan is left alone: every hidden candle with "hold" until it ends. */
export function playOut(round, plan) {
  let t = planTrade(round, plan);
  for (let k = 0; k < FUTURE && t.status === "open"; k++) {
    const candle = round.candles[VISIBLE + k];
    if (!candle) break; // a short (test) round: r stays marked at the last close
    t = stepTrade(t, candle, "hold");
  }
  return t;
}

/** The coin flip: average net R of buying and of selling this chart with the same stop and target, no moves. */
export function coinFlipR(round, plan = {}) {
  const { stopAtr, targetR } = plan;
  return (playOut(round, { side: "long", stopAtr, targetR }).r + playOut(round, { side: "short", stopAtr, targetR }).r) / 2;
}

/** Units to trade so that hitting the stop loses riskPct% of cash (before costs; costs come on top, in R). */
export function sizeUnits(cash, riskPct, risk) {
  if (!(cash > 0) || !(riskPct > 0) || !(risk > 0)) return 0;
  return (cash * riskPct) / 100 / risk;
}

// ---------------------------------------------------------------------------------------------------------------
// Mistakes, tilt and stats

/** Title and the idea behind each kind, for result cards and the Cool-down Park lesson card. */
export const LESSONS = {
  fomo: {
    title: "Fear of missing out",
    lesson: "FOMO: people pile into whatever has just made a big, attention-grabbing move (Barber and Odean 2008, \"All That Glitters\"). By then you are buying from the people who got in early.",
  },
  panic: {
    title: "Panic selling",
    lesson: "Panic: fear is loudest right after a sharp fall, and prices that just fell hard have tended to bounce back partly in the following weeks (short-term reversal: Jegadeesh 1990; Lehmann 1990).",
  },
  revenge: {
    title: "Revenge trade",
    lesson: "Revenge trading: after a loss people take more risk to get back to even (the break-even effect, Thaler and Johnson 1990). Even professional futures traders who lost in the morning took more risk in the afternoon (Coval and Shumway 2005).",
  },
  "early-profit": {
    title: "Cut a winner short",
    lesson: "Disposition effect: people sell winners too early and hold losers too long (Shefrin and Statman 1985; Odean 1998). Small wins next to full-size losses add up to a loss.",
  },
  "moved-stop": {
    title: "Moved the stop away",
    lesson: "Loss aversion: a loss hurts about twice as much as an equal gain pleases (Kahneman and Tversky 1979; Tversky and Kahneman 1992), so people move the stop to avoid feeling it. The stop was the plan you made while calm.",
  },
  overtrading: {
    title: "Overtrading",
    lesson: "Overtrading: the households that traded the most earned 11.4% a year against 17.9% for the market (Barber and Odean 2000, \"Trading Is Hazardous to Your Wealth\"). Staying out is a decision too.",
  },
  chasing: {
    title: "Chasing",
    lesson: "Chasing: people expect a recent move to carry on (extrapolation, Greenwood and Shleifer 2014). After several big candles the move is old news, and a sensible stop sits far away.",
  },
  discipline: {
    title: "Discipline",
    lesson: "Process over outcome: judge a decision by the plan behind it, not by one result (Annie Duke, \"Thinking in Bets\", 2018). Exits set in advance and left alone keep in-the-moment feelings out of the trade.",
  },
};

/** Severity used when a history entry stores a mistake as a bare kind string. */
const DEFAULT_SEVERITY = { fomo: 2, panic: 2, revenge: 2, "early-profit": 2, "moved-stop": 2, overtrading: 1, chasing: 2, lottery: 2, "chasing-losses": 2 };

const pct = (x) => `${Math.round(Math.abs(x) * 100)}%`;
const fmtR = (r) => `${r < 0 ? "-" : "+"}${Math.abs(r).toFixed(1)}R`;
const fmtPrice = (p) => (Math.abs(p) >= 1000 ? Math.round(p).toLocaleString("en-US") : String(Number(p.toPrecision(4))));
const joinAnd = (parts) => (parts.length < 2 ? parts.join("") : `${parts.slice(0, -1).join(", ")} and ${parts.at(-1)}`);
const note = (kind, severity, message) => ({ kind, severity, title: LESSONS[kind].title, message, lesson: LESSONS[kind].lesson });

const isChartEntry = (h) => h && (h.kind == null || h.kind === "chart" || h.kind === "mission");
const isTradeSide = (side) => side === "long" || side === "short";

function toMs(v) {
  if (v instanceof Date) return v.getTime();
  if (typeof v === "number" && Number.isFinite(v)) return v < 1e11 ? v * 1000 : v; // seconds or milliseconds
  if (typeof v === "string") {
    const ms = Date.parse(v);
    return Number.isFinite(ms) ? ms : null;
  }
  return null;
}

/** A finished mission that lost game cash: a chart trade with r < 0, or (other kinds) cash going down. */
function isLoss(h) {
  if (!h || h.kind === "cooldown") return false;
  if (isChartEntry(h)) return isTradeSide(h.side) && Number.isFinite(h.r) && h.r < 0;
  return Number.isFinite(h.cashAfter) && Number.isFinite(h.cashBefore) && h.cashAfter < h.cashBefore;
}

/** Why the chart counts as stretched, in plain words, for each direction. */
function stretchReasons(setup) {
  const { ret10, rsi14 } = setup?.ctx ?? {};
  const hot = [];
  const cold = [];
  if (ret10 > STRETCH_RET10) hot.push(`it had already risen ${pct(ret10)} in 10 days`);
  if (rsi14 > RSI_HOT) hot.push(`RSI was ${Math.round(rsi14)} (overheated: above ${RSI_HOT})`);
  if (ret10 < -STRETCH_RET10) cold.push(`it had already fallen ${pct(ret10)} in 10 days`);
  if (rsi14 < RSI_COLD) cold.push(`RSI was ${Math.round(rsi14)} (washed out: below ${RSI_COLD})`);
  return { hot, cold, upRun: setup?.upRun ?? 0, downRun: setup?.downRun ?? 0 };
}

/**
 * The emotional mistakes (and the good habits) in one decision. `history` = the missions before this one;
 * `decision` = { side, stopAtr, targetR, round?, at? } where round is the Round traded (or pass setup/ctx), and at
 * is when the decision was made (ms), which lets "revenge" spot a trade taken straight after a loss; `trade` = the
 * trade from planTrade/stepTrade (finished, or null for a skip). The chart context falls back to trade.setup.
 * Returns [{ kind, severity, title, message, lesson }]: mistakes first (most severe first), then a "discipline"
 * note with severity 0 and good: true when earned.
 */
export function detectMistakes(history = [], decision = {}, trade = null) {
  const hist = Array.isArray(history) ? history : [];
  const d = decision ?? {};
  const side = d.side ?? trade?.side ?? "skip";
  const setup = d.round ? chartSetup(d.round) : d.setup ?? trade?.setup ?? (d.ctx ? { ctx: d.ctx, upRun: 0, downRun: 0 } : null);
  const stopAtr = Number(d.stopAtr ?? trade?.stopAtr);
  const targetR = d.targetR !== undefined ? d.targetR : trade?.targetR;
  const st = stretchReasons(setup);
  const trading = isTradeSide(side);
  const out = [];

  // Entry: buying a chart that has already flown, or betting on a fall after a crash.
  if (side === "long" && st.hot.length) out.push(note("fomo", st.hot.length > 1 ? 3 : 2, `You bought when ${joinAnd(st.hot)}: that is the fear of missing out talking.`));
  if (side === "short" && st.cold.length) out.push(note("panic", st.cold.length > 1 ? 3 : 2, `You bet on a fall when ${joinAnd(st.cold)}: selling into a crash is panic.`));

  // Entry: several big candles in a row in the same direction as the trade.
  const run = side === "long" ? st.upRun : side === "short" ? st.downRun : 0;
  if (run >= CHASE_RUN) {
    const word = side === "long" ? "bought after" : "bet on a fall after";
    const kind = side === "long" ? "up" : "down";
    out.push(note("chasing", run >= 5 ? 3 : 2, `You ${word} ${run} big ${kind} candles in a row (each bigger than an average candle): you were chasing the move.`));
  }

  // Revenge: right after a loss, a wider stop, a trade within two minutes, or carrying on through a losing streak.
  const prev = hist.at(-1);
  if (trading && isLoss(prev)) {
    let streak = 0;
    for (let i = hist.length - 1; i >= 0 && isLoss(hist[i]); i--) streak++;
    const wider = isChartEntry(prev) && Number.isFinite(stopAtr) && Number.isFinite(prev.stopAtr) && stopAtr > prev.stopAtr + EPS;
    const now = toMs(d.at);
    const then = toMs(prev.at);
    const gap = now != null && then != null ? now - then : null;
    const quick = gap != null && gap >= 0 && gap < REVENGE_MS;
    const parts = [];
    if (wider) parts.push(`widened your stop from ${prev.stopAtr} to ${stopAtr} ATR`);
    if (quick) parts.push(`jumped back in after only ${Math.max(1, Math.round(gap / 1000))} seconds`);
    if (wider || quick || streak >= 2) {
      let sev = Math.max(wider ? 2 : 0, quick ? 1 : 0, streak >= 3 ? 2 : streak >= 2 ? 1 : 0);
      if (wider && (quick || streak >= 2)) sev += 1;
      const lead = streak >= 2 ? `Straight after ${streak} losses in a row you` : "Right after a loss you";
      out.push(note("revenge", Math.min(3, sev), `${lead} ${parts.length ? joinAnd(parts) : "traded again"}: that is trying to win it back.`));
    }
  }

  // Overtrading: ten chart decisions in a row (this one included) without staying out once.
  if (trading) {
    let n = 1;
    for (let i = hist.length - 1; i >= 0; i--) {
      const h = hist[i];
      if (!isChartEntry(h)) continue; // other missions (the Strip, Cool-down Park) neither count nor reset
      if (!isTradeSide(h.side)) break;
      n++;
    }
    if (n >= OVERTRADE_RUN) out.push(note("overtrading", n >= 2 * OVERTRADE_RUN ? 2 : 1, `You traded ${n} charts in a row without staying out once: not every chart is worth a trade.`));
  }

  // Management: moving the stop further away, and closing a small winner when the plan aimed for 2R or more.
  if (trade && trading) {
    const wider = (trade.moves ?? []).filter((m) => m.wider);
    if (wider.length) {
      const dir = dirOf(side);
      const first = wider[0];
      const lastTo = wider.at(-1).to;
      const worse = trade.exit != null && trade.stop0 != null && dir * (trade.exit - trade.stop0) < -EPS; // lost more than planned
      const times = wider.length > 1 ? ` ${wider.length} times` : "";
      const tail = worse ? `, and the loss ended bigger than you planned (${fmtR(trade.r)})` : `: your planned loss got bigger`;
      out.push(note("moved-stop", worse ? 3 : 2, `You moved your stop further away${times} (from ${fmtPrice(first.from)} to ${fmtPrice(lastTo)})${tail}.`));
    }
    if (trade.status === "closed" && trade.r > 0 && trade.r < 1 && Number(targetR) >= 2) {
      out.push(note("early-profit", 2, `You closed a winner at ${fmtR(trade.r)} when your target was ${Number(targetR)}R: small wins next to full-size losses do not add up.`));
    }
  }

  out.sort((a, b) => b.severity - a.severity);

  // Good habits: staying out of a stretched chart, or letting the stop and target work untouched.
  if (side === "skip") {
    const why = st.hot[0] ?? st.cold[0] ?? (st.upRun >= CHASE_RUN ? `${st.upRun} big up candles in a row` : st.downRun >= CHASE_RUN ? `${st.downRun} big down candles in a row` : null);
    if (why) out.push({ ...note("discipline", 0, `You stayed out of a stretched chart (${why}): doing nothing was a good decision.`), good: true });
  } else if (trade && trading && ["stopped", "target", "timeout"].includes(trade.status) && !(trade.moves ?? []).length) {
    const msg = trade.status === "timeout" ? "You stuck to your plan until time ran out, without touching the stop." : trade.target == null ? "You let your stop do its job without touching it." : "You let your stop and target do their job without touching them.";
    out.push({ ...note("discipline", 0, msg), good: true });
  }
  return out;
}

/** Points and the good-habit flag of one mission's mistakes (objects or bare kind strings). */
function scoreMistakes(mistakes) {
  let pts = 0;
  let good = false;
  for (const m of Array.isArray(mistakes) ? mistakes : []) {
    const kind = typeof m === "string" ? m : m?.kind;
    if (kind === "discipline" || m?.good) {
      good = true;
      continue;
    }
    const sev = typeof m === "object" && Number.isFinite(m?.severity) ? m.severity : DEFAULT_SEVERITY[kind] ?? 1;
    pts += Math.max(0, sev);
  }
  return { pts, good };
}

/**
 * Tilt 0..100: each mistake adds 10 points per severity point; a mission with no mistakes keeps 60% of the tilt
 * minus 4 points (minus 8 when it also earned a discipline note). Only the last 40 missions count. Entries of any
 * kind count (the Strip's mistakes too); an optional { kind: "cooldown", relief } entry takes `relief` points off
 * (half the tilt when relief is not given).
 */
export function tilt(history = []) {
  let t = 0;
  for (const h of (Array.isArray(history) ? history : []).slice(-TILT_WINDOW)) {
    if (h?.kind === "cooldown") {
      t = Number.isFinite(h.relief) ? t - h.relief : t / 2;
    } else {
      const { pts, good } = scoreMistakes(h?.mistakes);
      t = pts > 0 ? t + TILT_PER_POINT * pts : t * TILT_DECAY - (good ? 2 * TILT_CLEAN_DROP : TILT_CLEAN_DROP);
    }
    t = Math.min(100, Math.max(0, t));
  }
  return Math.round(t);
}

const mean = (xs) => xs.reduce((a, b) => a + b, 0) / xs.length;

/**
 * Totals for the HUD and the stats screen. Trade figures use chart missions only; edgeR is the average of
 * (your R - the coin flip's R) over the same trades, and t is its t-statistic (about 2 or more is when an edge
 * starts to look like more than luck; null with fewer than 2 trades). Cash covers every kind of mission.
 * -> { rounds, trades, skips, wins, winRate, avgR, totalR, coinFlipAvgR, edgeR, t, cashStart, cash, mistakes, discipline }
 */
export function stats(history = [], startCash = START_CASH) {
  const hist = Array.isArray(history) ? history : [];
  const chart = hist.filter(isChartEntry);
  const trades = chart.filter((h) => isTradeSide(h.side) && Number.isFinite(h.r));
  const skips = chart.filter((h) => h.side === "skip").length;
  const rs = trades.map((h) => h.r);
  const wins = rs.filter((r) => r > 0).length;
  const paired = trades.filter((h) => Number.isFinite(h.coinR));
  const diffs = paired.map((h) => h.r - h.coinR);
  let t = null;
  if (diffs.length >= 2) {
    const m = mean(diffs);
    const sd = Math.sqrt(diffs.reduce((a, x) => a + (x - m) ** 2, 0) / (diffs.length - 1));
    if (sd > 0) t = m / (sd / Math.sqrt(diffs.length));
  }
  const mistakes = {};
  let discipline = 0;
  for (const h of hist) {
    for (const m of Array.isArray(h?.mistakes) ? h.mistakes : []) {
      const kind = typeof m === "string" ? m : m?.kind;
      if (!kind) continue;
      if (kind === "discipline" || m?.good) discipline++;
      else mistakes[kind] = (mistakes[kind] ?? 0) + 1;
    }
  }
  const firstCash = hist.find((h) => Number.isFinite(h?.cashBefore))?.cashBefore;
  let lastCash;
  for (let i = hist.length - 1; i >= 0 && lastCash === undefined; i--) if (Number.isFinite(hist[i]?.cashAfter)) lastCash = hist[i].cashAfter;
  const cashStart = firstCash ?? startCash;
  return {
    rounds: trades.length + skips,
    trades: trades.length,
    skips,
    wins,
    winRate: trades.length ? wins / trades.length : null,
    avgR: trades.length ? mean(rs) : null,
    totalR: rs.reduce((a, b) => a + b, 0),
    coinFlipAvgR: paired.length ? mean(paired.map((h) => h.coinR)) : null,
    edgeR: diffs.length ? mean(diffs) : null,
    t,
    cashStart,
    cash: lastCash ?? cashStart,
    mistakes,
    discipline,
  };
}
