"use client";
import { useEffect, useRef, useState } from "react";

/**
 * Filters server-rendered items in place, so pages stay static.
 * Items carry data-* attributes named after the groups; containers marked
 * data-fgroup are hidden when none of their items are visible.
 */
export default function Filters({ groups, search, children, countLabel = "shown" }) {
  const [sel, setSel] = useState(() => Object.fromEntries(groups.map((g) => [g.name, g.initial ?? ""])));
  const [q, setQ] = useState("");
  const [count, setCount] = useState(null);
  const box = useRef(null);
  useEffect(() => {
    const root = box.current;
    if (!root) return;
    let shown = 0;
    root.querySelectorAll("[data-fi]").forEach((el) => {
      const ok = groups.every((g) => !sel[g.name] || (el.dataset[g.name] || "").split(" ").includes(sel[g.name]))
        && (!q || (el.dataset.text || el.textContent).toUpperCase().includes(q.toUpperCase()));
      el.hidden = !ok;
      if (ok) shown++;
    });
    root.querySelectorAll("[data-fgroup]").forEach((g) => {
      g.hidden = !g.querySelector("[data-fi]:not([hidden])");
    });
    setCount(shown);
  }, [sel, q, groups]);
  return (
    <>
      <div className="filters">
        {groups.map((g) => (
          <div className="seg" role="group" aria-label={g.label} key={g.name}>
            {g.options.map(([v, l]) => (
              <button key={l} type="button" aria-pressed={sel[g.name] === v} onClick={() => setSel((s) => ({ ...s, [g.name]: v }))}>{l}</button>
            ))}
          </div>
        ))}
        {search ? <input className="search" type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder={search} aria-label={search} /> : null}
        {count != null ? <span className="count">{count} {countLabel}</span> : null}
      </div>
      <div ref={box}>{children}</div>
    </>
  );
}
