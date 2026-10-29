import Link from "next/link";
import { Table } from "@/components/ui";
import { fmt, load } from "@/lib/data";

export const metadata = { title: "Research" };

export default function Research() {
  const { research, backtests, docs } = load();
  const changes = docs.find((d) => d.kind === "changes");
  return (
    <main>
      <div className="page-head">
        <span className="eyebrow">Why the desk is built this way</span>
        <h1>Research</h1>
        <p className="lede">
          Properly controlled studies find no reliable stock-picking skill in LLMs on their own: they test after the
          model's training cutoff, over long periods, with costs. Rule-based momentum has the better record, and LLMs
          are useful at spotting red flags. Hence a momentum screen with an LLM veto, next to a control account without it.
        </p>
      </div>
      <section className="section">
        <h2>Evidence</h2>
        <Table rows={research} cols={[
          { key: "study", label: "Study" },
          { key: "sample", label: "Sample", wrap: true },
          { key: "finding", label: "Finding", wrap: true },
          { key: "verdict", label: "Verdict", render: (r) => <span className={`chip ${r.verdict === "Evidence" ? "buy" : r.verdict === "No edge" || r.verdict === "Bias" ? "sell" : ""}`}>{r.verdict}</span> },
          { key: "link", label: "", render: (r) => <a href={r.link}>Source</a> },
        ]} />
      </section>
      <section className="section">
        <div className="section-head"><h2>Backtests of this system</h2><p className="note">Indian stocks, Indian costs, Jan 2024 to Oct 2026. Today's index members (survivorship bias flatters results). No row is statistically significant.</p></div>
        <Table rows={backtests} cols={[
          { key: "variant", label: "Variant", wrap: true },
          { key: "return_pct", label: "Return", n: true, render: (r) => <span className={fmt.tone(r.return_pct)}>{fmt.pct(r.return_pct)}</span> },
          { key: "max_drawdown_pct", label: "Max DD", n: true, render: (r) => fmt.pct(r.max_drawdown_pct) },
          { key: "trades", label: "Trades", n: true },
          { key: "charges_inr", label: "Charges ₹", n: true, render: (r) => fmt.num(r.charges_inr, 0) },
          { key: "windows_beating_index", label: "Beat Nifty" },
        ]} />
      </section>
      {changes ? (
        <section className="section">
          <div className="section-head"><h2>Strategy change log</h2><Link className="note" href={`/notes/${changes.id}`}>Open →</Link></div>
          <p className="note">Settings (stops, sizing, screen) change only with backtest plus paper evidence, and each change is logged with its reason.</p>
        </section>
      ) : null}
    </main>
  );
}
