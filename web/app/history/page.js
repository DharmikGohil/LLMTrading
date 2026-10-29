import Filters from "@/components/Filters";
import { Book, Kpi, Kpis, Panel, Side, Signed, Table } from "@/components/ui";
import { allTrades, dailyLedger, fmt, load, marketOf } from "@/lib/data";

export const metadata = { title: "History" };

export default function History() {
  const data = load();
  const ledger = dailyLedger(data);
  const trades = allTrades(data);
  const closed = trades.filter((t) => t.realized != null);
  const wins = closed.filter((t) => t.realized > 0).length;
  const buys = trades.filter((t) => t.side === "BUY").length;
  const sells = trades.filter((t) => t.side === "SELL").length;
  const sessions = new Set(ledger.map((r) => `${r.desk}${r.date}`)).size;

  return (
    <main>
      <div className="page-head">
        <div>
          <span className="label">Everything the desk has done</span>
          <h1>History</h1>
          <p className="sub">Each session&apos;s closing equity for both books against the index, and every order with its realized result.</p>
        </div>
      </div>

      <Kpis>
        <Kpi label="Sessions recorded" value={sessions} delta="desk-days" />
        <Kpi label="Orders" value={trades.length} delta={`${buys} buys · ${sells} sells`} />
        <Kpi label="Closed trades" value={closed.length} delta={closed.length ? `${Math.round((wins / closed.length) * 100)}% winners` : "none closed yet"} />
        <Kpi label="Realized P&L" value={<span className="num">
          {["US", "India"].map((m, i) => {
            const v = closed.filter((t) => t.market === m && t.book === "main").reduce((a, t) => a + t.realized, 0);
            return <span key={m}>{i ? " · " : ""}<Signed v={v} sym={marketOf(m).symbol} d={0} /></span>;
          })}
        </span>} delta="LLM-reviewed books, US · India" />
      </Kpis>

      <div className="grid" style={{ marginTop: 12 }}>
        <div className="c12">
          <Panel title="Daily ledger" meta="close of each session · edge is cumulative" flush>
            <Table rows={ledger} rowKey={(r) => r.id} empty="The first close will appear here." cols={[
              { key: "date", label: "Date", render: (r) => <span className="mono">{fmt.day(r.date)}</span> },
              { key: "market", label: "Desk", render: (r) => <span className="chip ghost">{r.market === "US" ? "US" : "NSE"}</span> },
              { key: "main", label: "LLM-reviewed", n: true, render: (r) => fmt.money(r.main, r.symbol) },
              { key: "mainDay", label: "Day", n: true, render: (r) => <span className={fmt.tone(r.mainDay)}>{fmt.pct(r.mainDay)}</span> },
              { key: "mainTotal", label: "Total", n: true, render: (r) => <span className={fmt.tone(r.mainTotal)}>{fmt.pct(r.mainTotal)}</span> },
              { key: "factor", label: "LLM off", n: true, render: (r) => fmt.money(r.factor, r.symbol) },
              { key: "factorDay", label: "Day", n: true, render: (r) => <span className={fmt.tone(r.factorDay)}>{fmt.pct(r.factorDay)}</span> },
              { key: "indexDay", label: "Index day", n: true, render: (r) => <span className={fmt.tone(r.indexDay)}>{fmt.pct(r.indexDay)}</span> },
              { key: "indexTotal", label: "Index total", n: true, render: (r) => <span className={fmt.tone(r.indexTotal)}>{fmt.pct(r.indexTotal)}</span> },
              { key: "edge", label: "LLM edge", n: true, render: (r) => <b className={fmt.tone(r.edge)}>{fmt.pp(r.edge)}</b> },
              { key: "orders", label: "Orders", n: true },
              { key: "vetoes", label: "Vetoes", n: true },
            ]} />
          </Panel>
        </div>

        <div className="c12">
          <Panel title="Trade blotter" meta="every order, newest first · exchange-local time" flush>
            <div style={{ padding: "12px 14px 0" }}>
              <Filters countLabel="orders" search="Filter by stock" groups={[
                { name: "market", label: "Desk", options: [["", "Both desks"], ["US", "US"], ["India", "India"]] },
                { name: "book", label: "Book", options: [["", "Both books"], ["main", "LLM-reviewed"], ["factor", "LLM off"]] },
                { name: "side", label: "Side", options: [["", "All"], ["BUY", "Buys"], ["SELL", "Sells"]] },
              ]}>
                <Table rows={trades} empty="No orders yet."
                  rowProps={(r) => ({ "data-fi": "", "data-market": r.market, "data-book": r.book, "data-side": r.side, "data-text": r.symbol })} cols={[
                  { key: "time", label: "Time", render: (r) => { const m = marketOf(r.market); return <span className="mono muted">{fmt.time(r.time, m.tz, m.tzLabel)}</span>; } },
                  { key: "market", label: "Desk", render: (r) => <span className="chip ghost">{r.market === "US" ? "US" : "NSE"}</span> },
                  { key: "book", label: "Book", render: (r) => <Book b={r.book} /> },
                  { key: "side", label: "Side", render: (r) => <Side s={r.side} /> },
                  { key: "symbol", label: "Stock", sym: true },
                  { key: "qty", label: "Qty", n: true },
                  { key: "price", label: "Price", n: true, render: (r) => fmt.num(r.price) },
                  { key: "notional", label: "Value", n: true, render: (r) => (r.price ? fmt.money(r.price * r.qty, marketOf(r.market).symbol, 0) : "—") },
                  { key: "realized", label: "Realized", n: true, render: (r) => (r.realized == null ? <span className="muted">—</span> : <Signed v={r.realized} sym={marketOf(r.market).symbol} />) },
                  { key: "status", label: "Status", render: (r) => <span className={`chip ${r.status === "COMPLETE" ? "" : "down"}`}>{r.status}</span> },
                ]} />
              </Filters>
            </div>
          </Panel>
        </div>
      </div>
    </main>
  );
}
