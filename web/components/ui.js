import Link from "next/link";
import { BOOKS, RATING_TONE, fmt } from "@/lib/data";

export function Panel({ title, meta, act, children, flush, className = "", foot, id }) {
  return (
    <section className={`panel ${className}`} id={id} aria-label={typeof title === "string" ? title : undefined}>
      <header className="panel-h">
        <h2>{title}</h2>
        {meta ? <span className="meta">{meta}</span> : null}
        {act ? <span className="act">{act}</span> : null}
      </header>
      <div className={`panel-b ${flush ? "flush" : ""}`}>{children}</div>
      {foot ? <div className="panel-foot">{foot}</div> : null}
    </section>
  );
}

export function Kpis({ children }) {
  return <div className="kpis">{children}</div>;
}

export function Kpi({ label, value, delta, tone, deltaTone, hl }) {
  return (
    <div className={`kpi ${hl ? "hl" : ""}`}>
      <span className="label">{label}</span>
      <span className={`v ${tone || ""}`}>{value}</span>
      {delta != null ? <span className={`d ${deltaTone || ""}`}>{delta}</span> : null}
    </div>
  );
}

/** cols: {key, label, n (numeric), wrap, sym, render(row)} */
export function Table({ cols, rows, empty = "Nothing yet.", rowKey, rowProps, max }) {
  if (!rows?.length) return <div className="empty">{empty}</div>;
  const list = max ? rows.slice(0, max) : rows;
  return (
    <div className="tbl-wrap">
      <table>
        <thead>
          <tr>{cols.map((c) => <th key={c.key} className={c.n ? "n" : ""}>{c.label}</th>)}</tr>
        </thead>
        <tbody>
          {list.map((r, i) => (
            <tr key={rowKey ? rowKey(r) : r.id ?? i} {...(rowProps ? rowProps(r) : {})}>
              {cols.map((c) => (
                <td key={c.key} className={[c.n && "n", c.wrap && "wrap", c.sym && "sym"].filter(Boolean).join(" ")}>
                  {c.render ? c.render(r) : c.sym ? <SymLink s={r[c.key]} /> : r[c.key] ?? "—"}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function SymLink({ s }) {
  return s ? <Link href={`/symbol/${encodeURIComponent(s)}`}>{s}</Link> : "—";
}

export function Rating({ r }) {
  return <span className={`chip ${RATING_TONE[r] || ""}`}>{r || "—"}</span>;
}

export function Book({ b }) {
  return <span className={`book ${b}`}>{BOOKS[b] || b}</span>;
}

export function Side({ s }) {
  return <span className={`side ${s}`}>{s}</span>;
}

export function Conf({ v }) {
  if (v == null) return "—";
  return (
    <span className="conf">
      {Math.round(v)}%<span className="confbar" aria-hidden="true"><i style={{ width: `${Math.min(100, v)}%` }} /></span>
    </span>
  );
}

/** Signed % with a centred data bar scaled to `scale` (the largest |value| in the table). */
export function PnlPct({ v, scale = 2 }) {
  if (v == null) return "—";
  const w = Math.min(50, (Math.abs(v) / (scale || 1)) * 50);
  const t = fmt.tone(v);
  return (
    <span className="num">
      <span className={t}>{fmt.pct(v)}</span>
      <span className="pbar" aria-hidden="true">{t ? <i className={t} style={{ width: `${w}%` }} /> : null}</span>
    </span>
  );
}

export function Signed({ v, sym = "", d = 2 }) {
  if (v == null) return "—";
  const t = fmt.tone(v);
  return <span className={t}>{t === "up" ? "+" : ""}{fmt.money(t ? v : 0, sym, d)}</span>;
}
