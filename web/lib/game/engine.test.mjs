// Tests for the Candle City engine. Run from the repo root: node --test web/lib/game/*.test.mjs
// Synthetic candles with known outcomes, plus sanity checks on the real web/public/game/series.json when present.
import test from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import * as E from "./engine.js";

const { VISIBLE, FUTURE, WINDOW } = E;

const near = (a, b, eps = 1e-9, msg = "") => assert.ok(Math.abs(a - b) <= eps, `${msg} expected ${b}, got ${a}`);
const C = (o, h, l, c) => ({ o, h, l, c });

/** A series from candles (t = consecutive days unless given). */
function seriesOf(candles, extra = {}) {
  const s = { id: "test", name: "Test", market: "crypto", cost: 0, t: [], o: [], h: [], l: [], c: [], ...extra };
  candles.forEach((b, i) => {
    s.t.push(b.t ?? 18000 + i);
    s.o.push(b.o);
    s.h.push(b.h);
    s.l.push(b.l);
    s.c.push(b.c);
  });
  return s;
}

/** Calm candles: open = close = p, high p+1, low p-1. Every true range is 2, so ATR = 2 exactly; RSI = 50. */
const calm = (n = VISIBLE, p = 100) => Array.from({ length: n }, () => C(p, p + 1, p - 1, p));

/** A round with a calm visible chart (ATR 2) and these hidden candles, padded with quiet candles to FUTURE. */
function roundWith(hidden, { cost = 0 } = {}) {
  const fut = hidden.slice();
  while (fut.length < FUTURE) {
    const p = fut.length ? fut.at(-1).c : 100;
    fut.push(C(p, p + 0.25, p - 0.25, p));
  }
  return E.makeRound(seriesOf([...calm(), ...fut], { cost }), 0);
}

/** Apply candles one by one with the given actions (default "hold"). */
function run(trade, candles, actions = []) {
  let t = trade;
  candles.forEach((c, i) => {
    t = E.stepTrade(t, c, actions[i] ?? "hold");
  });
  return t;
}

/** The hidden candles of a round, in order. */
const hiddenOf = (round) => round.candles.slice(VISIBLE);

// ---------------------------------------------------------------------------------------------------------------
test("rng: mulberry32, repeatable, in [0, 1)", () => {
  // Reference mulberry32 (Tommy Ettinger's algorithm as commonly published).
  function ref(a) {
    return () => {
      let t = (a += 0x6d2b79f5);
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  for (const seed of [0, 1, 42, 123456789, 4294967295]) {
    const a = E.rng(seed);
    const b = ref(seed);
    for (let i = 0; i < 50; i++) assert.equal(a(), b());
  }
  const a = E.rng(7);
  const b = E.rng(7);
  const xs = Array.from({ length: 10000 }, () => a());
  assert.deepEqual(xs.slice(0, 20), Array.from({ length: 20 }, () => b()));
  assert.ok(xs.every((x) => x >= 0 && x < 1));
  near(xs.reduce((s, x) => s + x, 0) / xs.length, 0.5, 0.02, "mean");
  assert.notEqual(E.rng(1)(), E.rng(2)());
  assert.equal(E.rng("monday")(), E.rng("monday")());
  assert.notEqual(E.rng("monday")(), E.rng("tuesday")());
});

// ---------------------------------------------------------------------------------------------------------------
test("wilderRsi matches the StockCharts worked example", () => {
  const closes = [44.3389, 44.0902, 44.1497, 43.6124, 44.3278, 44.8264, 45.0955, 45.4245, 45.8433, 46.0826, 45.8931, 46.0328, 45.614, 46.282, 46.282, 46.0028, 46.0328, 46.4116, 46.2222, 45.6439, 46.2122, 46.2521, 45.7137, 46.4515, 45.7835, 45.3548, 44.0288, 44.1783, 44.2181, 44.5672, 43.4205, 42.6628, 43.1314];
  const expected = [70.53, 66.32, 66.55, 69.41, 66.36, 57.97, 62.93, 63.26, 56.06, 62.38, 54.71, 50.42, 39.99, 41.46, 41.87, 45.46, 37.3, 33.08, 37.77];
  const rsi = E.wilderRsi(closes);
  assert.ok(rsi.slice(0, 14).every((v) => v === null), "null while warming up");
  rsi.slice(14).forEach((v, i) => near(v, expected[i], 0.005, `RSI[${i + 14}]`));
});

test("wilderRsi edge cases: all up 100, all down 0, flat 50", () => {
  const up = Array.from({ length: 30 }, (_, i) => 100 + i);
  assert.equal(E.wilderRsi(up).at(-1), 100);
  assert.equal(E.wilderRsi(up.slice().reverse()).at(-1), 0);
  assert.equal(E.wilderRsi(Array(30).fill(5)).at(-1), 50);
});

test("wilderAtr: hand-computed example (n = 3) and gaps count", () => {
  const bars = [
    { h: 10, l: 9, c: 9.5 },
    { h: 11, l: 10, c: 10.5 }, // TR = max(1, 1.5, 0.5) = 1.5
    { h: 10.8, l: 10, c: 10.2 }, // TR = max(0.8, 0.3, 0.5) = 0.8
    { h: 12, l: 10.1, c: 11.9 }, // TR = 1.9 -> first ATR = (1.5 + 0.8 + 1.9) / 3 = 1.4
    { h: 11.5, l: 9.9, c: 10 }, // TR = max(1.6, 0.4, 2.0) = 2.0 -> (1.4 * 2 + 2) / 3 = 1.6
    { h: 13.5, l: 12.8, c: 13.2 }, // gap up: TR = max(0.7, 3.5, 2.8) = 3.5 -> (1.6 * 2 + 3.5) / 3
  ];
  const atr = E.wilderAtr(bars, 3);
  assert.deepEqual(atr.slice(0, 3), [null, null, null]);
  near(atr[3], 1.4);
  near(atr[4], 1.6);
  near(atr[5], (1.6 * 2 + 3.5) / 3);
});

test("wilderAtr (14) agrees with a straightforward reference on random candles", () => {
  const rand = E.rng(99);
  const bars = [];
  let p = 100;
  for (let i = 0; i < 200; i++) {
    const o = p * (1 + (rand() - 0.5) * 0.04); // gaps
    const c = o * (1 + (rand() - 0.5) * 0.05);
    bars.push({ o, h: Math.max(o, c) * (1 + rand() * 0.02), l: Math.min(o, c) * (1 - rand() * 0.02), c });
    p = c;
  }
  const tr = bars.map((b, i) => (i ? Math.max(b.h - b.l, Math.abs(b.h - bars[i - 1].c), Math.abs(b.l - bars[i - 1].c)) : null));
  const ref = [];
  for (let i = 0; i < bars.length; i++) {
    if (i < 14) ref.push(null);
    else if (i === 14) ref.push(tr.slice(1, 15).reduce((a, b) => a + b, 0) / 14);
    else ref.push((ref[i - 1] * 13 + tr[i]) / 14);
  }
  const atr = E.wilderAtr(bars);
  atr.forEach((v, i) => (ref[i] === null ? assert.equal(v, null) : near(v, ref[i], 1e-9)));
});

// ---------------------------------------------------------------------------------------------------------------
test("makeRound: window shape, ATR and context from the visible candles only", () => {
  // A steady ramp: close = 100 + i, open = previous close, high = close + 0.5, low = open - 0.5 -> TR = 2.
  const candles = Array.from({ length: 200 }, (_, i) => {
    const c = 100 + i;
    const o = i ? 99 + i : 100;
    return C(o, c + 0.5, o - 0.5, c);
  });
  const s = seriesOf(candles, { id: "ramp", cost: 0.0012 });
  const r = E.makeRound(s, 10);
  assert.equal(r.seriesId, "ramp");
  assert.equal(r.i0, 10);
  assert.equal(r.i1, 10 + VISIBLE);
  assert.equal(r.i2, 10 + WINDOW);
  assert.equal(r.candles.length, WINDOW);
  assert.equal(r.cost, 0.0012);
  r.candles.forEach((b, k) => assert.deepEqual(b, { t: s.t[10 + k], o: s.o[10 + k], h: s.h[10 + k], l: s.l[10 + k], c: s.c[10 + k] }));
  near(r.atr, 2);
  const last = 100 + 10 + VISIBLE - 1; // close of the last visible candle (index 99 -> 199)
  near(r.ctx.ret10, last / (last - 10) - 1);
  near(r.ctx.ret30, last / (last - 30) - 1);
  near(r.ctx.vsSma50, last / (last - 24.5) - 1); // average of the last 50 closes = last - 24.5
  assert.equal(r.ctx.rsi14, 100); // no down closes
  assert.throws(() => E.makeRound(s, 200 - WINDOW + 1), RangeError);
});

test("no look-ahead: the hidden future and the past before the window do not change atr or ctx", () => {
  const rand = E.rng(5);
  const candles = [];
  let p = 50;
  for (let i = 0; i < 300; i++) {
    const c = p * (1 + (rand() - 0.5) * 0.06);
    candles.push(C(p, Math.max(p, c) * 1.01, Math.min(p, c) * 0.99, c));
    p = c;
  }
  const s = seriesOf(candles);
  const a = E.makeRound(s, 100);
  const s2 = structuredClone(s);
  for (let j = 0; j < 100; j++) s2.c[j] *= 3; // the past before i0
  for (let j = 190; j < 300; j++) {
    s2.h[j] *= 2; // the hidden future and beyond
    s2.c[j] *= 1.5;
  }
  const b = E.makeRound(s2, 100);
  assert.equal(b.atr, a.atr);
  assert.deepEqual(b.ctx, a.ctx);
});

test("windowStarts: skips big gaps, bad candles and out-of-order dates", () => {
  const base = calm(300);
  const plain = seriesOf(base);
  assert.equal(E.windowStarts(plain).length, 300 - WINDOW + 1);

  // A 10-day hole between candle 149 and 150: windows must sit wholly on one side.
  const gap = seriesOf(base.map((b, i) => ({ ...b, t: 18000 + i + (i >= 150 ? 10 : 0) })));
  const starts = E.windowStarts(gap);
  assert.equal(starts.length, 31 + 31);
  assert.ok(starts.every((i0) => i0 + WINDOW - 1 <= 149 || i0 >= 150));

  // Gap limits: 5 days is a long weekend for a stock market but missing data for crypto.
  const five = base.map((b, i) => ({ ...b, t: 18000 + i + (i >= 150 ? 4 : 0) }));
  assert.equal(E.windowStarts(seriesOf(five, { market: "india" })).length, 300 - WINDOW + 1);
  assert.equal(E.windowStarts(seriesOf(five, { market: "crypto" })).length, 62);
  assert.equal(E.gapLimitDays({ market: "crypto" }), 3);
  assert.equal(E.gapLimitDays({ market: "india" }), 7);

  // A broken candle (zero, NaN, high below low) cuts the series in two, as does a date going backwards.
  for (const bad of [C(0, 1, 0, 1), C(NaN, 101, 99, 100), C(100, 99, 101, 100)]) {
    const s = seriesOf(base.map((b, i) => (i === 150 ? bad : b)));
    const st = E.windowStarts(s);
    assert.equal(st.length, 31 + 30, JSON.stringify(bad));
    assert.ok(st.every((i0) => i0 + WINDOW - 1 < 150 || i0 > 150));
  }
  const back = seriesOf(base.map((b, i) => ({ ...b, t: i === 150 ? 18000 + 140 : 18000 + i })));
  assert.ok(E.windowStarts(back).every((i0) => i0 + WINDOW - 1 <= 149 || i0 >= 151));

  assert.deepEqual(E.windowStarts(seriesOf(calm(WINDOW - 1))), []);
});

test("pickRound never straddles a gap and returns well-formed rounds", () => {
  const base = calm(400).map((b, i) => ({ ...b, t: 18000 + i + (i >= 200 ? 30 : 0) }));
  // Some movement so the ATR is not constant and the windows differ.
  base.forEach((b, i) => {
    b.c = b.o = 100 + Math.sin(i / 7) * 5;
    b.h = b.c + 1;
    b.l = b.c - 1;
  });
  const s = seriesOf(base, { id: "gappy" });
  for (let seed = 0; seed < 500; seed++) {
    const r = E.pickRound([s], E.rng(seed));
    assert.equal(r.candles.length, WINDOW);
    assert.ok(r.i2 <= 200 || r.i0 >= 200, `window ${r.i0}..${r.i2} straddles the gap`);
    for (let k = 1; k < WINDOW; k++) assert.ok(r.candles[k].t - r.candles[k - 1].t <= 3);
    assert.ok(r.atr > 0);
  }
  assert.deepEqual(E.pickRound(s, E.rng(3)), E.pickRound([s], E.rng(3)), "a single series works");
  assert.deepEqual(E.pickRound({ series: [s] }, 3), E.pickRound([s], E.rng(3)), "the data object and a number seed work");
});

test("pickRound gives every series the same chance, whatever its length", () => {
  const wave = (n) => Array.from({ length: n }, (_, i) => {
    const p = 100 + Math.sin(i / 5) * 3;
    return C(p, p + 1, p - 1, p);
  });
  const long = seriesOf(wave(5000), { id: "long" });
  const short = seriesOf(wave(WINDOW + 10), { id: "short" }); // 11 windows only
  const tiny = seriesOf(wave(WINDOW - 1), { id: "tiny" }); // no window at all: never picked
  const rand = E.rng(2024);
  const count = { long: 0, short: 0, tiny: 0 };
  const shortStarts = new Set();
  const N = 4000;
  for (let i = 0; i < N; i++) {
    const r = E.pickRound([long, short, tiny], rand);
    count[r.seriesId]++;
    if (r.seriesId === "short") shortStarts.add(r.i0);
  }
  assert.equal(count.tiny, 0);
  assert.ok(count.short / N > 0.45 && count.short / N < 0.55, `short picked ${count.short} of ${N}`);
  assert.equal(shortStarts.size, 11, "every window of the short series comes up");
  assert.throws(() => E.pickRound([tiny], rand), /no series/);
  // District filter.
  const a = { ...long, id: "a", district: "docks" };
  const b = { ...short, id: "b", district: "market" };
  for (let i = 0; i < 50; i++) assert.equal(E.pickRound([a, b], rand, { district: "market" }).seriesId, "b");
});

test("pickRound skips windows whose prices never move (no ATR)", () => {
  const frozen = seriesOf(Array.from({ length: 300 }, () => C(5, 5, 5, 5)), { id: "frozen" });
  const live = seriesOf(Array.from({ length: 300 }, (_, i) => C(100 + (i % 3), 102 + (i % 3), 99 + (i % 3), 100 + (i % 3))), { id: "live" });
  for (let seed = 0; seed < 100; seed++) {
    const r = E.pickRound([frozen, live], E.rng(seed));
    assert.equal(r.seriesId, "live");
    assert.ok(r.atr > 0);
  }
  assert.throws(() => E.pickRound([frozen], E.rng(1)), /moves/);
});

// ---------------------------------------------------------------------------------------------------------------
test("planTrade: entry at the first hidden open, stop and target from ATR and R", () => {
  const round = roundWith([C(100, 101, 99, 100)]);
  assert.equal(round.atr, 2);
  const long = E.planTrade(round, { side: "long", stopAtr: 1, targetR: 2 });
  assert.equal(long.entry, 100);
  assert.equal(long.stop, 98);
  assert.equal(long.stop0, 98);
  assert.equal(long.target, 104);
  assert.equal(long.risk, 2);
  assert.equal(long.cost, 0);
  assert.equal(long.status, "open");
  assert.equal(long.bars, 0);
  assert.deepEqual(long.moves, []);
  assert.equal(long.r, 0);

  const short = E.planTrade(round, { side: "short", stopAtr: 1.5, targetR: 3 });
  assert.equal(short.stop, 103);
  assert.equal(short.target, 91);
  assert.equal(short.risk, 3);

  assert.equal(E.planTrade(round, { side: "long", stopAtr: 2, targetR: null }).target, null);
  assert.equal(E.planTrade(round, { side: "long", stopAtr: 0.2, targetR: 1 }).stopAtr, 1, "stopAtr clamped to 1..3");
  assert.equal(E.planTrade(round, { side: "long", stopAtr: 9, targetR: 1 }).risk, 6);

  const skip = E.planTrade(round, { side: "skip" });
  assert.equal(skip.status, "skipped");
  assert.equal(skip.r, 0);
  assert.equal(E.stepTrade(skip, round.candles[VISIBLE]), skip);
  assert.throws(() => E.planTrade(round, { side: "sideways" }));

  // With costs, closing at once costs both sides: 0.1% x (100 + 100) / 2 = 0.1R.
  const costly = E.planTrade(roundWith([C(100, 101, 99, 100)], { cost: 0.001 }), { side: "long", stopAtr: 1, targetR: 2 });
  near(costly.r, -0.1);
});

test("stepTrade long: target and stop inside a candle, stop first when both are touched", () => {
  const plan = { side: "long", stopAtr: 1, targetR: 2 }; // entry 100, stop 98, target 104
  let round = roundWith([C(100, 101, 99.5, 100.5), C(100.5, 104.5, 100, 104.2)]);
  let t = E.stepTrade(E.planTrade(round, plan), round.candles[VISIBLE]);
  assert.equal(t.status, "open");
  assert.equal(t.bars, 1);
  assert.equal(t.last, 100.5);
  near(t.r, 0.25, 1e-9, "open trade is marked at the last close");
  t = E.stepTrade(t, round.candles[VISIBLE + 1]);
  assert.equal(t.status, "target");
  assert.equal(t.exit, 104);
  assert.equal(t.exitBar, 1);
  assert.equal(t.bars, 2);
  near(t.r, 2);

  round = roundWith([C(100, 100.5, 97.5, 98.5)]);
  t = run(E.planTrade(round, plan), hiddenOf(round).slice(0, 1));
  assert.equal(t.status, "stopped");
  assert.equal(t.exit, 98);
  near(t.r, -1);

  round = roundWith([C(100, 105, 97, 101)]); // touches both 98 and 104
  t = run(E.planTrade(round, plan), hiddenOf(round).slice(0, 1));
  assert.equal(t.status, "stopped");
  assert.equal(t.exit, 98);
});

test("stepTrade long: a gap through a level fills at the open", () => {
  const plan = { side: "long", stopAtr: 1, targetR: 2 };
  let round = roundWith([C(100, 101, 99, 100), C(96, 97, 95, 96.5)]);
  let t = run(E.planTrade(round, plan), hiddenOf(round).slice(0, 2));
  assert.equal(t.status, "stopped");
  assert.equal(t.exit, 96, "gapped below the stop: filled at the open, worse than the stop");
  near(t.r, -2);

  round = roundWith([C(100, 101, 99, 100), C(106, 107, 105, 106.5)]);
  t = run(E.planTrade(round, plan), hiddenOf(round).slice(0, 2));
  assert.equal(t.status, "target");
  assert.equal(t.exit, 106, "gapped above the target: filled at the open, better than the target");
  near(t.r, 3);

  round = roundWith([C(100, 101, 99, 100), C(98, 99, 97.5, 98.8)]);
  t = run(E.planTrade(round, plan), hiddenOf(round).slice(0, 2));
  assert.equal(t.status, "stopped");
  assert.equal(t.exit, 98, "opening exactly at the stop");
});

test("stepTrade short: the mirror image", () => {
  const plan = { side: "short", stopAtr: 1, targetR: 2 }; // entry 100, stop 102, target 96
  const cases = [
    [[C(100, 100.5, 95.5, 96.2)], "target", 96, 2],
    [[C(100, 102.5, 99, 101)], "stopped", 102, -1],
    [[C(100, 103, 95, 99)], "stopped", 102, -1], // both touched: stop first
    [[C(100, 101, 99, 100), C(104, 105, 103.5, 104)], "stopped", 104, -2], // gap up through the stop
    [[C(100, 101, 99, 100), C(93, 94, 92, 93.5)], "target", 93, 3.5], // gap down through the target
  ];
  for (const [hidden, status, exit, r] of cases) {
    const round = roundWith(hidden);
    const t = run(E.planTrade(round, plan), hidden);
    assert.equal(t.status, status, JSON.stringify(hidden));
    assert.equal(t.exit, exit);
    near(t.r, r);
  }
});

test("R is net of costs on both sides", () => {
  const cost = 0.001;
  let round = roundWith([C(100, 104.5, 99.5, 104)], { cost });
  let t = run(E.planTrade(round, { side: "long", stopAtr: 1, targetR: 2 }), hiddenOf(round).slice(0, 1));
  near(t.r, (4 - cost * (100 + 104)) / 2); // 1.898R
  round = roundWith([C(100, 102.5, 99, 101)], { cost });
  t = run(E.planTrade(round, { side: "short", stopAtr: 1, targetR: 2 }), hiddenOf(round).slice(0, 1));
  near(t.r, (-2 - cost * (100 + 102)) / 2); // -1.101R
});

test("timeout after FUTURE bars at that candle's close", () => {
  const hidden = Array.from({ length: FUTURE }, (_, k) => {
    const p = 100 + 0.05 * k;
    return C(p, p + 0.5, p - 0.5, p + 0.05);
  });
  const round = roundWith(hidden);
  let t = E.planTrade(round, { side: "long", stopAtr: 1, targetR: 2 });
  for (let k = 0; k < FUTURE; k++) {
    assert.equal(t.status, "open", `still open before bar ${k}`);
    t = E.stepTrade(t, hidden[k]);
  }
  assert.equal(t.status, "timeout");
  assert.equal(t.bars, FUTURE);
  assert.equal(t.exitBar, FUTURE - 1);
  assert.equal(t.exit, hidden[FUTURE - 1].c);
  near(t.r, (hidden[FUTURE - 1].c - 100) / 2);
  assert.equal(E.stepTrade(t, hidden[0]), t, "a finished trade ignores more candles");
});

test("close exits at the open of the next candle", () => {
  const hidden = [C(100, 100.8, 99.6, 100.4), C(100.4, 101, 100, 100.9), C(101.2, 101.5, 100.5, 101)];
  const round = roundWith(hidden);
  const t = run(E.planTrade(round, { side: "long", stopAtr: 1, targetR: 2 }), hidden, ["hold", "hold", "close"]);
  assert.equal(t.status, "closed");
  assert.equal(t.exit, 101.2);
  assert.equal(t.exitBar, 2);
  assert.equal(t.bars, 3);
  near(t.r, 0.6);
});

test("moving a stop: wider moves are allowed and recorded, wrong-side moves ignored", () => {
  const hidden = [C(100, 100.8, 99.6, 100.5), C(100.4, 100.6, 97, 98), C(97.5, 98, 95, 95.5)];
  const round = roundWith(hidden);
  const start = E.planTrade(round, { side: "long", stopAtr: 1, targetR: 2 });
  const frozen = structuredClone(start);
  let t = E.stepTrade(start, hidden[0]);
  assert.deepEqual(start, frozen, "stepTrade does not change its input");

  assert.equal(E.canMoveStop(t, 101), false, "a long stop above the last price");
  const same = E.stepTrade(t, hidden[1], { moveStop: 101 });
  assert.deepEqual(same.moves, []);
  assert.equal(same.status, "stopped", "the ignored move left the stop at 98");
  assert.equal(same.exit, 98);

  assert.equal(E.canMoveStop(t, 96), true);
  t = E.stepTrade(t, hidden[1], { moveStop: 96 }); // low 97 would have hit 98, not 96
  assert.equal(t.status, "open");
  assert.equal(t.stop, 96);
  assert.equal(t.stop0, 98);
  assert.deepEqual(t.moves, [{ bar: 1, from: 98, to: 96, wider: true }]);
  t = E.stepTrade(t, hidden[2]);
  assert.equal(t.status, "stopped");
  assert.equal(t.exit, 96);
  near(t.r, -2, 1e-9, "R stays measured against the planned risk");

  // Breakeven: tighter, so not wider.
  const up = [C(100, 103.5, 99.8, 103), C(102.5, 103, 99.5, 100)];
  const r2 = roundWith(up);
  let b = E.stepTrade(E.planTrade(r2, { side: "long", stopAtr: 1, targetR: 3 }), up[0]);
  b = E.stepTrade(b, up[1], { moveStop: 100 });
  assert.deepEqual(b.moves, [{ bar: 1, from: 98, to: 100, wider: false }]);
  assert.equal(b.status, "stopped");
  near(b.r, 0);

  // A short's stop moved up is wider.
  const s = E.stepTrade(E.planTrade(r2, { side: "short", stopAtr: 2, targetR: 2 }), C(100, 101, 99, 100), { moveStop: 106 });
  assert.equal(s.moves[0].wider, true);
});

test("coinFlipR averages long and short with the same plan", () => {
  // Rising one point a day: the long reaches 104 (2R) on bar 3; the short is stopped at 102 on bar 1.
  const hidden = Array.from({ length: FUTURE }, (_, k) => C(100 + k, 101 + k, 99.9 + k, 101 + k));
  let round = roundWith(hidden);
  near(E.coinFlipR(round, { stopAtr: 1, targetR: 2 }), (2 + -1) / 2);
  round = roundWith(hidden, { cost: 0.001 });
  near(E.coinFlipR(round, { stopAtr: 1, targetR: 2 }), ((4 - 0.001 * 204) / 2 + (-2 - 0.001 * 202) / 2) / 2);
  // The side in the plan is ignored, and a trade object works as the plan.
  const trade = E.planTrade(round, { side: "short", stopAtr: 1, targetR: 2 });
  near(E.coinFlipR(round, trade), E.coinFlipR(round, { side: "long", stopAtr: 1, targetR: 2 }));
  const L = E.playOut(round, { side: "long", stopAtr: 1, targetR: 2 });
  const S = E.playOut(round, { side: "short", stopAtr: 1, targetR: 2 });
  assert.equal(L.status, "target");
  assert.equal(L.exitBar, 3);
  assert.equal(S.status, "stopped");
  near(E.coinFlipR(round, { stopAtr: 1, targetR: 2 }), (L.r + S.r) / 2);
  // No target: the long rides to the timeout.
  const N = E.playOut(round, { side: "long", stopAtr: 1, targetR: null });
  assert.equal(N.status, "timeout");
  assert.equal(N.exit, 101 + FUTURE - 1);
});

test("sizeUnits: hitting the stop loses riskPct% of cash", () => {
  assert.equal(E.sizeUnits(10000, 1, 2), 50);
  assert.equal(E.sizeUnits(10000, 1, 2) * 2, 100);
  near(E.sizeUnits(12345, 1, 0.037) * 0.037, 123.45, 1e-9);
  for (const bad of [[0, 1, 2], [10000, 0, 2], [10000, 1, 0], [10000, 1, NaN], [-5, 1, 2]]) assert.equal(E.sizeUnits(...bad), 0);
  // Cash change = units x risk x R, costs included.
  const round = roundWith([C(100, 104.5, 99.5, 104)], { cost: 0.0015 });
  const t = E.playOut(round, { side: "long", stopAtr: 1, targetR: 2 });
  const units = E.sizeUnits(10000, 1, t.risk);
  near(units * (t.exit - t.entry - t.cost * (t.entry + t.exit)), units * t.risk * t.r, 1e-9);
});

// ---------------------------------------------------------------------------------------------------------------
// Mistakes

const setup = (ctx, upRun = 0, downRun = 0) => ({ ctx: { ret10: 0, ret30: 0, rsi14: 50, vsSma50: 0, ...ctx }, upRun, downRun });
const kinds = (ms) => ms.map((m) => m.kind);
const loss = (extra = {}) => ({ seriesId: "btc", side: "long", stopAtr: 1.5, targetR: 2, r: -1, coinR: 0, mistakes: [], cashBefore: 10000, cashAfter: 9900, at: 1_800_000_000_000, ...extra });
const win = (extra = {}) => loss({ r: 1.5, cashAfter: 10150, ...extra });
const skipped = (extra = {}) => loss({ side: "skip", r: 0, cashAfter: 10000, ...extra });

test("every note has kind, severity, title, a one-line message and a lesson", () => {
  const all = [
    ...E.detectMistakes([], { side: "long", setup: setup({ ret10: 0.3, rsi14: 80 }, 4) }),
    ...E.detectMistakes([], { side: "short", setup: setup({ ret10: -0.3, rsi14: 20 }, 0, 4) }),
    ...E.detectMistakes([], { side: "skip", setup: setup({ ret10: 0.3 }) }),
  ];
  assert.ok(all.length >= 5);
  for (const m of all) {
    assert.equal(typeof m.kind, "string");
    assert.ok(Number.isInteger(m.severity) && m.severity >= 0 && m.severity <= 3);
    assert.ok(m.title && m.message && m.lesson);
    assert.ok(!m.message.includes("\n"));
    assert.equal(m.lesson, E.LESSONS[m.kind].lesson);
  }
  assert.match(E.LESSONS["early-profit"].lesson, /Odean 1998/);
});

test("fomo: buying after +15% in 10 days or RSI above 75", () => {
  let ms = E.detectMistakes([], { side: "long", setup: setup({ ret10: 0.2 }) });
  assert.deepEqual(kinds(ms), ["fomo"]);
  assert.equal(ms[0].severity, 2);
  assert.match(ms[0].message, /20%/);
  ms = E.detectMistakes([], { side: "long", setup: setup({ rsi14: 80 }) });
  assert.deepEqual(kinds(ms), ["fomo"]);
  assert.match(ms[0].message, /RSI was 80/);
  assert.equal(E.detectMistakes([], { side: "long", setup: setup({ ret10: 0.2, rsi14: 80 }) })[0].severity, 3);
  assert.deepEqual(E.detectMistakes([], { side: "long", setup: setup({ ret10: 0.15, rsi14: 75 }) }), [], "thresholds are strict");
  assert.deepEqual(E.detectMistakes([], { side: "short", setup: setup({ ret10: 0.2, rsi14: 80 }) }), [], "selling a stretched chart is not FOMO");
});

test("fomo from a real round passed as decision.round, and from trade.setup", () => {
  // Calm at 100, then a jump to 120 nine candles before the end.
  const vis = calm().map((b, i) => (i >= 81 ? C(120, 121, 119, 120) : b));
  const round = E.makeRound(seriesOf([...vis, ...calm(FUTURE, 120)]), 0);
  near(round.ctx.ret10, 0.2);
  let ms = E.detectMistakes([], { side: "long", stopAtr: 2, targetR: 2, round });
  assert.ok(kinds(ms).includes("fomo"));
  const trade = E.planTrade(round, { side: "long", stopAtr: 2, targetR: 2 });
  ms = E.detectMistakes([], { side: "long" }, trade);
  assert.ok(kinds(ms).includes("fomo"), "falls back to the setup stored in the trade");
});

test("panic: betting on a fall after -15% in 10 days or RSI below 25", () => {
  let ms = E.detectMistakes([], { side: "short", setup: setup({ ret10: -0.18 }) });
  assert.deepEqual(kinds(ms), ["panic"]);
  assert.match(ms[0].message, /fallen 18%/);
  ms = E.detectMistakes([], { side: "short", setup: setup({ rsi14: 20 }) });
  assert.deepEqual(kinds(ms), ["panic"]);
  assert.equal(E.detectMistakes([], { side: "short", setup: setup({ ret10: -0.2, rsi14: 20 }) })[0].severity, 3);
  assert.deepEqual(E.detectMistakes([], { side: "long", setup: setup({ ret10: -0.2, rsi14: 20 }) }), []);
});

/**
 * 87 choppy candles (closes 99/101, every true range 3, so ATR 3), then three candles that each close 4 higher (or
 * lower) than they opened at the previous close: true range 5, above the ATR. `tweak(candles)` may edit them.
 */
function chaseRound(dir, tweak = () => {}) {
  const closes = Array.from({ length: VISIBLE - 3 }, (_, i) => (i % 2 ? 101 : 99));
  let c = closes.at(-1);
  for (let k = 0; k < 3; k++) closes.push((c += 4 * dir));
  const vis = closes.map((x, i) => C(i ? closes[i - 1] : x, x + 1, x - 1, x));
  tweak(vis);
  return E.makeRound(seriesOf([...vis, ...calm(FUTURE, c)]), 0);
}

test("chasing: 3+ big candles in the trade's direction", () => {
  const up = chaseRound(1);
  const st = E.chartSetup(up);
  assert.equal(st.upRun, 3);
  assert.ok(up.ctx.ret10 < 0.15 && up.ctx.rsi14 < 75, "fixture: not stretched by the FOMO rules");
  let ms = E.detectMistakes([], { side: "long", round: up });
  assert.deepEqual(kinds(ms), ["chasing"]);
  assert.match(ms[0].message, /3 big up candles/);
  assert.deepEqual(E.detectMistakes([], { side: "short", round: up }), []);
  ms = E.detectMistakes([], { side: "skip", round: up });
  assert.deepEqual(kinds(ms), ["discipline"]);
  assert.match(ms[0].message, /3 big up candles/);

  const down = chaseRound(-1);
  assert.equal(E.chartSetup(down).downRun, 3);
  assert.deepEqual(kinds(E.detectMistakes([], { side: "short", round: down })), ["chasing"]);
  assert.deepEqual(E.detectMistakes([], { side: "long", round: down }), []);
  assert.equal(E.detectMistakes([], { side: "long", setup: setup({}, 5) })[0].severity, 3);

  // Not big up candles: one that gaps up but closes below its open (red), or one smaller than the ATR.
  const red = chaseRound(1, (v) => {
    v[88] = C(v[88].c + 0.5, v[88].c + 1, v[88].c - 1, v[88].c);
  });
  assert.equal(E.chartSetup(red).upRun, 1);
  const small = chaseRound(1, (v) => {
    const pc = v[88].c;
    v[89] = C(pc, pc + 1.2, pc - 0.2, pc + 1); // true range 1.4, under the ATR
  });
  assert.equal(E.chartSetup(small).upRun, 0);
});

test("revenge: a wider stop, a quick trade or a losing streak straight after a loss", () => {
  const calmSetup = setup({});
  let ms = E.detectMistakes([loss()], { side: "long", stopAtr: 2.5, setup: calmSetup });
  assert.deepEqual(kinds(ms), ["revenge"]);
  assert.equal(ms[0].severity, 2);
  assert.match(ms[0].message, /from 1.5 to 2.5 ATR/);

  assert.deepEqual(E.detectMistakes([loss()], { side: "long", stopAtr: 1.5, setup: calmSetup }), [], "same stop, no clock: not revenge");
  assert.deepEqual(E.detectMistakes([loss()], { side: "skip", stopAtr: 3, setup: calmSetup }), [], "a skip is never revenge");
  assert.deepEqual(E.detectMistakes([win()], { side: "long", stopAtr: 3, setup: calmSetup }), [], "after a win");

  const at = loss().at;
  ms = E.detectMistakes([loss()], { side: "short", stopAtr: 1.5, setup: calmSetup, at: at + 30_000 });
  assert.deepEqual(kinds(ms), ["revenge"]);
  assert.equal(ms[0].severity, 1);
  assert.match(ms[0].message, /30 seconds/);
  assert.deepEqual(E.detectMistakes([loss()], { side: "short", stopAtr: 1.5, setup: calmSetup, at: at + 5 * 60_000 }), []);
  ms = E.detectMistakes([loss({ at: new Date(at).toISOString() })], { side: "long", stopAtr: 1.5, setup: calmSetup, at: new Date(at + 10_000).toISOString() });
  assert.deepEqual(kinds(ms), ["revenge"], "ISO timestamps work");

  ms = E.detectMistakes([loss(), loss()], { side: "long", stopAtr: 1.5, setup: calmSetup });
  assert.deepEqual(kinds(ms), ["revenge"]);
  assert.equal(ms[0].severity, 1);
  assert.match(ms[0].message, /2 losses in a row/);
  assert.equal(E.detectMistakes([loss(), loss(), loss()], { side: "long", stopAtr: 1.5, setup: calmSetup })[0].severity, 2);
  assert.equal(E.detectMistakes([loss(), loss()], { side: "long", stopAtr: 3, setup: calmSetup })[0].severity, 3);
  assert.deepEqual(E.detectMistakes([loss(), skipped(), loss()], { side: "long", stopAtr: 1.5, setup: calmSetup }), [], "a skip breaks the streak");
  assert.deepEqual(E.detectMistakes([loss(), { kind: "cooldown" }], { side: "long", stopAtr: 3, setup: calmSetup }), [], "a pause in the park");

  const strip = { kind: "strip", cashBefore: 10000, cashAfter: 9900, at, mistakes: [] };
  assert.deepEqual(kinds(E.detectMistakes([strip], { side: "long", stopAtr: 1.5, setup: calmSetup, at: at + 20_000 })), ["revenge"]);
});

test("early-profit: closing a winner below +1R when the target was 2R or more", () => {
  const hidden = [C(100, 100.8, 99.6, 100.5), C(101.2, 101.5, 100.5, 101)];
  const round = roundWith(hidden);
  const closed = run(E.planTrade(round, { side: "long", stopAtr: 1, targetR: 2 }), hidden, ["hold", "close"]);
  near(closed.r, 0.6);
  let ms = E.detectMistakes([], { side: "long", stopAtr: 1, targetR: 2, round }, closed);
  assert.deepEqual(kinds(ms), ["early-profit"]);
  assert.match(ms[0].message, /\+0\.6R/);
  const oneR = run(E.planTrade(round, { side: "long", stopAtr: 1, targetR: 1 }), hidden, ["hold", "close"]);
  assert.deepEqual(E.detectMistakes([], { side: "long", targetR: 1, round }, oneR), [], "target 1R");
  const big = roundWith([C(100, 102.6, 99.6, 102.5), C(102.6, 103, 102, 102.8)]);
  const bigClose = run(E.planTrade(big, { side: "long", stopAtr: 1, targetR: 3 }), hiddenOf(big).slice(0, 2), ["hold", "close"]);
  near(bigClose.r, 1.3);
  assert.deepEqual(E.detectMistakes([], { side: "long", targetR: 3, round: big }, bigClose), [], "+1.3R is not early");
  const lossClose = run(E.planTrade(round, { side: "short", stopAtr: 1, targetR: 2 }), hidden, ["hold", "close"]);
  assert.deepEqual(E.detectMistakes([], { side: "short", targetR: 2, round }, lossClose), [], "a losing close");
});

test("moved-stop: moving the stop further away; worse when the loss ends past the planned stop", () => {
  const hidden = [C(100, 100.8, 99.6, 100.5), C(100.4, 100.6, 97, 98), C(97.5, 98, 95, 95.5)];
  const round = roundWith(hidden);
  const t = run(E.planTrade(round, { side: "long", stopAtr: 1, targetR: 2 }), hidden, ["hold", { moveStop: 96 }, "hold"]);
  let ms = E.detectMistakes([], { side: "long", round }, t);
  assert.deepEqual(kinds(ms), ["moved-stop"]);
  assert.equal(ms[0].severity, 3);
  assert.match(ms[0].message, /from 98 to 96/);
  assert.match(ms[0].message, /-2\.0R/);

  // Moved away, then the price recovered: still a mistake, severity 2, and no discipline note.
  const rec = [C(100, 100.8, 99.6, 100.5), C(100.4, 100.6, 97, 99), C(99, 104.5, 98.5, 104)];
  const r2 = roundWith(rec);
  const t2 = run(E.planTrade(r2, { side: "long", stopAtr: 1, targetR: 2 }), rec, ["hold", { moveStop: 96 }, "hold"]);
  assert.equal(t2.status, "target");
  ms = E.detectMistakes([], { side: "long", round: r2 }, t2);
  assert.deepEqual(kinds(ms), ["moved-stop"]);
  assert.equal(ms[0].severity, 2);

  // Tighter moves are fine.
  const up = [C(100, 103.5, 99.8, 103), C(102.5, 103, 99.5, 100)];
  const r3 = roundWith(up);
  const t3 = run(E.planTrade(r3, { side: "long", stopAtr: 1, targetR: 3 }), up, ["hold", { moveStop: 100 }]);
  assert.deepEqual(E.detectMistakes([], { side: "long", round: r3 }, t3), []);
});

test("overtrading: no skip in the last 10 decisions", () => {
  const s0 = setup({});
  const trades = (n) => Array.from({ length: n }, () => win());
  assert.deepEqual(E.detectMistakes(trades(8), { side: "long", setup: s0 }), []);
  let ms = E.detectMistakes(trades(9), { side: "long", setup: s0 });
  assert.deepEqual(kinds(ms), ["overtrading"]);
  assert.equal(ms[0].severity, 1);
  assert.match(ms[0].message, /10 charts in a row/);
  assert.deepEqual(E.detectMistakes([...trades(5), skipped(), ...trades(5)], { side: "long", setup: s0 }), []);
  const strip = { kind: "strip", cashBefore: 1, cashAfter: 2, mistakes: [] };
  assert.deepEqual(kinds(E.detectMistakes([...trades(5), strip, ...trades(4)], { side: "long", setup: s0 })), ["overtrading"]);
  assert.equal(E.detectMistakes(trades(19), { side: "long", setup: s0 })[0].severity, 2);
  assert.deepEqual(E.detectMistakes(trades(20), { side: "skip", setup: s0 }), []);
});

test("discipline: an untouched plan, or staying out of a stretched chart", () => {
  const round = roundWith([C(100, 104.5, 99.5, 104)]);
  const t = E.playOut(round, { side: "long", stopAtr: 1, targetR: 2 });
  let ms = E.detectMistakes([], { side: "long", round }, t);
  assert.deepEqual(kinds(ms), ["discipline"]);
  assert.equal(ms[0].severity, 0);
  assert.equal(ms[0].good, true);

  const flat = roundWith([]);
  const timeout = E.playOut(flat, { side: "long", stopAtr: 1, targetR: null });
  assert.equal(timeout.status, "timeout");
  assert.match(E.detectMistakes([], { side: "long", round: flat }, timeout)[0].message, /time ran out/);

  const closed = run(E.planTrade(flat, { side: "long", stopAtr: 1, targetR: 2 }), hiddenOf(flat).slice(0, 2), ["hold", "close"]);
  assert.deepEqual(E.detectMistakes([], { side: "long", round: flat }, closed), [], "closing by hand earns no discipline note");

  assert.deepEqual(E.detectMistakes([], { side: "skip", round: flat }), [], "skipping a calm chart is neutral");
  ms = E.detectMistakes([], { side: "skip", setup: setup({ ret10: -0.25 }) });
  assert.deepEqual(kinds(ms), ["discipline"]);
  assert.match(ms[0].message, /fallen 25%/);

  // Mistakes come first, most severe first; the good note last.
  ms = E.detectMistakes([], { side: "long", setup: setup({ ret10: 0.3, rsi14: 80 }, 3) }, { ...t, setup: undefined });
  assert.deepEqual(kinds(ms), ["fomo", "chasing", "discipline"]);
});

// ---------------------------------------------------------------------------------------------------------------
test("tilt rises with mistakes, decays with clean decisions, stays in 0..100", () => {
  const m = (...sev) => ({ side: "long", r: 0, mistakes: sev.map((s) => ({ kind: "fomo", severity: s })) });
  const clean = { side: "long", r: 0, mistakes: [] };
  const good = { side: "long", r: 0, mistakes: [{ kind: "discipline", severity: 0, good: true }] };
  assert.equal(E.tilt([]), 0);
  assert.equal(E.tilt([m(2)]), 20);
  assert.equal(E.tilt([m(3, 2)]), 50);
  assert.equal(E.tilt([m(2), clean]), 8); // 20 x 0.6 - 4
  assert.equal(E.tilt([m(3, 2), good]), 22); // 50 x 0.6 - 8
  assert.ok(E.tilt([m(3, 2), good]) < E.tilt([m(3, 2), clean]), "a discipline note helps more");
  let h = [m(3, 3), m(3, 3)];
  assert.equal(E.tilt(h), 100, "capped");
  const seq = [];
  for (let i = 0; i < 8; i++) {
    h = [...h, clean];
    seq.push(E.tilt(h));
  }
  assert.ok(seq.every((v, i) => i === 0 || v <= seq[i - 1]), `decays: ${seq}`);
  assert.equal(seq.at(-1), 0);
  assert.equal(E.tilt([{ mistakes: ["revenge", "overtrading"] }]), 30, "bare kind strings use default severities");
  assert.equal(E.tilt([{ kind: "strip", mistakes: [{ kind: "lottery", severity: 2 }] }]), 20, "the Strip's mistakes count");
  assert.equal(E.tilt([m(3, 3), { kind: "cooldown" }]), 30);
  assert.equal(E.tilt([m(3, 3), { kind: "cooldown", relief: 100 }]), 0);
});

test("stats: win rate, R, coin-flip edge and its t-statistic, cash", () => {
  const empty = E.stats([]);
  assert.deepEqual(
    { ...empty },
    { rounds: 0, trades: 0, skips: 0, wins: 0, winRate: null, avgR: null, totalR: 0, coinFlipAvgR: null, edgeR: null, t: null, cashStart: 10000, cash: 10000, mistakes: {}, discipline: 0 },
  );
  const rs = [2, -1, -1, 0.5];
  const coin = [0.1, -0.2, 0, -0.1];
  let cash = 10000;
  const history = rs.map((r, i) => {
    const before = cash;
    cash += r * 100;
    return { seriesId: "btc", side: i % 2 ? "short" : "long", stopAtr: 2, targetR: 2, r, coinR: coin[i], mistakes: i === 1 ? [{ kind: "fomo", severity: 2 }] : [{ kind: "discipline", severity: 0, good: true }], cashBefore: before, cashAfter: cash, at: i };
  });
  history.splice(2, 0, { seriesId: "eth", side: "skip", stopAtr: 2, targetR: 2, r: 0, coinR: 0.3, mistakes: [], cashBefore: 10100, cashAfter: 10100, at: 9 });
  history.push({ kind: "strip", stake: 100, payout: 0, mistakes: ["lottery"], cashBefore: cash, cashAfter: cash - 100, at: 10 });
  const s = E.stats(history);
  assert.equal(s.rounds, 5);
  assert.equal(s.trades, 4);
  assert.equal(s.skips, 1);
  assert.equal(s.wins, 2);
  near(s.winRate, 0.5);
  near(s.avgR, 0.125);
  near(s.totalR, 0.5);
  near(s.coinFlipAvgR, -0.05);
  near(s.edgeR, 0.175);
  const d = rs.map((r, i) => r - coin[i]);
  const sd = Math.sqrt(d.reduce((a, x) => a + (x - 0.175) ** 2, 0) / 3);
  near(s.t, 0.175 / (sd / 2));
  assert.equal(s.cashStart, 10000);
  assert.equal(s.cash, 10050 - 100, "cash includes the Strip");
  assert.deepEqual(s.mistakes, { fomo: 1, lottery: 1 });
  assert.equal(s.discipline, 3);
  assert.equal(E.stats([history[0]]).t, null, "one trade: no t-statistic");
});

// ---------------------------------------------------------------------------------------------------------------
// Property checks on random synthetic charts with gaps: the outcome always obeys the fill rules.

function checkOutcome(round, t) {
  const dir = t.side === "long" ? 1 : -1;
  const hidden = hiddenOf(round);
  assert.ok(Number.isFinite(t.r), "finite R");
  const gross = (dir * (t.exit - t.entry)) / t.risk;
  const bar = hidden[t.exitBar];
  if (t.status === "stopped") {
    assert.ok(gross <= -1 + 1e-9 && t.r <= -1 + 1e-9, `stopped beyond -1R: ${gross}`);
    assert.ok(t.exit === t.stop || t.exit === bar.o);
  } else if (t.status === "target") {
    assert.ok(gross >= t.targetR - 1e-9, `target below plan: ${gross}`);
    assert.ok(t.exit === t.target || t.exit === bar.o);
  } else {
    assert.equal(t.status, "timeout");
    assert.equal(t.bars, FUTURE);
    assert.equal(t.exit, hidden[FUTURE - 1].c);
  }
  // No earlier candle reached a level (the trade would have ended there).
  for (let k = 0; k < t.exitBar; k++) {
    const b = hidden[k];
    assert.ok(dir > 0 ? b.l > t.stop : b.h < t.stop, `bar ${k} touched the stop`);
    if (t.target != null) assert.ok(dir > 0 ? b.h < t.target : b.l > t.target, `bar ${k} touched the target`);
  }
}

test("property: random charts with gaps always follow the fill rules", () => {
  const rand = E.rng(31337);
  for (let n = 0; n < 300; n++) {
    const candles = [];
    let p = 20 + rand() * 1000;
    const vol = 0.005 + rand() * 0.05;
    for (let i = 0; i < WINDOW; i++) {
      const o = p * (1 + (rand() - 0.5) * vol * (rand() < 0.15 ? 6 : 1)); // occasional big gaps
      const c = o * (1 + (rand() - 0.5) * vol * 2);
      candles.push(C(o, Math.max(o, c) * (1 + rand() * vol), Math.min(o, c) * (1 - rand() * vol), c));
      p = c;
    }
    const round = E.makeRound(seriesOf(candles, { cost: rand() < 0.5 ? 0.0015 : 0 }), 0);
    const plan = { stopAtr: 1 + Math.floor(rand() * 5) / 2, targetR: [1, 2, 3, null][Math.floor(rand() * 4)] };
    const L = E.playOut(round, { ...plan, side: "long" });
    const S = E.playOut(round, { ...plan, side: "short" });
    checkOutcome(round, L);
    checkOutcome(round, S);
    near(E.coinFlipR(round, plan), (L.r + S.r) / 2, 1e-12);
  }
});

// ---------------------------------------------------------------------------------------------------------------
// The real data, when it has been built.

const DATA = new URL("../../public/game/series.json", import.meta.url);

test("real series.json: clean windows, fair picks, sane outcomes", { skip: !existsSync(DATA) && "series.json not built" }, () => {
  const data = JSON.parse(readFileSync(DATA, "utf8"));
  const byId = Object.fromEntries(data.series.map((s) => [s.id, s]));
  const count = Object.fromEntries(data.series.map((s) => [s.id, 0]));
  const rand = E.rng(20261031);
  const N = 300 * data.series.length;
  for (let i = 0; i < N; i++) {
    const r = E.pickRound(data, rand);
    count[r.seriesId]++;
    const s = byId[r.seriesId];
    assert.equal(r.candles.length, WINDOW);
    assert.equal(r.cost, s.cost);
    assert.equal(r.candles[0].t, s.t[r.i0]);
    assert.equal(r.candles.at(-1).t, s.t[r.i2 - 1]);
    for (let k = 1; k < WINDOW; k++) assert.ok(r.candles[k].t - r.candles[k - 1].t <= E.gapLimitDays(s));
    assert.ok(r.atr > 0);
    for (const v of Object.values(r.ctx)) assert.ok(Number.isFinite(v));
    if (i % 5 === 0) {
      const plan = { stopAtr: 1 + (i % 3), targetR: [1, 2, 3, null][i % 4] };
      checkOutcome(r, E.playOut(r, { ...plan, side: "long" }));
      checkOutcome(r, E.playOut(r, { ...plan, side: "short" }));
      assert.ok(Number.isFinite(E.coinFlipR(r, plan)));
    }
  }
  for (const [id, n] of Object.entries(count)) assert.ok(n > 0.75 * 300 && n < 1.25 * 300, `${id} picked ${n} times of ${N}`);
});
