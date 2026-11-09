"use client";
import { useEffect, useMemo, useState } from "react";
import { SESSIONS, sessionState, useLive } from "@/components/Live";
import { fmt } from "@/lib/fmt";

const sign = (v, sym, d = 2) => {
  if (v == null || Number.isNaN(v)) return "—";
  const t = fmt.tone(v);
  return <span className={t}>{t === "up" ? "+" : ""}{fmt.money(t ? v : 0, sym, d)}</span>;
};
const pctc = (v) => (v == null || Number.isNaN(v) ? "—" : <span className={fmt.tone(v)}>{fmt.pct(v)}</span>);
const today = (tz) => new Intl.DateTimeFormat("en-CA", { timeZone: tz }).format(new Date());

function useTab(ids) {
  const [tab, setTab] = useState(ids[0]);
  useEffect(() => {
    try {
      const t = localStorage.getItem("pf-tab");
      if (t && ids.includes(t)) setTab(t);
    } catch {}
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const pick = (t) => {
    setTab(t);
    try { localStorage.setItem("pf-tab", t); } catch {}
  };
  return [tab, pick];
}

/** Holdings, funds and orders of one paper stock account, priced live from the quote feed. */
function Equity({ a }) {
  const { quotes } = useLive();
  const day = today(a.tz);
  const rows = a.holdings.map((h) => {
    const q = quotes[`${a.market}:${h.symbol}`];
    const ltp = q?.p ?? h.last;
    const pc = q?.pc ?? null;
    const boughtToday = h.opened === day;
    const ref = boughtToday ? h.avg : pc;
    return {
      ...h, ltp, live: !!q, invested: h.qty * h.avg, cur: h.qty * ltp, pnl: h.qty * (ltp - h.avg), net: (ltp / h.avg - 1) * 100,
      dayPct: pc ? (ltp / pc - 1) * 100 : null, dayPnl: ref ? h.qty * (ltp - ref) : null,
    };
  });
  const invested = rows.reduce((s, r) => s + r.invested, 0);
  const cur = rows.reduce((s, r) => s + r.cur, 0);
  const pnl = cur - invested;
  const dayPnl = rows.reduce((s, r) => s + (r.dayPnl || 0), 0);
  const value = a.cash + cur;
  const ret = (value / a.start - 1) * 100;
  const c = a.cur;
  return (
    <>
      <div className="pf-funds">
        <div><span className="label">Account value</span><b>{fmt.money(value, c)}</b><span className={fmt.tone(ret)}>{fmt.pct(ret)} on {fmt.money(a.start, c, 0)}</span></div>
        <div><span className="label">Invested</span><b>{fmt.money(invested, c)}</b><span className="muted">{rows.length} holdings</span></div>
        <div><span className="label">Current value</span><b>{fmt.money(cur, c)}</b><span className="muted">at live prices</span></div>
        <div><span className="label">Total P&amp;L</span><b>{sign(pnl, c)}</b><span>{pctc(invested ? (pnl / invested) * 100 : null)}</span></div>
        <div><span className="label">Day&apos;s P&amp;L</span><b>{sign(dayPnl, c)}</b><span className="muted">vs previous close</span></div>
        <div><span className="label">Cash available</span><b>{fmt.money(a.cash, c)}</b><span className="muted">booked P&amp;L {fmt.money(a.realized, c)}</span></div>
      </div>

      <ul className="pf-list" aria-label="Holdings">
        {rows.map((r) => (
          <li key={r.symbol}>
            <div><span className="muted">{r.qty} × {fmt.num(r.avg)}</span><span>{pctc(r.net)}</span></div>
            <div><a className="sym" href={`/symbol/${encodeURIComponent(r.symbol)}`}>{r.symbol}</a><b>{sign(r.pnl, "")}</b></div>
            <div><span className="muted">Invested {fmt.money(r.invested, "", 0)}</span><span className="muted">LTP <b className="ink">{fmt.num(r.ltp)}</b> {r.dayPct != null ? <>({pctc(r.dayPct)})</> : null}</span></div>
          </li>
        ))}
        {!rows.length ? <li className="empty">No holdings.</li> : null}
      </ul>

      <div className="tbl-wrap pf-desk">
        <table className="pf-table">
          <thead><tr>
            <th>Instrument</th><th className="n">Qty</th><th className="n">Avg. cost</th><th className="n">LTP</th>
            <th className="n">Cur. val</th><th className="n">P&amp;L</th><th className="n">Net chg.</th><th className="n">Day chg.</th><th className="n">Stop</th>
          </tr></thead>
          <tbody>
            {rows.length ? rows.map((r) => (
              <tr key={r.symbol}>
                <td className="sym"><a href={`/symbol/${encodeURIComponent(r.symbol)}`}>{r.symbol}</a>{r.live ? null : <span className="muted"> · last sync</span>}</td>
                <td className="n">{r.qty}</td>
                <td className="n">{fmt.num(r.avg)}</td>
                <td className="n"><b>{fmt.num(r.ltp)}</b></td>
                <td className="n">{fmt.money(r.cur, "", 2)}</td>
                <td className="n">{sign(r.pnl, "")}</td>
                <td className="n">{pctc(r.net)}</td>
                <td className="n">{pctc(r.dayPct)}</td>
                <td className="n muted">{r.stop ? fmt.num(r.stop) : "—"}</td>
              </tr>
            )) : <tr><td colSpan={9} className="empty">No holdings.</td></tr>}
          </tbody>
          {rows.length ? (
            <tfoot><tr>
              <td>Total</td><td /><td /><td />
              <td className="n">{fmt.money(cur, "", 2)}</td><td className="n">{sign(pnl, "")}</td>
              <td className="n">{pctc(invested ? (pnl / invested) * 100 : null)}</td><td className="n">{sign(dayPnl, "")}</td><td />
            </tr></tfoot>
          ) : null}
        </table>
      </div>

      <h3 className="pf-h">Orders</h3>
      <div className="tbl-wrap">
        <table className="pf-table">
          <thead><tr><th>Time</th><th>Type</th><th>Instrument</th><th className="n">Qty</th><th className="n">Price</th><th>Status</th><th className="pf-why">Why</th></tr></thead>
          <tbody>
            {a.orders.length ? a.orders.map((o) => (
              <tr key={o.id}>
                <td className="mono muted">{fmt.time(o.time, a.tz, a.tzLabel)}</td>
                <td><span className={`side ${o.side}`}>{o.side}</span></td>
                <td className="sym">{o.symbol}</td>
                <td className="n">{o.qty}</td>
                <td className="n">{fmt.num(o.price)}</td>
                <td className="mono">{o.status}</td>
                <td className="pf-why muted" title={o.reason}>{o.reason}</td>
              </tr>
            )) : <tr><td colSpan={7} className="empty">No orders yet.</td></tr>}
          </tbody>
        </table>
      </div>
    </>
  );
}

/** Option legs priced from NSE through /api/options while the market is open; falls back to the last synced marks. */
function useOptionQuotes(open) {
  const [state, setState] = useState({ q: null, err: null });
  const key = open ? `${open.expiry}|${open.legs.map((l) => `${l.kind}${l.strike}`).join(",")}` : "";
  useEffect(() => {
    if (!key) return;
    const [expiry, legs] = key.split("|");
    let timer, dead = false;
    const tick = async () => {
      const nse = sessionState(SESSIONS[0], new Date()).open;
      if (document.visibilityState === "visible") {
        try {
          const j = await (await fetch(`/api/options?expiry=${expiry}&legs=${legs}`)).json();
          if (!dead) setState(j.error ? { q: null, err: j.error } : { q: j, err: null });
        } catch (e) {
          if (!dead) setState({ q: null, err: String(e) });
        }
      }
      if (!dead) timer = setTimeout(tick, nse ? 15000 : 300000);
    };
    tick();
    return () => { dead = true; clearTimeout(timer); };
  }, [key]);
  return state;
}

function OptionBook({ id, title, b, spot }) {
  const o = b.open;
  const { q, err } = useOptionQuotes(o);
  const legs = (o?.legs || []).map((l, i) => {
    const lq = q?.legs?.[`${l.kind}${l.strike}`];
    // exit-side price: a short leg is bought back at the ask, a long leg sold at the bid
    const live = lq ? (l.side === "SELL" ? lq.ask || lq.ltp : lq.bid || lq.ltp) : null;
    const now = live ?? b.mark?.prices?.[i] ?? null;
    const pnl = now == null ? null : (l.side === "SELL" ? l.entry - now : now - l.entry) * l.qty;
    return { ...l, now, ltp: lq?.ltp ?? null, pnl, live: live != null };
  });
  const openPnl = legs.length && legs.every((l) => l.pnl != null) ? legs.reduce((s, l) => s + l.pnl, 0) : b.mark?.pnl ?? null;
  // the synced equity already includes the synced mark; swap in the live open P&L
  const value = o && openPnl != null ? b.equity - (b.mark?.pnl ?? 0) + openPnl : b.equity;
  const ret = (value / b.capital - 1) * 100;
  const anyLive = legs.some((l) => l.live);
  return (
    <div className="pf-card">
      <div className="pf-card-head">
        <b>{title}</b>
        <span className="muted">{o ? `open · expiry ${fmt.short(o.expiry)}` : "flat"}</span>
      </div>
      <div className="pf-funds sm">
        <div><span className="label">Invested</span><b>{fmt.money(b.capital, "₹", 0)}</b></div>
        <div><span className="label">Value</span><b>{fmt.money(value, "₹", 0)}</b><span className={fmt.tone(ret)}>{fmt.pct(ret)}</span></div>
        <div><span className="label">Booked P&amp;L</span><b>{sign(b.realized, "₹", 0)}</b></div>
        <div><span className="label">Open P&amp;L</span><b>{o ? sign(openPnl, "₹", 0) : "—"}</b><span className="muted">{o ? (anyLive ? "live" : "last sync") : ""}</span></div>
      </div>
      {o ? (
        <div className="tbl-wrap">
          <table className="pf-table">
            <thead><tr><th>Instrument</th><th>Side</th><th className="n">Qty</th><th className="n">Avg.</th><th className="n">LTP</th><th className="n">Exit price</th><th className="n">P&amp;L</th></tr></thead>
            <tbody>
              {legs.map((l) => (
                <tr key={`${l.kind}${l.strike}${l.side}`}>
                  <td className="sym">NIFTY {fmt.short(o.expiry)} {l.strike} {l.kind}</td>
                  <td><span className={`side ${l.side}`}>{l.side}</span></td>
                  <td className="n">{l.side === "SELL" ? -l.qty : l.qty}</td>
                  <td className="n">{fmt.num(l.entry)}</td>
                  <td className="n">{l.ltp != null ? fmt.num(l.ltp) : "—"}</td>
                  <td className="n"><b>{l.now != null ? fmt.num(l.now) : "—"}</b></td>
                  <td className="n">{sign(l.pnl, "", 0)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      {o && err ? <p className="muted pf-note">Live option prices unavailable ({err}); showing the last sync.</p> : null}
      {o && spot ? <p className="muted pf-note">Nifty {fmt.num(q?.spot ?? spot)} {q?.spot ? "· live" : "· last sync"}</p> : null}
    </div>
  );
}

function Options({ options }) {
  const names = { main: "Range bet with LLM", control: "Range bet without LLM", lotto: "₹1,000 test" };
  const books = Object.entries(names).filter(([k]) => options.books[k]);
  const closed = books.flatMap(([k]) => (options.books[k].closed || []).map((c) => ({ ...c, arm: names[k] })))
    .sort((a, b) => new Date(b.closed) - new Date(a.closed)).slice(0, 20);
  return (
    <>
      <div className="pf-cards">
        {books.map(([k, t]) => <OptionBook key={k} id={k} title={t} b={options.books[k]} spot={options.spot} />)}
      </div>
      <h3 className="pf-h">Closed positions</h3>
      <div className="tbl-wrap">
        <table className="pf-table">
          <thead><tr><th>Closed</th><th>Account</th><th>Position</th><th className="n">P&amp;L</th><th>Exit</th></tr></thead>
          <tbody>
            {closed.length ? closed.map((c) => (
              <tr key={c.arm + c.closed}>
                <td className="mono muted">{fmt.time(c.closed)}</td>
                <td>{c.arm}</td>
                <td className="mono">{c.legs.map((l) => `${l.side === "SELL" ? "S" : "B"} ${l.strike}${l.kind}`).join(" · ")}</td>
                <td className="n">{sign(c.pnl, "₹", 0)}</td>
                <td className="wrap muted">{c.reason}</td>
              </tr>
            )) : <tr><td colSpan={5} className="empty">Nothing closed yet.</td></tr>}
          </tbody>
        </table>
      </div>
    </>
  );
}

export default function Portfolio({ accounts, options }) {
  const tabs = useMemo(() => [...accounts.map((a) => ({ id: a.id, label: a.tab })), ...(options ? [{ id: "fo", label: "Nifty F&O" }] : [])], [accounts, options]);
  const [tab, setTab] = useTab(tabs.map((t) => t.id));
  const acct = accounts.find((a) => a.id === tab);
  return (
    <div>
      <div className="seg pf-tabs" role="tablist" aria-label="Account">
        {tabs.map((t) => (
          <button key={t.id} type="button" role="tab" aria-selected={tab === t.id} aria-pressed={tab === t.id} onClick={() => setTab(t.id)}>{t.label}</button>
        ))}
      </div>
      <div className="pf-body" role="tabpanel">
        {acct ? <Equity a={acct} /> : options ? <Options options={options} /> : null}
      </div>
    </div>
  );
}
