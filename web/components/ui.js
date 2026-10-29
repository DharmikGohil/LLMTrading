import { fmt } from "@/lib/data";

export function Fig({ label, value, sub, tone, subTone, className }) {
  return (
    <div className={`fig ${className || ""}`}>
      <span className="fig-label">{label}</span>
      <span className={`fig-value ${tone || ""}`}>{value}</span>
      {sub ? <span className={`fig-sub ${subTone || ""}`}>{sub}</span> : null}
    </div>
  );
}

const RATING_CLASS = { Buy: "buy", Overweight: "ow", Hold: "", Underweight: "uw", Sell: "sell", BUY: "buy", SELL: "sell" };

export function Chip({ children, kind }) {
  return <span className={`chip ${kind ?? RATING_CLASS[children] ?? ""}`}>{children}</span>;
}

export function Table({ cols, rows, empty = "Nothing yet." }) {
  if (!rows.length) return <div className="tablebox"><div className="empty">{empty}</div></div>;
  return (
    <div className="tablebox">
      <table>
        <thead>
          <tr>{cols.map((c) => <th key={c.key} className={c.n ? "n" : undefined}>{c.label}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={r.id ?? i}>
              {cols.map((c) => (
                <td key={c.key} className={c.n ? "n" : c.sym ? "sym" : c.wrap ? "wrap" : undefined}>
                  {c.render ? c.render(r) : r[c.key] ?? "—"}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function PnL({ v, pct }) {
  return <span className={fmt.tone(v)}>{pct ? fmt.pct(v) : fmt.num(v)}</span>;
}
