import Link from "next/link";
import { Chip, Table } from "@/components/ui";
import { fmt, load } from "@/lib/data";

export const metadata = { title: "Journal" };

export default function Journal() {
  const { lessons, docs } = load();
  const reviews = docs.filter((d) => d.kind === "review");
  const reports = docs.filter((d) => d.kind === "report");
  return (
    <main>
      <div className="page-head">
        <span className="eyebrow">How the desk learns</span>
        <h1>Journal</h1>
        <p className="lede">
          The model is not retrained. Instead every close produces a graded review (orders, how each veto turned out,
          calls versus the index), and patterns go into a lesson book. A lesson starts as a hypothesis, becomes
          confirmed after three supporting cases and is retired when the evidence turns against it. Every analyst run
          reads the lesson book first. Lessons can sharpen judgement but never loosen risk limits.
        </p>
      </div>

      <section className="section">
        <div className="section-head"><h2>Lesson book</h2></div>
        <Table rows={lessons} empty="No lessons yet. They need evidence first: the first candidates come once vetoes have outcomes." cols={[
          { key: "status", label: "Status", render: (r) => <span className={`chip ${r.status === "confirmed" ? "buy" : r.status === "retired" ? "sell" : ""}`}>{r.status}</span> },
          { key: "market", label: "Market" },
          { key: "lesson", label: "Lesson", wrap: true },
          { key: "evidence_for", label: "For", n: true },
          { key: "evidence_against", label: "Against", n: true },
          { key: "examples", label: "Cases", wrap: true },
        ]} />
      </section>

      <section className="section">
        <div className="section-head"><h2>Daily reviews</h2></div>
        <div className="list">
          {reviews.length ? reviews.map((d) => (
            <Link key={d.id} href={`/notes/${d.id}`}><span>{d.market} desk review</span><span className="note">{fmt.day(d.date)}</span></Link>
          )) : <div className="empty">No reviews yet.</div>}
        </div>
      </section>

      <section className="section">
        <div className="section-head"><h2>Analyst reports</h2></div>
        <div className="list">
          {reports.length ? reports.map((d) => (
            <Link key={d.id} href={`/notes/${d.id}`}><span>{d.market} analyst report</span><span className="note">data to {fmt.day(d.date)}</span></Link>
          )) : <div className="empty">No reports yet.</div>}
        </div>
      </section>
    </main>
  );
}
