// The Strip: casino-style missions that teach the house edge of buying cheap options ("lottery tickets").
// Pure functions, no DOM. Game cash only.
//
// A ticket is an out-of-the-money Nifty option (a call pays if the Nifty ends above the strike, a put if it ends
// below) bought at the close of a real past day and settled at the close `days` trading days later. It is priced
// the way option sellers price it: implied volatility above recent realised volatility, plus a bid-ask spread.
// The "fair" value uses realised volatility only, so paid - fair is the house edge you hand over on every ticket.

export const IV_MARKUP = 1.25;   // implied volatility usually sits above realised; sellers are paid for the risk
export const SPREAD = 0.05;      // the buyer pays about 5% over the middle price on cheap options
export const MIN_VOL = 0.1;      // never price with less than 10% a year
export const LOOKBACK = 20;      // realised volatility over the last 20 trading days

// Abramowitz-Stegun approximation of the normal CDF (error < 1e-7)
export function ncdf(x) {
  const t = 1 / (1 + 0.2316419 * Math.abs(x));
  const d = 0.3989422804 * Math.exp((-x * x) / 2);
  const p = d * t * (0.31938153 + t * (-0.356563782 + t * (1.781477937 + t * (-1.821255978 + t * 1.330274429))));
  return x > 0 ? 1 - p : p;
}

/** Black-Scholes price with zero rates. type "call" | "put"; years > 0; vol a yearly fraction. */
export function bs(type, spot, strike, years, vol) {
  if (years <= 0 || vol <= 0) return Math.max(0, type === "call" ? spot - strike : strike - spot);
  const s = vol * Math.sqrt(years);
  const d1 = (Math.log(spot / strike) + 0.5 * s * s) / s;
  const d2 = d1 - s;
  return type === "call" ? spot * ncdf(d1) - strike * ncdf(d2) : strike * ncdf(-d2) - spot * ncdf(-d1);
}

/** Yearly realised volatility from the LOOKBACK daily closes ending at index i (inclusive). */
export function realisedVol(closes, i) {
  const r = [];
  for (let k = Math.max(1, i - LOOKBACK + 1); k <= i; k++) r.push(Math.log(closes[k] / closes[k - 1]));
  const m = r.reduce((a, b) => a + b, 0) / r.length;
  const v = r.reduce((a, b) => a + (b - m) ** 2, 0) / Math.max(1, r.length - 1);
  return Math.max(MIN_VOL, Math.sqrt(v * 252));
}

/** Price a ticket at the close of day i. Returns everything the screen shows before you buy. */
export function quote(series, i, { type, otmPct, days }) {
  const spot = series.c[i];
  const strike = Math.round((type === "call" ? spot * (1 + otmPct / 100) : spot * (1 - otmPct / 100)) / 50) * 50;
  const years = days / 252;
  const rv = realisedVol(series.c, i);
  const iv = Math.max(MIN_VOL, rv * IV_MARKUP);
  const fair = bs(type, spot, strike, years, rv);
  const mid = bs(type, spot, strike, years, iv);
  const paid = mid * (1 + SPREAD);
  // chance the ticket pays back more than it cost (lognormal, realised vol, no drift)
  const be = type === "call" ? strike + paid : strike - paid;
  const s = rv * Math.sqrt(years);
  const z = Math.log(be / spot) / s + 0.5 * s;
  const odds = be <= 0 ? 0 : type === "call" ? 1 - ncdf(z) : ncdf(z);
  return { i, spot, strike, days, type, otmPct, rv, iv, fair, mid, paid, breakeven: be, odds,
           edgePct: paid > 0 ? (100 * (paid - fair)) / paid : 0 };
}

/** A random past day for a ticket: needs LOOKBACK days before it and `days` after it. */
export function pickDay(series, rand, days = 5) {
  const lo = LOOKBACK + 1, hi = series.c.length - 1 - days;
  return lo + Math.floor(rand() * (hi - lo + 1));
}

/** Settle a quoted ticket on the real path. stake in game cash; returns the path to reveal and the result. */
export function settle(series, q, stake) {
  const units = stake / q.paid;
  const path = [];
  for (let k = 1; k <= q.days; k++) {
    const c = series.c[q.i + k];
    path.push({ t: series.t[q.i + k], close: c, chg: (100 * (c / series.c[q.i + k - 1] - 1)) });
  }
  const last = path[path.length - 1].close;
  const intrinsic = Math.max(0, q.type === "call" ? last - q.strike : q.strike - last);
  const payout = units * intrinsic;
  return { path, units, intrinsic, payout, net: payout - stake, fairStake: units * q.fair };
}

/** Mistakes specific to the Strip. history: earlier entries (any kind); decision: { otmPct, stake }. */
export function stripMistakes(history, decision) {
  const out = [];
  if (decision.otmPct >= 3) {
    out.push({ kind: "lottery", severity: 2, title: "Lottery ticket",
      message: "A ticket this far out is cheap because it almost never pays. Cheap is not the same as good value.",
      lesson: "Lottery preference: people overpay for small chances of a big win (Kumar 2009; Bali, Cakici & Whitelaw 2011)." });
  }
  const prev = [...history].reverse().find((h) => h.kind === "strip");
  if (prev && prev.payout < prev.stake && decision.stake > prev.stake) {
    out.push({ kind: "chasing-losses", severity: 3, title: "Chasing losses",
      message: "You raised the stake straight after a loss. That is how a small loss becomes a big one.",
      lesson: "Break-even effect: after a loss, people take bigger risks to win it back (Thaler & Johnson 1990)." });
  }
  return out;
}

/** Running totals on the Strip. */
export function stripStats(history) {
  const s = history.filter((h) => h.kind === "strip");
  const staked = s.reduce((a, h) => a + h.stake, 0);
  const back = s.reduce((a, h) => a + h.payout, 0);
  const fair = s.reduce((a, h) => a + (h.fair || 0), 0);
  return { tickets: s.length, wins: s.filter((h) => h.payout > h.stake).length, staked, back,
           returnPct: staked ? (100 * (back - staked)) / staked : 0, fairBack: fair };
}
