// Technical indicators for the price chart. Same definitions as indtrader/signals/chart.py and technical.py,
// so the chart shows what the analyst reads. Input arrays are oldest first; outputs align with them (null while
// warming up).

export function sma(x, n) {
  const out = new Array(x.length).fill(null);
  let s = 0;
  for (let i = 0; i < x.length; i++) {
    s += x[i];
    if (i >= n) s -= x[i - n];
    if (i >= n - 1) out[i] = s / n;
  }
  return out;
}

export function ema(x, n) {
  const a = 2 / (n + 1);
  const out = new Array(x.length).fill(null);
  let prev = null;
  for (let i = 0; i < x.length; i++) {
    if (x[i] == null) continue;
    prev = prev == null ? x[i] : a * x[i] + (1 - a) * prev;
    out[i] = prev;
  }
  return out;
}

/** Wilder's RSI (smoothing 1/n), as in pandas ewm(alpha=1/n, adjust=False). */
export function rsi(close, n = 14) {
  const out = new Array(close.length).fill(null);
  let g = 0, l = 0;
  for (let i = 1; i < close.length; i++) {
    const d = close[i] - close[i - 1];
    const up = Math.max(d, 0), dn = Math.max(-d, 0);
    if (i === 1) { g = up; l = dn; } else { g = g + (up - g) / n; l = l + (dn - l) / n; }
    if (i >= n) out[i] = l === 0 ? 100 : 100 - 100 / (1 + g / l);
  }
  return out;
}

export function macd(close, fast = 12, slow = 26, signal = 9) {
  const f = ema(close, fast), s = ema(close, slow);
  const line = close.map((_, i) => (f[i] != null && s[i] != null ? f[i] - s[i] : null));
  const sig = ema(line.map((v) => v ?? 0), signal).map((v, i) => (i < slow - 1 ? null : v));
  return { line: line.map((v, i) => (i < slow - 1 ? null : v)), signal: sig, hist: line.map((v, i) => (i < slow - 1 || sig[i] == null ? null : v - sig[i])) };
}

export function bollinger(close, n = 20, k = 2) {
  const mid = sma(close, n);
  const upper = new Array(close.length).fill(null), lower = new Array(close.length).fill(null);
  for (let i = n - 1; i < close.length; i++) {
    let v = 0;
    for (let j = i - n + 1; j <= i; j++) v += (close[j] - mid[i]) ** 2;
    const sd = Math.sqrt(v / n);
    upper[i] = mid[i] + k * sd;
    lower[i] = mid[i] - k * sd;
  }
  return { mid, upper, lower };
}

export function atr(bars, n = 14) {
  const out = new Array(bars.length).fill(null);
  let prev = null;
  for (let i = 0; i < bars.length; i++) {
    const b = bars[i], pc = i ? bars[i - 1].c : b.c;
    const tr = Math.max(b.h - b.l, Math.abs(b.h - pc), Math.abs(b.l - pc));
    prev = prev == null ? tr : prev + (tr - prev) / n;
    out[i] = prev;
  }
  return out;
}

/** Horizontal support/resistance: fractal swing points (k bars each side) clustered within tol x ATR. */
export function levels(bars, { k = 5, tolAtr = 0.6, lookback = 250, max = 4 } = {}) {
  const d = bars.slice(-lookback);
  if (d.length < 2 * k + 10) return { support: [], resistance: [] };
  const a = atr(d).at(-1) || 0;
  const tol = Math.max(tolAtr * a, 1e-9);
  const pts = [];
  for (let i = k; i < d.length - k; i++) {
    const win = d.slice(i - k, i + k + 1);
    if (d[i].h === Math.max(...win.map((b) => b.h))) pts.push([i, d[i].h]);
    if (d[i].l === Math.min(...win.map((b) => b.l))) pts.push([i, d[i].l]);
  }
  pts.sort((x, y) => x[1] - y[1]);
  const clusters = [];
  for (const p of pts) {
    const c = clusters.at(-1);
    if (c && p[1] - c.reduce((s, q) => s + q[1], 0) / c.length <= tol) c.push(p);
    else clusters.push([p]);
  }
  const last = d.at(-1).c, n = d.length;
  const lv = clusters.filter((c) => c.length >= 2).map((c) => ({
    price: c.reduce((s, q) => s + q[1], 0) / c.length,
    touches: c.length,
    strength: c.reduce((s, [i]) => s + 0.5 + (0.5 * i) / n, 0),
  }));
  const pick = (xs) => xs.sort((x, y) => y.strength - x.strength).slice(0, max);
  return { support: pick(lv.filter((x) => x.price < last)), resistance: pick(lv.filter((x) => x.price >= last)) };
}

/** Candlestick patterns on the last bar, in the context of the prior trend (same rules as chart.py). */
export function candles(bars, trendBars = 10) {
  const n = bars.length;
  if (n < trendBars + 2) return [];
  const b = bars[n - 1], p = bars[n - 2];
  const body = Math.abs(b.c - b.o), rng = b.h - b.l;
  if (rng <= 0) return [];
  const upper = b.h - Math.max(b.o, b.c), lower = Math.min(b.o, b.c) - b.l;
  const falling = p.c < bars[n - 2 - trendBars].c, rising = p.c > bars[n - 2 - trendBars].c;
  const out = [];
  if (body <= 0.1 * rng) out.push("doji");
  if (lower >= 2 * body && upper <= 0.25 * rng && body > 0) out.push(falling ? "hammer" : rising ? "hanging man" : "hammer-shaped");
  if (upper >= 2 * body && lower <= 0.25 * rng && body > 0) out.push(rising ? "shooting star" : falling ? "inverted hammer" : "inverted-hammer-shaped");
  const pLo = Math.min(p.o, p.c), pHi = Math.max(p.o, p.c);
  if (b.c > b.o && p.c < p.o && b.o <= pLo && b.c >= pHi) out.push("bullish engulfing");
  if (b.c < b.o && p.c > p.o && b.o >= pHi && b.c <= pLo) out.push("bearish engulfing");
  if (b.h < p.h && b.l > p.l) out.push("inside bar");
  if (b.h > p.h && b.l < p.l) out.push("outside bar");
  return out;
}
