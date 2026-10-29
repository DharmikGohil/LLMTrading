"use client";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

/** Ticker box: type a symbol, press Enter (or GO) to open everything on it. */
export function TickerGo({ symbols }) {
  const router = useRouter();
  const [v, setV] = useState("");
  const go = (e) => {
    e.preventDefault();
    const s = v.trim().toUpperCase();
    if (!s) return;
    const hit = symbols.find((x) => x === s) || symbols.find((x) => x.startsWith(s));
    router.push(`/symbol/${encodeURIComponent(hit || s)}`);
    setV("");
    e.target.querySelector("input")?.blur();
  };
  return (
    <form className="go" onSubmit={go} role="search">
      <input id="go-input" list="go-symbols" value={v} onChange={(e) => setV(e.target.value)} placeholder="Ticker  /" aria-label="Open a stock by ticker" autoComplete="off" spellCheck={false} />
      <datalist id="go-symbols">{symbols.map((s) => <option key={s} value={s} />)}</datalist>
      <button type="submit">GO</button>
    </form>
  );
}

export function ThemeToggle() {
  const [t, setT] = useState("dark");
  useEffect(() => setT(document.documentElement.dataset.theme || "dark"), []);
  const flip = () => {
    const n = t === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = n;
    try { localStorage.setItem("theme", n); } catch {}
    setT(n);
  };
  return (
    <button type="button" className="iconbtn" onClick={flip} aria-label={`Switch to ${t === "dark" ? "light" : "dark"} theme`} title="Theme">
      {t === "dark" ? (
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></svg>
      ) : (
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" /></svg>
      )}
    </button>
  );
}

// Regular sessions only; exchange holidays are not modelled here (the desk itself checks them).
const SESSIONS = [
  { name: "NSE", tz: "Asia/Kolkata", label: "IST", open: 9 * 60 + 15, close: 15 * 60 + 30 },
  { name: "NYSE", tz: "America/New_York", label: "ET", open: 9 * 60 + 30, close: 16 * 60 },
];

function state(s, now) {
  const p = Object.fromEntries(new Intl.DateTimeFormat("en-GB", { timeZone: s.tz, weekday: "short", hour: "2-digit", minute: "2-digit", hour12: false })
    .formatToParts(now).map((x) => [x.type, x.value]));
  const mins = Number(p.hour) * 60 + Number(p.minute);
  const weekday = !["Sat", "Sun"].includes(p.weekday);
  return { open: weekday && mins >= s.open && mins < s.close, clock: `${p.hour}:${p.minute}` };
}

export function MarketClocks({ asOf }) {
  const [now, setNow] = useState(null);
  useEffect(() => {
    setNow(new Date());
    const id = setInterval(() => setNow(new Date()), 20000);
    return () => clearInterval(id);
  }, []);
  const ago = now && asOf ? Math.max(0, Math.round((now - new Date(asOf)) / 60000)) : null;
  const agoTxt = ago == null ? "" : ago < 60 ? `${ago}m ago` : ago < 48 * 60 ? `${Math.round(ago / 60)}h ago` : `${Math.round(ago / 1440)}d ago`;
  return (
    <>
      {SESSIONS.map((s) => {
        const st = now ? state(s, now) : null;
        return (
          <span className="mkt" key={s.name}>
            <i className={`dot ${st?.open ? "open" : ""}`} aria-hidden="true" />
            {s.name} <span className={st?.open ? "up" : "muted"}>{st ? (st.open ? "OPEN" : "CLOSED") : "—"}</span>
            <span className="muted">{st ? `${st.clock} ${s.label}` : ""}</span>
          </span>
        );
      })}
      <span className="sep" aria-hidden="true" />
      <span>Last desk update <span className="accent">{asOf ? new Date(asOf).toLocaleString("en-GB", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "Asia/Kolkata" }) + " IST" : "—"}</span>{agoTxt ? <span className="muted"> · {agoTxt}</span> : null}</span>
    </>
  );
}
