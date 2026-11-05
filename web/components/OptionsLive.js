"use client";
import { useQuote } from "@/components/Live";
import { fmt } from "@/lib/fmt";

const NIFTY = ["India", "^NSEI"];

/** Live Nifty 50 (Yahoo, about 15 s), falling back to the desk's last synced spot. */
export function LiveNiftyKpi({ fallback, syncedAt }) {
  const q = useQuote(...NIFTY);
  const p = q?.p ?? fallback;
  const chg = q?.p != null && q?.pc ? (q.p / q.pc - 1) * 100 : null;
  return (
    <div className="kpi">
      <span className="label">Nifty 50 {q ? <span className="up">· live</span> : "· last sync"}</span>
      <span className="v">{fmt.num(p)}</span>
      <span className={`d ${chg == null ? "" : fmt.tone(chg)}`}>
        {chg != null ? `${fmt.pct(chg)} today · ${fmt.clock(q.t)} IST` : fmt.time(syncedAt)}
      </span>
    </div>
  );
}

/** Where live Nifty sits against an open position's strikes. Condor: room to each short strike. Long option: distance to strike. */
export function StrikeWatch({ legs, fallback }) {
  const q = useQuote(...NIFTY);
  const spot = q?.p ?? fallback;
  if (!spot || !legs?.length) return null;
  const shortCall = legs.find((l) => l.side === "SELL" && l.kind === "CE");
  const shortPut = legs.find((l) => l.side === "SELL" && l.kind === "PE");
  const room = (k) => ({ pts: k - spot, pct: (k / spot - 1) * 100 });
  const Item = ({ label, k, good }) => {
    const r = room(k);
    return (
      <div className="sw-item">
        <span className="label">{label}</span>
        <b className="mono">{fmt.num(k, 0)}</b>
        <span className={`mono ${good ? "up" : "down"}`}>{r.pts >= 0 ? "+" : "−"}{fmt.num(Math.abs(r.pts), 0)} pts ({fmt.pct(r.pct)})</span>
      </div>
    );
  };
  if (shortCall && shortPut) {
    const inside = spot > shortPut.strike && spot < shortCall.strike;
    const span = shortCall.strike - shortPut.strike;
    const pos = Math.max(0, Math.min(100, ((spot - shortPut.strike) / span) * 100));
    return (
      <div className="sw">
        <div className="sw-head">
          <span className="label">Nifty vs the short strikes {q ? "· live" : "· last sync"}</span>
          <span className={inside ? "up" : "down"}>{inside ? "inside the profit zone" : "outside the profit zone"}</span>
        </div>
        <div className="sw-bar" aria-hidden="true"><i style={{ left: `${pos}%` }} /></div>
        <div className="sw-row">
          <Item label="Short put" k={shortPut.strike} good={spot > shortPut.strike} />
          <div className="sw-item"><span className="label">Nifty</span><b className="mono">{fmt.num(spot)}</b></div>
          <Item label="Short call" k={shortCall.strike} good={spot < shortCall.strike} />
        </div>
      </div>
    );
  }
  const leg = legs[0];
  const itm = leg.kind === "CE" ? spot > leg.strike : spot < leg.strike;
  return (
    <div className="sw">
      <div className="sw-head">
        <span className="label">Nifty vs the strike {q ? "· live" : "· last sync"}</span>
        <span className={itm ? "up" : "flat"}>{itm ? "in the money" : "out of the money"}</span>
      </div>
      <div className="sw-row">
        <div className="sw-item"><span className="label">Nifty</span><b className="mono">{fmt.num(spot)}</b></div>
        <Item label={`${leg.strike} ${leg.kind}`} k={leg.strike} good={itm} />
      </div>
    </div>
  );
}
