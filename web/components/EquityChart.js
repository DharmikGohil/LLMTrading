import { fmt } from "@/lib/data";

/** Return since the first snapshot for both accounts and the index, on one % scale. */
export default function EquityChart({ rows, indexName }) {
  const series = {};
  for (const r of rows) {
    const t = new Date(r.time).getTime();
    if (Number.isNaN(t)) continue;
    (series[r.book] ??= []).push({ t, v: Number(r.equity), idx: r.index_close == null ? null : Number(r.index_close) });
  }
  const main = (series.main ?? []).sort((a, b) => a.t - b.t);
  const ctrl = (series.factor ?? []).sort((a, b) => a.t - b.t);
  if (main.length < 2) {
    return <p className="note">The chart starts after the second snapshot of this desk.</p>;
  }
  const rel = (pts, key) => {
    const base = pts.find((p) => p[key] != null)?.[key];
    return pts.filter((p) => p[key] != null).map((p) => ({ t: p.t, y: 100 * (p[key] / base - 1) }));
  };
  const lines = [
    { key: "main", label: "LLM-reviewed", pts: rel(main, "v"), color: "var(--signal)", w: 2.25 },
    { key: "factor", label: "LLM off", pts: rel(ctrl, "v"), color: "var(--control)", w: 1.5 },
    { key: "index", label: indexName, pts: rel(main, "idx"), color: "var(--ink)", w: 1, dash: "3 3" },
  ].filter((l) => l.pts.length > 1);

  const W = 760, H = 240, L = 48, R = 132, T = 12, B = 26;
  const all = lines.flatMap((l) => l.pts);
  const t0 = Math.min(...all.map((p) => p.t)), t1 = Math.max(...all.map((p) => p.t));
  let y0 = Math.min(0, ...all.map((p) => p.y)), y1 = Math.max(0, ...all.map((p) => p.y));
  const pad = Math.max(0.05, (y1 - y0) * 0.12);
  y0 -= pad; y1 += pad;
  const x = (t) => L + ((t - t0) / Math.max(1, t1 - t0)) * (W - L - R);
  const y = (v) => T + (1 - (v - y0) / (y1 - y0)) * (H - T - B);
  const step = niceStep((y1 - y0) / 4);
  const ticks = [];
  for (let v = Math.ceil(y0 / step) * step; v <= y1 + 1e-9; v += step) ticks.push(Number(v.toFixed(6)));
  const dayTicks = [...new Set(all.map((p) => new Date(p.t).toISOString().slice(0, 10)))];

  // end labels, pushed apart so they never overlap
  const ends = lines.map((l) => ({ ...l, last: l.pts[l.pts.length - 1], ly: y(l.pts[l.pts.length - 1].y) })).sort((a, b) => a.ly - b.ly);
  for (let i = 1; i < ends.length; i++) if (ends[i].ly - ends[i - 1].ly < 14) ends[i].ly = ends[i - 1].ly + 14;

  return (
    <svg className="chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Return since start: both accounts and the ${indexName}`}>
      {ticks.map((v) => (
        <g key={v}>
          <line x1={L} x2={W - R} y1={y(v)} y2={y(v)} stroke={v === 0 ? "var(--line-strong)" : "var(--line)"} />
          <text x={L - 8} y={y(v)} dy="0.32em" textAnchor="end">{`${v > 0 ? "+" : ""}${v.toFixed(step < 0.1 ? 2 : 1)}%`}</text>
        </g>
      ))}
      {dayTicks.slice(0, 8).map((d) => {
        const t = new Date(`${d}T00:00:00Z`).getTime();
        if (t < t0 || t > t1) return null;
        return <text key={d} x={x(t)} y={H - 6} textAnchor="middle">{fmt.day(d).split(",")[0]}</text>;
      })}
      {lines.map((l) => (
        <g key={l.key}>
          <polyline fill="none" stroke={l.color} strokeWidth={l.w} strokeLinejoin="round" strokeLinecap="round" strokeDasharray={l.dash}
            points={l.pts.map((p) => `${x(p.t).toFixed(1)},${y(p.y).toFixed(1)}`).join(" ")} />
          {l.pts.map((p) => (
            <circle key={p.t} cx={x(p.t)} cy={y(p.y)} r="5" fill="transparent">
              <title>{`${l.label}: ${fmt.pct(p.y, 3)} at ${fmt.time(p.t)}`}</title>
            </circle>
          ))}
        </g>
      ))}
      {ends.map((l) => (
        <text key={l.key} x={W - R + 8} y={l.ly} dy="0.32em" style={{ fill: l.key === "main" ? "var(--signal)" : "var(--muted)" }}>
          {`${l.label} ${fmt.pct(l.last.y)}`}
        </text>
      ))}
    </svg>
  );
}

function niceStep(raw) {
  const p = 10 ** Math.floor(Math.log10(raw || 1));
  const m = raw / p;
  return (m <= 1 ? 1 : m <= 2 ? 2 : m <= 5 ? 5 : 10) * p;
}
