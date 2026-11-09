import Link from "next/link";
import { LiveEdge, LiveEquity, LiveIndexRet } from "@/components/Live";
import Log from "@/components/Log";
import Spark from "@/components/Spark";
import { Conf, Panel, Rating } from "@/components/ui";
import { MARKET_LIST, deskOf, equitySeries, fmt, liveSpec, load, optionsView, timeline } from "@/lib/data";

const pct = (v) => <span className={fmt.tone(v)}>{fmt.pct(v)}</span>;
const pp = (v) => <span className={fmt.tone(v)}>{fmt.pp(v)}</span>;

function series(eq, key) {
  const s = eq.series.find((x) => x.key === key);
  return s ? s.values.map((p) => (p ? p.r : null)) : null;
}

export default function Home() {
  const data = load();
  const stockDesks = MARKET_LIST.slice().reverse().map((m) => ({ ...deskOf(data, m.key), spec: liveSpec(data, m.key), eq: equitySeries(data, m.key) }));
  const opt = data.options ? optionsView(data.options) : null;
  const c = data.crypto;
  const cBook = (k) => c?.books?.[k];
  const cRows = (c?.equity || []).map((r) => ({ main: +r.main, control: +r.control, hold: +r.hold }));
  const calls = stockDesks.flatMap((d) => d.latestCalls.slice(0, 4).map((s) => ({ ...s, desk: d.name })));

  return (
    <main>
      <div className="page-head">
        <div>
          <h1>Overview</h1>
          <p className="sub">
            Four paper-money desks. Each runs the same rules in two accounts: one with the LLM (Claude), which can block or
            shrink a trade but never add one, and one without. The LLM difference is the gap between them.
          </p>
        </div>
      </div>

      <div className="cards">
        {stockDesks.map((d) => (
          <Link key={d.key} href={`/desk/${d.key}`} className="card">
            <div className="top"><span className="nm">{d.name} stocks</span><span className="tag">{d.universe}</span></div>
            <span className="val"><LiveEquity spec={d.spec} cur={d.symbol} /></span>
            <div className="row"><span>With LLM</span><b><LiveEquity spec={d.spec} show="ret" /></b></div>
            <div className="row"><span>{d.index}</span><b><LiveIndexRet spec={d.spec} /></b></div>
            <div className="row"><span>LLM difference</span><b><LiveEdge spec={d.spec} /></b></div>
            <Spark values={series(d.eq, "main")} bench={series(d.eq, "index")} />
          </Link>
        ))}
        {opt ? (
          <Link href="/options" className="card">
            <div className="top"><span className="nm">Nifty options</span><span className="tag">weekly range bet</span></div>
            <span className="val">{fmt.money(data.options.books.main.equity, "₹", 0)}</span>
            <div className="row"><span>With LLM</span><b>{pct((data.options.books.main.equity / data.options.books.main.capital - 1) * 100)}</b></div>
            <div className="row"><span>Without LLM</span><b>{pct((data.options.books.control.equity / data.options.books.control.capital - 1) * 100)}</b></div>
            <div className="row"><span>LLM difference</span><b>{pp(((data.options.books.main.equity - data.options.books.control.equity) / data.options.books.main.capital) * 100)}</b></div>
            <Spark values={series(opt.condorChart, "main")} bench={series(opt.condorChart, "index")} />
          </Link>
        ) : null}
        {c ? (
          <Link href="/crypto" className="card">
            <div className="top"><span className="nm">Crypto</span><span className="tag">BTC + ETH, in cash when falling</span></div>
            <span className="val">${cBook("main").value.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
            <div className="row"><span>With LLM</span><b>{pct(cBook("main").return_pct)}</b></div>
            <div className="row"><span>Just hold BTC</span><b>{pct(cBook("hold").return_pct)}</b></div>
            <div className="row"><span>LLM difference</span><b>{pp(cBook("main").return_pct - cBook("control").return_pct)}</b></div>
            <Spark values={cRows.map((r) => (r.main / 10000 - 1) * 100)} bench={cRows.map((r) => (r.hold / 10000 - 1) * 100)} />
          </Link>
        ) : null}
      </div>

      <div className="grid section">
        <div className="c7">
          <Panel title="Latest activity" act={<Link href="/tape">See all</Link>} flush>
            <Log days={timeline(data)} limit={10} compact />
          </Panel>
        </div>
        <div className="c5">
          <Panel title="Latest analyst calls" act={<Link href="/calls">See all</Link>} flush>
            <div className="mini-calls">
              {calls.length ? calls.map((s) => (
                <Link key={`${s.desk}${s.symbol}`} href={`/symbol/${encodeURIComponent(s.symbol)}`} title={s.thesis}>
                  <span className="muted">{s.desk === "US" ? "US" : "IN"}</span>
                  <span className="sym">{s.symbol}</span>
                  <Rating r={s.rating} />
                  <Conf v={s.confidence} />
                </Link>
              )) : <div className="empty">No calls yet.</div>}
            </div>
          </Panel>
        </div>
      </div>

      <details className="how section">
        <summary>How it works</summary>
        <div>
          <p>
            <b>Stocks (India and US):</b> the rules pick stocks that have been rising strongly (a momentum screen). Each morning Claude
            reviews them for red flags (results dates, filings, news) and can veto or shrink a buy, never add one. The account
            without LLM trades the screen alone.
          </p>
          <p style={{ marginTop: 10 }}>
            <b>Nifty options:</b> a weekly bet that Nifty stays inside a range, with the loss capped (an iron condor). Claude can bet a wider range or skip a risky week; the
            account without LLM ignores the gate. There is also a ₹1,000 option-buying test.
          </p>
          <p style={{ marginTop: 10 }}>
            <b>Crypto:</b> holds BTC and ETH only while they are rising (above their 50-day average), otherwise waits in cash.
            It runs 24/7 on GitHub Actions, against simply holding BTC.
          </p>
          <p style={{ marginTop: 10 }}>
            Every rule was backtested before it went live, and most ideas failed honestly. See the{" "}
            <Link className="accent" href="/research">research</Link>.
          </p>
        </div>
      </details>
    </main>
  );
}
