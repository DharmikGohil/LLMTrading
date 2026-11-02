import Link from "next/link";
import Payoff from "@/components/Payoff";
import { Kpi, Kpis, Panel, Signed, Table } from "@/components/ui";
import { fmt, load } from "@/lib/data";

export const metadata = { title: "Nifty options" };

const ARMS = {
  main: { title: "LLM-reviewed iron condor", sub: "Rules plus Claude's event gate (trade, widen or skip)" },
  control: { title: "Rules-only iron condor", sub: "Same rules, no LLM: the control" },
  lotto: { title: "Rs 1,000 option buying", sub: "One cheap out-of-the-money option per expiry, trend direction" },
};

function legRows(o, mark) {
  return o.legs.map((l, i) => {
    const now = mark?.prices?.[i];
    const pnl = now == null ? null : (l.side === "SELL" ? l.entry - now : now - l.entry) * l.qty;
    return { ...l, now, pnl, id: `${l.kind}${l.strike}${l.side}` };
  });
}

export default function Options() {
  const { options } = load();
  if (!options) {
    return <main><div className="page-head"><div><h1>Nifty options</h1><p className="sub">The options desk has not exported data yet.</p></div></div></main>;
  }
  const books = options.books;
  const gate = options.gates?.at(-1);
  return (
    <main>
      <div className="page-head">
        <div>
          <span className="label">NSE · Nifty weekly options · paper</span>
          <h1>Nifty options desk</h1>
          <p className="sub">
            Defined-risk iron condors on Nifty weekly options: sell an out-of-the-money call and put, buy protection further out,
            so the maximum loss is fixed at entry. Take profit at 50% of the credit, stop when the loss equals the credit, and
            always close by 15:15 on the last trading day before expiry. A one-minute monitor watches the exits during market hours.
            Fills at the bid and ask of NSE&apos;s live option chain, with full F&amp;O charges.
          </p>
        </div>
      </div>

      <Kpis>
        {Object.entries(ARMS).map(([k, a]) => {
          const b = books[k];
          if (!b) return null;
          const ret = (b.equity / b.capital - 1) * 100;
          return <Kpi key={k} hl={k === "main"} label={a.title} value={fmt.money(b.equity, "₹")} delta={`${fmt.pct(ret)} · realized ${fmt.money(b.realized, "₹", 0)}`} deltaTone={fmt.tone(ret)} />;
        })}
        <Kpi label="Nifty at last sync" value={options.spot ? fmt.num(options.spot) : "—"} delta={fmt.time(options.time)} />
      </Kpis>

      {gate ? (
        <div className="callout" style={{ marginTop: 12 }}>
          <b>Today&apos;s gate ({fmt.short(gate.date)}): {gate.action}</b>
          {gate.lotto_direction !== "none" ? <> · lotto direction <b>{gate.lotto_direction}</b></> : null}. {gate.note}
        </div>
      ) : null}

      <div className="grid" style={{ marginTop: 12 }}>
        {Object.entries(ARMS).map(([k, a]) => {
          const b = books[k];
          if (!b) return null;
          const o = b.open;
          return (
            <div className="c12" key={k}>
              <Panel title={a.title} meta={a.sub}>
                {o ? (
                  <div className="grid">
                    <div className="c7">
                      <Table rows={legRows(o, b.mark)} cols={[
                        { key: "side", label: "Side", render: (r) => <span className={`side ${r.side === "SELL" ? "SELL" : "BUY"}`}>{r.side}</span> },
                        { key: "strike", label: "Strike", n: true },
                        { key: "kind", label: "Type" },
                        { key: "qty", label: "Qty", n: true },
                        { key: "entry", label: "Entry", n: true, render: (r) => fmt.num(r.entry) },
                        { key: "now", label: "Now", n: true, render: (r) => (r.now == null ? "—" : fmt.num(r.now)) },
                        { key: "pnl", label: "P&L", n: true, render: (r) => <Signed v={r.pnl} sym="₹" d={0} /> },
                      ]} />
                      <p className="muted" style={{ fontSize: 12.5, marginTop: 10 }}>
                        Expiry {fmt.day(o.expiry)} · {o.credit >= 0 ? `credit ${fmt.money(o.credit, "₹", 0)}` : `cost ${fmt.money(-o.credit, "₹", 0)}`} ·
                        max loss {fmt.money(o.max_loss, "₹", 0)} · charges {fmt.money(o.entry_charges, "₹", 0)} ·
                        {b.mark ? <> marked P&amp;L <Signed v={b.mark.pnl} sym="₹" d={0} /></> : " no mark"} · opened {fmt.time(o.opened)}
                      </p>
                      <p className="muted" style={{ fontSize: 12.5 }}>{o.note}</p>
                    </div>
                    <div className="c5">
                      <span className="label">P&amp;L at expiry</span>
                      <Payoff legs={o.legs} spot={options.spot} charges={o.entry_charges} />
                    </div>
                  </div>
                ) : <div className="empty">Flat: no open position.</div>}
                {b.closed?.length ? (
                  <div style={{ marginTop: 12 }}>
                    <span className="label">Closed</span>
                    <Table rows={[...b.closed].reverse()} rowKey={(r) => r.opened} cols={[
                      { key: "opened", label: "Opened", render: (r) => <span className="mono muted">{fmt.time(r.opened)}</span> },
                      { key: "closed", label: "Closed", render: (r) => <span className="mono muted">{fmt.time(r.closed)}</span> },
                      { key: "expiry", label: "Expiry", render: (r) => fmt.short(r.expiry) },
                      { key: "pnl", label: "P&L", n: true, render: (r) => <Signed v={r.pnl} sym="₹" d={0} /> },
                      { key: "reason", label: "Exit", wrap: true },
                    ]} />
                  </div>
                ) : null}
              </Panel>
            </div>
          );
        })}
      </div>
      <p className="muted" style={{ fontSize: 12.5, marginTop: 12 }}>
        Prices here are from the last sync; positions are checked every minute during market hours. See the <Link className="accent" href="/research">research</Link> on
        option selling and the SEBI F&amp;O studies before drawing conclusions from a few weeks.
      </p>
    </main>
  );
}
