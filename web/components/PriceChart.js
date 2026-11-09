"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import { bollinger, candles, ema, levels, macd, rsi, sma } from "@/lib/ta";
import { fmt } from "@/lib/fmt";

const RANGES = [["3M", 63], ["6M", 126], ["1Y", 252], ["2Y", 9999]];
const OVERLAYS = [
  ["ema20", "EMA 20", "var(--ink)"],
  ["ema50", "EMA 50", "var(--accent)"],
  ["sma200", "SMA 200", "var(--ink-2)"],
  ["bb", "Bollinger 20,2", "var(--muted)"],
  ["sr", "Support / resistance", "var(--ink-2)"],
];
const PANES = [["vol", "Volume"], ["rsi", "RSI 14"], ["macd", "MACD 12,26,9"]];

function useWidth(ref) {
  const [w, setW] = useState(760);
  useEffect(() => {
    if (!ref.current) return;
    const ro = new ResizeObserver(([e]) => setW(Math.max(300, Math.round(e.contentRect.width))));
    ro.observe(ref.current);
    return () => ro.disconnect();
  }, [ref]);
  return w;
}

const nice = (lo, hi, n = 5) => {
  const span = hi - lo || 1;
  const step0 = span / n;
  const mag = 10 ** Math.floor(Math.log10(step0));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => span / s <= n) || 10 * mag;
  const out = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push(Number(v.toFixed(8)));
  return out;
};

/** Candlestick chart with indicators, levels and a crosshair, plus a plain-English chart read. */
export default function PriceChart({ market, sym, avg, stop, cur = "" }) {
  const wrap = useRef(null);
  const w = useWidth(wrap);
  const [bars, setBars] = useState(null);
  const [err, setErr] = useState(null);
  const [range, setRange] = useState("6M");
  const [on, setOn] = useState({ ema20: true, ema50: true, sma200: true, bb: false, sr: true, vol: true, rsi: true, macd: true });
  const [hi, setHi] = useState(null);

  useEffect(() => {
    let dead = false;
    setBars(null); setErr(null);
    fetch(`/api/ohlc?s=${encodeURIComponent(`${market}:${sym}`)}&range=2y`)
      .then((r) => r.json())
      .then((j) => { if (!dead) (j.bars?.length ? setBars(j.bars) : setErr(j.error || "no data")); })
      .catch((e) => { if (!dead) setErr(String(e)); });
    return () => { dead = true; };
  }, [market, sym]);

  const ind = useMemo(() => {
    if (!bars) return null;
    const c = bars.map((b) => b.c);
    return { ema20: ema(c, 20), ema50: ema(c, 50), sma200: sma(c, 200), bb: bollinger(c), rsi: rsi(c), macd: macd(c),
      vol50: sma(bars.map((b) => b.v), 50), lv: levels(bars), pat: candles(bars) };
  }, [bars]);

  if (err) return <div className="empty">Chart unavailable ({err}).</div>;
  if (!bars || !ind) return <div className="empty" ref={wrap}>Loading chart…</div>;

  const n = Math.min(RANGES.find((r) => r[0] === range)[1], bars.length);
  const from = bars.length - n;
  const view = bars.slice(from);
  const sl = (arr) => arr.slice(from);

  const narrow = w < 560;
  const m = { l: 8, r: narrow ? 50 : 62, t: 8 };
  const pw = w - m.l - m.r;
  const priceH = narrow ? 240 : 320, paneH = narrow ? 58 : 72, gap = 10;
  const panes = PANES.filter(([k]) => on[k]);
  const H = m.t + priceH + panes.length * (paneH + gap) + 22;
  const step = pw / view.length;
  const x = (i) => m.l + (i + 0.5) * step;
  const bw = Math.max(1, Math.min(9, step * 0.68));

  // price scale: candles plus visible overlays and levels
  const vals = [...view.flatMap((b) => [b.h, b.l])];
  if (on.bb) vals.push(...sl(ind.bb.upper).filter(Boolean), ...sl(ind.bb.lower).filter(Boolean));
  const srShow = on.sr ? [...ind.lv.support, ...ind.lv.resistance].filter((l) => {
    const lo = Math.min(...view.map((b) => b.l)), hiP = Math.max(...view.map((b) => b.h));
    return l.price >= lo - (hiP - lo) * 0.25 && l.price <= hiP + (hiP - lo) * 0.25;
  }) : [];
  vals.push(...srShow.map((l) => l.price));
  if (avg) vals.push(avg);
  if (stop) vals.push(stop);
  const pLo = Math.min(...vals), pHi = Math.max(...vals);
  const pad = (pHi - pLo) * 0.04;
  const y = (v) => m.t + priceH - ((v - (pLo - pad)) / (pHi - pLo + 2 * pad)) * priceH;
  const yt = nice(pLo, pHi, 6);

  const line = (arr) => {
    let d = "", pen = false;
    sl(arr).forEach((v, i) => {
      if (v == null) { pen = false; return; }
      d += `${pen ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`;
      pen = true;
    });
    return d;
  };

  // panes
  let top = m.t + priceH + gap;
  const paneBox = {};
  for (const [k] of panes) { paneBox[k] = top; top += paneH + gap; }
  const vmax = Math.max(...view.map((b) => b.v)) || 1;
  const macdV = sl(ind.macd.line).concat(sl(ind.macd.signal), sl(ind.macd.hist)).filter((v) => v != null);
  const mAbs = Math.max(...macdV.map(Math.abs), 1e-9);
  const yM = (v) => paneBox.macd + paneH / 2 - (v / mAbs) * (paneH / 2 - 3);
  const yR = (v) => paneBox.rsi + paneH - (v / 100) * paneH;
  const paneLine = (arr, yf) => {
    let d = "", pen = false;
    sl(arr).forEach((v, i) => {
      if (v == null) { pen = false; return; }
      d += `${pen ? "L" : "M"}${x(i).toFixed(1)},${yf(v).toFixed(1)}`;
      pen = true;
    });
    return d;
  };

  // x ticks: month starts
  const mfmt = new Intl.DateTimeFormat("en-GB", { month: "short", year: n > 300 ? "2-digit" : undefined });
  const xt = [];
  let lastX = -1e9;
  view.forEach((b, i) => {
    const d = new Date(b.t), p = i ? new Date(view[i - 1].t) : null;
    if (p && d.getMonth() === p.getMonth()) return;
    if (x(i) - lastX < 48) return;
    xt.push([i, mfmt.format(d)]);
    lastX = x(i);
  });

  const move = (clientX) => {
    const r = wrap.current.getBoundingClientRect();
    const i = Math.floor((clientX - r.left - m.l) / step);
    setHi(i >= 0 && i < view.length ? i : null);
  };

  const hb = hi != null ? view[hi] : view.at(-1);
  const hiAbs = hi != null ? from + hi : bars.length - 1;
  const prevC = hiAbs > 0 ? bars[hiAbs - 1].c : hb.o;
  const chg = (hb.c / prevC - 1) * 100;

  // chart read (always on the latest bar)
  const L = bars.length - 1, last = bars[L].c;
  const read = [];
  const e50 = ind.ema50[L], s200 = ind.sma200[L];
  if (s200) read.push(last > s200 ? (last > e50 ? "Uptrend: above both the 50-day EMA and the 200-day SMA." : "Above the 200-day SMA but below the 50-day EMA: pullback in an uptrend.") : (last < e50 ? "Downtrend: below both the 50-day EMA and the 200-day SMA." : "Below the 200-day SMA but above the 50-day EMA: a bounce in a downtrend."));
  const r14 = ind.rsi[L];
  if (r14 != null) read.push(`RSI ${r14.toFixed(0)}: ${r14 >= 80 ? "very overbought (blow-off risk)" : r14 >= 70 ? "overbought (strong, but stretched)" : r14 <= 30 ? "oversold" : r14 >= 50 ? "bullish momentum" : "weak momentum"}.`);
  const mh = ind.macd.hist[L], mh1 = ind.macd.hist[L - 1];
  if (mh != null && mh1 != null) read.push(`MACD ${ind.macd.line[L] > ind.macd.signal[L] ? "above" : "below"} its signal line, ${ind.macd.line[L] > 0 ? "above" : "below"} zero; histogram ${mh > mh1 ? "rising" : "falling"}${Math.sign(mh) !== Math.sign(mh1) ? " (crossed today)" : ""}.`);
  const up = ind.bb.upper[L], lo = ind.bb.lower[L];
  if (up != null) {
    const pb = (last - lo) / (up - lo);
    const bwNow = (up - lo) / ind.bb.mid[L];
    const bwMin = Math.min(...ind.bb.upper.slice(-126).map((u, i) => { const j = bars.length - 126 + i; return u == null ? Infinity : (u - ind.bb.lower[j]) / ind.bb.mid[j]; }));
    read.push(`Bollinger %B ${pb.toFixed(2)}${pb > 1 ? " (closed above the upper band)" : pb < 0 ? " (closed below the lower band)" : ""}${bwNow <= bwMin * 1.05 ? "; bands at a 6-month squeeze: a big move often follows, direction unknown" : ""}.`);
  }
  const ns = [...ind.lv.support].sort((a, b) => b.price - a.price)[0], nr = [...ind.lv.resistance].sort((a, b) => a.price - b.price)[0];
  if (ns) read.push(`Nearest support ${fmt.num(ns.price)} (${ns.touches} touches, ${((ns.price / last - 1) * 100).toFixed(1)}%).`);
  if (nr) read.push(`Nearest resistance ${fmt.num(nr.price)} (${nr.touches} touches, +${((nr.price / last - 1) * 100).toFixed(1)}%).`);
  if (ind.pat.length) read.push(`Last candle: ${ind.pat.join(", ")}.`);
  const v50 = ind.vol50[L];
  if (v50) read.push(`Volume ${(bars[L].v / v50).toFixed(1)}× its 50-day average.`);

  return (
    <div>
      <div className="chart-top pc-top">
        <div className="seg" role="group" aria-label="Range">
          {RANGES.map(([r]) => <button key={r} type="button" aria-pressed={range === r} onClick={() => { setRange(r); setHi(null); }}>{r}</button>)}
        </div>
        <div className="pc-toggles" role="group" aria-label="Indicators">
          {[...OVERLAYS, ...PANES.map(([k, l]) => [k, l, null])].map(([k, label, color]) => (
            <label key={k} className={on[k] ? "on" : ""}>
              <input type="checkbox" checked={on[k]} onChange={() => setOn((o) => ({ ...o, [k]: !o[k] }))} />
              {color ? <i style={{ background: color }} /> : null}{label}
            </label>
          ))}
        </div>
      </div>
      <div className="pc-legend mono">
        <span>{new Date(hb.t).toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" })}</span>
        <span>O {fmt.num(hb.o)}</span><span>H {fmt.num(hb.h)}</span><span>L {fmt.num(hb.l)}</span>
        <span>C <b className={fmt.tone(chg)}>{fmt.num(hb.c)} ({fmt.pct(chg)})</b></span>
        {on.ema20 && ind.ema20[hiAbs] ? <span style={{ color: "var(--ink)" }}>EMA20 {fmt.num(ind.ema20[hiAbs])}</span> : null}
        {on.ema50 && ind.ema50[hiAbs] ? <span style={{ color: "var(--accent)" }}>EMA50 {fmt.num(ind.ema50[hiAbs])}</span> : null}
        {on.sma200 && ind.sma200[hiAbs] ? <span>SMA200 {fmt.num(ind.sma200[hiAbs])}</span> : null}
        {on.rsi && ind.rsi[hiAbs] != null ? <span>RSI {ind.rsi[hiAbs].toFixed(1)}</span> : null}
        {on.macd && ind.macd.hist[hiAbs] != null ? <span>MACD {ind.macd.line[hiAbs].toFixed(2)} / {ind.macd.signal[hiAbs].toFixed(2)}</span> : null}
      </div>
      <div className="chart pc" ref={wrap}>
        <svg width={w} height={H} viewBox={`0 0 ${w} ${H}`} role="img" aria-label={`${sym} daily candlestick chart, ${range}`}
          onPointerMove={(e) => move(e.clientX)} onPointerLeave={() => setHi(null)} style={{ touchAction: "pan-y" }}>
          {yt.map((t) => (
            <g key={t}>
              <line className="gl" x1={m.l} x2={m.l + pw} y1={y(t)} y2={y(t)} />
              <text x={m.l + pw + 6} y={y(t) + 3.5}>{fmt.num(t, t >= 1000 ? 0 : 2)}</text>
            </g>
          ))}
          {xt.map(([i, l]) => <text key={i} x={x(i)} y={H - 6} textAnchor="middle">{l}</text>)}

          {on.bb ? (
            <g>
              <path d={line(ind.bb.upper)} fill="none" stroke="var(--muted)" strokeWidth="1" strokeDasharray="3 3" />
              <path d={line(ind.bb.lower)} fill="none" stroke="var(--muted)" strokeWidth="1" strokeDasharray="3 3" />
              <path d={line(ind.bb.mid)} fill="none" stroke="var(--muted)" strokeWidth="0.8" opacity="0.6" />
            </g>
          ) : null}
          {srShow.map((l) => {
            const isRes = l.price >= last;
            return (
              <g key={`${l.price}`}>
                <line x1={m.l} x2={m.l + pw} y1={y(l.price)} y2={y(l.price)} stroke={isRes ? "var(--down)" : "var(--up)"} strokeWidth={Math.min(2.5, 0.6 + l.touches * 0.25)} strokeDasharray="6 4" opacity="0.7" />
              </g>
            );
          })}
          {avg ? <line x1={m.l} x2={m.l + pw} y1={y(avg)} y2={y(avg)} stroke="var(--ink)" strokeWidth="1" /> : null}
          {stop ? <line x1={m.l} x2={m.l + pw} y1={y(stop)} y2={y(stop)} stroke="var(--down)" strokeWidth="1.2" /> : null}

          {view.map((b, i) => {
            const upC = b.c >= b.o, col = upC ? "var(--up)" : "var(--down)";
            const y1 = y(Math.max(b.o, b.c)), y2 = y(Math.min(b.o, b.c));
            return (
              <g key={b.t}>
                <line x1={x(i)} x2={x(i)} y1={y(b.h)} y2={y(b.l)} stroke={col} strokeWidth="1" />
                <rect x={x(i) - bw / 2} y={y1} width={bw} height={Math.max(1, y2 - y1)} fill={upC ? "var(--panel)" : col} stroke={col} strokeWidth="1" />
              </g>
            );
          })}
          {on.ema20 ? <path d={line(ind.ema20)} fill="none" stroke="var(--ink)" strokeWidth="1.2" opacity="0.75" /> : null}
          {on.ema50 ? <path d={line(ind.ema50)} fill="none" stroke="var(--accent)" strokeWidth="1.4" /> : null}
          {on.sma200 ? <path d={line(ind.sma200)} fill="none" stroke="var(--ink-2)" strokeWidth="1.4" strokeDasharray="5 3" /> : null}
          <g>
            <line x1={m.l} x2={m.l + pw} y1={y(last)} y2={y(last)} stroke="var(--ink-2)" strokeWidth="0.6" strokeDasharray="1 3" />
            <rect x={m.l + pw + 2} y={y(last) - 8} width={m.r - 4} height={16} rx="2" fill="var(--panel-2)" stroke="var(--line-2)" />
            <text x={m.l + pw + 6} y={y(last) + 3.5} className="lbl">{fmt.num(last, last >= 1000 ? 0 : 2)}</text>
          </g>

          {on.vol ? (
            <g>
              {view.map((b, i) => {
                const h = (b.v / vmax) * (paneH - 4);
                return <rect key={b.t} x={x(i) - bw / 2} y={paneBox.vol + paneH - h} width={bw} height={h} fill={b.c >= b.o ? "var(--up)" : "var(--down)"} opacity="0.7" />;
              })}
              <path d={paneLine(ind.vol50, (v) => paneBox.vol + paneH - (v / vmax) * (paneH - 4))} fill="none" stroke="var(--ink-2)" strokeWidth="1" />
            </g>
          ) : null}
          {on.rsi ? (
            <g>
              <rect x={m.l} y={yR(70)} width={pw} height={yR(30) - yR(70)} fill="var(--flat-soft)" />
              {[30, 50, 70].map((v) => (
                <g key={v}><line className="gl" x1={m.l} x2={m.l + pw} y1={yR(v)} y2={yR(v)} strokeDasharray={v === 50 ? "2 3" : undefined} /><text x={m.l + pw + 6} y={yR(v) + 3.5}>{v}</text></g>
              ))}
              <path d={paneLine(ind.rsi, yR)} fill="none" stroke="var(--accent)" strokeWidth="1.3" />
            </g>
          ) : null}
          {on.macd ? (
            <g>
              <line className="gl" x1={m.l} x2={m.l + pw} y1={yM(0)} y2={yM(0)} />
              {sl(ind.macd.hist).map((v, i) => (v == null ? null : (
                <rect key={i} x={x(i) - bw / 2} y={Math.min(yM(0), yM(v))} width={bw} height={Math.abs(yM(v) - yM(0))} fill={v >= 0 ? "var(--up)" : "var(--down)"} opacity="0.7" />
              )))}
              <path d={paneLine(ind.macd.line, yM)} fill="none" stroke="var(--ink)" strokeWidth="1.2" opacity="0.75" />
              <path d={paneLine(ind.macd.signal, yM)} fill="none" stroke="var(--accent)" strokeWidth="1.1" />
            </g>
          ) : null}

          <g pointerEvents="none">
            {srShow.map((l) => {
              const isRes = l.price >= last;
              return <text key={l.price} x={m.l + 4} y={y(l.price) - 3} className="halo" style={{ fill: isRes ? "var(--down)" : "var(--up)" }}>{isRes ? "R" : "S"} {fmt.num(l.price)} ×{l.touches}</text>;
            })}
            {avg ? <text x={m.l + pw - 4} y={y(avg) - 3} textAnchor="end" className="halo" style={{ fill: "var(--ink)" }}>avg cost {fmt.num(avg)}</text> : null}
            {stop ? <text x={m.l + pw - 4} y={y(stop) + 11} textAnchor="end" className="halo" style={{ fill: "var(--down)" }}>stop {fmt.num(stop)}</text> : null}
            {on.vol ? <text x={m.l + 2} y={paneBox.vol + 9} className="halo">Vol</text> : null}
            {on.rsi ? <text x={m.l + 2} y={paneBox.rsi + 9} className="halo">RSI 14</text> : null}
            {on.macd ? <text x={m.l + 2} y={paneBox.macd + 9} className="halo">MACD</text> : null}
          </g>
          {hi != null ? (
            <g pointerEvents="none">
              <line className="xh" x1={x(hi)} x2={x(hi)} y1={m.t} y2={H - 18} />
              <line className="xh" x1={m.l} x2={m.l + pw} y1={y(view[hi].c)} y2={y(view[hi].c)} />
            </g>
          ) : null}
        </svg>
      </div>
      <div className="pc-read">
        <span className="label">Chart read (latest bar)</span>
        <ul>{read.map((r) => <li key={r}>{r}</li>)}</ul>
        <p className="muted">Reading aids, not signals: trend and momentum have the strongest evidence; RSI, MACD, Bollinger and candlestick rules have not beaten buy-and-hold after costs in most tests. See the <a className="accent" href="https://github.com/DharmikGohil/LLMTrading/blob/main/docs/technical-analysis.md">technical-analysis notes</a>.</p>
      </div>
    </div>
  );
}
