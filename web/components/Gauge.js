/** A semicircle gauge (0-100%), as in the reference's "execution speed" card. */
export default function Gauge({ value, label, sub }) {
  const v = Math.max(0, Math.min(100, value ?? 0));
  const r = 80, cx = 100, cy = 96;
  const a = Math.PI * (1 - v / 100);
  const x = cx + r * Math.cos(a), y = cy - r * Math.sin(a);
  const arc = `M${cx - r},${cy} A${r},${r} 0 0 1 ${x.toFixed(2)},${y.toFixed(2)}`;
  return (
    <div className="gauge">
      <svg viewBox="0 0 200 108" role="img" aria-label={`${label}: ${v.toFixed(0)}%`}>
        <path d={`M${cx - r},${cy} A${r},${r} 0 0 1 ${cx + r},${cy}`} className="gauge-track" />
        {v > 0 ? <path d={arc} className="gauge-fill" /> : null}
        <circle cx={x} cy={y} r="7" className="gauge-knob" />
      </svg>
      <div className="gauge-v">
        <b>{v.toFixed(0)}%</b>
        <span>{label}</span>
      </div>
      {sub ? <p className="gauge-sub">{sub}</p> : null}
    </div>
  );
}
