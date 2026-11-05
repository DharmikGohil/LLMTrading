import Link from "next/link";
import EquityChart from "@/components/EquityChart";
import { LiveNiftyKpi, StrikeWatch } from "@/components/OptionsLive";
import Payoff from "@/components/Payoff";
import { Kpi, Kpis, Panel, Signed, Table } from "@/components/ui";
import { OPTION_ARMS, fmt, load, optionsView } from "@/lib/data";

export const metadata = { title: "Nifty options" };

function legRows(o, mark) {
  return o.legs.map((l, i) => {
    const now = mark?.prices?.[i];
    const pnl = now == null ? null : (l.side === "SELL" ? l.entry - now : now - l.entry) * l.qty;
    return { ...l, now, pnl, id: `${l.kind}${l.strike}${l.side}` };
  });
}

const money = (v, d = 0) => fmt.money(v, "₹", d);

export default function Options() {
  const { options } = load();
  if (!options) {
    return <main><div className="page-head"><div><h1>Nifty options</h1><p className="sub">The options desk has not exported data yet.</p></div></div></main>;
  }
  const books = options.books;
  const gate = options.gates?.at(-1);
  const v = optionsView(options);
  return (
    <main>
      <div className="page-head">
        <div>
          <span className="label">NSE · Nifty weekly options · paper money</span>
          <h1>Nifty options desk</h1>
          <p className="sub">
            Three paper accounts. Two sell defined-risk iron condors on Nifty weekly options: an LLM-reviewed one, where
            Claude&apos;s event gate can widen or skip a trade, and a rules-only control. The third is a Rs 1,000 option-buying
            test. A one-minute monitor checks exits during market hours.
          </p>
        </div>
      </div>

      <Kpis>
        <Kpi hl label="Invested (paper)" value={money(v.totals.invested)} delta="3 accounts" />
        <Kpi label="Value now" value={money(v.totals.value)} delta={`as of ${fmt.time(options.time)}`} />
        <Kpi label="Total P&L" value={<Signed v={v.totals.pnl} sym="₹" d={0} />} delta={fmt.pct(v.totals.ret)} deltaTone={fmt.tone(v.totals.ret)} />
        <LiveNiftyKpi fallback={options.spot} syncedAt={options.time} />
      </Kpis>

      <div className="grid" style={{ marginTop: 12 }}>
        <div className="c12">
          <Panel title="Accounts" meta="Invested, value and return of each paper account">
            <Table rows={v.rows} cols={[
              { key: "name", label: "Account", render: (r) => <b>{r.name}</b> },
              { key: "ret", label: "Return", n: true, render: (r) => <span className={fmt.tone(r.ret)}>{fmt.pct(r.ret)}</span> },
              { key: "value", label: "Value", n: true, render: (r) => money(r.value) },
              { key: "invested", label: "Invested", n: true, render: (r) => money(r.invested) },
              { key: "pnl", label: "P&L", n: true, render: (r) => <Signed v={r.pnl} sym="₹" d={0} /> },
              { key: "realized", label: "Booked", n: true, render: (r) => <Signed v={r.realized} sym="₹" d={0} /> },
              { key: "open", label: "Open P&L", n: true, render: (r) => (r.open == null ? <span className="muted">{r.status}</span> : <Signed v={r.open} sym="₹" d={0} />) },
              { key: "trades", label: "Trades", n: true, render: (r) => `${r.trades} · ${r.wins} won` },
              { key: "best", label: "Best / worst", n: true, render: (r) => (r.best == null ? "—" : <><Signed v={r.best} sym="₹" d={0} /> / <Signed v={r.worst} sym="₹" d={0} /></>) },
            ]} />
          </Panel>
        </div>

        <div className="c7">
          <Panel title="Condor accounts vs Nifty" meta="Return since start, at each sync">
            <EquityChart data={v.condorChart} height={240} compact ranges={false} />
          </Panel>
        </div>
        <div className="c5">
          <Panel title="Rs 1,000 test" meta="Return on Rs 1,000; it reinvests its whole balance each trade">
            {v.lottoChart ? <EquityChart data={v.lottoChart} height={240} compact ranges={false} /> : <div className="empty">No data yet.</div>}
          </Panel>
        </div>
      </div>

      {gate ? (
        <div className="callout" style={{ marginTop: 12 }}>
          <b>Latest gate ({fmt.short(gate.date)}): {gate.action}</b>
          {gate.lotto_direction && gate.lotto_direction !== "none" ? <> · lotto direction <b>{gate.lotto_direction}</b></> : null}. {gate.note}
        </div>
      ) : null}

      <div className="grid" style={{ marginTop: 12 }}>
        {Object.entries(OPTION_ARMS).map(([k, a]) => {
          const b = books[k];
          if (!b) return null;
          const o = b.open;
          return (
            <div className="c12" key={k}>
              <Panel title={a.title} meta={a.sub}>
                {o ? (
                  <div className="grid">
                    <div className="c7">
                      <StrikeWatch legs={o.legs} fallback={options.spot} />
                      <Table rows={legRows(o, b.mark)} cols={[
                        { key: "side", label: "Side", render: (r) => <span className={`side ${r.side === "SELL" ? "SELL" : "BUY"}`}>{r.side}</span> },
                        { key: "strike", label: "Strike", n: true },
                        { key: "kind", label: "Type" },
                        { key: "qty", label: "Qty", n: true },
                        { key: "entry", label: "Entry", n: true, render: (r) => fmt.num(r.entry) },
                        { key: "now", label: "At sync", n: true, render: (r) => (r.now == null ? "—" : fmt.num(r.now)) },
                        { key: "pnl", label: "P&L", n: true, render: (r) => <Signed v={r.pnl} sym="₹" d={0} /> },
                      ]} />
                      <p className="muted" style={{ fontSize: 12.5, marginTop: 10 }}>
                        Expiry {fmt.day(o.expiry)} · {o.credit >= 0 ? `credit ${money(o.credit)}` : `cost ${money(-o.credit)}`} ·
                        max loss {money(o.max_loss)} · charges {money(o.entry_charges)} ·
                        {b.mark ? <> P&amp;L at sync <Signed v={b.mark.pnl} sym="₹" d={0} /></> : " no mark"} · opened {fmt.time(o.opened)}
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
                    <span className="label">Closed trades</span>
                    <Table rows={[...b.closed].reverse()} rowKey={(r) => r.opened + r.closed} cols={[
                      { key: "opened", label: "Opened", render: (r) => <span className="mono muted">{fmt.time(r.opened)}</span> },
                      { key: "closed", label: "Closed", render: (r) => <span className="mono muted">{fmt.time(r.closed)}</span> },
                      { key: "legs", label: "Position", render: (r) => <span className="mono">{r.legs.map((l) => `${l.side === "SELL" ? "S" : "B"} ${l.strike}${l.kind}`).join(" · ")}</span> },
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
        The Nifty price and the strike distances update live, about every 15 seconds. Option prices, account values and the
        charts update when the desk syncs, at each scheduled run (09:35, 12:35 and 15:05 IST, plus the US-session runs).
        NSE&apos;s option chain cannot be read from this website directly. See the <Link className="accent" href="/research">research</Link> and
        the <Link className="accent" href="https://github.com/DharmikGohil/LLMTrading/blob/main/docs/options-backtest.md">options backtest</Link> before
        drawing conclusions from a few weeks.
      </p>
    </main>
  );
}
