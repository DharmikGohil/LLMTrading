import Link from "next/link";
import Filters from "@/components/Filters";
import { Conf, Kpi, Kpis, Rating } from "@/components/ui";
import { RATING_TONE, fmt, load } from "@/lib/data";

export const metadata = { title: "Analyst calls" };

export default function Calls() {
  const { signals, docs } = load();
  const rows = [...signals].sort((a, b) => b.date.localeCompare(a.date) || a.market.localeCompare(b.market) || (a.screen_rank ?? 99) - (b.screen_rank ?? 99));
  const groups = new Map();
  for (const s of rows) {
    const k = `${s.date}|${s.market}`;
    if (!groups.has(k)) groups.set(k, []);
    groups.get(k).push(s);
  }
  const blocks = rows.filter((s) => RATING_TONE[s.rating] === "down" && (s.confidence ?? 0) >= 55).length;
  const shrinks = rows.filter((s) => s.rating === "Hold").length;
  return (
    <main>
      <div className="page-head">
        <div>
          <span className="label">Claude as risk reviewer</span>
          <h1>Analyst calls</h1>
          <p className="sub">
            For every stock the momentum screen proposes, the analyst checks results dates, exchange filings and recent news, then rates it.
            Underweight or Sell at 55% confidence or more <b>blocks</b> the buy, Hold shrinks it, Buy and Overweight mean no objection. Every reason cites its source.
          </p>
        </div>
      </div>
      <Kpis>
        <Kpi label="Calls made" value={rows.length} delta={`${groups.size} review sessions`} />
        <Kpi hl label="Blocking calls" value={blocks} delta="Underweight/Sell ≥ 55%" />
        <Kpi label="Size cuts" value={shrinks} delta="Hold ratings" />
        <Kpi label="No objection" value={rows.length - blocks - shrinks} delta="Buy / Overweight" />
      </Kpis>
      <div style={{ marginTop: 12 }}>
        <Filters countLabel="calls" search="Filter by stock or text" groups={[
          { name: "market", label: "Desk", options: [["", "Both desks"], ["US", "US"], ["India", "India"]] },
          { name: "tone", label: "Rating", options: [["", "All ratings"], ["down", "Blocks"], ["flat", "Hold"], ["up", "Buy / Overweight"]] },
        ]}>
          {[...groups.entries()].map(([k, list]) => {
            const [date, market] = k.split("|");
            const report = docs.find((d) => d.kind === "report" && d.date === date && d.market === market);
            return (
              <section key={k} data-fgroup style={{ marginBottom: 18 }}>
                <div className="filters" style={{ justifyContent: "space-between", marginBottom: 8 }}>
                  <h2 style={{ fontSize: 14 }}><span className="chip ghost" style={{ marginRight: 8 }}>{market === "US" ? "US" : "NSE"}</span>Data to {fmt.day(date)}</h2>
                  {report ? <Link className="accent mono" style={{ fontSize: 12 }} href={`/notes/${report.id}`}>Full report with sources →</Link> : null}
                </div>
                <div className="calls">
                  {list.map((s) => {
                    const tone = RATING_TONE[s.rating] || "flat";
                    return (
                      <article key={s.symbol} className={`call ${tone === "down" ? "veto" : ""}`} data-fi data-market={s.market} data-tone={tone} data-text={`${s.symbol} ${s.thesis}`}>
                        <div className="call-h">
                          <span className="rk">#{s.screen_rank ?? "—"}</span>
                          <Link className="sym" href={`/symbol/${encodeURIComponent(s.symbol)}`}>{s.symbol}</Link>
                          <Rating r={s.rating} />
                          <span className="conf"><Conf v={s.confidence} /></span>
                        </div>
                        <p>{s.thesis}</p>
                      </article>
                    );
                  })}
                </div>
              </section>
            );
          })}
        </Filters>
      </div>
    </main>
  );
}
