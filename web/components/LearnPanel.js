import { Table } from "@/components/ui";
import { fmt } from "@/lib/data";

const usd = (v) => (v == null || v === "" ? "—" : `$${(+v).toLocaleString("en-US", { maximumFractionDigits: +v < 100 ? 2 : 0 })}`);
const STATUS = { confirmed: "up", retired: "down", hypothesis: "" };

/** The crypto learning loop: is the LLM's forecasting better than a no-skill baseline, and what has it learned? */
export function LearnStats({ learn }) {
  const s = learn?.summary?.["24h"] || { n: 0 };
  const skill = s.skill_pct;
  return (
    <div className="learn">
      <p className="sub">
        Three times a day the LLM says how likely BTC and ETH are to be higher in 24 hours, and gives a price range. Each call is
        graded when the time is up and compared with a no-skill guess (50/50, with a range from recent volatility). This shows
        whether the LLM&apos;s judgement adds anything, long before money is involved.
      </p>
      <div className="learn-kpis">
        <div><span className="label">Calls graded</span><b>{s.n}</b><span className="muted">{learn?.open ? `${learn.open} waiting` : "24h calls"}</span></div>
        <div><span className="label">Better than no-skill guess</span>
          <b className={skill == null ? "" : fmt.tone(skill)}>{skill == null ? "—" : `${skill > 0 ? "+" : ""}${skill}%`}</b>
          <span className="muted">Brier score{s.t != null ? `, t = ${s.t}` : ""}</span></div>
        <div><span className="label">Price inside the range</span><b>{s.coverage_llm_pct != null ? `${s.coverage_llm_pct}%` : "—"}</b>
          <span className="muted">aim: 80%</span></div>
        <div><span className="label">Verdict so far</span><b className="verdict">{s.verdict || "no scored calls yet"}</b>
          <span className="muted">needs 30+ calls</span></div>
      </div>
      {learn?.brackets ? <BracketStats b={learn.brackets.summary} /> : null}
    </div>
  );
}

export function ForecastTable({ learn }) {
  const rows = learn?.recent || [];
  return (
    <Table rows={rows} rowKey={(r) => r.id} empty="No calls yet: the first ones come at the next scheduled run." cols={[
      { key: "made", label: "Made (UTC)", render: (r) => <span className="muted">{fmt.time(r.made, "UTC", "UTC")}</span> },
      { key: "coin", label: "Coin", render: (r) => <b>{r.coin}</b> },
      { key: "horizon_h", label: "Ahead", render: (r) => (+r.horizon_h === 168 ? "7 days" : "24h") },
      { key: "spot", label: "Price then", n: true, render: (r) => usd(r.spot) },
      { key: "p_up", label: "Chance higher", n: true, render: (r) => `${Math.round(+r.p_up * 100)}%` },
      { key: "range", label: "Range (80%)", n: true, render: (r) => `${usd(r.lo)} – ${usd(r.hi)}` },
      { key: "px", label: "Price after", n: true, render: (r) => (r.px == null ? <span className="muted">waiting</span> : usd(r.px)) },
      { key: "res", label: "Result", render: (r) => {
        if (r.px == null) return <span className="muted">—</span>;
        const right = (+r.p_up > 0.5) === (+r.up === 1);
        const call = +r.p_up === 0.5 ? null : right;
        return (
          <span>
            {call == null ? <span className="chip">no lean</span> : <span className={`chip ${call ? "up" : "down"}`}>{call ? "right way" : "wrong way"}</span>}{" "}
            <span className={`chip ${+r.inside ? "up" : "down"}`}>{+r.inside ? "in range" : "outside"}</span>
          </span>
        );
      } },
      { key: "note", label: "Reasoning", wrap: true },
    ]} />
  );
}

export function LessonTable({ learn }) {
  const rows = learn?.lessons || [];
  return (
    <Table rows={rows} rowKey={(r) => r.id} empty="No lessons yet." cols={[
      { key: "status", label: "Status", render: (r) => <span className={`chip ${STATUS[r.status] || ""}`}>{r.status}</span> },
      { key: "lesson", label: "Lesson", wrap: true },
      { key: "kind", label: "About", render: (r) => (r.kind === "market" ? "the market" : "the LLM") },
      { key: "ev", label: "Evidence", n: true, render: (r) => {
        const e = r.evidence || {};
        if (!e.n) return <span className="muted">no cases yet</span>;
        const mkt = e.up_pct != null ? ` · ${e.up_pct}% up${e.other_up_pct != null ? ` vs ${e.other_up_pct}% otherwise` : ""}` : "";
        return `${e.n} calls${mkt || (e.skill_pct != null ? ` · skill ${e.skill_pct}%` : "")}${e.t != null ? ` · t ${e.t}` : ""}`;
      } },
      { key: "hist", label: "History 2018-26 (already seen)", n: true, render: (r) => {
        const h = r.evidence_history;
        if (!h?.design_years?.days_on) return <span className="muted">—</span>;
        const f = (x) => `${x.up_on_pct}% vs ${x.up_off_pct}% (t ${x.t})`;
        return <span title="Up-rate when the tag was on vs the other days; exploratory, does not change the status">{f(h.design_years)} · {f(h["2023_26"])}</span>;
      } },
    ]} />
  );
}

/** "Which is hit first?" calls (bracket-v1): judged against the coin's own measured base rates, not a coin flip. */
function BracketStats({ b }) {
  const a = b?.all || { n: 0 };
  const skill = a.skill_vs_base_pct;
  return (
    <>
      <p className="sub" style={{ marginTop: 18 }}>
        Which is hit first in 24 hours: a target 1.5 days&apos; volatility away, a stop one day&apos;s volatility away, or neither?
        Judged against how often each really happened on the coin&apos;s recent history. Expected value is logged, never traded.
      </p>
      <div className="learn-kpis">
        <div><span className="label">Bracket calls</span><b>{b?.calls ?? 0}</b><span className="muted">{a.n || 0} sides graded</span></div>
        <div><span className="label">Better than base rates</span>
          <b className={skill == null ? "" : fmt.tone(skill)}>{skill == null ? "—" : `${skill > 0 ? "+" : ""}${skill}%`}</b>
          <span className="muted">Brier score</span></div>
        <div><span className="label">Trust in the LLM (blend weight)</span><b>{a.fitted ? a.w : "—"}</b>
          <span className="muted">{a.fitted ? "0 = ignore, 1 = follow" : "fitted after 30 graded sides"}</span></div>
        <div><span className="label">Average logged EV</span>
          <b className={b?.mean_ev_r == null ? "" : fmt.tone(b.mean_ev_r)}>{b?.mean_ev_r == null ? "—" : `${b.mean_ev_r > 0 ? "+" : ""}${b.mean_ev_r}R`}</b>
          <span className="muted">after costs; below 0 = no trade</span></div>
      </div>
    </>
  );
}
