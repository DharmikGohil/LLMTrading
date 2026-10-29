import Link from "next/link";
import EquityChart from "@/components/EquityChart";
import { LiveEdge, LiveEquity, LiveIndexRet, LiveLast, LivePnl, LivePnlPct, LiveToStop, LiveUnrealized } from "@/components/Live";
import Log from "@/components/Log";
import { Conf, Kpi, Kpis, Panel, Rating, Signed, Table } from "@/components/ui";
import { MARKET_LIST, deskOf, equitySeries, fmt, liveSpec, load, marketOf, timeline } from "@/lib/data";

export default function Overview() {
  const data = load();
  const desks = MARKET_LIST.map((m) => ({ ...deskOf(data, m.key), spec: liveSpec(data, m.key) }));
  const vetoes = desks.reduce((a, d) => a + d.vetoes.length, 0);
  const orders = desks.reduce((a, d) => a + d.trades.length, 0);
  const positions = data.positions.filter((p) => p.book === "main")
    .map((p) => ({ ...p, toStop: p.stop && p.last_price ? ((p.last_price - p.stop) / p.last_price) * 100 : null }))
    .sort((a, b) => a.market.localeCompare(b.market) || (b.value ?? 0) - (a.value ?? 0));
  const scale = Math.max(0.5, ...positions.map((p) => Math.abs(p.unrealized_pct ?? 0)));
  const bt = data.backtests;
  const btMax = Math.max(1, ...bt.flatMap((b) => [Math.abs(b.return_pct ?? 0)]));

  return (
    <main>
      <div className="page-head">
        <div>
          <span className="label">Live paper desk · NSE and US</span>
          <h1>Does an LLM analyst make a momentum strategy better?</h1>
          <p className="sub">
            Each desk runs two accounts on the same momentum screen. In the <b className="accent">LLM-reviewed</b> account Claude
            checks every candidate for red flags and can only veto or shrink a buy. The <b>LLM off</b> account trades the screen
            alone. The gap between them is the LLM&apos;s measured value.
          </p>
        </div>
      </div>

      <Kpis>
        {desks.map((d) => [
          <Kpi key={`${d.key}-eq`} label={`${d.name} · LLM-reviewed`} value={<LiveEquity spec={d.spec} cur={d.symbol} />}
            delta={<><LiveEquity spec={d.spec} show="ret" /> vs {d.index} <LiveIndexRet spec={d.spec} /></>} />,
          <Kpi key={`${d.key}-edge`} hl label={`${d.name} · LLM edge`} value={<LiveEdge spec={d.spec} />}
            delta={<>LLM off <LiveEquity spec={d.spec} book="factor" show="ret" /></>} />,
        ])}
        <Kpi label="LLM vetoes" value={vetoes} delta="buys blocked so far" />
        <Kpi label="Orders" value={orders} delta="both desks, both books" />
      </Kpis>

      <div className="grid" style={{ marginTop: 12 }}>
        <div className="c12">
          <Panel title="Scoreboard" meta="since each desk started" flush>
            <Table rowKey={(r) => r.key} rows={desks} cols={[
              { key: "name", label: "Desk", render: (d) => <Link href={`/desk/${d.key}`} className="sym">{d.title} →</Link> },
              { key: "eq", label: "LLM-reviewed", n: true, render: (d) => <LiveEquity spec={d.spec} cur={d.symbol} /> },
              { key: "ret", label: "Return", n: true, render: (d) => <LiveEquity spec={d.spec} show="ret" /> },
              { key: "ceq", label: "LLM off", n: true, render: (d) => <LiveEquity spec={d.spec} book="factor" cur={d.symbol} /> },
              { key: "cret", label: "Return", n: true, render: (d) => <LiveEquity spec={d.spec} book="factor" show="ret" /> },
              { key: "idx", label: "Index", n: true, render: (d) => <span>{d.index} <LiveIndexRet spec={d.spec} /></span> },
              { key: "edge", label: "LLM edge", n: true, render: (d) => <b><LiveEdge spec={d.spec} /></b> },
              { key: "pnl", label: "Unrealized", n: true, render: (d) => <LiveUnrealized spec={d.spec} cur={d.symbol} /> },
              { key: "cash", label: "Cash", n: true, render: (d) => (d.main ? `${Math.round((d.main.cash / d.main.equity) * 100)}%` : "—") },
              { key: "pos", label: "Positions", n: true, render: (d) => d.main?.open_positions ?? 0 },
              { key: "veto", label: "Vetoes", n: true, render: (d) => d.vetoes.length },
            ]} />
          </Panel>
        </div>

        {desks.map((d) => (
          <div className="c6" key={d.key}>
            <Panel title={`${d.name} equity`} meta={`% since start · vs ${d.index}`} act={<Link href={`/desk/${d.key}`}>Desk →</Link>}>
              <EquityChart data={equitySeries(data, d.key)} spec={d.spec} height={230} compact />
            </Panel>
          </div>
        ))}

        <div className="c8">
          <Panel title="Open positions" meta="LLM-reviewed books" act={<Link href="/history">Full history →</Link>} flush>
            <Table rows={positions} empty="No open positions." cols={[
              { key: "symbol", label: "Stock", sym: true },
              { key: "market", label: "Mkt", render: (p) => <span className="chip ghost">{p.market === "US" ? "US" : "NSE"}</span> },
              { key: "qty", label: "Qty", n: true },
              { key: "avg_price", label: "Avg", n: true, render: (p) => fmt.num(p.avg_price) },
              { key: "last_price", label: "Last", n: true, render: (p) => <LiveLast market={p.market} sym={p.symbol} fallback={p.last_price} /> },
              { key: "unrealized", label: "P&L", n: true, render: (p) => <LivePnl market={p.market} sym={p.symbol} qty={p.qty} avg={p.avg_price} fallback={p.unrealized} cur={marketOf(p.market).symbol} /> },
              { key: "unrealized_pct", label: "P&L %", n: true, render: (p) => <LivePnlPct market={p.market} sym={p.symbol} avg={p.avg_price} fallback={p.unrealized_pct} scale={scale} /> },
              { key: "stop", label: "Stop", n: true, render: (p) => fmt.num(p.stop) },
              { key: "toStop", label: "To stop", n: true, render: (p) => <LiveToStop market={p.market} sym={p.symbol} stop={p.stop} fallback={p.last_price} /> },
            ]} />
          </Panel>
        </div>

        <div className="c4">
          <Panel title="Latest analyst calls" act={<Link href="/calls">All calls →</Link>} flush>
            {desks.map((d) => (
              <div key={d.key}>
                <div className="log-day" style={{ position: "static" }}><span>{d.name}</span><span>data to {d.lastCallDate ? fmt.short(d.lastCallDate) : "—"}</span></div>
                <div className="mini-calls">
                  {d.latestCalls.length ? d.latestCalls.map((s) => (
                    <Link key={s.symbol} href={`/symbol/${encodeURIComponent(s.symbol)}`} title={s.thesis}>
                      <span className="muted mono">{s.screen_rank ?? "·"}</span>
                      <span className="sym">{s.symbol}</span>
                      <Rating r={s.rating} />
                      <Conf v={s.confidence} />
                    </Link>
                  )) : <div className="empty">No calls yet.</div>}
                </div>
              </div>
            ))}
          </Panel>
        </div>

        <div className="c7">
          <Panel title="Activity" meta="newest first" act={<Link href="/tape">Everything →</Link>} flush>
            <Log days={timeline(data)} limit={16} compact />
          </Panel>
        </div>

        <div className="c5 stack">
          <Panel title="Run schedule" meta="IST, weekdays · each run is a scheduled Claude session" flush>
            <div className="runs">
              {[
                ["07:40", "NSE", "Analyst reviews the screen's candidates (results dates, filings, news)"],
                ["09:35", "NSE", "Trade both accounts"],
                ["12:35", "NSE", "Monitor stops"],
                ["15:05", "NSE", "Close: equity, graded review, lessons"],
                ["19:20", "US", "Analyst review, then trade (09:50 ET)"],
                ["22:20", "US", "Monitor stops (12:50 ET)"],
                ["01:15", "US", "Close: equity, graded review, lessons (15:45 ET)"],
              ].map(([t, mk, what]) => (
                <div key={t}><b>{t}</b><span className="chip ghost">{mk}</span><span className="muted">{what}</span></div>
              ))}
            </div>
          </Panel>
          <Panel title="Backtests" meta="Nifty 200 · Jan 2024 to Oct 2026" act={<Link href="/research">Research →</Link>}
            foot="Indian costs included. Today's index members, so survivorship bias flatters every row; none is statistically significant.">
            <div className="hbars">
              {bt.map((b) => {
                const v = b.return_pct ?? 0;
                const w = (Math.abs(v) / btMax) * 50;
                const cls = b.id === "nifty" ? "ref" : v >= 0 ? "up" : "down";
                return (
                  <div className="hbar" key={b.id}>
                    <span className="nm">{b.variant}{b.id === "slow_sepa" ? <span className="chip llm" style={{ marginLeft: 6 }}>live</span> : null}</span>
                    <span className="tr" style={{ "--zero": "50%" }}>
                      <span className={`b ${cls} ${b.id === "slow_sepa" ? "cur" : ""}`} style={v >= 0 ? { left: "50%", width: `${w}%` } : { right: "50%", width: `${w}%` }} />
                    </span>
                    <span className={`val ${fmt.tone(v)}`}>{fmt.pct(v, 1)}</span>
                  </div>
                );
              })}
            </div>
          </Panel>
        </div>
      </div>
    </main>
  );
}
