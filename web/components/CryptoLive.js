"use client";
import { createContext, useContext, useEffect, useState } from "react";
import { fmt } from "@/lib/fmt";

// Live crypto prices straight from Binance's public market-data mirror (CORS-enabled), every 10 s while visible.
const Ctx = createContext({});
export const useCrypto = () => useContext(Ctx);

export function CryptoProvider({ coins, children }) {
  const [q, setQ] = useState({});
  const key = [...new Set(coins)].sort().join(",");
  useEffect(() => {
    if (!key) return;
    let timer, dead = false;
    const syms = encodeURIComponent(JSON.stringify(key.split(",").map((c) => `${c}USDT`)));
    const tick = async () => {
      if (document.visibilityState === "visible") {
        try {
          const rows = await (await fetch(`https://data-api.binance.vision/api/v3/ticker/24hr?symbols=${syms}`)).json();
          if (!dead && Array.isArray(rows)) {
            setQ(Object.fromEntries(rows.map((r) => [r.symbol.slice(0, -4), { last: +r.lastPrice, bid: +r.bidPrice, chg: +r.priceChangePercent, t: r.closeTime }])));
          }
        } catch {}
      }
      if (!dead) timer = setTimeout(tick, 10000);
    };
    tick();
    return () => { dead = true; clearTimeout(timer); };
  }, [key]);
  return <Ctx.Provider value={q}>{children}</Ctx.Provider>;
}

const usd = (v, d = 2) => (v == null ? "—" : `${v < 0 ? "−" : ""}$${Math.abs(v).toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d })}`);
const px = (v) => (v == null ? "—" : v >= 100 ? v.toLocaleString("en-US", { maximumFractionDigits: 2 }) : v >= 1 ? v.toFixed(4) : v.toPrecision(4));
const signed = (v, d = 2) => <span className={fmt.tone(v)}>{v > 0 ? "+" : ""}{usd(v, d)}</span>;

/** An account's value and return at live prices (falls back to the last sync). */
export function liveBook(b, q) {
  const pos = b.positions.map((p) => {
    const last = q[p.coin]?.last ?? p.last;
    return { ...p, last, value: p.qty * last, pnl: p.qty * (last - p.avg), pnl_pct: (last / p.avg - 1) * 100, day: q[p.coin]?.chg ?? p.day_pct, live: !!q[p.coin] };
  });
  const value = b.cash + pos.reduce((s, p) => s + p.value, 0);
  return { ...b, pos, value, ret: (value / b.capital - 1) * 100, live: pos.some((p) => p.live) };
}

export function CryptoKpis({ books, names }) {
  const q = useCrypto();
  return (
    <div className="kpis">
      {Object.entries(names).map(([k, n]) => {
        const b = liveBook(books[k], q);
        return (
          <div key={k} className={`kpi ${k === "main" ? "hl" : ""}`}>
            <span className="label">{n}{b.live ? <span className="up"> · live</span> : null}</span>
            <span className="v">{usd(b.value)}</span>
            <span className={`d ${fmt.tone(b.ret)}`}>{fmt.pct(b.ret)} on {usd(b.capital, 0)}</span>
          </div>
        );
      })}
      <div className="kpi">
        <span className="label">BTC{q.BTC ? <span className="up"> · live</span> : null}</span>
        <span className="v">{q.BTC ? usd(q.BTC.last, 0) : "—"}</span>
        <span className={`d ${fmt.tone(q.BTC?.chg)}`}>{q.BTC ? `${fmt.pct(q.BTC.chg)} 24h` : ""}</span>
      </div>
    </div>
  );
}

export function CryptoHoldings({ book }) {
  const q = useCrypto();
  const b = liveBook(book, q);
  if (!b.pos.length) return <div className="empty">All in USDT ({usd(b.cash)}): no coin passes the rules right now.</div>;
  return (
    <div className="tbl-wrap">
      <table className="pf-table">
        <thead><tr><th>Coin</th><th className="n">Qty</th><th className="n">Avg.</th><th className="n">Last</th><th className="n">Value</th><th className="n">P&amp;L</th><th className="n">24h</th></tr></thead>
        <tbody>
          {b.pos.map((p) => (
            <tr key={p.coin}>
              <td className="sym">{p.coin}{p.live ? null : <span className="muted"> · last sync</span>}</td>
              <td className="n">{p.qty < 1 ? p.qty.toFixed(6) : p.qty.toLocaleString("en-US", { maximumFractionDigits: 3 })}</td>
              <td className="n">{px(p.avg)}</td>
              <td className="n"><b>{px(p.last)}</b></td>
              <td className="n">{usd(p.value)}</td>
              <td className="n">{signed(p.pnl)} <span className={fmt.tone(p.pnl_pct)}>({fmt.pct(p.pnl_pct)})</span></td>
              <td className="n"><span className={fmt.tone(p.day)}>{fmt.pct(p.day)}</span></td>
            </tr>
          ))}
        </tbody>
        <tfoot><tr><td>Cash (USDT)</td><td /><td /><td /><td className="n">{usd(b.cash)}</td><td className="n">booked {signed(b.realized)}</td><td className="n muted">fees {usd(b.fees)}</td></tr></tfoot>
      </table>
    </div>
  );
}
