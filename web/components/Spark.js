/** A small, quiet trend line: the account's return path, with the benchmark as a faint dashed line. */
export default function Spark({ values, bench, w = 260, h = 44 }) {
  const pts = (values || []).filter((v) => v != null);
  if (pts.length < 2) return <div className="spark" aria-hidden="true" />;
  const all = [...pts, ...(bench || []).filter((v) => v != null)];
  const lo = Math.min(...all), hi = Math.max(...all);
  const span = hi - lo || 1;
  const path = (arr) => {
    const xs = arr.map((v, i) => [(i / (arr.length - 1)) * w, v]);
    let d = "", pen = false;
    for (const [x, v] of xs) {
      if (v == null) { pen = false; continue; }
      d += `${pen ? "L" : "M"}${x.toFixed(1)},${(h - 3 - ((v - lo) / span) * (h - 6)).toFixed(1)}`;
      pen = true;
    }
    return d;
  };
  const color = "var(--s-main)";
  return (
    <div className="spark" aria-hidden="true">
      <svg viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none">
        {bench ? <path d={path(bench)} fill="none" stroke="var(--s-index)" strokeWidth="1.2" strokeDasharray="3 3" vectorEffect="non-scaling-stroke" /> : null}
        <path d={`${path(values.map((v) => v ?? pts[0]))}L${w},${h}L0,${h}Z`} fill={color} fillOpacity="0.08" stroke="none" />
        <path d={path(values)} fill="none" stroke={color} strokeWidth="2" vectorEffect="non-scaling-stroke" strokeLinejoin="round" strokeLinecap="round" />
      </svg>
    </div>
  );
}
