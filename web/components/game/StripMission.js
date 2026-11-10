"use client";
// The Strip: a neon casino-style mission that teaches the house edge of option "lottery tickets".
// Props match Mission: { data, seed, history, cash, tilt, onDone(result), onExit() }. Game cash only.
import { useEffect, useMemo, useRef, useState } from "react";
import { pickDay, quote, settle, stripMistakes, stripStats } from "@/lib/game/strip";
import s from "./StripMission.module.css";

const CASINOS = ["The Lucky Strike", "Expiry Palace", "Theta Lounge", "The Gamma Room"];
const STAKES = [50, 100, 250];

function rng(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const money = (v) => `$${Math.abs(v) >= 1000 ? Math.round(v).toLocaleString("en-US") : (Math.round(v * 100) / 100).toFixed(2)}`;
const pts = (v) => Math.round(v).toLocaleString("en-IN");
const day = (t) => new Date(t * 86400000).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });

function Spark({ closes, strike }) {
  const lo = Math.min(...closes, strike), hi = Math.max(...closes, strike), w = 300, h = 70;
  const y = (v) => h - 4 - ((v - lo) / (hi - lo || 1)) * (h - 8);
  const d = closes.map((v, i) => `${i ? "L" : "M"}${((i / (closes.length - 1)) * w).toFixed(1)},${y(v).toFixed(1)}`).join("");
  return (
    <svg className={s.spark} viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" aria-hidden="true">
      <line x1="0" x2={w} y1={y(strike)} y2={y(strike)} className={s.strikeLine} />
      <path d={d} className={s.sparkPath} />
    </svg>
  );
}

export default function StripMission({ data, seed, history = [], cash, onDone, onExit }) {
  const nifty = useMemo(() => data?.series?.find((x) => x.id === "nifty"), [data]);
  const casino = CASINOS[(seed >>> 3) % CASINOS.length];
  const [i] = useState(() => (nifty ? pickDay(nifty, rng(seed), 5) : 0));
  const [type, setType] = useState("call");
  const [otmPct, setOtm] = useState(2);
  const [days, setDays] = useState(5);
  const maxStake = Math.max(50, Math.floor((cash * 0.05) / 50) * 50);
  const [stake, setStake] = useState(100);
  const [phase, setPhase] = useState("pick");          // pick -> spin -> result
  const [shown, setShown] = useState(0);
  const [rolling, setRolling] = useState(null);
  const sent = useRef(false);

  const q = useMemo(() => (nifty ? quote(nifty, i, { type, otmPct, days }) : null), [nifty, i, type, otmPct, days]);
  const res = useMemo(() => (phase !== "pick" && q ? settle(nifty, q, stake) : null), [phase, q, nifty, stake]);
  const mistakes = useMemo(() => stripMistakes(history, { otmPct, stake }), [history, otmPct, stake]);

  // reveal one trading day at a time, with a short "reel" of random numbers before each settles
  useEffect(() => {
    if (phase !== "spin" || !res) return undefined;
    if (shown >= res.path.length) { setPhase("result"); return undefined; }
    const target = res.path[shown].close;
    let n = 0;
    const roll = setInterval(() => {
      n += 1;
      setRolling(target * (1 + (Math.random() - 0.5) * 0.04));
      if (n >= 10) { clearInterval(roll); setRolling(null); setShown((k) => k + 1); }
    }, 70);
    return () => clearInterval(roll);
  }, [phase, shown, res]);

  useEffect(() => {
    if (phase !== "result" || !res || sent.current) return;
    sent.current = true;
    onDone?.({ kind: "strip", seriesId: "nifty", side: type, stake, payout: res.payout, fair: res.fairStake,
      edgePct: q.edgePct, otmPct, days, r: null, coinR: null, mistakes,
      cashBefore: cash, cashAfter: cash - stake + res.payout, at: Date.now() });
  }, [phase, res, onDone, type, stake, q, otmPct, days, mistakes, cash]);

  if (!nifty || !q) return <div className={s.wrap}><p>Loading the Strip…</p></div>;
  const closes = nifty.c.slice(i - 29, i + 1);
  const total = stripStats(phase === "result" ? [...history, { kind: "strip", stake, payout: res.payout, fair: res.fairStake }] : history);
  const units = stake / q.paid;
  const fairStake = units * q.fair;
  const word = type === "call" ? "above" : "below";

  return (
    <div className={s.wrap} role="dialog" aria-label={`${casino}: lottery tickets on the Nifty`}>
      <div className={s.sign}>
        <span className={s.neon}>{casino}</span>
        <span className={s.tag}>Lottery tickets on the Nifty · game cash only</span>
      </div>

      {phase === "pick" ? (
        <div className={s.card}>
          <p className={s.lead}>
            A real past day, date hidden. Buy a ticket that pays if the Nifty ends far enough {type === "call" ? "up" : "down"}.
            Everything the seller knows is on the ticket. Read it before you buy.
          </p>
          <Spark closes={closes} strike={q.strike} />
          <div className={s.row}><span>Nifty now</span><b>{pts(q.spot)}</b></div>

          <div className={s.group} role="group" aria-label="Ticket direction">
            <button type="button" aria-pressed={type === "call"} onClick={() => setType("call")}>Up ticket</button>
            <button type="button" aria-pressed={type === "put"} onClick={() => setType("put")}>Down ticket</button>
          </div>
          <div className={s.group} role="group" aria-label="How far away">
            {[1, 2, 3].map((p) => <button key={p} type="button" aria-pressed={otmPct === p} onClick={() => setOtm(p)}>{p}% away</button>)}
          </div>
          <div className={s.group} role="group" aria-label="Expiry">
            <button type="button" aria-pressed={days === 1} onClick={() => setDays(1)}>Tomorrow</button>
            <button type="button" aria-pressed={days === 5} onClick={() => setDays(5)}>In 5 days</button>
          </div>
          <div className={s.group} role="group" aria-label="Stake">
            {STAKES.filter((v) => v <= maxStake).map((v) => <button key={v} type="button" aria-pressed={stake === v} onClick={() => setStake(v)}>{money(v)}</button>)}
          </div>

          <dl className={s.ticket}>
            <div><dt>Pays if the Nifty closes {word}</dt><dd>{pts(q.strike)}</dd></div>
            <div><dt>To make a profit it must close {word}</dt><dd>{pts(q.breakeven)}</dd></div>
            <div><dt>Chance it pays back more than it cost</dt><dd className={s.hot}>{(100 * q.odds).toFixed(0)}%</dd></div>
            <div><dt>You pay</dt><dd>{money(stake)}</dd></div>
            <div><dt>Fair value of the same ticket</dt><dd>{money(fairStake)}</dd></div>
            <div><dt>House edge (what the seller keeps)</dt><dd className={s.hot}>{q.edgePct.toFixed(0)}%</dd></div>
          </dl>
          {mistakes.map((m) => <p key={m.kind} className={s.warn}><b>{m.title}.</b> {m.message}</p>)}
          <div className={s.actions}>
            <button type="button" className={s.go} onClick={() => setPhase("spin")}>Buy ticket and spin</button>
            <button type="button" className={s.ghost} onClick={onExit}>Walk away</button>
          </div>
        </div>
      ) : (
        <div className={s.card}>
          <div className={s.reels} aria-live="polite">
            {res.path.map((p, k) => (
              <div key={k} className={`${s.reel} ${k < shown ? (p.close > q.strike === (type === "call") ? s.win : s.lose) : ""}`}>
                <span>Day {k + 1}</span>
                <b>{k < shown ? pts(p.close) : k === shown && rolling ? pts(rolling) : "· · ·"}</b>
                <small>{k < shown ? `${p.chg >= 0 ? "+" : ""}${p.chg.toFixed(2)}%` : ""}</small>
              </div>
            ))}
          </div>
          <div className={s.row}><span>Needs a close {word}</span><b>{pts(q.strike)}</b></div>

          {phase === "result" ? (
            <>
              <div className={`${s.payout} ${res.payout > stake ? s.winText : s.loseText}`}>
                {res.payout > 0 ? `Paid ${money(res.payout)}` : "Expired worthless"}
                <small>{res.net >= 0 ? "+" : "−"}{money(Math.abs(res.net))} on a {money(stake)} ticket</small>
              </div>
              <dl className={s.ticket}>
                <div><dt>Fair value you paid {money(stake)} for</dt><dd>{money(fairStake)}</dd></div>
                <div><dt>House edge on this ticket</dt><dd className={s.hot}>{q.edgePct.toFixed(0)}%</dd></div>
                <div><dt>Your Strip total: staked / got back</dt><dd>{money(total.staked)} / {money(total.back)} ({total.returnPct >= 0 ? "+" : ""}{total.returnPct.toFixed(0)}%)</dd></div>
                <div><dt>Tickets that paid more than they cost</dt><dd>{total.wins} of {total.tickets}</dd></div>
              </dl>
              {mistakes.map((m) => <p key={m.kind} className={s.warn}><b>{m.title}.</b> {m.message} <i>{m.lesson}</i></p>)}
              <p className={s.fact}>
                Real life: SEBI found that about 9 in 10 individual F&amp;O traders lost money (87.7% in FY26, 90.9% in FY25),
                and our own backtest of ₹1,000 option buying lost 11-22% of everything staked. The odds on the ticket are the lesson.
              </p>
              <p className={s.revealed}>It was the Nifty 50, {day(nifty.t[i])} to {day(nifty.t[i + days])}.</p>
              <div className={s.actions}>
                <button type="button" className={s.ghost} onClick={onExit}>Back to the city</button>
              </div>
            </>
          ) : null}
        </div>
      )}
    </div>
  );
}
