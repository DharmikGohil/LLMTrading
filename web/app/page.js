import Link from "next/link";
import EquityChart from "@/components/EquityChart";
import Event from "@/components/Event";
import { Fig } from "@/components/ui";
import { deskOf, fmt, load, timeline } from "@/lib/data";

export default function Overview() {
  const data = load();
  const desks = ["us", "india"].map((m) => deskOf(data, m));
  const recent = timeline(data).slice(0, 2);
  return (
    <main>
      <div className="page-head">
        <span className="eyebrow">Live paper desk</span>
        <h1>Does an LLM analyst make a momentum strategy better?</h1>
        <p className="lede">
          Each desk runs two paper accounts on the same momentum screen. In the <b>LLM-reviewed</b> account Claude checks every
          candidate for red flags (results dates, filings, news) and can only veto or shrink a buy. The <b>LLM off</b> account
          trades the screen alone. The gap between them is the LLM's measured value.
        </p>
      </div>

      <div className="desks">
        {desks.map((d) => (
          <section className="card" key={d.key} aria-labelledby={`h-${d.key}`}>
            <div className="desk-top">
              <h2 id={`h-${d.key}`}><Link href={`/desk/${d.key}`}>{d.title}</Link></h2>
              <span className="note">{d.positions.filter((p) => p.book === "main").length} positions · {d.trades.length} orders</span>
            </div>
            {d.main ? (
              <>
                <div className="figures">
                  <Fig label="LLM-reviewed" value={fmt.money(d.main.equity, d.symbol)} sub={fmt.pct(d.main.return_pct)} subTone={fmt.tone(d.main.return_pct)} />
                  <Fig label="LLM off (control)" value={d.control ? fmt.money(d.control.equity, d.symbol) : "—"} sub={d.control ? fmt.pct(d.control.return_pct) : "starts after first trade"} subTone={d.control ? fmt.tone(d.control.return_pct) : ""} />
                  <Fig label="LLM edge" value={fmt.pp(d.edge)} tone={fmt.tone(d.edge)} className="edge" />
                  <Fig label={`${d.index} since start`} value={fmt.pct(d.main.index_return_pct)} tone={fmt.tone(d.main.index_return_pct)} />
                </div>
                <EquityChart rows={d.equity} indexName={d.index} />
                <div className="legend">
                  <span><i className="sw" style={{ background: "var(--signal)" }} />LLM-reviewed</span>
                  <span><i className="sw" style={{ background: "var(--control)" }} />LLM off</span>
                  <span><i className="sw" style={{ background: "var(--ink)" }} />{d.index}</span>
                </div>
              </>
            ) : (
              <p className="note">No data yet.</p>
            )}
            <p className="note" style={{ marginTop: 10 }}>{d.schedule}</p>
          </section>
        ))}
      </div>

      <section className="section">
        <div className="section-head">
          <h2>Latest activity</h2>
          <Link href="/timeline" className="note">Full timeline →</Link>
        </div>
        <div className="thread">
          {recent.map(([day, events]) => (
            <div className="day" key={day}>
              <div className="day-label">{fmt.day(day)}</div>
              <div className="events">
                {events.slice(0, 12).map((e, i) => <Event key={i} e={e} />)}
              </div>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}
