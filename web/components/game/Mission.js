"use client";
// Candle City mission: a real past chart with its name and dates hidden. Read it, then buy, sell or stay out with a
// stop and a target, reveal the next 30 candles one at a time, and finish with the result in R, the game-cash change,
// a comparison with a coin flip, the emotional mistakes spotted, and the reveal of what the chart was.
// Game cash only: no real money, no real orders.
//
// Props (CONTRACT section 3): { data, seed, history, cash, tilt, onDone(result), onExit() }.
// Optional extra prop `district` ("docks" | "market") limits the pick to that district's series.
// onDone(entry) is called once, as soon as the result is known (leaving the page cannot dodge a loss);
// "Back to the city" then calls onExit(). This is the same pattern as StripMission.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  FUTURE, VISIBLE, coinFlipR, detectMistakes, pickRound, planTrade, rng, sizeUnits, stats, stepTrade, tilt as tiltOf,
} from "@/lib/game/engine";
import s from "./Mission.module.css";

const RISK_PCT = 1;                        // risk per trade, fixed: 1% of game cash
const STOPS = [1, 1.5, 2, 2.5, 3];         // stop distance, in ATRs
const TARGETS = [1, 2, 3, null];           // target, in R (null = no target)
const DISTRICT = { docks: "Crypto Docks", market: "Nifty Market" };
const AUTO_MS = 700;                       // Auto: one candle every 0.7 s
const ENTRY_KINDS = new Set(["fomo", "panic", "revenge", "overtrading", "chasing"]); // knowable before entering
const DAY_MS = 86400000;

/* ---------- formatting ---------- */
const sign = (v) => (v > 0 ? "+" : v < 0 ? "−" : "");
const round2 = (v, d) => Number(v.toFixed(d));   // so -0.001 shows as 0.00, not −0.00
const fmtR = (r, d = 2) => (r == null || !Number.isFinite(r) ? "—" : `${sign(round2(r, d))}${Math.abs(r).toFixed(d)}R`);
const fmtPct = (v, d = 1) => (v == null || !Number.isFinite(v) ? "—" : `${sign(round2(v, d))}${Math.abs(v).toFixed(d)}%`);
const tone = (v, eps = 0.005) => (v > eps ? s.up : v < -eps ? s.down : "");

/** Game cash, always in "$" (game dollars). Whole dollars from $100 up. */
function fmtCash(v, signed = false) {
  const a = Math.abs(v);
  const d = a >= 100 ? 0 : 2;
  const body = a.toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
  return `${signed ? sign(round2(v, d)) : v < 0 ? "−" : ""}$${body}`;
}

/** A price in the series' own currency, with decimals that suit its size (or a fixed number of digits). */
function fmtPrice(v, cur = "", digits) {
  if (v == null || !Number.isFinite(v)) return "—";
  const a = Math.abs(v);
  const d = digits ?? (a >= 1000 ? 0 : a >= 100 ? 1 : a >= 10 ? 2 : a >= 1 ? 3 : 4);
  return `${cur}${v.toLocaleString(cur === "₹" ? "en-IN" : "en-US", { minimumFractionDigits: d, maximumFractionDigits: d })}`;
}

const dayText = (t, opts) => new Date(t * DAY_MS).toLocaleDateString("en-GB", { timeZone: "UTC", ...opts });

/** "3–11 Mar 2020", "28 Feb – 4 Mar 2020" or "28 Dec 2019 – 5 Jan 2020". */
function rangeText(t0, t1) {
  const a = new Date(t0 * DAY_MS), b = new Date(t1 * DAY_MS);
  const y = { year: "numeric" }, dm = { day: "numeric", month: "short" };
  if (a.getUTCFullYear() !== b.getUTCFullYear()) return `${dayText(t0, { ...dm, ...y })} – ${dayText(t1, { ...dm, ...y })}`;
  if (a.getUTCMonth() !== b.getUTCMonth()) return `${dayText(t0, dm)} – ${dayText(t1, { ...dm, ...y })}`;
  return `${a.getUTCDate()}–${dayText(t1, { ...dm, ...y })}`;
}

/* ---------- small maths helpers (no trading logic: that lives in the engine) ---------- */

/** 50-day simple average of closes for each candle of the round, using the history before the window. */
function sma50(series, i0, n) {
  const c = series.c, out = new Array(n).fill(null);
  for (let k = 0; k < n; k++) {
    const i = i0 + k;
    if (i < 49) continue;
    let sum = 0;
    for (let j = i - 49; j <= i; j++) sum += c[j];
    out[k] = sum / 50;
  }
  return out;
}

/** The same plan run hands-off (no moves, no early close) over the hidden candles. */
function handsOff(round, plan) {
  let tr = planTrade(round, plan);
  for (let k = VISIBLE; k < round.candles.length && tr.status === "open"; k++) tr = stepTrade(tr, round.candles[k], "hold");
  return tr;
}

/** The engine gives returns as fractions (0.15 = +15%); the screen shows percent. */
const asPct = (v) => (v == null || !Number.isFinite(v) ? null : v * 100);

/* ---------- canvas candlestick chart ---------- */

const PAD = { left: 4, top: 22, bottom: 22 };

/**
 * Plot geometry. The right gutter is sized to the widest price label, so the trade-line pills and the price ticks
 * never cover candles (on a phone the last candles are the interesting ones).
 */
function layout(w, h, n, gutter) {
  const L = PAD.left, R = w - gutter, T = PAD.top, B = h - PAD.bottom;
  return { L, R, T, B, gutter, slot: (R - L) / n };
}

function readColors(el) {
  const cs = getComputedStyle(el);
  const v = (name, fb) => cs.getPropertyValue(name).trim() || fb;
  return {
    up: v("--up", "#0f7a45"), down: v("--down", "#c62f45"), accent: v("--accent", "#6339d5"), ink: v("--ink", "#0e0d1e"),
    ink2: v("--ink-2", "#4a4862"), muted: v("--muted", "#6e6b85"), grid: v("--grid", "#f0eff6"), line2: v("--line-2", "#dedbea"),
    panel: v("--panel", "#ffffff"), font: getComputedStyle(document.body).fontFamily || "sans-serif",
  };
}

/** Dark or light text for a pill, by the WCAG luminance of its background (the dark theme's pills are pale). */
function textOn(color) {
  const m = /^#?([0-9a-f]{6})$/i.exec(color.trim());
  if (!m) return "#ffffff";
  const lin = (i) => { const v = parseInt(m[1].slice(i, i + 2), 16) / 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; };
  return 0.2126 * lin(0) + 0.7152 * lin(2) + 0.0722 * lin(4) > 0.25 ? "#0e0d1e" : "#ffffff";
}

function niceTicks(lo, hi, n) {
  const span = hi - lo || Math.abs(hi) || 1;
  const mag = 10 ** Math.floor(Math.log10(span / n));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((x) => span / x <= n) || 10 * mag;
  const out = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + step * 1e-6; v += step) out.push(v);
  return { out, digits: Math.max(0, Math.min(6, -Math.floor(Math.log10(step) + 1e-9))) };
}

function rrect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

/**
 * Draw one frame and return the geometry used (for touch picking). st.disp is the fractional number of candles
 * shown: the last one grows in from its open while it animates.
 */
function paint(cv, w, h, dpr, st, col) {
  const ctx = cv.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, w, h);
  const { candles, sma, disp, lo, hi, lines, exit, dates, hover, showSma, nowIdx } = st;
  const n = candles.length;
  const small = `500 11px ${col.font}`, bold = `650 11px ${col.font}`;
  const { out: ticks, digits } = niceTicks(lo, hi, h < 280 ? 4 : 5);

  // gutter: wide enough for the widest tick or pill text
  ctx.font = bold;
  const pillText = (ln) => `${ln.approx ? "≈" : ""}${fmtPrice(ln.price)}`;
  let widest = 0;
  for (const p of ticks) widest = Math.max(widest, ctx.measureText(fmtPrice(p, "", digits)).width);
  for (const ln of lines) if (ln.label) widest = Math.max(widest, ctx.measureText(pillText(ln)).width);
  const geo = layout(w, h, n, Math.ceil((widest + 16) / 8) * 8);   // in 8 px steps, so the plot does not jitter
  const { L, R, T, B, slot } = geo;
  const X = (k) => L + slot * (k + 0.5);
  const Y = (p) => T + ((hi - p) / (hi - lo || 1)) * (B - T);
  const crisp = (v) => (Math.round(v * dpr) + 0.5) / dpr;   // centre of a device pixel, for hairlines
  const full = Math.floor(disp), part = disp - full;

  // grid
  ctx.lineWidth = 1 / dpr;
  ctx.strokeStyle = col.grid;
  for (const p of ticks) {
    const y = crisp(Y(p));
    if (y < T - 2 || y > B + 2) continue;
    ctx.beginPath(); ctx.moveTo(L, y); ctx.lineTo(R, y); ctx.stroke();
  }

  // the hidden future: a hatched zone with a question mark, shrinking as candles are revealed
  const firstHidden = Math.ceil(disp);
  if (firstHidden < n) {
    const x0 = L + slot * firstHidden;
    ctx.save();
    ctx.beginPath(); ctx.rect(x0, T, R - x0, B - T); ctx.clip();
    ctx.globalAlpha = 0.07; ctx.fillStyle = col.accent; ctx.fillRect(x0, T, R - x0, B - T);
    ctx.globalAlpha = 0.16; ctx.strokeStyle = col.accent; ctx.lineWidth = 1;
    for (let x = x0 - (B - T); x < R; x += 9) { ctx.beginPath(); ctx.moveTo(x, B); ctx.lineTo(x + (B - T), T); ctx.stroke(); }
    ctx.restore();
    if (R - x0 > 34) {
      // a halo in the card colour keeps the text readable where a trade line crosses it
      ctx.textAlign = "center"; ctx.textBaseline = "middle"; ctx.lineJoin = "round";
      ctx.strokeStyle = col.panel; ctx.lineWidth = 3; ctx.fillStyle = col.accent;
      ctx.font = `700 20px ${col.font}`; ctx.strokeText("?", (x0 + R) / 2, T + 18); ctx.fillText("?", (x0 + R) / 2, T + 18);
      ctx.font = small; ctx.strokeText(`${n - firstHidden} hidden`, (x0 + R) / 2, T + 36); ctx.fillText(`${n - firstHidden} hidden`, (x0 + R) / 2, T + 36);
    }
  }

  // "now": between the last visible candle and the first hidden one
  const xNow = crisp(L + slot * nowIdx);
  ctx.save();
  ctx.setLineDash([3, 3]); ctx.strokeStyle = col.line2; ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(xNow, T - 4); ctx.lineTo(xNow, B); ctx.stroke();
  ctx.restore();
  ctx.font = small; ctx.fillStyle = col.muted; ctx.textAlign = "center"; ctx.textBaseline = "alphabetic";
  ctx.fillText("Now", xNow, T - 8);

  // 50-day average: clipped to the plot, so a far-away average never squashes the candles
  if (showSma) {
    ctx.save();
    ctx.beginPath(); ctx.rect(L, T, R - L, B - T); ctx.clip();
    ctx.strokeStyle = col.accent; ctx.lineWidth = 1.6; ctx.globalAlpha = 0.85; ctx.lineJoin = "round";
    ctx.beginPath();
    let pen = false;
    const lastK = Math.min(n - 1, part > 0 ? full : full - 1);
    for (let k = 0; k <= lastK; k++) {
      if (sma[k] == null) { pen = false; continue; }
      const x = X(k), y = Y(sma[k]);
      if (pen) ctx.lineTo(x, y); else { ctx.moveTo(x, y); pen = true; }
    }
    ctx.stroke();
    ctx.restore();
  }

  // candles; the ones after the exit are faded ("what happened next")
  const bodyW = Math.max(1 / dpr, Math.round(slot * 0.64 * dpr) / dpr);
  ctx.lineWidth = Math.max(1, Math.round(dpr * 0.9)) / dpr;
  for (let k = 0; k < Math.min(n, Math.ceil(disp)); k++) {
    const c = candles[k];
    const p = k < full ? 1 : part;             // a growing candle: close and wicks move out from the open
    const cc = c.o + (c.c - c.o) * p, hh = c.o + (c.h - c.o) * p, ll = c.o + (c.l - c.o) * p;
    ctx.globalAlpha = (exit && k > exit.k ? 0.4 : 1) * (p < 1 ? 0.35 + 0.65 * p : 1);
    ctx.fillStyle = ctx.strokeStyle = c.c >= c.o ? col.up : col.down;
    const x = crisp(X(k));
    ctx.beginPath(); ctx.moveTo(x, Y(hh)); ctx.lineTo(x, Y(ll)); ctx.stroke();
    const y1 = Y(Math.max(c.o, cc)), y2 = Y(Math.min(c.o, cc));
    const bx = Math.round((X(k) - bodyW / 2) * dpr) / dpr;
    ctx.fillRect(bx, Math.round(y1 * dpr) / dpr, bodyW, Math.max(1 / dpr, Math.round((y2 - y1) * dpr) / dpr));
  }
  ctx.globalAlpha = 1;

  // entry / stop / target lines across the future
  const pills = [];
  for (const ln of lines) {
    const y = crisp(Y(ln.price));
    const color = col[ln.tone] || col.ink2;
    ctx.save();
    ctx.globalAlpha = ln.alpha ?? 1;
    ctx.strokeStyle = color; ctx.lineWidth = ln.width || 1.4;
    if (ln.dash) ctx.setLineDash(ln.dash);
    ctx.beginPath(); ctx.moveTo(Math.max(L, L + slot * ln.from), y); ctx.lineTo(R, y); ctx.stroke();
    ctx.restore();
    if (ln.label) pills.push({ y, text: pillText(ln), color, alpha: ln.alpha ?? 1 });
  }
  // pills in the gutter, pushed apart so they never overlap
  pills.sort((a, b) => a.y - b.y);
  for (let i = 1; i < pills.length; i++) if (pills[i].y - pills[i - 1].y < 18) pills[i].y = pills[i - 1].y + 18;
  const over = pills.length ? pills[pills.length - 1].y - (B + 6) : 0;
  if (over > 0) for (const pl of pills) pl.y -= over;

  // price ticks in the gutter, skipping any that a pill would cover
  ctx.font = small; ctx.textBaseline = "middle"; ctx.textAlign = "left"; ctx.fillStyle = col.muted;
  for (const p of ticks) {
    const y = Y(p);
    if (y < T + 4 || y > B - 2 || pills.some((pl) => Math.abs(pl.y - y) < 14)) continue;
    ctx.fillText(fmtPrice(p, "", digits), R + 7, y);
  }
  ctx.font = bold;
  for (const pl of pills) {
    const tw = ctx.measureText(pl.text).width;
    ctx.globalAlpha = pl.alpha;
    ctx.fillStyle = pl.color; rrect(ctx, R + 2, pl.y - 9, Math.min(w - R - 3, tw + 10), 18, 6); ctx.fill();
    ctx.fillStyle = textOn(pl.color); ctx.fillText(pl.text, R + 7, pl.y + 0.5);
    ctx.globalAlpha = 1;
  }

  // exit marker
  if (exit && disp > exit.k) {
    const x = X(exit.k), y = Y(exit.price);
    ctx.beginPath(); ctx.arc(x, y, 4.5, 0, Math.PI * 2);
    ctx.fillStyle = col.panel; ctx.fill(); ctx.lineWidth = 2; ctx.strokeStyle = col.ink; ctx.stroke();
    ctx.font = bold; ctx.fillStyle = col.ink; ctx.textBaseline = "alphabetic";
    const tw = ctx.measureText("Exit").width;
    ctx.textAlign = "left";
    ctx.fillText("Exit", Math.min(R - tw - 2, Math.max(L, x - tw / 2)), y - 9 < T + 4 ? y + 18 : y - 9);
  }

  // hover / touch crosshair
  if (hover != null && hover < disp) {
    ctx.save(); ctx.globalAlpha = 0.45; ctx.strokeStyle = col.ink2; ctx.lineWidth = 1 / dpr;
    const x = crisp(X(hover));
    ctx.beginPath(); ctx.moveTo(x, T); ctx.lineTo(x, B); ctx.stroke(); ctx.restore();
  }

  // x labels: days relative to the decision while the dates are secret, real dates after the reveal.
  // Laid out right to left; a label that would touch its right-hand neighbour is dropped.
  ctx.font = small; ctx.fillStyle = col.muted; ctx.textBaseline = "alphabetic"; ctx.textAlign = "left";
  const marks = [[n - 1, n - nowIdx], [nowIdx + 14, 15], [nowIdx - 1, 0], [nowIdx - 31, -30], [nowIdx - 61, -60]];
  let limit = Infinity;
  marks.forEach(([k, d], i) => {
    if (k < 0 || k >= n) return;
    const text = dates ? dayText(candles[k].t, { day: "numeric", month: "short", ...(i === marks.length - 1 ? { year: "2-digit" } : {}) })
      : d === 0 ? "Day 0" : `${d > 0 ? "+" : "−"}${Math.abs(d)}d`;
    const tw = ctx.measureText(text).width;
    const x0 = i === 0 ? R - tw : Math.max(L, X(k) - tw / 2);
    if (x0 + tw > limit - 6) return;
    ctx.fillText(text, x0, h - 6);
    limit = x0;
  });
  return geo;
}

/** Responsive, high-DPI candlestick chart. Newly revealed candles grow in; the price range eases to fit. */
function CandleChart({ candles, sma, shown, lines, exit, dates, cur, nowIdx, label }) {
  const wrapRef = useRef(null);
  const cvRef = useRef(null);
  const geoRef = useRef(null);
  const anim = useRef({ disp: null, lo: null, hi: null, raf: 0 });
  const [size, setSize] = useState({ w: 0, h: 0 });
  const [hover, setHover] = useState(null);
  const [showSma, setShowSma] = useState(true);
  const [themeTick, setThemeTick] = useState(0);

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return undefined;
    const ro = new ResizeObserver(([e]) => {
      const w = Math.round(e.contentRect.width);
      setSize((o) => (o.w === w ? o : { w, h: Math.round(Math.min(380, Math.max(200, w * 0.56))) }));
    });
    ro.observe(el);
    // the site's theme toggle flips data-theme on <html>: re-read the colours
    const mo = new MutationObserver(() => setThemeTick((t) => t + 1));
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    return () => { ro.disconnect(); mo.disconnect(); };
  }, []);

  useEffect(() => {
    const cv = cvRef.current;
    if (!cv || !size.w) return undefined;
    const dpr = Math.min(3, window.devicePixelRatio || 1);
    const W = Math.round(size.w * dpr), H = Math.round(size.h * dpr);
    if (cv.width !== W || cv.height !== H) { cv.width = W; cv.height = H; }
    const col = readColors(wrapRef.current);
    const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

    // price range to fit: the shown candles and the trade lines (the 50-day line is clipped instead)
    let tlo = Infinity, thi = -Infinity;
    for (let k = 0; k < shown; k++) { tlo = Math.min(tlo, candles[k].l); thi = Math.max(thi, candles[k].h); }
    for (const ln of lines) { tlo = Math.min(tlo, ln.price); thi = Math.max(thi, ln.price); }
    const pad = (thi - tlo) * 0.07 || thi * 0.01;
    tlo -= pad; thi += pad;

    const a = anim.current;
    if (a.disp == null || shown < a.disp || reduce) a.disp = shown;   // first draw or reduced motion: no animation
    if (a.lo == null || reduce) { a.lo = tlo; a.hi = thi; }
    const draw = () => {
      geoRef.current = paint(cv, size.w, size.h, dpr, { candles, sma, disp: a.disp, lo: a.lo, hi: a.hi, lines, exit, dates, hover, showSma, nowIdx }, col);
    };
    draw();
    let last = performance.now();
    const frame = (now) => {
      const dt = Math.min(64, now - last);
      last = now;
      const behind = shown - a.disp;
      if (behind > 0) a.disp = Math.min(shown, a.disp + dt / (behind > 2 ? 40 : 240)); // catch up fast when far behind
      const k = Math.min(1, dt / 140);
      a.lo += (tlo - a.lo) * k; a.hi += (thi - a.hi) * k;
      const eps = (thi - tlo) * 0.002;
      const done = a.disp >= shown && Math.abs(a.lo - tlo) < eps && Math.abs(a.hi - thi) < eps;
      if (done) { a.lo = tlo; a.hi = thi; }
      draw();
      if (!done) a.raf = requestAnimationFrame(frame);
    };
    a.raf = requestAnimationFrame(frame);
    return () => cancelAnimationFrame(a.raf);
  }, [size, shown, candles, sma, lines, exit, dates, hover, showSma, nowIdx, themeTick]);

  const pick = (e) => {
    const cv = cvRef.current, g = geoRef.current;
    if (!cv || !g) return;
    const k = Math.floor((e.clientX - cv.getBoundingClientRect().left - g.L) / g.slot);
    setHover(k >= 0 && k < shown ? k : null);
  };

  const hc = hover != null && hover < shown ? candles[hover] : null;
  const prev = hc && hover > 0 ? candles[hover - 1].c : null;
  const when = hc ? (dates ? dayText(hc.t, { weekday: "short", day: "numeric", month: "short", year: "numeric" })
    : hover < nowIdx ? (hover === nowIdx - 1 ? "Day 0" : `Day −${nowIdx - 1 - hover}`) : `Day +${hover - nowIdx + 1}`) : null;

  return (
    <div className={s.chartBox}>
      <div className={s.readout} aria-live="off">
        {hc ? (
          <>
            <b>{when}</b>
            <span>O {fmtPrice(hc.o, cur)}</span><span>H {fmtPrice(hc.h, cur)}</span>
            <span>L {fmtPrice(hc.l, cur)}</span><span>C {fmtPrice(hc.c, cur)}</span>
            {prev ? <span className={tone(hc.c / prev - 1, 0)}>{fmtPct(100 * (hc.c / prev - 1), 2)}</span> : null}
          </>
        ) : <span className={s.hint}>Touch a candle to read it · 1 candle = 1 day</span>}
      </div>
      <div ref={wrapRef} className={s.canvasWrap} style={{ height: size.h || 220 }}>
        <canvas ref={cvRef} role="img" aria-label={label} className={s.canvas}
          onPointerMove={pick} onPointerDown={pick} onPointerLeave={(e) => { if (e.pointerType === "mouse") setHover(null); }} />
      </div>
      <div className={s.legend}>
        <button type="button" className={s.legendBtn} aria-pressed={showSma} onClick={() => setShowSma((v) => !v)}>
          <i className={s.keySma} />50-day average
        </button>
        {lines.some((l) => l.key === "entry") ? <span><i className={s.keyEntry} />Entry</span> : null}
        {lines.some((l) => l.key === "stop") ? <span><i className={s.keyStop} />Stop</span> : null}
        {lines.some((l) => l.key === "target") ? <span><i className={s.keyTarget} />Target</span> : null}
      </div>
    </div>
  );
}

/* ---------- the mission ---------- */

/** Keyed by seed so a new mission always starts from a clean slate. */
export default function Mission(props) {
  return <MissionInner key={`${props.seed}|${props.district || ""}`} {...props} />;
}

function MissionInner({ data, seed, history = [], cash = 10000, tilt = 0, onDone, onExit, district }) {
  const setup = useMemo(() => {
    const all = data?.series || [];
    if (!all.length) return null;
    let round = null;
    // every series gets the same chance; an unknown district falls back to all of them
    for (const opts of district ? [{ district }, {}] : [{}]) {
      try { round = pickRound(all, rng(seed ?? 1), opts); break; } catch { round = null; }
    }
    const series = round && all.find((x) => x.id === round.seriesId);
    if (!series) return null;
    return { series, round, sma: sma50(series, round.i0, round.candles.length) };
  }, [data, seed, district]);
  const [openedAt] = useState(() => Date.now());   // for the "straight back in after a loss" check

  const [phase, setPhase] = useState("plan");   // plan -> live -> result
  const [side, setSide] = useState(null);        // "long" | "short" | "skip"
  const [stopAtr, setStopAtr] = useState(2);
  const [targetR, setTargetR] = useState(2);
  const [live, setLive] = useState(null);        // { trade (null when staying out), shown, at (decision time) }
  const [auto, setAuto] = useState(false);
  const [moveOpen, setMoveOpen] = useState(false);
  const [note, setNote] = useState("");
  const [result, setResult] = useState(null);
  const [revealed, setRevealed] = useState(false);
  const sent = useRef(false);
  const rootRef = useRef(null);

  const round = setup?.round;
  const total = round ? round.candles.length : 0;
  const riskCash = (cash * RISK_PCT) / 100;

  /** Reveal the next candle, applying one action to the open trade first ("hold", "close" or { moveStop }). */
  const advance = useCallback((action = "hold") => {
    setLive((p) => {
      if (!p || p.shown >= total || (p.trade && p.trade.status !== "open")) return p;
      const candle = round.candles[p.shown];
      return { ...p, trade: p.trade ? stepTrade(p.trade, candle, action) : null, shown: p.shown + 1 };
    });
  }, [round, total]);

  /** The mission is over: score it, build the history entry, and reveal the rest of the candles. */
  const finish = useCallback((lv) => {
    const trade = lv.trade;
    const r = trade ? trade.r : 0;
    const coinR = coinFlipR(round, { stopAtr, targetR });
    const mistakes = detectMistakes(history, { side, stopAtr, targetR, round, at: lv.at }, trade);
    const entry = {
      seriesId: round.seriesId, side, stopAtr, targetR, r, coinR, mistakes,
      cashBefore: cash, cashAfter: cash + r * riskCash, at: Date.now(),
    };
    const after = [...history, entry];
    setResult({
      entry, trade,
      exitK: trade ? VISIBLE + (trade.exitBar ?? Math.max(0, trade.bars - 1)) : null,
      long: handsOff(round, { side: "long", stopAtr, targetR }).r,
      short: handsOff(round, { side: "short", stopAtr, targetR }).r,
      stats: stats(after), tiltBefore: tilt, tiltAfter: tiltOf(after),
    });
    setAuto(false);
    setMoveOpen(false);
    setPhase("result");
    setLive({ ...lv, shown: total });
  }, [round, stopAtr, targetR, side, history, cash, riskCash, tilt, total]);

  // the trade ended by itself (stop, target, close, 30 days) or the watch-only round ran out of candles
  useEffect(() => {
    if (phase !== "live" || !live) return;
    if (live.trade ? live.trade.status !== "open" : live.shown >= total) finish(live);
  }, [phase, live, total, finish]);

  // record the result once (StrictMode runs effects twice in development)
  useEffect(() => {
    if (!result || sent.current) return;
    sent.current = true;
    onDone?.(result.entry);
  }, [result, onDone]);

  // Auto: one candle at a time until the trade ends or the player takes over
  useEffect(() => {
    if (!auto || phase !== "live") return undefined;
    const id = setInterval(() => advance("hold"), AUTO_MS);
    return () => clearInterval(id);
  }, [auto, phase, advance]);

  // bring the chart back into view when the phase changes (phones scroll down to the buttons)
  useEffect(() => {
    if (phase === "plan") return;
    const el = rootRef.current;
    if (el && el.getBoundingClientRect().top < 0) el.scrollIntoView({ block: "start", behavior: "smooth" });
  }, [phase]);

  const act = useCallback((action, msg = "") => { setAuto(false); setMoveOpen(false); setNote(msg); advance(action); }, [advance]);

  // keyboard on desktop: → or N = next, A = auto, C = close now
  const hasTrade = Boolean(live?.trade);
  useEffect(() => {
    if (phase !== "live") return undefined;
    const on = (e) => {
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const el = document.activeElement;
      if (el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.isContentEditable)) return;
      const k = e.key.toLowerCase();
      if (k === "arrowright" || k === "n") { e.preventDefault(); act("hold"); }
      else if (k === "a") { e.preventDefault(); setAuto((v) => !v); }
      else if (k === "c" && hasTrade) { e.preventDefault(); act("close", "You closed the trade at the next open."); }
    };
    window.addEventListener("keydown", on);
    return () => window.removeEventListener("keydown", on);
  }, [phase, act, hasTrade]);

  /* ----- derived values for drawing ----- */
  const series = setup?.series;
  const cur = series?.cur || "";
  const atr = round?.atr || 0;
  const lastVis = round ? round.candles[VISIBLE - 1] : null;
  const dir = side === "short" ? -1 : 1;
  const trade = live?.trade || null;
  const shown = live?.shown ?? VISIBLE;
  const k = shown - VISIBLE;                                  // hidden candles revealed so far
  const latest = round ? round.candles[shown - 1] : null;

  const chartLines = useChartLines({ round, phase, side, stopAtr, targetR, atr, lastVis, trade, result });

  const exit = result?.trade && result.trade.exit != null ? { k: result.exitK, price: result.trade.exit } : null;

  if (!setup) {
    return <div className={s.wrap}><p className={s.loading}>Loading the chart…</p></div>;
  }

  const ctx = round.ctx || {};
  const ret10 = asPct(ctx.ret10), ret30 = asPct(ctx.ret30), vs50 = asPct(ctx.vsSma50), rsi = ctx.rsi14;
  const shownCash = result ? result.entry.cashAfter : cash;
  const shownTilt = Math.round(result ? result.tiltAfter : tilt);

  // the plan preview, from the last close (the real entry is the next candle's open, still hidden)
  const prevStopDist = stopAtr * atr;
  const prevUnits = sizeUnits(cash, RISK_PCT, prevStopDist);
  const warnings = side === "long" || side === "short"
    ? detectMistakes(history, { side, stopAtr, targetR, round, at: openedAt }, null).filter((m) => ENTRY_KINDS.has(m.kind))
    : [];

  const title = phase === "plan" ? "Read the chart. What is your call?"
    : phase === "live" ? (trade ? `${side === "long" ? "You bought" : "You sold short"} · day ${k} of ${FUTURE}` : `Just watching · day ${k} of ${FUTURE}`)
      : "How did it go?";

  return (
    <div ref={rootRef} className={s.wrap} role="dialog" aria-label="Chart mission">
      <header className={s.head}>
        <span className={s.kicker}>{DISTRICT[series.district] || "Mission"} · mystery chart</span>
        <div className={s.headMeta}>
          <span className={s.pill} title="Game cash: not real money">Cash <b>{fmtCash(shownCash)}</b></span>
          <span className={`${s.pill} ${shownTilt >= 60 ? s.hot : shownTilt >= 30 ? s.warm : ""}`}>Tilt <b>{shownTilt}</b></span>
          {phase === "plan" ? (
            <button type="button" className={s.close} onClick={onExit} aria-label="Leave this mission">
              <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true"><path d="M6 6l12 12M18 6 6 18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" /></svg>
            </button>
          ) : null}
        </div>
        <h2 className={s.title}>{title}</h2>
      </header>

      <div className={s.grid}>
        <section className={s.card}>
          <CandleChart
            candles={round.candles} sma={setup.sma} shown={shown} lines={chartLines} exit={exit}
            dates={revealed} cur={cur} nowIdx={VISIBLE}
            label={revealed
              ? `Candlestick chart of ${series.name}, ${rangeText(round.candles[0].t, round.candles[total - 1].t)}.`
              : `Candlestick chart, name and dates hidden: ${VISIBLE} days shown, ${k} of ${FUTURE} future days revealed.`}
          />
          {phase === "plan" ? (
            <ul className={s.reads} aria-label="Reading the chart">
              <li>
                <span>Last 10 days</span><b className={tone(ret10)}>{fmtPct(ret10)}</b>
                <small>{ret10 > 15 ? "A big run-up. Buying now is where FOMO lives." : ret10 < -15 ? "A big drop. Selling now is where panic lives." : "Nothing extreme."}</small>
              </li>
              <li>
                <span>Last 30 days</span><b className={tone(ret30)}>{fmtPct(ret30)}</b>
                <small>{ret30 > 0 ? "Rising over the month." : "Falling over the month."}</small>
              </li>
              <li>
                <span>vs 50-day average</span><b className={tone(vs50)}>{fmtPct(vs50)}</b>
                <small>{vs50 > 0 ? "Above its average: an uptrend, for now." : "Below its average: a downtrend, for now."}</small>
              </li>
              <li>
                <span>RSI (14 days)</span><b>{rsi != null ? Math.round(rsi) : "—"}</b>
                <small>{rsi > 70 ? "Stretched up: it rose fast." : rsi < 30 ? "Stretched down: it fell fast." : "In the normal 30-70 zone."}</small>
              </li>
            </ul>
          ) : null}
        </section>

        <section className={`${s.card} ${s.panel}`}>
          {phase === "plan" ? (
            <PlanPanel {...{ side, setSide, stopAtr, setStopAtr, targetR, setTargetR, atr, lastVis, cur, riskCash, prevUnits, warnings, tilt, onExit, series }}
              onStart={() => {
                if (!side) return;
                const t0 = side === "skip" ? null : planTrade(round, { side, stopAtr, targetR });
                // the first hidden candle is the entry candle: reveal it straight away so the fill is visible
                const first = round.candles[VISIBLE];
                setLive({ trade: t0 ? stepTrade(t0, first, "hold") : null, shown: VISIBLE + 1, at: Date.now() });
                setNote(t0 ? `Filled at the open: ${fmtPrice(t0.entry, cur)}.` : "");
                setPhase("live");
              }} />
          ) : phase === "live" ? (
            <LivePanel {...{ trade, side, dir, k, latest, atr, cur, riskCash, auto, setAuto, moveOpen, setMoveOpen, note, act }}
              onWatchEnd={() => finish({ ...live, shown: total })} />
          ) : (
            <ResultPanel {...{ result, side, cur, series, round, revealed, setRevealed, onExit }} riskCash={(result.entry.cashBefore * RISK_PCT) / 100} />
          )}
        </section>
      </div>
      <p className={s.foot}>Practice with game cash only: no real money and no real orders. Real past prices, name and dates hidden until the end.</p>
    </div>
  );
}

/**
 * Entry, stop and target lines for the chart. `tone` names a colour the chart reads from the theme ("ink2", "down",
 * "up"); `from` is the candle slot the line starts at.
 */
function useChartLines({ round, phase, side, stopAtr, targetR, atr, lastVis, trade, result }) {
  return useMemo(() => {
    if (!round) return [];
    const tr = result ? result.trade : trade;
    if (tr && (tr.side === "long" || tr.side === "short")) {
      const out = [{ key: "entry", price: tr.entry, tone: "ink2", dash: [5, 4], from: VISIBLE - 0.5, label: "Entry" }];
      const planned = tr.stop0 ?? tr.moves?.[0]?.from ?? null;   // the stop as planned, kept faint once moved
      if (planned != null && planned !== tr.stop) out.push({ key: "stop0", price: planned, tone: "down", dash: [2, 3], alpha: 0.45, from: VISIBLE - 0.5, width: 1 });
      out.push({ key: "stop", price: tr.stop, tone: "down", from: VISIBLE - 0.5, label: "Stop" });
      if (tr.target != null) out.push({ key: "target", price: tr.target, tone: "up", from: VISIBLE - 0.5, label: "Target" });
      return out;
    }
    if (phase === "plan" && (side === "long" || side === "short") && lastVis) {
      // preview from the last close: dashed and lighter, since the real entry is the next (hidden) open
      const d = side === "short" ? -1 : 1;
      const out = [{ key: "stop", price: lastVis.c - d * stopAtr * atr, tone: "down", dash: [4, 4], alpha: 0.8, from: VISIBLE - 1, label: "Stop", approx: true }];
      if (targetR != null) out.push({ key: "target", price: lastVis.c + d * targetR * stopAtr * atr, tone: "up", dash: [4, 4], alpha: 0.8, from: VISIBLE - 1, label: "Target", approx: true });
      return out;
    }
    return [];
  }, [round, result, trade, phase, side, stopAtr, targetR, atr, lastVis]);
}

/* ---------- panels ---------- */

function Seg({ label, children }) {
  return <div className={s.seg} role="group" aria-label={label}>{children}</div>;
}

function PlanPanel({ side, setSide, stopAtr, setStopAtr, targetR, setTargetR, atr, lastVis, cur, riskCash, prevUnits, warnings, tilt, onExit, series, onStart }) {
  const trading = side === "long" || side === "short";
  const stopDist = stopAtr * atr;
  const word = side === "short" ? "above" : "below";
  return (
    <div className={s.planBody}>
      <h3 className={s.h3}>Your call</h3>
      <div className={s.sides} role="group" aria-label="Your call">
        <button type="button" className={`${s.sideBtn} ${s.buy}`} aria-pressed={side === "long"} onClick={() => setSide("long")}>
          <span className={s.sideIcon} aria-hidden="true">▲</span>Buy<small>win if it rises</small>
        </button>
        <button type="button" className={`${s.sideBtn} ${s.sell}`} aria-pressed={side === "short"} onClick={() => setSide("short")}>
          <span className={s.sideIcon} aria-hidden="true">▼</span>Sell<small>win if it falls</small>
        </button>
        <button type="button" className={`${s.sideBtn} ${s.skip}`} aria-pressed={side === "skip"} onClick={() => setSide("skip")}>
          <span className={s.sideIcon} aria-hidden="true">◦</span>Stay out<small>just watch</small>
        </button>
      </div>

      {trading ? (
        <>
          <div className={s.field}>
            <div className={s.fieldHead}><span>Stop-loss</span><b>{stopAtr} ATR ≈ {fmtPrice(stopDist, cur)} {word}</b></div>
            <Seg label="Stop distance in ATR">
              {STOPS.map((v) => <button key={v} type="button" aria-pressed={stopAtr === v} onClick={() => setStopAtr(v)}>{v}</button>)}
            </Seg>
            <p className={s.help}>
              ATR is the typical daily move here, about {fmtPrice(atr, cur)} ({((100 * atr) / lastVis.c).toFixed(1)}% of the price).
              A tight stop gets hit by normal noise; a wide one costs the same $ but needs fewer units.
            </p>
          </div>
          <div className={s.field}>
            <div className={s.fieldHead}><span>Target</span><b>{targetR == null ? "None: you decide" : `${targetR}R = +${fmtCash(targetR * riskCash)}`}</b></div>
            <Seg label="Target in R">
              {TARGETS.map((v) => <button key={String(v)} type="button" aria-pressed={targetR === v} onClick={() => setTargetR(v)}>{v == null ? "None" : `${v}R`}</button>)}
            </Seg>
            <p className={s.help}>1R is the distance to your stop. A 2R target wins twice what the stop loses.</p>
          </div>
          <div className={s.risk}>
            <span>Risk, fixed at {RISK_PCT}% of game cash</span>
            <b>{fmtCash(riskCash)} if the stop is hit</b>
            <small>Size about {prevUnits >= 100 ? Math.round(prevUnits).toLocaleString("en-US") : prevUnits.toPrecision(3)} units of a {fmtPrice(lastVis.c, cur)} {series.market === "crypto" ? "coin" : "share"}. You get in at the next candle&apos;s open.</small>
          </div>
        </>
      ) : side === "skip" ? (
        <p className={s.help}>No trade, no risk. You will still see what happened next, and what a buy, a sell and a coin flip would have done. Staying out of an unclear chart is a skill.</p>
      ) : (
        <p className={s.help}>Pick Buy, Sell or Stay out. Nothing happens until you press start.</p>
      )}

      {warnings.length ? (
        <div className={s.checks} role="note">
          <b>Check yourself first</b>
          {warnings.map((m) => <p key={m.kind}><span className={s.checkTitle}>{m.title}?</span> {m.message}</p>)}
        </div>
      ) : null}
      {tilt >= 60 ? (
        <p className={s.tiltWarn}>Your tilt is {Math.round(tilt)}. On tilt, people trade to feel better, not because the chart is good. Staying out, or a drive to Cool-down Park, is a fine move.</p>
      ) : null}

      <div className={s.actions}>
        <button type="button" className={s.go} disabled={!side} onClick={onStart}>
          {side === "long" ? "Buy at the next open" : side === "short" ? "Sell at the next open" : side === "skip" ? "Stay out and watch" : "Pick a side first"}
        </button>
        <button type="button" className={s.ghost} onClick={onExit}>Leave</button>
      </div>
    </div>
  );
}

function nudge(trade, r) {
  if (!trade) return "No money on it. Notice how calm it feels to watch without a position: that is the mind you want when you decide.";
  if (r <= -0.6) return "This is where it hurts. Your stop is your plan: moving it further away turns a small loss into a big one.";
  if (trade.targetR >= 2 && r >= 0.8) return "In profit and itching to grab it? Closing winners early keeps wins small while losses stay full size.";
  if (r >= 0.5 && trade.stop != null && (trade.side === "short" ? trade.stop > trade.entry : trade.stop < trade.entry)) return "Doing well. Moving the stop to breakeven is allowed: it protects you, but it can also shake you out of a good trade.";
  return "Stop and target are set. You can just press Next and let the plan work.";
}

function LivePanel({ trade, side, dir, k, latest, atr, cur, riskCash, auto, setAuto, moveOpen, setMoveOpen, note, act, onWatchEnd }) {
  const sheetRef = useRef(null);
  // on a phone the stop choices open below the fold: bring them into view
  useEffect(() => { if (moveOpen) sheetRef.current?.scrollIntoView({ block: "nearest", behavior: "smooth" }); }, [moveOpen]);
  const px = latest.c;
  const r = trade ? trade.r : 0;   // while open, the engine marks r at the last close, net of costs
  const atBe = trade && (dir > 0 ? trade.stop >= trade.entry : trade.stop <= trade.entry);
  const canBe = trade && !atBe && dir * (px - trade.entry) > 0;
  const fix = (v) => Number(v.toPrecision(5));
  const moves = trade ? [
    { key: "tight", label: "Tighten by ½ ATR", sub: "closer to the price", price: fix(trade.stop + dir * 0.5 * atr) },
    { key: "trail", label: "Trail behind the last candle", sub: dir > 0 ? "just under its low" : "just over its high", price: fix(dir > 0 ? latest.l : latest.h) },
    { key: "wide", label: "Give it more room", sub: "½ ATR further away", price: fix(trade.stop - dir * 0.5 * atr) },
  ].filter((m) => m.price > 0 && dir * (px - m.price) > 0 && Math.abs(m.price - trade.stop) > 1e-9
    && (m.key !== "trail" || dir * (m.price - trade.stop) > 0)) : [];

  return (
    <div className={s.liveBody}>
      <div className={s.progress} aria-label={`Day ${k} of ${FUTURE}`}>
        <i style={{ width: `${(100 * k) / FUTURE}%` }} />
      </div>
      {trade ? (
        <>
          <div className={s.pnl}>
            <b className={`${s.pnlBig} ${tone(r, 0.01)}`}>{fmtR(r)}</b>
            <span className={s.pnlSide}>
              <b className={tone(r, 0.01)}>{fmtCash(r * riskCash, true)} game cash</b>
              <small>{side === "long" ? "Bought" : "Sold short"} · open result, after costs</small>
            </span>
          </div>
          <dl className={s.levels}>
            <div><dt>Now</dt><dd>{fmtPrice(px, cur)}</dd></div>
            <div><dt>Entry</dt><dd>{fmtPrice(trade.entry, cur)}</dd></div>
            <div><dt>Stop</dt><dd className={s.down}>{fmtPrice(trade.stop, cur)}</dd></div>
            <div><dt>Target</dt><dd className={s.up}>{trade.target != null ? fmtPrice(trade.target, cur) : "none"}</dd></div>
          </dl>
        </>
      ) : (
        <div className={s.pnl}>
          <b className={s.pnlBig}>{fmtPrice(px, cur)}</b>
          <span className={s.pnlSide}><b>Price now</b><small>No position: just watching</small></span>
        </div>
      )}
      <p className={s.nudge} aria-live="polite">{note ? <b className={s.note}>{note} </b> : null}{nudge(trade, r)}</p>

      <div className={s.controls}>
        <button type="button" className={s.next} onClick={() => act("hold")}>Next candle</button>
        <button type="button" className={s.autoBtn} aria-pressed={auto} onClick={() => setAuto((v) => !v)}>
          {auto ? "Pause" : "Auto"}
        </button>
      </div>
      {trade ? (
        <>
          <div className={s.controls3}>
            <button type="button" onClick={() => act("close", "You closed the trade at the next open.")}>Close now</button>
            <button type="button" disabled={!canBe} title={canBe ? "" : atBe ? "Already at breakeven or better" : "Only when the trade is in profit"}
              onClick={() => act({ moveStop: trade.entry }, `Stop moved to breakeven (${fmtPrice(trade.entry, cur)}).`)}>Stop to breakeven</button>
            <button type="button" aria-expanded={moveOpen} onClick={() => setMoveOpen((v) => !v)}>Move stop</button>
          </div>
          {moveOpen ? (
            <div className={s.moveSheet} ref={sheetRef}>
              <p>Pick a new stop. It applies from the next candle.</p>
              {moves.map((m) => (
                <button key={m.key} type="button"
                  onClick={() => act({ moveStop: m.price }, `Stop moved to ${fmtPrice(m.price, cur)}.`)}>
                  <span>{m.label}<small>{m.sub}</small></span><b>{fmtPrice(m.price, cur)}</b>
                </button>
              ))}
              {!moves.length ? <p className={s.help}>No sensible new stop right now.</p> : null}
              <button type="button" className={s.ghost} onClick={() => setMoveOpen(false)}>Keep the stop where it is</button>
            </div>
          ) : null}
        </>
      ) : (
        <div className={s.controls3}>
          <button type="button" className={s.wideBtn} onClick={onWatchEnd}>Skip to the result</button>
        </div>
      )}
      <p className={s.keys}>Keys: → next · A auto{trade ? " · C close" : ""}</p>
    </div>
  );
}

const HEADLINE = { target: "Target hit", stopped: "Stopped out", closed: "You closed it", timeout: `Time is up: ${FUTURE} days passed` };

function ResultPanel({ result, side, cur, series, round, revealed, setRevealed, onExit, riskCash }) {
  if (!result) return null;
  const { entry, trade, long, short, stats: st } = result;
  const r = entry.r;
  const skip = side === "skip";
  let head = skip ? "You stayed out" : HEADLINE[trade.status] || "Done";
  if (!skip && trade.status === "stopped" && r > -0.2) head = r > 0.05 ? "Stopped out in profit" : "Stopped out near breakeven";
  const diff = r - entry.coinR;
  const isGood = (m) => m.good || m.kind === "discipline";
  const bad = entry.mistakes.filter((m) => !isGood(m));
  const good = entry.mistakes.filter(isGood);
  const scale = Math.max(1, Math.abs(r), Math.abs(entry.coinR), Math.abs(long ?? 0), Math.abs(short ?? 0));
  const bar = (v) => ({ width: `${(50 * Math.min(Math.abs(v), scale)) / scale}%`, [v >= 0 ? "left" : "right"]: "50%" });
  const tradesN = st?.trades ?? 0;
  const t0 = round.candles[0].t, t1 = round.candles[round.candles.length - 1].t;

  let verdict;
  if (skip) verdict = bad.length ? "You stayed out, but notice the pattern flagged below." : "No trade can be the best trade. You kept your cash and your head.";
  else if (r < 0 && !bad.length) verdict = "A loss with a clean plan is still a good decision. Losses are the cost of doing business; what matters is that they stay small.";
  else if (r > 0 && bad.length) verdict = "You made money, but with a mistake. Lucky wins teach bad habits: judge the decision, not the result.";
  else if (r > 0) verdict = "A clean plan that paid. Good process and a good result.";
  else verdict = "A loss and a mistake: the lesson below is the useful part.";

  return (
    <div className={s.resultBody}>
      <p className={s.kick}>{head}</p>
      <div className={s.bigRow}>
        <b className={`${s.bigR} ${tone(r, 0.01)}`}>{skip ? "0R" : fmtR(r)}</b>
        <span className={s.cashMove}>
          <b className={tone(r, 0.01)}>{fmtCash(entry.cashAfter - entry.cashBefore, true)}</b>
          <small>{fmtCash(entry.cashBefore)} → {fmtCash(entry.cashAfter)} game cash</small>
        </span>
      </div>
      {!skip ? <p className={s.help}>1R = {fmtCash(riskCash)}, the amount you risked. Results are after trading costs.</p> : null}
      <p className={s.verdict}>{verdict}</p>

      <div className={s.block}>
        <h4>You vs a coin flip</h4>
        <div className={s.bars}>
          {[[skip ? "You (out)" : "You", r, true], ["Coin flip", entry.coinR, false], ["Buy, hands off", long, false], ["Sell, hands off", short, false]]
            .map(([nm, v, me]) => (
              <div key={nm} className={`${s.barRow} ${me ? s.me : ""}`}>
                <span>{nm}</span>
                <span className={s.track}><i className={v >= 0 ? s.barUp : s.barDown} style={bar(v ?? 0)} /></span>
                <b className={tone(v ?? 0, 0.01)}>{fmtR(v ?? 0)}</b>
              </div>
            ))}
        </div>
        {skip ? (
          <p className={s.help}>
            Staying out earns 0R. A coin flip (buy or sell at random, a {entry.stopAtr} ATR stop, {entry.targetR ? `a ${entry.targetR}R target` : "no target"},
            hands off) would have averaged {fmtR(entry.coinR)} here: buying {fmtR(long)}, selling {fmtR(short)}. Nobody knows
            which one in advance, which is why staying out of an unclear chart costs you nothing.
          </p>
        ) : (
          <p className={s.help}>
            The coin flip picks buy or sell at random with your stop and target and never touches the trade: on average it
            earns {fmtR(entry.coinR)} here. {Math.abs(diff) < 0.05 ? "You matched it this time." : diff > 0 ? `You beat it by ${fmtR(diff).replace("+", "")} this round.` : `It beat you by ${fmtR(-diff).replace("+", "")} this round.`}
            {" "}One round is mostly luck.
          </p>
        )}
        {st ? (
          <p className={s.help}>
            {tradesN
              ? <>Over your {tradesN} trade{tradesN === 1 ? "" : "s"}: you average <b>{fmtR(st.avgR)}</b>, the coin <b>{fmtR(st.coinFlipAvgR)}</b>, an edge of <b className={tone(st.edgeR, 0.01)}>{fmtR(st.edgeR)}</b> per trade. </>
              : null}
            {tradesN < 30 || !(Math.abs(st.t) >= 2)
              ? "Too early to call it skill: it takes about 30 trades and an edge well clear of the coin."
              : st.edgeR > 0 ? "That edge is now hard to explain by luck alone. Keep the same discipline." : "The coin is reliably ahead of you: the mistakes below are costing real edge."}
          </p>
        ) : null}
      </div>

      <div className={s.block}>
        <h4>Mistakes and lessons</h4>
        {bad.length ? bad.map((m) => (
          <div key={m.kind} className={s.mistake}>
            <div className={s.mHead}>
              <b>{m.title}</b>
              <span className={s.sev} aria-label={`Severity ${m.severity} of 3`}>{[1, 2, 3].map((i) => <i key={i} className={i <= m.severity ? s.sevOn : ""} />)}</span>
            </div>
            <p>{m.message}</p>
            {m.lesson ? <p className={s.lesson}>{m.lesson}</p> : null}
          </div>
        )) : <p className={s.help}>No emotional mistakes spotted. That is the part you control.</p>}
        {good.map((m) => (
          <div key={`g-${m.title}`} className={`${s.mistake} ${s.goodOne}`}>
            <div className={s.mHead}><b>{m.title}</b></div>
            <p>{m.message}</p>
            {m.lesson ? <p className={s.lesson}>{m.lesson}</p> : null}
          </div>
        ))}
        <p className={s.tiltLine}>
          Tilt {Math.round(result.tiltBefore)} → <b className={result.tiltAfter >= 60 ? s.down : ""}>{Math.round(result.tiltAfter)}</b>
          {result.tiltAfter >= 60 ? ". High: a drive to Cool-down Park before the next mission would help." : result.tiltAfter > result.tiltBefore ? ". Rising: slow down." : ". Calm and steady."}
        </p>
      </div>

      <div className={`${s.block} ${s.reveal} ${revealed ? s.revealed : ""}`}>
        {revealed ? (
          <>
            <span className={s.kicker}>It was</span>
            <p className={s.revealName}>{series.name} <small>{series.symbol}</small></p>
            <p className={s.revealDates}>{rangeText(t0, t1)}</p>
            {!skip && trade ? (
              <p className={s.help}>Your trade: {rangeText(round.candles[VISIBLE].t, round.candles[Math.min(result.exitK, round.candles.length - 1)].t)}, entry {fmtPrice(trade.entry, cur)}, exit {fmtPrice(trade.exit, cur)}.</p>
            ) : null}
          </>
        ) : (
          <button type="button" className={s.revealBtn} onClick={() => setRevealed(true)}>
            What was it? <b>Reveal the name and dates</b>
          </button>
        )}
      </div>

      <div className={s.actions}>
        <button type="button" className={s.go} onClick={onExit}>Back to the city</button>
      </div>
    </div>
  );
}
