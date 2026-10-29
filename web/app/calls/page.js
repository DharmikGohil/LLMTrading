import Link from "next/link";
import { Chip } from "@/components/ui";
import { fmt, load } from "@/lib/data";

export const metadata = { title: "Analyst calls" };

export default function Calls() {
  const { signals, docs } = load();
  const byDay = new Map();
  for (const s of [...signals].sort((a, b) => b.date.localeCompare(a.date) || (a.screen_rank ?? 99) - (b.screen_rank ?? 99))) {
    const k = `${s.date}|${s.market}`;
    if (!byDay.has(k)) byDay.set(k, []);
    byDay.get(k).push(s);
  }
  return (
    <main>
      <div className="page-head">
        <span className="eyebrow">Claude as risk reviewer</span>
        <h1>Analyst calls</h1>
        <p className="lede">
          For every stock the momentum screen proposes, the analyst checks results dates, exchange filings and recent news,
          then rates it. Underweight or Sell at 55% confidence or more <b>blocks</b> the buy. Hold shrinks it. Buy and
          Overweight mean no objection. Every reason cites its source.
        </p>
      </div>
      {[...byDay.entries()].map(([k, rows]) => {
        const [date, market] = k.split("|");
        const report = docs.find((d) => d.kind === "report" && d.date === date && d.market === market);
        return (
          <section className="section" key={k}>
            <div className="section-head">
              <h2>{market} · data to {fmt.day(date)}</h2>
              {report ? <Link className="note" href={`/notes/${report.id}`}>Full report with sources →</Link> : null}
            </div>
            <ol className="calls">
              {rows.map((r) => (
                <li key={r.symbol}>
                  <div className="call-head">
                    <span className="call-rank">{r.screen_rank ?? "—"}</span>
                    <span className="sym">{r.symbol}</span>
                    <Chip>{r.rating}</Chip>
                    <span className="call-conf">{r.confidence == null ? "" : `${Math.round(r.confidence)}%`}</span>
                  </div>
                  <p className="call-body">{r.thesis}</p>
                </li>
              ))}
            </ol>
          </section>
        );
      })}
      {byDay.size === 0 ? <p className="note">No calls yet.</p> : null}
    </main>
  );
}
