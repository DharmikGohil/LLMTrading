"use client";
import { useEffect, useMemo, useRef, useState } from "react";

const COLOR = { main: "var(--s-main)", factor: "var(--s-factor)", index: "var(--s-index)" };
const RANGES = [["1D", 1], ["5D", 5], ["1M", 31], ["All", Infinity]];
const STEPS = [0.01, 0.02, 0.05, 0.1, 0.2, 0.25, 0.5, 1, 2, 2.5, 5, 10, 20, 25, 50, 100];

const pct = (v) => {
  if (v == null) return "—";
  const x = Math.abs(v) < 0.005 ? 0 : v;
  return `${x > 0 ? "+" : x < 0 ? "−" : ""}${Math.abs(x).toFixed(2)}%`;
};
const money = (v, sym) => `${sym}${Number(v).toLocaleString("en-IN", { maximumFractionDigits: 2, minimumFractionDigits: 2 })}`;

function niceTicks(lo, hi) {
  const span = Math.max(hi - lo, 0.02);
  const step = STEPS.find((s) => span / s <= 5) || 100;
  const a = Math.floor(lo / step) * step;
  const b = Math.ceil(hi / step) * step;
  const out = [];
  for (let v = a; v <= b + step / 2; v += step) out.push(Number(v.toFixed(4)));
  return out;
}

/** Equity of both books and the index, as % since start. Ordinal x (one slot per observation) so nights and weekends don't stretch the line. */
export default function EquityChart({ data, height = 260, compact = false, ranges = true }) {
  const wrap = useRef(null);
  const [w, setW] = useState(720);
  const [range, setRange] = useState("All");
  const [hi, setHi] = useState(null);

  useEffect(() => {
    if (!wrap.current) return;
    const ro = new ResizeObserver(([e]) => setW(Math.max(280, Math.round(e.contentRect.width))));
    ro.observe(wrap.current);
    return () => ro.disconnect();
  }, []);

  const view = useMemo(() => {
    const { times } = data;
    if (!times.length) return null;
    const days = RANGES.find((r) => r[0] === range)[1];
    const last = times[times.length - 1];
    let from = times.findIndex((t) => t >= last - days * 86400000);
    if (from < 0 || times.length - from < 2) from = 0;
    const idx = times.map((_, i) => i).filter((i) => i >= from);
    return { idx, times: idx.map((i) => times[i]), series: data.series.map((s) => ({ ...s, values: idx.map((i) => s.values[i]) })) };
  }, [data, range]);

  if (!view) return <div className="empty">The equity curve starts after the first run.</div>;

  const narrow = w < 520;
  const m = { l: 46, r: narrow ? 8 : compact ? 112 : 128, t: 10, b: 24 };
  const pw = w - m.l - m.r;
  const ph = height - m.t - m.b;
  const n = view.times.length;
  const x = (i) => m.l + (n === 1 ? pw / 2 : (i * pw) / (n - 1));
  const all = view.series.flatMap((s) => s.values.filter(Boolean).map((p) => p.r));
  const ticks = niceTicks(Math.min(0, ...all), Math.max(0, ...all));
  const y0 = ticks[0], y1 = ticks[ticks.length - 1];
  const y = (v) => m.t + ph - ((v - y0) / (y1 - y0 || 1)) * ph;

  const dayFmt = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", timeZone: data.tz });
  const keyFmt = new Intl.DateTimeFormat("en-CA", { timeZone: data.tz });
  const xt = [];
  let lastX = -1e9;
  view.times.forEach((t, i) => {
    if (i > 0 && keyFmt.format(t) === keyFmt.format(view.times[i - 1])) return;
    if (x(i) - lastX < 56) return;
    xt.push([i, dayFmt.format(t)]);
    lastX = x(i);
  });

  const paths = view.series.map((s) => {
    let d = "", pen = false;
    s.values.forEach((p, i) => {
      if (!p) { pen = false; return; }
      d += `${pen ? "L" : "M"}${x(i).toFixed(1)},${y(p.r).toFixed(1)}`;
      pen = true;
    });
    const lastI = s.values.map((p, i) => (p ? i : -1)).filter((i) => i >= 0).at(-1);
    return { ...s, d, lastI, last: lastI != null ? s.values[lastI] : null };
  });

  // end labels: keep them on their line; if two collide, spread and draw a leader line
  const labels = paths.filter((p) => p.last).map((p) => ({ key: p.key, text: `${p.key === "index" ? p.label : p.label} ${pct(p.last.r)}`, ly: y(p.last.r), y: y(p.last.r), x: x(p.lastI) }));
  labels.sort((a, b) => a.y - b.y);
  for (let k = 0; k < 4; k++) {
    for (let i = 1; i < labels.length; i++) if (labels[i].ly - labels[i - 1].ly < 14) labels[i].ly = labels[i - 1].ly + 14;
    const over = labels.length ? labels[labels.length - 1].ly - (m.t + ph) : 0;
    if (over > 0) labels.forEach((l) => (l.ly -= over));
  }

  const move = (clientX) => {
    const r = wrap.current.getBoundingClientRect();
    const px = clientX - r.left;
    const i = n === 1 ? 0 : Math.round(((px - m.l) / pw) * (n - 1));
    setHi(Math.max(0, Math.min(n - 1, i)));
  };
  const key = (e) => {
    if (e.key === "ArrowLeft") { setHi((h) => Math.max(0, (h ?? n) - 1)); e.preventDefault(); }
    if (e.key === "ArrowRight") { setHi((h) => Math.min(n - 1, (h ?? -1) + 1)); e.preventDefault(); }
    if (e.key === "Escape") setHi(null);
  };

  const tipLeft = hi != null ? (x(hi) > w / 2 ? x(hi) - 206 : x(hi) + 12) : 0;
  const timeFmt = new Intl.DateTimeFormat("en-GB", { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", hour12: false, timeZone: data.tz });
  const latest = paths.map((p) => `${p.label} ${p.last ? pct(p.last.r) : "—"}`).join(", ");

  return (
    <div>
      <div className="chart-top">
        <div className="chart-legend" aria-hidden="true">
          {view.series.map((s) => (
            <span key={s.key}><i className={s.key === "index" ? "dash" : ""} style={{ background: COLOR[s.key] }} />{s.label}</span>
          ))}
        </div>
        {ranges ? (
          <div className="seg" role="group" aria-label="Range">
            {RANGES.map(([r]) => (
              <button key={r} type="button" aria-pressed={range === r} onClick={() => { setRange(r); setHi(null); }}>{r}</button>
            ))}
          </div>
        ) : null}
      </div>
      <div className="chart" ref={wrap}>
        <svg
          width={w} height={height} viewBox={`0 0 ${w} ${height}`} tabIndex={0} role="img"
          aria-label={`Return since start. Latest: ${latest}. Use arrow keys to step through points.`}
          onPointerMove={(e) => move(e.clientX)} onPointerLeave={() => setHi(null)} onKeyDown={key} onBlur={() => setHi(null)}
          style={{ touchAction: "pan-y" }}
        >
          {ticks.map((t) => (
            <g key={t}>
              <line className={t === 0 ? "zero" : "gl"} x1={m.l} x2={m.l + pw} y1={y(t)} y2={y(t)} />
              <text x={m.l - 8} y={y(t) + 3.5} textAnchor="end">{t > 0 ? "+" : ""}{t}%</text>
            </g>
          ))}
          {xt.map(([i, l]) => <text key={i} x={x(i)} y={height - 6} textAnchor={i === 0 ? "start" : "middle"}>{l}</text>)}
          {paths.map((p) => (
            <path key={p.key} d={p.d} fill="none" stroke={COLOR[p.key]} strokeWidth={p.key === "main" ? 2.25 : 2}
              strokeDasharray={p.key === "index" ? "5 4" : undefined} strokeLinejoin="round" strokeLinecap="round" />
          ))}
          {paths.filter((p) => p.last).map((p) => (
            <circle key={p.key} cx={x(p.lastI)} cy={y(p.last.r)} r={3.5} fill={COLOR[p.key]} stroke="var(--panel)" strokeWidth={2} />
          ))}
          {!narrow && labels.map((l) => (
            <g key={l.key}>
              {Math.abs(l.ly - l.y) > 1 ? <line x1={l.x + 5} y1={l.y} x2={l.x + 12} y2={l.ly} stroke="var(--line-2)" /> : null}
              <text className="lbl" x={l.x + 14} y={l.ly + 3.5}>{l.text}</text>
            </g>
          ))}
          {hi != null ? (
            <g>
              <line className="xh" x1={x(hi)} x2={x(hi)} y1={m.t} y2={m.t + ph} />
              {view.series.map((s) => s.values[hi] ? (
                <circle key={s.key} cx={x(hi)} cy={y(s.values[hi].r)} r={4.5} fill={COLOR[s.key]} stroke="var(--panel)" strokeWidth={2} />
              ) : null)}
            </g>
          ) : null}
        </svg>
        {hi != null ? (
          <div className="tip" style={{ left: Math.max(0, tipLeft), top: 8 }} role="status">
            <div className="t">{timeFmt.format(view.times[hi])} {data.tzLabel}</div>
            {view.series.map((s) => {
              const p = s.values[hi];
              return (
                <div className="row" key={s.key}>
                  <i style={{ background: COLOR[s.key] }} />
                  <span>{s.label}</span>
                  <b className={p ? (p.r > 0 ? "up" : p.r < 0 ? "down" : "") : ""}>{p ? pct(p.r) : "—"}</b>
                  <span>{p ? (s.key === "index" ? Number(p.v).toFixed(2) : money(p.v, data.symbol)) : ""}</span>
                </div>
              );
            })}
          </div>
        ) : null}
      </div>
    </div>
  );
}
