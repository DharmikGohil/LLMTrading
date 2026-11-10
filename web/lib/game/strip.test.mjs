import assert from "node:assert/strict";
import test from "node:test";
import { bs, ncdf, quote, realisedVol, settle, stripMistakes, stripStats } from "./strip.js";

const series = (closes) => ({ t: closes.map((_, i) => 20000 + i), c: closes });

test("normal CDF and Black-Scholes put-call parity (zero rates)", () => {
  assert.ok(Math.abs(ncdf(0) - 0.5) < 1e-6 && Math.abs(ncdf(1.96) - 0.975) < 1e-3);
  const c = bs("call", 100, 103, 5 / 252, 0.15), p = bs("put", 100, 103, 5 / 252, 0.15);
  assert.ok(Math.abs(c - p - (100 - 103)) < 1e-6);
  assert.equal(bs("call", 100, 90, 0, 0.2), 10);
});

test("the ticket costs more than its fair value: the house edge is positive", () => {
  const closes = Array.from({ length: 60 }, (_, i) => 20000 * (1 + 0.006 * Math.sin(i)));
  const q = quote(series(closes), 40, { type: "call", otmPct: 2, days: 5 });
  assert.ok(q.paid > q.mid && q.mid > q.fair && q.edgePct > 0);
  assert.ok(q.strike % 50 === 0 && q.strike > q.spot);
  assert.ok(q.odds > 0 && q.odds < 0.5);
  assert.ok(realisedVol(closes, 40) >= 0.1);
});

test("settle pays the intrinsic value at expiry, and nothing out of the money", () => {
  const closes = Array.from({ length: 60 }, () => 20000);
  closes.push(20200, 20400, 20600, 20800, 21000);       // a 5% rally over 5 days
  const s = series(closes);
  const q = quote(s, 59, { type: "call", otmPct: 2, days: 5 });
  const r = settle(s, q, 100);
  assert.equal(r.path.length, 5);
  assert.equal(r.intrinsic, 21000 - q.strike);
  assert.ok(Math.abs(r.payout - (100 / q.paid) * (21000 - q.strike)) < 1e-6);
  const put = settle(s, quote(s, 59, { type: "put", otmPct: 2, days: 5 }), 100);
  assert.equal(put.payout, 0);
  assert.equal(put.net, -100);
});

test("mistakes: far out-of-the-money tickets, and raising the stake after a loss", () => {
  assert.deepEqual(stripMistakes([], { otmPct: 1, stake: 100 }), []);
  assert.equal(stripMistakes([], { otmPct: 3, stake: 100 })[0].kind, "lottery");
  const lost = [{ kind: "strip", stake: 100, payout: 0 }];
  assert.equal(stripMistakes(lost, { otmPct: 1, stake: 250 })[0].kind, "chasing-losses");
  assert.deepEqual(stripMistakes(lost, { otmPct: 1, stake: 100 }), []);
});

test("Strip totals", () => {
  const h = [{ kind: "strip", stake: 100, payout: 0, fair: 70 }, { kind: "strip", stake: 100, payout: 250, fair: 70 },
             { kind: "chart", r: 1 }];
  const s = stripStats(h);
  assert.equal(s.tickets, 2);
  assert.equal(s.wins, 1);
  assert.equal(s.returnPct, 25);
  assert.equal(s.fairBack, 140);
});
