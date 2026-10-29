import Link from "next/link";
import { fmt } from "@/lib/data";

export default function Event({ e }) {
  const kind = { call: "Analyst call", skip: "Not bought", order: "Order", review: "Daily review", report: "Analyst report" }[e.kind];
  return (
    <div className={`ev ${e.kind}`} data-market={e.market} data-kind={e.kind}>
      <div className="ev-head">
        <span className={`chip ${e.kind === "call" || e.kind === "skip" ? "llm" : ""}`}>{kind}</span>
        <span className="chip">{e.market}</span>
        {e.href ? <Link className="ev-title" href={e.href}>{e.title}</Link> : <span className="ev-title">{e.title}</span>}
        {e.kind === "order" || e.kind === "skip" ? <span className="ev-meta">{fmt.time(e.t)}</span> : null}
      </div>
      {e.body ? <div className="ev-body">{e.body}</div> : null}
    </div>
  );
}
