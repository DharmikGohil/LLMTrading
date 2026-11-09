import { fmt } from "@/lib/fmt";

/** P&L at expiry of an options structure across Nifty levels (server-rendered SVG). */
export default function Payoff({ legs, spot, charges = 0, width = 560, height = 200 }) {
  if (!legs?.length || !spot) return null;
  const pnlAt = (s) => legs.reduce((a, l) => {
    const v = l.kind === "CE" ? Math.max(s - l.strike, 0) : Math.max(l.strike - s, 0);
    return a + (l.side === "SELL" ? l.entry - v : v - l.entry) * l.qty;
  }, -charges);
  const strikes = legs.map((l) => l.strike);
  const lo = Math.min(...strikes, spot) * 0.985, hi = Math.max(...strikes, spot) * 1.015;
  const N = 160;
  const pts = Array.from({ length: N + 1 }, (_, i) => { const s = lo + ((hi - lo) * i) / N; return [s, pnlAt(s)]; });
  const ys = pts.map((p) => p[1]);
  const ymax = Math.max(...ys, 0), ymin = Math.min(...ys, 0);
  const m = { l: 72, r: 12, t: 12, b: 26 };
  const pw = width - m.l - m.r, ph = height - m.t - m.b;
  const x = (s) => m.l + ((s - lo) / (hi - lo)) * pw;
  const y = (v) => m.t + ((ymax - v) / (ymax - ymin || 1)) * ph;
  const line = pts.map(([s, v], i) => `${i ? "L" : "M"}${x(s).toFixed(1)},${y(v).toFixed(1)}`).join("");
  const area = (sign) => {
    const clip = pts.map(([s, v]) => [s, sign > 0 ? Math.max(v, 0) : Math.min(v, 0)]);
    return `M${x(lo)},${y(0)}` + clip.map(([s, v]) => `L${x(s).toFixed(1)},${y(v).toFixed(1)}`).join("") + `L${x(hi)},${y(0)}Z`;
  };
  const breakevens = [];
  for (let i = 1; i < pts.length; i++) if ((pts[i - 1][1] < 0) !== (pts[i][1] < 0)) breakevens.push(pts[i][0]);
  return (
    <div className="chart payoff">
      <svg width="100%" viewBox={`0 0 ${width} ${height}`} role="img"
        aria-label={`Profit or loss at expiry. Best case ${fmt.money(ymax, "₹", 0)}, worst case ${fmt.money(ymin, "₹", 0)}; breakevens ${breakevens.map((b) => b.toFixed(0)).join(" and ")}.`}>
        <path d={area(1)} fill="var(--up)" opacity="0.12" />
        <path d={area(-1)} fill="var(--down)" opacity="0.12" />
        <line className="zero" x1={m.l} x2={m.l + pw} y1={y(0)} y2={y(0)} />
        <path d={line} fill="none" stroke="var(--ink-2)" strokeWidth="2" strokeLinejoin="round" />
        <text x={m.l - 6} y={y(ymax) + 4} textAnchor="end">{fmt.money(ymax, "₹", 0)}</text>
        <text x={m.l - 6} y={y(ymin) + 4} textAnchor="end">{fmt.money(ymin, "₹", 0)}</text>
        <line x1={x(spot)} x2={x(spot)} y1={m.t} y2={m.t + ph} stroke="var(--accent)" strokeDasharray="3 3" />
        <text className="lbl" x={x(spot)} y={height - 8} textAnchor="middle">Nifty {spot.toFixed(0)}</text>
        {breakevens.map((b) => (
          <g key={b}>
            <circle cx={x(b)} cy={y(0)} r="3.5" fill="var(--ink-2)" stroke="var(--panel)" strokeWidth="2" />
            <text x={x(b)} y={y(0) - 8} textAnchor="middle">{b.toFixed(0)}</text>
          </g>
        ))}
      </svg>
    </div>
  );
}
