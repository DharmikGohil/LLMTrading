import Link from "next/link";
import EquityChart from "@/components/EquityChart";
import { CryptoHoldings, CryptoKpis, CryptoProvider } from "@/components/CryptoLive";
import { Panel, Table } from "@/components/ui";
import { fmt, load } from "@/lib/data";

export const metadata = { title: "Crypto desk" };

const NAMES = { main: "LLM-gated momentum", control: "Rules-only momentum", hold: "BTC buy and hold" };

function chartData(c) {
  const rows = (c.equity || []).map((r) => ({ t: new Date(r.time).getTime(), btc: +r.btc, main: +r.main, control: +r.control, hold: +r.hold }))
    .filter((r) => r.t).sort((a, b) => a.t - b.t);
  const cap = (k) => c.books[k]?.capital || 10000;
  const line = (key, label, pick, base) => ({ key, label, values: rows.map((r) => (pick(r) ? { v: pick(r), r: (pick(r) / base - 1) * 100 } : null)) });
  return { tz: "UTC", tzLabel: "UTC", symbol: "$", times: rows.map((r) => r.t), series: [
    line("main", NAMES.main, (r) => r.main, cap("main")),
    line("factor", NAMES.control, (r) => r.control, cap("control")),
    line("index", NAMES.hold, (r) => r.hold, cap("hold")),
  ] };
}

export default function Crypto() {
  const { crypto: c } = load();
  if (!c) {
    return <main><div className="page-head"><div><h1>Crypto desk</h1><p className="sub">The crypto desk has not run yet.</p></div></div></main>;
  }
  const s = c.strategy || {};
  const coins = ["BTC", ...Object.values(c.books).flatMap((b) => b.positions.map((p) => p.coin))];
  const gate = c.gates?.at(-1);
  const trades = [...(c.trades || [])].reverse();
  return (
    <CryptoProvider coins={coins}>
      <main>
        <div className="page-head">
          <div>
            <span className="label">Binance spot · USDT · paper money · runs 24/7</span>
            <h1>Crypto desk</h1>
            <p className="sub">
              Momentum with a trend filter, tested before it went live (see the{" "}
              <a className="accent" href="https://github.com/DharmikGohil/LLMTrading/blob/main/docs/crypto-desk.md">desk notes</a>).
              Every {s.rebalance_days ?? 7} days the desk holds the top {s.top_k ?? 3} of the 20 most-traded coins by{" "}
              {s.lookback ?? 90}-day return{s.risk_adjusted ? " per unit of volatility" : ""}, each above its {s.coin_trend_sma ?? 50}-day average,
              and goes to USDT while BTC is below its {s.regime_sma ?? 100}-day average.
              {s.core_btc ? ` ${Math.round(s.core_btc * 100)}% always sits in BTC.` : ""}{" "}
              The LLM-gated account can cut exposure or exclude coins around risky events. The control follows the rules
              alone, and buying and holding BTC is the benchmark both must beat.
            </p>
          </div>
        </div>

        <CryptoKpis books={c.books} names={NAMES} />

        {gate ? (
          <div className="callout" style={{ marginTop: 12 }}>
            <b>Latest gate ({fmt.short(gate.date)}): exposure {Math.round((gate.max_exposure ?? 1) * 100)}%{gate.exclude?.length ? `, excluded ${gate.exclude.join(", ")}` : ""}.</b> {gate.note}
          </div>
        ) : null}

        <div className="grid" style={{ marginTop: 12 }}>
          <div className="c12">
            <Panel title="Return since start" meta="Each account against buying and holding BTC, at every run">
              <EquityChart data={chartData(c)} height={240} compact ranges={false} />
            </Panel>
          </div>
          {Object.entries(NAMES).map(([k, n]) => (
            <div className="c12" key={k}>
              <Panel title={n} meta={c.books[k]?.last_rebalance ? `last rebalance ${fmt.time(c.books[k].last_rebalance, "UTC", "UTC")}` : ""}>
                <CryptoHoldings book={c.books[k]} />
              </Panel>
            </div>
          ))}
          <div className="c12">
            <Panel title="Trades" meta={`${trades.length}`} flush>
              <Table rows={trades} rowKey={(r) => r.arm + r.time + r.coin + r.side} empty="No trades yet." cols={[
                { key: "time", label: "Time (UTC)", render: (r) => <span className="mono muted">{fmt.time(r.time, "UTC", "UTC")}</span> },
                { key: "arm", label: "Account", render: (r) => NAMES[r.arm] || r.arm },
                { key: "side", label: "Side", render: (r) => <span className={`side ${r.side}`}>{r.side}</span> },
                { key: "coin", label: "Coin", sym: false },
                { key: "value", label: "Value", n: true, render: (r) => `$${(+r.value).toLocaleString("en-US", { maximumFractionDigits: 2 })}` },
                { key: "price", label: "Price", n: true, render: (r) => (+r.price).toPrecision(6) },
                { key: "pnl", label: "P&L", n: true, render: (r) => (r.pnl === "" || r.pnl == null ? "—" : <span className={fmt.tone(+r.pnl)}>{(+r.pnl).toFixed(2)}</span>) },
                { key: "reason", label: "Why", wrap: true },
              ]} />
            </Panel>
          </div>
        </div>
        <p className="muted" style={{ fontSize: 12.5, marginTop: 12 }}>
          Prices and account values on this page update live from Binance every 10 seconds. Trades happen only at the desk&apos;s
          scheduled runs, on GitHub Actions: a daily rebalance check at 00:10 UTC and a gate and equity check every 2 hours.
          Indian crypto tax (30% plus cess on every gain, no loss set-off) is not deducted here; see the{" "}
          <Link className="accent" href="/research">research</Link> for after-tax results.
        </p>
      </main>
    </CryptoProvider>
  );
}
