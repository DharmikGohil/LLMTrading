import Link from "next/link";
import { Book, Rating } from "@/components/ui";
import { fmt, marketOf } from "@/lib/data";

const KIND = { call: "Call", skip: "Not bought", order: "Order", review: "Review", report: "Report" };

export function LogEvent({ e, compact }) {
  const m = marketOf(e.market);
  const veto = e.kind === "skip" && /veto/.test(e.body || "");
  const when = e.kind === "order" || e.kind === "skip" ? fmt.clock(e.t, m.tz) + " " + m.tzLabel : e.kind === "call" ? "pre-open" : e.kind === "report" ? "pre-open" : "close";
  return (
    <div className={`ev ${e.kind}`} data-fi data-market={e.market} data-kind={veto ? `${e.kind} veto` : e.kind} data-book={e.book || ""} data-text={`${e.symbol || ""} ${e.title} ${e.body || ""}`}>
      <div className="meta-row">
        <span className="tm">{when}</span>
        <span className="chip ghost">{m.name === "US" ? "US" : "NSE"}</span>
        <span className={`chip ${veto || e.kind === "call" ? "llm" : e.kind === "order" ? (e.side === "BUY" ? "up" : "down") : ""}`}>{veto ? "LLM veto" : KIND[e.kind]}</span>
      </div>
      <div>
        <div className="ti">
          {e.kind === "call" ? (
            <><Link className="s" href={`/symbol/${encodeURIComponent(e.symbol)}`}>{e.symbol}</Link> <Rating r={e.rating} /> <span className="muted mono">{e.confidence != null ? `${Math.round(e.confidence)}%` : ""}</span></>
          ) : e.href ? <Link href={e.href}>{e.title} →</Link> : e.symbol ? (
            <>
              <Link className="s" href={`/symbol/${encodeURIComponent(e.symbol)}`}>{e.title}</Link>{" "}
              {e.book ? <Book b={e.book} /> : null}
            </>
          ) : e.title}
        </div>
        {e.body ? <div className={`bd ${compact ? "clamp" : ""}`} title={compact ? e.body : undefined}>{e.body}</div> : null}
      </div>
    </div>
  );
}

/** Day-grouped log. `days` comes from timeline(); `limit` caps the number of events. */
export default function Log({ days, limit, compact }) {
  let left = limit ?? Infinity;
  const out = [];
  for (const [day, evs] of days) {
    if (left <= 0) break;
    const list = evs.slice(0, left);
    left -= list.length;
    out.push(
      <div key={day} data-fgroup>
        <div className="log-day"><span>{fmt.day(day)}</span><span>{evs.length} events</span></div>
        {list.map((e, i) => <LogEvent key={i} e={e} compact={compact} />)}
      </div>,
    );
  }
  return out.length ? <div className="log">{out}</div> : <div className="empty">No activity yet.</div>;
}
