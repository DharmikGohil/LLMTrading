import Link from "next/link";
import EquityChart from "@/components/EquityChart";
import { LiveNiftyKpi, StrikeWatch } from "@/components/OptionsLive";
import Payoff from "@/components/Payoff";
import Tabs from "@/components/Tabs";
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
  const edge = books.main && books.control ? ((books.main.equity - books.control.equity) / books.main.capital) * 100 : null;
  const arm = (k) => {
    const b = books[k];
    const o = b.open;
    return (
      <div className="pad" style={{ paddingBottom: 16 }}>
        <p className="muted" style={{ fontSize: 13, marginBottom: 12 }}>{OPTION_ARMS[k].sub}</p>
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
              {o.note ? <p className="muted" style={{ fontSize: 12.5, marginTop: 4 }}>{o.note}</p> : null}
            </div>
            <div className="c5">
              <span className="label">P&amp;L at expiry</span>
              <Payoff legs={o.legs} spot={options.spot} charges={o.entry_charges} />
            </div>
          </div>
        ) : <div className="empty">Flat: no open position.</div>}
        {b.closed?.length ? (
          <div style={{ marginTop: 16 }}>
            <span className="label">Closed trades</span>
            <Table rows={[...b.closed].reverse()} rowKey={(r) => r.opened + r.closed} cols={[
              { key: "opened", label: "Opened", render: (r) => <span className="muted">{fmt.time(r.opened)}</span> },
              { key: "closed", label: "Closed", render: (r) => <span className="muted">{fmt.time(r.closed)}</span> },
              { key: "legs", label: "Position", render: (r) => r.legs.map((l) => `${l.side === "SELL" ? "S" : "B"} ${l.strike}${l.kind}`).join(" · ") },
              { key: "pnl", label: "P&L", n: true, render: (r) => <Signed v={r.pnl} sym="₹" d={0} /> },
              { key: "reason", label: "Exit", wrap: true },
            ]} />
          </div>
        ) : null}
      </div>
    );
  };

  return (
    <main>
      <div className="page-head">
        <div>
          <h1>Nifty options</h1>
          <p className="sub">
            Bets that Nifty stays inside a range each week. If it does, the account keeps a small premium; a big move up or down loses, up to a fixed cap. Run with and without the LLM, plus a ₹1,000 lottery-ticket test.
          </p>
        </div>
      </div>

      <Kpis>
        <Kpi hl label="Value now" value={money(v.totals.value)} delta={`of ${money(v.totals.invested)} invested`} />
        <Kpi label="Total P&L" value={<Signed v={v.totals.pnl} sym="₹" d={0} />} delta={fmt.pct(v.totals.ret)} deltaTone={fmt.tone(v.totals.ret)} />
        <Kpi label="LLM difference" value={<span className={fmt.tone(edge)}>{fmt.pp(edge)}</span>} delta="with LLM minus without" />
        <LiveNiftyKpi fallback={options.spot} syncedAt={options.time} />
      </Kpis>

      <div className="grid section">
        <div className="c7">
          <Panel title="With vs without LLM" meta="% since start, against Nifty">
            <EquityChart data={v.condorChart} height={240} compact ranges={false} />
          </Panel>
        </div>
        <div className="c5">
          <Panel title="₹1,000 test" meta="% on the ₹1,000 start">
            {v.lottoChart ? <EquityChart data={v.lottoChart} height={240} compact ranges={false} /> : <div className="empty">No data yet.</div>}
          </Panel>
        </div>
      </div>

      {gate ? (
        <div className="callout section">
          <b>Latest gate, {fmt.short(gate.date)}: {gate.action}</b>
          {gate.lotto_direction && gate.lotto_direction !== "none" ? <> · lotto direction <b>{gate.lotto_direction}</b></> : null}. {gate.note}
        </div>
      ) : null}

      <div className="section">
        <Tabs tabs={[
          {
            label: "Accounts", body: (
              <Table rows={v.rows} cols={[
                { key: "name", label: "Account", render: (r) => <b>{r.name}</b> },
                { key: "ret", label: "Return", n: true, render: (r) => <span className={fmt.tone(r.ret)}>{fmt.pct(r.ret)}</span> },
                { key: "value", label: "Value", n: true, render: (r) => money(r.value) },
                { key: "invested", label: "Invested", n: true, render: (r) => money(r.invested) },
                { key: "pnl", label: "P&L", n: true, render: (r) => <Signed v={r.pnl} sym="₹" d={0} /> },
                { key: "realized", label: "Booked", n: true, render: (r) => <Signed v={r.realized} sym="₹" d={0} /> },
                { key: "open", label: "Open P&L", n: true, render: (r) => (r.open == null ? <span className="muted">{r.status}</span> : <Signed v={r.open} sym="₹" d={0} />) },
                { key: "trades", label: "Trades", n: true, render: (r) => `${r.trades} · ${r.wins} won` },
              ]} />
            ),
          },
          ...Object.keys(OPTION_ARMS).filter((k) => books[k]).map((k) => ({
            label: OPTION_ARMS[k].short, count: books[k].open ? "open" : null, body: arm(k),
          })),
        ]} />
      </div>

      <details className="how section">
        <summary>How this desk works</summary>
        <div>
          <p>
            Three paper accounts. Two make the weekly range bet (in trading terms, an iron condor): they sell Nifty options
            above and below the current price and collect the premium, and buy options further out as insurance so the loss is
            capped. The account with LLM lets Claude bet a wider range or skip a risky week; the account without LLM bets every
            week by the rules. The third buys one cheap option a week in the direction Nifty is moving, staking at most ₹1,000 a
            trade (before 5 November it re-staked its whole balance).
            A one-minute monitor checks exits during market hours.
          </p>
          <p style={{ marginTop: 10 }}>
            The Nifty price and strike distances update live, about every 15 seconds. Option prices, account values and the charts
            update when the desk syncs at each scheduled run (09:16, 12:35 and 15:05 IST, plus the US-session runs). Read the{" "}
            <Link className="accent" href="https://github.com/DharmikGohil/LLMTrading/blob/main/docs/options-backtest.md">options backtest</Link>{" "}
            before drawing conclusions from a few weeks.
          </p>
        </div>
      </details>
    </main>
  );
}
