"use client";
import { useState } from "react";

/**
 * Broker-style tabs for the detail tables on a page (Positions, Orders, ...).
 * Every pane is rendered on the server; only the chosen one is shown, so filters and links keep working.
 * tabs: [{ label, count?, body }]
 */
export default function Tabs({ tabs, initial = 0 }) {
  const [on, setOn] = useState(initial);
  return (
    <div className="tabs">
      <div className="tabs-h" role="tablist">
        {tabs.map((t, i) => (
          <button key={t.label} type="button" role="tab" aria-selected={i === on} onClick={() => setOn(i)}>
            {t.label}
            {t.count != null ? <span className="n">{t.count}</span> : null}
          </button>
        ))}
      </div>
      {tabs.map((t, i) => (
        <div key={t.label} role="tabpanel" hidden={i !== on} className="tabs-b">
          {t.body}
        </div>
      ))}
    </div>
  );
}
