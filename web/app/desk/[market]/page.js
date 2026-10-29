import { notFound } from "next/navigation";
import EquityChart from "@/components/EquityChart";
import { Chip, Fig, PnL, Table } from "@/components/ui";
import { BOOKS, MARKETS, cleanNote, deskOf, fmt, load } from "@/lib/data";

export function generateStaticParams() {
  return Object.keys(MARKETS).map((market) => ({ market }));
}

export async function generateMetadata({ params }) {
  const { market } = await params;
  return { title: MARKETS[market]?.title ?? "Desk" };
}

export default async function Desk({ params }) {
  const { market } = await params;
  if (!MARKETS[market]) notFound();
  const d = deskOf(load(), market);
  const book = (b) => <span className={b === "main" ? "chip llm" : "chip"}>{BOOKS[b] ?? b}</span>;
  const money = (v) => fmt.num(v);
  return (
    <main>
      <div className="page-head">
        <span className="eyebrow">{d.currency} · {d.index}</span>
        <h1>{d.title}</h1>
        <p className="lede">{d.schedule}</p>
      </div>

      {d.main ? (
        <section className="card">
          <div className="figures">
            <Fig label="LLM-reviewed equity" value={fmt.money(d.main.equity, d.symbol)} sub={`${fmt.pct(d.main.return_pct)} · cash ${fmt.money(d.main.cash, d.symbol)}`} />
            <Fig label="LLM off equity" value={d.control ? fmt.money(d.control.equity, d.symbol) : "—"} sub={d.control ? fmt.pct(d.control.return_pct) : ""} />
            <Fig label="LLM edge" value={fmt.pp(d.edge)} tone={fmt.tone(d.edge)} className="edge" />
            <Fig label="Realised P&L (reviewed)" value={fmt.money(d.main.realized_pnl, d.symbol)} tone={fmt.tone(d.main.realized_pnl)} />
            <Fig label="Unrealised P&L (reviewed)" value={fmt.money(d.main.unrealized_pnl, d.symbol)} tone={fmt.tone(d.main.unrealized_pnl)} />
          </div>
          <EquityChart rows={d.equity} indexName={d.index} />
        </section>
      ) : <p className="note">No data for this desk yet.</p>}

      <section className="section">
        <div className="section-head"><h2>Open positions</h2><p className="note">Stops trail upward only. The slow momentum book has no fixed profit target.</p></div>
        <Table rows={d.positions} empty="No open positions." cols={[
          { key: "book", label: "Account", render: (r) => book(r.book) },
          { key: "symbol", label: "Stock", sym: true },
          { key: "qty", label: "Shares", n: true },
          { key: "avg_price", label: "Avg", n: true, render: (r) => money(r.avg_price) },
          { key: "last_price", label: "Last", n: true, render: (r) => money(r.last_price) },
          { key: "unrealized", label: "P&L", n: true, render: (r) => <PnL v={r.unrealized} /> },
          { key: "unrealized_pct", label: "P&L %", n: true, render: (r) => <PnL v={r.unrealized_pct} pct /> },
          { key: "stop", label: "Stop", n: true, render: (r) => money(r.stop) },
          { key: "opened", label: "Opened" },
        ]} />
      </section>

      <section className="section">
        <div className="section-head"><h2>Decisions on every candidate</h2><p className="note">Why each screened stock was bought, shrunk, vetoed or skipped.</p></div>
        <Table rows={d.decisions.slice(0, 200)} cols={[
          { key: "time", label: "Time", render: (r) => fmt.time(r.time) },
          { key: "book", label: "Account", render: (r) => book(r.book) },
          { key: "symbol", label: "Stock", sym: true },
          { key: "decision", label: "Decision", wrap: true, render: (r) => cleanNote(r.decision) },
        ]} />
      </section>

      <section className="section">
        <div className="section-head"><h2>Orders</h2></div>
        <Table rows={d.trades} cols={[
          { key: "time", label: "Time", render: (r) => fmt.time(r.time) },
          { key: "book", label: "Account", render: (r) => book(r.book) },
          { key: "side", label: "Side", render: (r) => <Chip>{r.side}</Chip> },
          { key: "symbol", label: "Stock", sym: true },
          { key: "qty", label: "Shares", n: true },
          { key: "price", label: "Price", n: true, render: (r) => money(r.price) },
          { key: "status", label: "Status" },
          { key: "reason", label: "Reason", wrap: true, render: (r) => cleanNote(r.reason) },
        ]} />
      </section>
    </main>
  );
}
