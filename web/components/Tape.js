import Link from "next/link";
import { fmt } from "@/lib/data";

/** Scrolling strip of the LLM-reviewed books' open positions (pauses on hover, static with reduced motion). */
export default function Tape({ items }) {
  if (!items.length) return null;
  const set = (hidden) => (
    <div className="tape-set" aria-hidden={hidden || undefined}>
      {items.map((p) => (
        <Link key={`${p.market}-${p.symbol}`} href={`/symbol/${encodeURIComponent(p.symbol)}`} tabIndex={hidden ? -1 : undefined}>
          <span>{p.symbol}</span>
          <span className="mk">{p.market === "US" ? "US" : "NSE"}</span>
          <span className="muted">{fmt.num(p.last)}</span>
          <span className={fmt.tone(p.pct)}>{fmt.pct(p.pct)}</span>
        </Link>
      ))}
    </div>
  );
  // two copies make the loop seamless; with few items, repeat so the strip is always full
  const reps = Math.max(1, Math.ceil(12 / items.length));
  return (
    <div className="tape" aria-label="Open positions, LLM-reviewed books">
      <div className="tape-track">
        {Array.from({ length: reps * 2 }, (_, i) => <span key={i} style={{ display: "contents" }}>{set(i > 0)}</span>)}
      </div>
    </div>
  );
}
