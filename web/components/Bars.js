/**
 * Daily bars with the latest bar highlighted and labelled, as in a broker "profit" card.
 * items: [{ label, v }] in time order; v is a % change (may be negative or null).
 */
export default function Bars({ items, h = 120, unit = "%", digits = 2 }) {
  const rows = (items || []).filter((x) => x && x.v != null);
  if (!rows.length) return <div className="bars-empty">No sessions yet.</div>;
  const max = Math.max(0.01, ...rows.map((r) => Math.abs(r.v)));
  const hasNeg = rows.some((r) => r.v < 0);
  const zero = hasNeg ? h / 2 : h - 2;
  const scale = (hasNeg ? h / 2 - 6 : h - 8) / max;
  const n = rows.length;
  const w = 100 / n;
  const last = rows[n - 1];
  const lastX = (n - 0.5) * w;
  const fmtV = (v) => `${v > 0 ? "+" : ""}${v.toFixed(digits)}${unit}`;
  return (
    <div className="bars">
      <div className="bars-tip" style={{ left: `${Math.min(88, Math.max(12, lastX))}%` }}>
        <b className={last.v >= 0 ? "up" : "down"}>{fmtV(last.v)}</b>
        <span>{last.label}</span>
      </div>
      <svg viewBox={`0 0 100 ${h}`} preserveAspectRatio="none" role="img" aria-label={`Daily change, latest ${fmtV(last.v)} on ${last.label}`}>
        <line x1="0" x2="100" y1={zero} y2={zero} className="bars-zero" vectorEffect="non-scaling-stroke" />
        {rows.map((r, i) => {
          const bh = Math.max(1.5, Math.abs(r.v) * scale);
          const y = r.v >= 0 ? zero - bh : zero;
          const on = i === n - 1;
          return (
            <rect key={i} x={i * w + w * 0.18} width={w * 0.64} y={y} height={bh} rx="1.2"
              className={`bar ${on ? "on" : r.v >= 0 ? "pos" : "neg"}`}>
              <title>{`${r.label}: ${fmtV(r.v)}`}</title>
            </rect>
          );
        })}
      </svg>
      <div className="bars-x">
        <span>{rows[0].label}</span>
        <span>{last.label}</span>
      </div>
    </div>
  );
}
