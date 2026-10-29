import Link from "next/link";
import { notFound } from "next/navigation";
import EquityChart from "@/components/EquityChart";
import Filters from "@/components/Filters";
import Log from "@/components/Log";
import { Book, Conf, Kpi, Kpis, Panel, PnlPct, Rating, Side, Signed, Table } from "@/components/ui";
import { BOOK_LONG, MARKETS, cleanNote, dailyLedger, deskOf, equitySeries, fmt, isSkip, isVeto, load, timeline } from "@/lib/data";

export function generateStaticParams() {
  return Object.keys(MARKETS).map((market) => ({ market }));
}

export async function generateMetadata({ params }) {
  const { market } = await params;
  return { title: MARKETS[market]?.title || "Desk" };
}

function Exposure({ s, book, sym }) {
  if (!s) return <div className="empty">No account yet.</div>;
  const inv = Math.max(0, s.equity - s.cash);
  const ip = (inv / s.equity) * 100;
  return (
    <div style={{ marginBottom: 14 }}>
      <div className="split-legend"><Book b={book} /><span>{fmt.money(s.equity, sym)}</span></div>
      <div className={`split ${book}`} role="img" aria-label={`${ip.toFixed(0)}% invested, ${(100 - ip).toFixed(0)}% cash`}>
        <i className="inv" style={{ width: `${ip}%` }} />
        <i className="cash" style={{ width: `${100 - ip}%` }} />
      </div>
      <div className="split-legend"><span>Invested {fmt.money(inv, sym, 0)} · {ip.toFixed(0)}%</span><span className="muted">Cash {fmt.money(s.cash, sym, 0)}</span></div>
    </div>
  );
}

export default async function Desk({ params }) {
  const { market } = await params;
  if (!MARKETS[market]) notFound();
  const data = load();
  const d = deskOf(data, market);
  const days = timeline(data).map(([day, evs]) => [day, evs.filter((e) => e.market === d.name)]).filter(([, evs]) => evs.length);
  const pos = d.positions.map((p) => ({ ...p, toStop: p.stop && p.last_price ? ((p.last_price - p.stop) / p.last_price) * 100 : null }));
  const scale = Math.max(0.5, ...pos.map((p) => Math.abs(p.unrealized_pct ?? 0)));
  const posCols = [
    { key: "symbol", label: "Stock", sym: true },
    { key: "qty", label: "Qty", n: true },
    { key: "avg_price", label: "Avg", n: true, render: (p) => fmt.num(p.avg_price) },
    { key: "last_price", label: "Last", n: true, render: (p) => fmt.num(p.last_price) },
    { key: "value", label: "Value", n: true, render: (p) => fmt.money(p.value, d.symbol, 0) },
    { key: "unrealized", label: "P&L", n: true, render: (p) => <Signed v={p.unrealized} sym={d.symbol} /> },
    { key: "unrealized_pct", label: "P&L %", n: true, render: (p) => <PnlPct v={p.unrealized_pct} scale={scale} /> },
    { key: "stop", label: "Stop", n: true, render: (p) => fmt.num(p.stop) },
    { key: "toStop", label: "To stop", n: true, render: (p) => (p.toStop == null ? "—" : `${p.toStop.toFixed(1)}%`) },
    { key: "opened", label: "Opened", render: (p) => <span className="muted mono">{p.opened ? fmt.short(p.opened) : "—"}</span> },
  ];
  const ledger = dailyLedger(data).filter((r) => r.desk === market);
  const decisions = d.decisions.map((x) => ({ ...x, veto: isVeto(x), skip: isSkip(x) }));

  return (
    <main>
      <div className="page-head">
        <div>
          <div className="crumbs"><span className="label">{d.exchange} · {d.universe} momentum · {d.currency}</span></div>
          <h1>{d.title}</h1>
          <div className="sched" style={{ marginTop: 8 }}>
            {d.schedule.map(([t, l]) => <span key={t}><b>{t}</b>{l}</span>)}
            <span className="muted">{d.tzLabel}, weekdays</span>
          </div>
        </div>
      </div>

      <Kpis>
        <Kpi label="LLM-reviewed equity" value={fmt.money(d.main?.equity, d.symbol)} delta={fmt.pct(d.main?.return_pct)} deltaTone={fmt.tone(d.main?.return_pct)} />
        <Kpi label="LLM off equity" value={fmt.money(d.control?.equity, d.symbol)} delta={fmt.pct(d.control?.return_pct)} deltaTone={fmt.tone(d.control?.return_pct)} />
        <Kpi hl label="LLM edge" value={fmt.pp(d.edge)} tone={fmt.tone(d.edge)} delta="reviewed minus LLM off" />
        <Kpi label={`${d.index} since start`} value={fmt.pct(d.indexReturn)} tone={fmt.tone(d.indexReturn)} delta="buy-and-hold benchmark" />
        <Kpi label="Unrealized P&L" value={<Signed v={d.main?.unrealized_pnl} sym={d.symbol} />} delta={`realized ${fmt.money(d.main?.realized_pnl, d.symbol)}`} />
        <Kpi label="LLM vetoes" value={d.vetoes.length} delta={`${d.signals.length} calls made`} />
      </Kpis>

      <div className="grid" style={{ marginTop: 12 }}>
        <div className="c8">
          <Panel title="Equity" meta={`% since start · ${d.tzLabel}`}>
            <EquityChart data={equitySeries(data, market)} height={300} />
          </Panel>
        </div>
        <div className="c4">
          <Panel title="Exposure" meta="invested vs cash">
            <Exposure s={d.main} book="main" sym={d.symbol} />
            <Exposure s={d.control} book="factor" sym={d.symbol} />
            <p className="muted" style={{ fontSize: 12.5 }}>
              Up to 10 positions of 10% each, at most 3 per sector. In a bear regime ({d.index} below its 200-day average) new buys are halved.
              Stops sit at 4× ATR and only ever move up.
            </p>
          </Panel>
        </div>

        <div className="c12">
          <Panel title="Open positions" meta={`${pos.filter((p) => p.book === "main").length} LLM-reviewed · ${pos.filter((p) => p.book === "factor").length} LLM off`} flush>
            <div style={{ padding: "12px 14px 0" }}>
              <Filters countLabel="positions" search="Filter by stock" groups={[
                { name: "book", label: "Book", initial: "main", options: [["main", BOOK_LONG.main], ["factor", BOOK_LONG.factor], ["", "Both"]] },
              ]}>
                <Table rows={pos} empty="No open positions." cols={[posCols[0], { key: "book", label: "Book", render: (p) => <Book b={p.book} /> }, ...posCols.slice(1)]}
                  rowProps={(p) => ({ "data-fi": "", "data-book": p.book, "data-text": p.symbol })} />
              </Filters>
            </div>
          </Panel>
        </div>

        <div className="c12">
          <Panel title="Analyst calls" meta={d.lastCallDate ? `data to ${fmt.day(d.lastCallDate)}` : ""} act={<Link href="/calls">All dates →</Link>} flush>
            <Table rows={d.latestCalls} rowKey={(r) => r.symbol} empty="No calls yet." cols={[
              { key: "screen_rank", label: "#", n: true, render: (r) => r.screen_rank ?? "—" },
              { key: "symbol", label: "Stock", sym: true },
              { key: "rating", label: "Rating", render: (r) => <Rating r={r.rating} /> },
              { key: "confidence", label: "Conf.", render: (r) => <Conf v={r.confidence} /> },
              { key: "thesis", label: "Reasoning and sources", wrap: true },
            ]} />
          </Panel>
        </div>

        <div className="c12">
          <Panel title="Daily history" meta="close of each session" act={<Link href="/history">Both desks →</Link>} flush>
            <Table rows={ledger} rowKey={(r) => r.id} empty="The first close will appear here." cols={[
              { key: "date", label: "Date", render: (r) => <span className="mono">{fmt.day(r.date)}</span> },
              { key: "main", label: "LLM-reviewed", n: true, render: (r) => fmt.money(r.main, d.symbol) },
              { key: "mainDay", label: "Day", n: true, render: (r) => <span className={fmt.tone(r.mainDay)}>{fmt.pct(r.mainDay)}</span> },
              { key: "factor", label: "LLM off", n: true, render: (r) => fmt.money(r.factor, d.symbol) },
              { key: "factorDay", label: "Day", n: true, render: (r) => <span className={fmt.tone(r.factorDay)}>{fmt.pct(r.factorDay)}</span> },
              { key: "indexDay", label: d.index, n: true, render: (r) => <span className={fmt.tone(r.indexDay)}>{fmt.pct(r.indexDay)}</span> },
              { key: "edge", label: "Edge (cum.)", n: true, render: (r) => <b className={fmt.tone(r.edge)}>{fmt.pp(r.edge)}</b> },
              { key: "orders", label: "Orders", n: true },
              { key: "vetoes", label: "Vetoes", n: true },
            ]} />
          </Panel>
        </div>

        <div className="c12">
          <Panel title="Decision on every candidate" meta="why each screened stock was bought, shrunk, vetoed or skipped" flush>
            <div style={{ padding: "12px 14px 0" }}>
              <Filters countLabel="decisions" search="Filter by stock or text" groups={[
                { name: "book", label: "Book", options: [["", "Both books"], ["main", "LLM-reviewed"], ["factor", "LLM off"]] },
                { name: "kind", label: "Outcome", options: [["", "All"], ["veto", "LLM vetoes"], ["skip", "Not bought"], ["bought", "Bought"]] },
              ]}>
                <Table rows={decisions} empty="No decisions yet."
                  rowProps={(r) => ({ "data-fi": "", "data-book": r.book, "data-kind": [r.veto && "veto", r.skip ? "skip" : "bought"].filter(Boolean).join(" ") })} cols={[
                  { key: "time", label: "Time", render: (r) => <span className="mono muted">{fmt.time(r.time, d.tz, d.tzLabel)}</span> },
                  { key: "book", label: "Book", render: (r) => <Book b={r.book} /> },
                  { key: "symbol", label: "Stock", sym: true },
                  { key: "out", label: "Outcome", render: (r) => <span className={`chip ${r.veto ? "llm" : r.skip ? "" : "up"}`}>{r.veto ? "LLM veto" : r.skip ? "Not bought" : "Bought"}</span> },
                  { key: "decision", label: "Reasoning", wrap: true, render: (r) => cleanNote(r.decision) },
                ]} />
              </Filters>
            </div>
          </Panel>
        </div>

        <div className="c7">
          <Panel title="Orders" meta={`${d.trades.length} total`} flush>
            <Table rows={d.trades} empty="No orders yet." cols={[
              { key: "time", label: "Time", render: (r) => <span className="mono muted">{fmt.time(r.time, d.tz, d.tzLabel)}</span> },
              { key: "book", label: "Book", render: (r) => <Book b={r.book} /> },
              { key: "side", label: "Side", render: (r) => <Side s={r.side} /> },
              { key: "symbol", label: "Stock", sym: true },
              { key: "qty", label: "Qty", n: true },
              { key: "price", label: "Price", n: true, render: (r) => fmt.num(r.price) },
              { key: "realized", label: "Realized", n: true, render: (r) => (r.realized == null ? <span className="muted">—</span> : <Signed v={r.realized} sym={d.symbol} />) },
              { key: "status", label: "Status", render: (r) => <span className={`chip ${r.status === "COMPLETE" ? "" : "down"}`}>{r.status}</span> },
            ]} />
          </Panel>
        </div>
        <div className="c5">
          <Panel title="Activity" meta={d.name} act={<Link href="/tape">Everything →</Link>} flush>
            <Log days={days} limit={14} compact />
          </Panel>
        </div>
      </div>
    </main>
  );
}
