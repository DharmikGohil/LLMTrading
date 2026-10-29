import Link from "next/link";
import { Panel, Table } from "@/components/ui";
import { fmt, load } from "@/lib/data";

export const metadata = { title: "Research" };

const VERDICT = { Evidence: "up", "No edge": "down", Bias: "down" };

export default function Research() {
  const { research, backtests, docs } = load();
  const changes = docs.find((d) => d.kind === "changes");
  return (
    <main>
      <div className="page-head">
        <div>
          <span className="label">Why the desk is built this way</span>
          <h1>Research</h1>
          <p className="sub">
            Properly controlled studies find no reliable stock-picking skill in LLMs on their own once they test after the model&apos;s
            training cutoff, over long periods, with costs. Rule-based momentum has the better record, and LLMs are useful at spotting
            red flags. Hence a momentum screen with an LLM veto, next to a control account without it.
          </p>
        </div>
      </div>
      <div className="grid">
        <div className="c12">
          <Panel title="Evidence" meta={`${research.length} studies`} flush>
            <Table rows={research} cols={[
              { key: "study", label: "Study", render: (r) => <b>{r.study}</b> },
              { key: "sample", label: "Sample", wrap: true },
              { key: "finding", label: "Finding", wrap: true },
              { key: "verdict", label: "Verdict", render: (r) => <span className={`chip ${VERDICT[r.verdict] || ""}`}>{r.verdict}</span> },
              { key: "link", label: "", render: (r) => <a className="accent mono" href={r.link}>Source ↗</a> },
            ]} />
          </Panel>
        </div>
        <div className="c12">
          <Panel title="Backtests of this system" meta="Nifty 200 · Indian costs · Jan 2024 to Oct 2026" flush
            foot="Today's index members, so survivorship bias flatters every row. No row is statistically significant.">
            <Table rows={backtests} cols={[
              { key: "variant", label: "Variant", render: (r) => <span>{r.variant}{r.id === "slow_sepa" ? <span className="chip llm" style={{ marginLeft: 8 }}>live</span> : null}</span> },
              { key: "universe", label: "Universe" },
              { key: "return_pct", label: "Return", n: true, render: (r) => <b className={fmt.tone(r.return_pct)}>{fmt.pct(r.return_pct)}</b> },
              { key: "max_drawdown_pct", label: "Max drawdown", n: true, render: (r) => <span className="down">{fmt.pct(r.max_drawdown_pct)}</span> },
              { key: "trades", label: "Trades", n: true },
              { key: "charges_inr", label: "Charges ₹", n: true, render: (r) => fmt.num(r.charges_inr, 0) },
              { key: "windows_beating_index", label: "Windows beating Nifty", n: true },
            ]} />
          </Panel>
        </div>
        {changes ? (
          <div className="c12">
            <div className="callout">
              <b>Strategy change log.</b> Settings (stops, sizing, screen) change only with backtest plus paper evidence, and each change is logged with its reason.{" "}
              <Link className="accent" href={`/notes/${changes.id}`}>Open the log →</Link>
            </div>
          </div>
        ) : null}
      </div>
    </main>
  );
}
