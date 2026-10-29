"use client";
import { createContext, useContext, useEffect, useRef, useState } from "react";
import { fmt } from "@/lib/fmt";

// Regular sessions only; exchange holidays are not modelled here (the desk itself checks them).
export const SESSIONS = [
  { name: "NSE", market: "India", tz: "Asia/Kolkata", label: "IST", open: 9 * 60 + 15, close: 15 * 60 + 30 },
  { name: "NYSE", market: "US", tz: "America/New_York", label: "ET", open: 9 * 60 + 30, close: 16 * 60 },
];

export function sessionState(s, now) {
  const p = Object.fromEntries(new Intl.DateTimeFormat("en-GB", { timeZone: s.tz, weekday: "short", hour: "2-digit", minute: "2-digit", hour12: false })
    .formatToParts(now).map((x) => [x.type, x.value]));
  const mins = (Number(p.hour) % 24) * 60 + Number(p.minute);
  const weekday = !["Sat", "Sun"].includes(p.weekday);
  return { open: weekday && mins >= s.open && mins < s.close, clock: `${p.hour}:${p.minute}` };
}

const LiveCtx = createContext({ quotes: {}, at: null, open: {} });
export const useLive = () => useContext(LiveCtx);

/** Polls /api/quotes: every 15 s while either exchange is open, every 5 min otherwise, paused in background tabs. */
export function LiveProvider({ keys, children }) {
  const [state, setState] = useState({ quotes: {}, at: null, open: {}, error: false });
  useEffect(() => {
    if (!keys.length) return;
    let timer, dead = false;
    const tick = async () => {
      const now = new Date();
      const open = Object.fromEntries(SESSIONS.map((s) => [s.market, sessionState(s, now).open]));
      if (document.visibilityState === "visible") {
        try {
          const r = await fetch(`/api/quotes?s=${encodeURIComponent(keys.join(","))}`);
          const j = await r.json();
          if (!dead) setState((st) => ({ quotes: { ...st.quotes, ...j.quotes }, at: j.at, open, error: false }));
        } catch {
          if (!dead) setState((st) => ({ ...st, open, error: true }));
        }
      }
      if (!dead) timer = setTimeout(tick, Object.values(open).some(Boolean) ? 15000 : 300000);
    };
    tick();
    const vis = () => { if (document.visibilityState === "visible") { clearTimeout(timer); tick(); } };
    document.addEventListener("visibilitychange", vis);
    return () => { dead = true; clearTimeout(timer); document.removeEventListener("visibilitychange", vis); };
  }, [keys]);
  return <LiveCtx.Provider value={state}>{children}</LiveCtx.Provider>;
}

export function useQuote(market, sym) {
  return useLive().quotes[`${market}:${sym}`] || null;
}

/** A number that flashes green/red for a moment when it changes. */
function Flash({ v, children, className = "" }) {
  const prev = useRef(v);
  const [dir, setDir] = useState("");
  const [n, setN] = useState(0);
  useEffect(() => {
    if (prev.current != null && v != null && v !== prev.current) {
      setDir(v > prev.current ? "fl-up" : "fl-down");
      setN((x) => x + 1);
    }
    prev.current = v;
  }, [v]);
  return <span key={n} className={`${className} ${dir}`}>{children}</span>;
}

export function LiveLast({ market, sym, fallback }) {
  const q = useQuote(market, sym);
  const v = q?.p ?? fallback;
  return <Flash v={v}>{fmt.num(v)}</Flash>;
}

export function LivePnl({ market, sym, qty, avg, fallback, cur }) {
  const q = useQuote(market, sym);
  const v = q ? (q.p - avg) * qty : fallback;
  const t = fmt.tone(v);
  return <Flash v={v} className={t}>{t === "up" ? "+" : ""}{fmt.money(t ? v : 0, cur)}</Flash>;
}

export function LivePnlPct({ market, sym, avg, fallback, scale = 2 }) {
  const q = useQuote(market, sym);
  const v = q && avg ? (q.p / avg - 1) * 100 : fallback;
  if (v == null) return "—";
  const t = fmt.tone(v);
  const w = Math.min(50, (Math.abs(v) / (scale || 1)) * 50);
  return (
    <span className="num">
      <Flash v={v} className={t}>{fmt.pct(v)}</Flash>
      <span className="pbar" aria-hidden="true">{t ? <i className={t} style={{ width: `${w}%` }} /> : null}</span>
    </span>
  );
}

export function LiveToStop({ market, sym, stop, fallback }) {
  const q = useQuote(market, sym);
  const px = q?.p ?? fallback;
  if (!stop || !px) return "—";
  const d = ((px - stop) / px) * 100;
  return <span className={d < 2 ? "down" : ""}>{d.toFixed(1)}%</span>;
}

/** Equity of one book from live prices (cash + holdings), falling back to the last recorded price per stock. */
export function liveEquity(book, quotes, market) {
  if (!book) return null;
  let any = false;
  const eq = book.cash + book.pos.reduce((a, [sym, qty, last]) => {
    const q = quotes[`${market}:${sym}`];
    if (q) any = true;
    return a + qty * (q?.p ?? last ?? 0);
  }, 0);
  return { eq: any ? eq : book.equity, ret: ((any ? eq : book.equity) / book.start - 1) * 100, live: any };
}

export function liveIndex(spec, quotes) {
  if (!spec?.index) return null;
  const q = quotes[spec.index.key];
  const p = q?.p ?? spec.index.last;
  return { p, ret: (p / spec.index.base - 1) * 100, live: !!q };
}

export function LiveEquity({ spec, book = "main", cur, show = "value" }) {
  const { quotes } = useLive();
  const e = liveEquity(spec[book], quotes, spec.market);
  if (!e) return "—";
  if (show === "ret") return <Flash v={e.ret} className={fmt.tone(e.ret)}>{fmt.pct(e.ret)}</Flash>;
  return <Flash v={e.eq}>{fmt.money(e.eq, cur)}</Flash>;
}

export function LiveUnrealized({ spec, book = "main", cur }) {
  const { quotes } = useLive();
  const b = spec[book];
  if (!b) return "—";
  const v = b.pos.reduce((a, [sym, qty, last, avg]) => a + qty * ((quotes[`${spec.market}:${sym}`]?.p ?? last ?? avg) - avg), 0);
  const t = fmt.tone(v);
  return <Flash v={Number(v.toFixed(2))} className={t}>{t === "up" ? "+" : ""}{fmt.money(t ? v : 0, cur)}</Flash>;
}

export function LiveValue({ market, sym, qty, fallback, cur }) {
  const q = useQuote(market, sym);
  return <>{fmt.money(q ? q.p * qty : fallback, cur, 0)}</>;
}

export function LiveEdge({ spec }) {
  const { quotes } = useLive();
  const a = liveEquity(spec.main, quotes, spec.market), b = liveEquity(spec.factor, quotes, spec.market);
  if (!a || !b) return "—";
  const v = a.ret - b.ret;
  return <Flash v={Number(v.toFixed(2))} className={fmt.tone(v)}>{fmt.pp(v)}</Flash>;
}

export function LiveIndexRet({ spec }) {
  const { quotes } = useLive();
  const i = liveIndex(spec, quotes);
  if (!i) return "—";
  return <Flash v={i.ret} className={fmt.tone(i.ret)}>{fmt.pct(i.ret)}</Flash>;
}

/** Status-bar badge: LIVE while an exchange is open and quotes are flowing. */
export function LiveBadge() {
  const { at, open, error, quotes } = useLive();
  const [now, setNow] = useState(null);
  useEffect(() => {
    setNow(Date.now());
    const id = setInterval(() => setNow(Date.now()), 5000);
    return () => clearInterval(id);
  }, []);
  const anyOpen = Object.values(open || {}).some(Boolean);
  const newest = Math.max(0, ...Object.values(quotes).map((q) => q.t || 0));
  const age = now && newest ? Math.max(0, Math.round((now - newest) / 1000)) : null;
  if (error) return <span className="muted">quotes unavailable</span>;
  if (!at) return <span className="muted">connecting…</span>;
  return anyOpen ? (
    <span className="mkt"><i className="dot live" aria-hidden="true" /><span className="up">LIVE</span><span className="muted">{age != null ? `last tick ${age < 90 ? `${age}s` : `${Math.round(age / 60)}m`} ago · refresh 15s` : ""}</span></span>
  ) : (
    <span className="mkt"><i className="dot" aria-hidden="true" /><span className="muted">Markets closed · last prices</span></span>
  );
}
