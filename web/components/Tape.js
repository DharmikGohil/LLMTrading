"use client";
import Link from "next/link";
import { useQuote } from "@/components/Live";
import { fmt } from "@/lib/fmt";

function Item({ p, hidden }) {
  const q = useQuote(p.market, p.symbol);
  const last = q?.p ?? p.last;
  const pct = q && p.avg ? (q.p / p.avg - 1) * 100 : p.pct;
  return (
    <Link href={`/symbol/${encodeURIComponent(p.symbol)}`} tabIndex={hidden ? -1 : undefined}>
      <span>{p.symbol}</span>
      <span className="mk">{p.market === "US" ? "US" : "NSE"}</span>
      <span className="muted">{fmt.num(last)}</span>
      <span className={fmt.tone(pct)}>{fmt.pct(pct)}</span>
    </Link>
  );
}

/** Scrolling strip of the LLM-reviewed books' open positions, live P&L vs entry (pauses on hover, static with reduced motion). */
export default function Tape({ items }) {
  if (!items.length) return null;
  const reps = Math.max(1, Math.ceil(12 / items.length));
  return (
    <div className="tape" aria-label="Open positions, LLM-reviewed books, P&L since entry">
      <div className="tape-track">
        {Array.from({ length: reps * 2 }, (_, i) => (
          <div className="tape-set" key={i} aria-hidden={i > 0 || undefined}>
            {items.map((p) => <Item key={`${p.market}-${p.symbol}`} p={p} hidden={i > 0} />)}
          </div>
        ))}
      </div>
    </div>
  );
}
