import Link from "next/link";
import { notFound } from "next/navigation";
import PriceChart from "@/components/PriceChart";
import { Book, Conf, Kpi, Kpis, Panel, PnlPct, Rating, Side, Signed, Table } from "@/components/ui";
import { cleanNote, fmt, isVeto, load, marketOf, symbolView, symbols } from "@/lib/data";

export function generateStaticParams() {
  return symbols(load()).map((s) => ({ sym: s.symbol }));
}

export async function generateMetadata({ params }) {
  const { sym } = await params;
  return { title: decodeURIComponent(sym) };
}

export default async function SymbolPage({ params }) {
  const sym = decodeURIComponent((await params).sym);
  const data = load();
  const v = symbolView(data, sym);
  const market = v.signals[0]?.market || v.positions[0]?.market || v.trades[0]?.market || v.decisions[0]?.market;
  if (!market) notFound();
  const m = marketOf(market);
  const held = (b) => v.positions.find((p) => p.book === b);
  const main = held("main"), ctl = held("factor");
  const last = main?.last_price ?? ctl?.last_price ?? v.trades[0]?.price;
  const vetoes = v.decisions.filter((d) => d.book === "main" && isVeto(d)).length;

  return (
    <main>
      <div className="page-head">
        <div>
          <div className="crumbs"><Link className="label" href={`/desk/${m.key}`}>{m.title} →</Link></div>
          <h1>{sym} <span className="chip ghost" style={{ verticalAlign: "middle" }}>{m.name === "US" ? "US" : "NSE"}</span></h1>
          <p className="sub">Everything the desk has said and done on {sym}.</p>
        </div>
      </div>

      <Kpis>
        <Kpi label="Last price" value={last != null ? fmt.money(last, m.symbol) : "—"} delta={main ? `held since ${fmt.short(main.opened)}` : "not held (reviewed)"} />
        <Kpi label="LLM-reviewed" value={main ? `${main.qty} sh` : "flat"} delta={main ? <><PnlPct v={main.unrealized_pct} />{main.stop ? ` · stop ${fmt.num(main.stop)}` : ""}</> : vetoes ? `${vetoes} LLM veto${vetoes > 1 ? "es" : ""}` : "—"} />
        <Kpi label="LLM off" value={ctl ? `${ctl.qty} sh` : "flat"} delta={ctl ? <PnlPct v={ctl.unrealized_pct} /> : "—"} />
        <Kpi hl label="Latest call" value={v.signals[0] ? <Rating r={v.signals[0].rating} /> : "—"} delta={v.signals[0] ? `${Math.round(v.signals[0].confidence ?? 0)}% · data to ${fmt.short(v.signals[0].date)}` : "never reviewed"} />
      </Kpis>

      <div className="grid section">
        <div className="c12">
          <Panel title="Price chart" meta="Daily candles · EMA 20/50 · SMA 200 · support/resistance · volume · RSI · MACD">
            <PriceChart market={market} sym={sym} avg={main?.avg_price} stop={main?.stop} cur={m.symbol} />
          </Panel>
        </div>
        <div className="c12">
          <Panel title="Analyst calls" meta={`${v.signals.length}`} flush>
            <Table rows={v.signals} rowKey={(r) => r.date} empty="Never reviewed by the analyst." cols={[
              { key: "date", label: "Data to", render: (r) => <span className="mono">{fmt.day(r.date)}</span> },
              { key: "screen_rank", label: "Rank", n: true, render: (r) => r.screen_rank ?? "—" },
              { key: "rating", label: "Rating", render: (r) => <Rating r={r.rating} /> },
              { key: "confidence", label: "Conf.", render: (r) => <Conf v={r.confidence} /> },
              { key: "thesis", label: "Reasoning and sources", wrap: true },
            ]} />
          </Panel>
        </div>
        <div className="c6">
          <Panel title="Orders" meta={`${v.trades.length}`} flush>
            <Table rows={v.trades} empty="No orders." cols={[
              { key: "time", label: "Time", render: (r) => <span className="mono muted">{fmt.time(r.time, m.tz, m.tzLabel)}</span> },
              { key: "book", label: "Book", render: (r) => <Book b={r.book} /> },
              { key: "side", label: "Side", render: (r) => <Side s={r.side} /> },
              { key: "qty", label: "Qty", n: true },
              { key: "price", label: "Price", n: true, render: (r) => fmt.num(r.price) },
              { key: "realized", label: "Realized", n: true, render: (r) => (r.realized == null ? <span className="muted">—</span> : <Signed v={r.realized} sym={m.symbol} />) },
            ]} />
          </Panel>
        </div>
        <div className="c6">
          <Panel title="Engine decisions" meta={`${v.decisions.length}`} flush>
            <Table rows={v.decisions} empty="No decisions." cols={[
              { key: "time", label: "Time", render: (r) => <span className="mono muted">{fmt.time(r.time, m.tz, m.tzLabel)}</span> },
              { key: "book", label: "Book", render: (r) => <Book b={r.book} /> },
              { key: "decision", label: "Decision", wrap: true, render: (r) => cleanNote(r.decision) },
            ]} />
          </Panel>
        </div>
      </div>
    </main>
  );
}
