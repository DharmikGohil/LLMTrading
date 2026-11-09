import Link from "next/link";
import EquityChart from "@/components/EquityChart";
import { CryptoHoldings, CryptoKpis, CryptoProvider } from "@/components/CryptoLive";
import Tabs from "@/components/Tabs";
import { Panel, Table } from "@/components/ui";
import { fmt, load } from "@/lib/data";

export const metadata = { title: "Crypto desk" };

const NAMES = { main: "LLM-gated trend", control: "Rules-only trend", hold: "BTC buy and hold" };

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
  const strat = s.mode === "trend"
    ? `${(s.coins || ["BTC", "ETH"]).join(" and ")}, each held while above its ${s.trend_sma ?? 50}-day average`
    : `top ${s.top_k ?? 3} coins by ${s.lookback ?? 90}-day return`;
  return (
    <CryptoProvider coins={coins}>
      <main>
        <div className="page-head">
          <div>
            <h1>Crypto</h1>
            <p className="sub">
              Trend-following on Binance spot in USDT: {strat}, otherwise in cash. Runs 24/7; the benchmark is simply holding BTC.
            </p>
          </div>
        </div>

        <CryptoKpis books={c.books} names={NAMES} />

        <div className="section">
          <Panel title="Return since start" meta="each account against holding BTC">
            <EquityChart data={chartData(c)} height={260} compact ranges={false} />
          </Panel>
        </div>

        {gate ? (
          <div className="callout section">
            <b>Latest gate, {fmt.short(gate.date)}: exposure {Math.round((gate.max_exposure ?? 1) * 100)}%{gate.exclude?.length ? `, excluded ${gate.exclude.join(", ")}` : ""}.</b> {gate.note}
          </div>
        ) : null}

        <div className="section">
          <Tabs tabs={[
            ...Object.entries(NAMES).filter(([k]) => c.books[k]).map(([k, n]) => ({
              label: n, count: c.books[k].positions.length || null, body: (
                <div className="pad" style={{ paddingBottom: 16 }}>
                  {c.books[k].last_rebalance ? <p className="muted" style={{ fontSize: 13, marginBottom: 10 }}>Last rebalance {fmt.time(c.books[k].last_rebalance, "UTC", "UTC")}</p> : null}
                  <CryptoHoldings book={c.books[k]} />
                </div>
              ),
            })),
            {
              label: "Trades", count: trades.length, body: (
                <Table rows={trades} rowKey={(r) => r.arm + r.time + r.coin + r.side} empty="No trades yet." cols={[
                  { key: "time", label: "Time (UTC)", render: (r) => <span className="muted">{fmt.time(r.time, "UTC", "UTC")}</span> },
                  { key: "arm", label: "Account", render: (r) => NAMES[r.arm] || r.arm },
                  { key: "side", label: "Side", render: (r) => <span className={`side ${r.side}`}>{r.side}</span> },
                  { key: "coin", label: "Coin", sym: false },
                  { key: "value", label: "Value", n: true, render: (r) => `$${(+r.value).toLocaleString("en-US", { maximumFractionDigits: 2 })}` },
                  { key: "price", label: "Price", n: true, render: (r) => (+r.price).toPrecision(6) },
                  { key: "pnl", label: "P&L", n: true, render: (r) => (r.pnl === "" || r.pnl == null ? "—" : <span className={fmt.tone(+r.pnl)}>{(+r.pnl).toFixed(2)}</span>) },
                  { key: "reason", label: "Why", wrap: true },
                ]} />
              ),
            },
          ]} />
        </div>

        <details className="how section">
          <summary>How this desk works</summary>
          <div>
            <p>
              Each coin gets an equal share while its daily close is above its {s.trend_sma ?? 50}-day average; otherwise that share sits
              in USDT. The rule was chosen by a test with a design period and an untouched test period; altcoin momentum lost money in
              that test (see the <a className="accent" href="https://github.com/DharmikGohil/LLMTrading/blob/main/docs/crypto-desk.md">desk notes</a>).
              The LLM-gated account can cut exposure or exclude coins around risky events; the control follows the rules alone.
            </p>
            <p style={{ marginTop: 10 }}>
              Prices and account values update live from Binance every 10 seconds. Trades happen only at the desk&apos;s scheduled runs on
              GitHub Actions: a daily rebalance check at 00:10 UTC (05:40 IST), and a gate and equity check every 2 hours. Indian crypto
              tax (30% plus cess on every gain, no loss set-off) is not deducted here; see the{" "}
              <Link className="accent" href="/research">research</Link> for after-tax results.
            </p>
          </div>
        </details>
      </main>
    </CryptoProvider>
  );
}
