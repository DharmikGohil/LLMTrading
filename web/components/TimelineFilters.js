"use client";
import { useState } from "react";

const MARKETS = [["", "All markets"], ["India", "India"], ["US", "US"]];
const KINDS = [["", "All events"], ["call", "Analyst calls"], ["skip", "Not bought"], ["order", "Orders"], ["report", "Reports"], ["review", "Reviews"]];

/** Filters the server-rendered thread in place (the page stays fully static). */
export default function TimelineFilters({ children }) {
  const [market, setMarket] = useState("");
  const [kind, setKind] = useState("");
  return (
    <>
      <div className="filters" role="group" aria-label="Market">
        {MARKETS.map(([v, l]) => (
          <button key={l} type="button" className="fbtn" aria-pressed={market === v} onClick={() => setMarket(v)}>{l}</button>
        ))}
      </div>
      <div className="filters" role="group" aria-label="Event type" style={{ marginTop: 8 }}>
        {KINDS.map(([v, l]) => (
          <button key={l} type="button" className="fbtn" aria-pressed={kind === v} onClick={() => setKind(v)}>{l}</button>
        ))}
      </div>
      <div className="thread section" data-market={market || undefined} data-kind={kind || undefined}>{children}</div>
    </>
  );
}
