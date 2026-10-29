import Link from "next/link";
import { Kpi, Kpis, Panel, Table } from "@/components/ui";
import { fmt, load } from "@/lib/data";

export const metadata = { title: "Journal" };

const STATUS = { confirmed: "up", retired: "down", hypothesis: "llm" };

export default function Journal() {
  const { lessons, docs, journal } = load();
  const reviews = docs.filter((d) => d.kind === "review");
  const reports = docs.filter((d) => d.kind === "report");
  const changes = docs.find((d) => d.kind === "changes");
  const latest = journal[0];
  return (
    <main>
      <div className="page-head">
        <div>
          <span className="label">How the desk learns</span>
          <h1>Journal</h1>
          <p className="sub">
            The model is not retrained. Every close produces a graded review (orders, how each veto turned out, calls versus the index),
            and patterns go into a lesson book: a hypothesis becomes confirmed after three supporting cases and is retired when the
            evidence turns against it. Every analyst run reads the lesson book first. Lessons sharpen judgement; they never loosen risk limits.
          </p>
        </div>
      </div>
      <Kpis>
        <Kpi label="Daily reviews" value={reviews.length} />
        <Kpi label="Analyst reports" value={reports.length} />
        <Kpi hl label="Confirmed lessons" value={lessons.filter((l) => l.status === "confirmed").length} delta="3+ supporting cases" />
        <Kpi label="Hypotheses" value={lessons.filter((l) => l.status === "hypothesis").length} delta="being tested" />
      </Kpis>
      <div className="grid" style={{ marginTop: 12 }}>
        <div className="c12">
          <Panel title="Lesson book" flush>
            <Table rows={lessons} empty="No lessons yet. They need evidence first: the first candidates come once vetoes have outcomes." cols={[
              { key: "status", label: "Status", render: (r) => <span className={`chip ${STATUS[r.status] || ""}`}>{r.status}</span> },
              { key: "market", label: "Desk" },
              { key: "lesson", label: "Lesson", wrap: true },
              { key: "evidence_for", label: "For", n: true },
              { key: "evidence_against", label: "Against", n: true },
              { key: "examples", label: "Cases", wrap: true, render: (r) => (Array.isArray(r.examples) ? r.examples.join("; ") : r.examples) },
            ]} />
          </Panel>
        </div>
        {latest ? (
          <div className="c12">
            <Panel title="Latest reflection" meta={`${latest.market} · ${fmt.day(latest.date)}`} act={<Link href={`/notes/review-${latest.id}`}>Full review →</Link>}>
              <div className="prose" style={{ whiteSpace: "pre-wrap", fontSize: 13.5 }}>{latest.reflection.replace(/\*\*/g, "")}</div>
            </Panel>
          </div>
        ) : null}
        <div className="c6">
          <Panel title="Daily reviews" flush>
            <div className="links">
              {reviews.length ? reviews.map((d) => (
                <Link key={d.id} href={`/notes/${d.id}`}><span><span className="chip ghost">{d.market === "US" ? "US" : "NSE"}</span> Close review</span><span className="r">{fmt.day(d.date)}</span></Link>
              )) : <div className="empty">No reviews yet.</div>}
            </div>
          </Panel>
        </div>
        <div className="c6">
          <Panel title="Analyst reports" flush>
            <div className="links">
              {reports.length ? reports.map((d) => (
                <Link key={d.id} href={`/notes/${d.id}`}><span><span className="chip ghost">{d.market === "US" ? "US" : "NSE"}</span> Pre-open report</span><span className="r">data to {fmt.day(d.date)}</span></Link>
              )) : <div className="empty">No reports yet.</div>}
              {changes ? <Link href={`/notes/${changes.id}`}><span><span className="chip llm">Log</span> Strategy change log</span><span className="r">all changes</span></Link> : null}
            </div>
          </Panel>
        </div>
      </div>
    </main>
  );
}
