"use client";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { SESSIONS, sessionState as state } from "@/components/Live";

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
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></svg>
      <input id="go-input" list="go-symbols" value={v} onChange={(e) => setV(e.target.value)} placeholder="Search stocks" aria-label="Open a stock by ticker" autoComplete="off" spellCheck={false} />
      <datalist id="go-symbols">{symbols.map((s) => <option key={s} value={s} />)}</datalist>
      <button type="submit">GO</button>
    </form>
  );
}

export function ThemeToggle() {
  const [t, setT] = useState("light");
  useEffect(() => setT(document.documentElement.dataset.theme || "light"), []);
  const flip = () => {
    const n = t === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = n;
    document.querySelector('meta[name="theme-color"]')?.setAttribute("content", n === "dark" ? "#0c0b14" : "#f3f2f8");
    try { localStorage.setItem("theme", n); } catch {}
    setT(n);
  };
  return (
    <button type="button" className="iconbtn" onClick={flip} aria-label={`Switch to ${t === "dark" ? "light" : "dark"} theme`} title="Theme">
      {t === "dark" ? (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true"><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></svg>
      ) : (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" /></svg>
      )}
    </button>
  );
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
            {s.name}{" "}<span className={st?.open ? "up" : "muted"}>{st ? (st.open ? "OPEN" : "CLOSED") : "—"}</span>
            <span className="muted">{st ? `${st.clock} ${s.label}` : ""}</span>
          </span>
        );
      })}
      <span className="sep" aria-hidden="true" />
      <span>Last desk update <span className="accent">{asOf ? new Date(asOf).toLocaleString("en-GB", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "Asia/Kolkata" }) + " IST" : "—"}</span>{agoTxt ? <span className="muted"> · {agoTxt}</span> : null}</span>
    </>
  );
}

/** Compact market status for the header: which exchanges are open right now. */
export function MarketPill() {
  const [now, setNow] = useState(null);
  useEffect(() => {
    setNow(new Date());
    const id = setInterval(() => setNow(new Date()), 30000);
    return () => clearInterval(id);
  }, []);
  if (!now) return null;
  const open = SESSIONS.filter((s) => state(s, now).open).map((s) => s.name);
  return (
    <span className="live-pill" title="Paper money only">
      <i className={`dot ${open.length ? "live" : ""}`} aria-hidden="true" />
      {open.length ? `${open.join(" · ")} open` : "Markets closed"}
    </span>
  );
}
