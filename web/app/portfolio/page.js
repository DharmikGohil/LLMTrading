import Portfolio from "@/components/Portfolio";
import { BOOKS, MARKET_LIST, load } from "@/lib/data";

export const metadata = { title: "Portfolio" };

/** Broker-style view of every paper account: funds, holdings at live prices, orders, and the F&O positions. */
export default function PortfolioPage() {
  const data = load();
  const accounts = [];
  for (const m of [...MARKET_LIST].reverse()) {
    for (const book of ["main", "factor"]) {
      const s = data.summary.find((r) => r.market === m.name && r.book === book);
      if (!s) continue;
      accounts.push({
        id: `${m.key}-${book}`, tab: `${m.name} · ${BOOKS[book]}`, market: m.name, cur: m.symbol, tz: m.tz, tzLabel: m.tzLabel,
        start: s.start_capital, cash: s.cash, realized: s.realized_pnl, updated: s.updated,
        holdings: data.positions.filter((p) => p.market === m.name && p.book === book)
          .map((p) => ({ symbol: p.symbol, qty: p.qty, avg: p.avg_price, last: p.last_price, stop: p.stop, opened: p.opened })),
        orders: data.trades.filter((t) => t.market === m.name && t.book === book)
          .sort((a, b) => new Date(b.time) - new Date(a.time)).slice(0, 40)
          .map((t) => ({ id: t.id, time: t.time, side: t.side, symbol: t.symbol, qty: t.qty, price: t.price, status: t.status, reason: t.reason })),
      });
    }
  }
  return (
    <main>
      <div className="page-head">
        <div>
          <span className="label">Paper money · all accounts</span>
          <h1>Portfolio</h1>
          <p className="sub">
            A broker-style view of every paper account. Stock holdings are priced live from the quote feed, about every
            15 seconds while the market is open. F&amp;O positions are priced from NSE&apos;s option chain when it can be
            reached, otherwise from the desk&apos;s last sync. Cash, orders and positions change when a scheduled run trades.
          </p>
        </div>
      </div>
      <Portfolio accounts={accounts} options={data.options} />
    </main>
  );
}
