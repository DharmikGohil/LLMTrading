import fs from "node:fs";
import path from "node:path";
import { fmt } from "./fmt";

const DATA = path.join(process.cwd(), "data");

function read(name, fallback) {
  try {
    return JSON.parse(fs.readFileSync(path.join(DATA, `${name}.json`), "utf8"));
  } catch {
    return fallback;
  }
}

export const MARKETS = {
  us: {
    key: "us", name: "US", title: "US desk", exchange: "NYSE · Nasdaq", universe: "S&P 100", index: "S&P 500",
    currency: "USD", symbol: "$", tz: "America/New_York", tzLabel: "ET",
    schedule: [["09:50", "Review + trade"], ["12:50", "Monitor"], ["15:45", "Close + review"]], openMin: 9 * 60 + 30,
  },
  india: {
    key: "india", name: "India", title: "India desk", exchange: "NSE", universe: "Nifty 200", index: "Nifty 50",
    currency: "INR", symbol: "₹", tz: "Asia/Kolkata", tzLabel: "IST",
    schedule: [["07:40", "Analyst review"], ["09:35", "Trade"], ["12:35", "Monitor"], ["15:05", "Close + review"]], openMin: 9 * 60 + 15,
  },
};
export const MARKET_LIST = [MARKETS.us, MARKETS.india];
export const marketOf = (name) => (name === "US" ? MARKETS.us : MARKETS.india);

export const BOOKS = { main: "LLM-reviewed", factor: "LLM off" };
export const BOOK_LONG = { main: "LLM-reviewed", factor: "LLM off (control)" };

let cache;
export function load() {
  if (cache) return cache;
  cache = {
    summary: read("summary", []),
    positions: read("positions", []),
    trades: read("trades", []),
    decisions: read("decisions", []),
    signals: read("signals", []),
    equity: read("equity", []),
    journal: read("journal", []),
    lessons: read("lessons", []),
    backtests: read("backtests", []),
    research: read("research", []),
    docs: read("docs", []),
  };
  return cache;
}

const ms = (t) => new Date(t).getTime();
const byTimeDesc = (a, b) => ms(b.time) - ms(a.time);

/** Local calendar date (YYYY-MM-DD) of a timestamp on an exchange. */
export function localDay(t, tz) {
  return new Intl.DateTimeFormat("en-CA", { timeZone: tz, year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date(t));
}

/** Latest timestamp anywhere in the data: when the desk last wrote something. */
export function asOf(data) {
  const ts = [
    ...data.summary.map((r) => r.updated),
    ...data.trades.map((r) => r.time),
    ...data.equity.map((r) => r.time),
  ].map(ms).filter(Number.isFinite);
  return ts.length ? new Date(Math.max(...ts)).toISOString() : null;
}

export const isVeto = (d) => /veto/.test(d.decision || "");
export const isSkip = (d) => /veto|blocked|not adding|missing/.test(d.decision || "");

/** Average-cost realized P&L on every SELL, per book and symbol. */
function withRealized(trades) {
  const book = new Map();
  return [...trades].sort((a, b) => ms(a.time) - ms(b.time)).map((t) => {
    const k = `${t.market}|${t.book}|${t.symbol}`;
    const pos = book.get(k) || { qty: 0, cost: 0 };
    let realized = null;
    if (t.status !== "COMPLETE" || t.price == null) return { ...t, realized };
    if (t.side === "BUY") {
      pos.cost += t.qty * t.price;
      pos.qty += t.qty;
    } else if (pos.qty > 0) {
      const avg = pos.cost / pos.qty;
      const q = Math.min(t.qty, pos.qty);
      realized = (t.price - avg) * q;
      pos.cost -= avg * q;
      pos.qty -= q;
    }
    book.set(k, pos);
    return { ...t, realized };
  });
}

export function allTrades(data) {
  return withRealized(data.trades).sort(byTimeDesc);
}

/** Equity paths for one desk: both books and the index, as % since start, on a shared ordinal time axis. */
export function equitySeries(data, market) {
  const m = MARKETS[market];
  const rows = data.equity.filter((r) => r.market === m.name).sort((a, b) => ms(a.time) - ms(b.time));
  const start = Object.fromEntries(data.summary.filter((s) => s.market === m.name).map((s) => [s.book, s.start_capital]));
  const times = [...new Set(rows.map((r) => ms(r.time)))].sort((a, b) => a - b);
  const idxRows = rows.filter((r) => r.index_close != null);
  const idxBase = idxRows.length ? idxRows[0].index_close : null;
  const path = (pick) => {
    let last = null;
    const at = new Map();
    for (const r of rows) { const v = pick(r); if (v != null) at.set(ms(r.time), v); }
    return times.map((t) => {
      if (at.has(t)) last = at.get(t);
      return last;
    });
  };
  const mk = (key, label, values, base) => ({
    key, label,
    values: values.map((v) => (v == null || !base ? null : { v, r: (v / base - 1) * 100 })),
  });
  const series = [];
  if (start.main) series.push(mk("main", BOOKS.main, path((r) => (r.book === "main" ? r.equity : null)), start.main));
  if (start.factor) series.push(mk("factor", BOOKS.factor, path((r) => (r.book === "factor" ? r.equity : null)), start.factor));
  if (idxBase) series.push(mk("index", m.index, path((r) => r.index_close), idxBase));
  return { times, series, tz: m.tz, tzLabel: m.tzLabel, symbol: m.symbol };
}

/** One row per desk per trading day: closing equity of each book, daily change, index, activity. */
export function dailyLedger(data) {
  const out = [];
  for (const m of MARKET_LIST) {
    const rows = data.equity.filter((r) => r.market === m.name).sort((a, b) => ms(a.time) - ms(b.time));
    const start = Object.fromEntries(data.summary.filter((s) => s.market === m.name).map((s) => [s.book, s.start_capital]));
    const days = new Map();
    const minuteOf = (t) => {
      const p = Object.fromEntries(new Intl.DateTimeFormat("en-GB", { timeZone: m.tz, hour: "2-digit", minute: "2-digit", hour12: false }).formatToParts(new Date(t)).map((x) => [x.type, x.value]));
      return Number(p.hour) * 60 + Number(p.minute);
    };
    for (const r of rows) {
      if (minuteOf(r.time) < m.openMin) continue; // overnight marks are not a session
      const d = localDay(r.time, m.tz);
      if (!days.has(d)) days.set(d, {});
      const day = days.get(d);
      day[r.book] = r.equity;
      if (r.index_close != null) day.index = r.index_close;
    }
    const prev = { main: start.main, factor: start.factor, index: null };
    const firstIdx = rows.find((r) => r.index_close != null)?.index_close ?? null;
    prev.index = firstIdx;
    const tradeDays = new Map();
    for (const t of data.trades.filter((t) => t.market === m.name)) {
      const d = localDay(t.time, m.tz);
      tradeDays.set(d, (tradeDays.get(d) || 0) + 1);
    }
    const vetoDays = new Map();
    for (const x of data.decisions.filter((x) => x.market === m.name && x.book === "main" && isVeto(x))) {
      const d = localDay(x.time, m.tz);
      vetoDays.set(d, (vetoDays.get(d) || 0) + 1);
    }
    for (const [date, v] of days) {
      const chg = (k) => (v[k] != null && prev[k] ? (v[k] / prev[k] - 1) * 100 : null);
      const row = {
        id: `${m.key}-${date}`, date, market: m.name, desk: m.key, symbol: m.symbol,
        main: v.main ?? null, mainDay: chg("main"), mainTotal: v.main && start.main ? (v.main / start.main - 1) * 100 : null,
        factor: v.factor ?? null, factorDay: chg("factor"), factorTotal: v.factor && start.factor ? (v.factor / start.factor - 1) * 100 : null,
        indexDay: chg("index"), indexTotal: v.index && firstIdx ? (v.index / firstIdx - 1) * 100 : null,
        orders: tradeDays.get(date) || 0, vetoes: vetoDays.get(date) || 0,
      };
      row.edge = row.mainTotal != null && row.factorTotal != null ? row.mainTotal - row.factorTotal : null;
      for (const k of ["main", "factor", "index"]) if (v[k] != null) prev[k] = v[k];
      out.push(row);
    }
  }
  return out.sort((a, b) => b.date.localeCompare(a.date) || a.market.localeCompare(b.market));
}

export function deskOf(data, market) {
  const m = MARKETS[market];
  const by = (rows) => rows.filter((r) => r.market === m.name);
  const main = data.summary.find((r) => r.market === m.name && r.book === "main");
  const control = data.summary.find((r) => r.market === m.name && r.book === "factor");
  const signals = by(data.signals);
  const lastCallDate = signals.map((s) => s.date).sort().at(-1);
  const decisions = by(data.decisions).sort(byTimeDesc);
  return {
    ...m,
    main,
    control,
    indexReturn: main?.index_return_pct ?? null,
    edge: main && control ? Number(main.return_pct) - Number(control.return_pct) : null,
    positions: by(data.positions),
    trades: allTrades(data).filter((t) => t.market === m.name),
    decisions,
    vetoes: decisions.filter((d) => d.book === "main" && isVeto(d)),
    signals,
    latestCalls: signals.filter((s) => s.date === lastCallDate).sort((a, b) => (a.screen_rank ?? 99) - (b.screen_rank ?? 99)),
    lastCallDate,
  };
}

/** Open positions of the LLM-reviewed books, for the ticker strip. */
export function tape(data) {
  return data.positions
    .filter((p) => p.book === "main")
    .map((p) => ({ symbol: p.symbol, market: p.market, last: p.last_price, pct: p.unrealized_pct, avg: p.avg_price }))
    .sort((a, b) => a.market.localeCompare(b.market) || a.symbol.localeCompare(b.symbol));
}

export function symbols(data) {
  const set = new Map();
  for (const r of [...data.signals, ...data.positions, ...data.trades, ...data.decisions]) {
    if (r.symbol && !set.has(r.symbol)) set.set(r.symbol, r.market);
  }
  return [...set.entries()].map(([symbol, market]) => ({ symbol, market })).sort((a, b) => a.symbol.localeCompare(b.symbol));
}

export function symbolView(data, sym) {
  const f = (rows) => rows.filter((r) => r.symbol === sym);
  return {
    symbol: sym,
    signals: f(data.signals).sort((a, b) => b.date.localeCompare(a.date)),
    positions: f(data.positions),
    trades: f(allTrades(data)),
    decisions: f(data.decisions).sort(byTimeDesc),
  };
}

/** Every event as one chronological thread: analyst calls, decisions, orders, reviews, reports. */
export function timeline(data) {
  const ev = [];
  for (const s of data.signals) {
    ev.push({ t: `${s.date}T23:59:00Z`, day: dayAfter(s.date), market: s.market, kind: "call", symbol: s.symbol, rating: s.rating,
      confidence: s.confidence, title: s.symbol, body: s.thesis });
  }
  for (const d of data.decisions) {
    if (!isSkip(d)) continue;
    ev.push({ t: d.time, day: localDay(d.time, marketOf(d.market).tz), market: d.market, kind: "skip", book: d.book, symbol: d.symbol,
      title: `${d.symbol} not bought`, body: cleanNote(d.decision) });
  }
  for (const tr of data.trades) {
    ev.push({ t: tr.time, day: localDay(tr.time, marketOf(tr.market).tz), market: tr.market, kind: "order", book: tr.book, symbol: tr.symbol,
      side: tr.side, title: `${tr.side} ${tr.qty} ${tr.symbol} @ ${tr.price ?? "—"}`, body: cleanNote(tr.reason) });
  }
  for (const doc of data.docs) {
    if (doc.kind === "changes") continue;
    ev.push({ t: `${doc.date}T${doc.kind === "report" ? "02:00" : "23:58"}:00Z`, day: doc.kind === "report" ? dayAfter(doc.date) : doc.date,
      market: doc.market, kind: doc.kind, title: doc.kind === "report" ? `Analyst report, data to ${fmt.short(doc.date)}` : "Daily review", href: `/notes/${doc.id}` });
  }
  ev.sort((a, b) => b.day.localeCompare(a.day) || ms(b.t) - ms(a.t));
  const days = new Map();
  for (const e of ev) {
    if (!days.has(e.day)) days.set(e.day, []);
    days.get(e.day).push(e);
  }
  return [...days.entries()];
}

function dayAfter(d) {
  // an analysis dated D (data to D's close) is acted on the next weekday
  const x = new Date(`${d}T12:00:00Z`);
  x.setUTCDate(x.getUTCDate() + 1);
  while (x.getUTCDay() === 0 || x.getUTCDay() === 6) x.setUTCDate(x.getUTCDate() + 1);
  return x.toISOString().slice(0, 10);
}

/** Engine notes carry "tp <price>"; the slow book's target is a placeholder (100R), so drop absurd ones. */
export function cleanNote(s) {
  if (!s) return s;
  return s.replace(/ stop ([\d.]+) tp ([\d.]+)/g, (m, stop, tp) => (Number(tp) > 3 * Number(stop) ? ` stop ${stop}` : m));
}

export { RATING_TONE, fmt } from "./fmt";

const YAHOO_INDEX = { US: "^GSPC", India: "^NSEI" };
export const yahooSymbol = (market, sym) => (market === "US" ? sym : `${sym}.NS`);

/** What the browser needs to recompute equity from live prices: cash, holdings, start capital, index base. */
export function liveSpec(data, market) {
  const m = MARKETS[market];
  const book = (b) => {
    const s = data.summary.find((r) => r.market === m.name && r.book === b);
    if (!s) return null;
    return { start: s.start_capital, cash: s.cash, equity: s.equity,
      pos: data.positions.filter((p) => p.market === m.name && p.book === b).map((p) => [p.symbol, p.qty, p.last_price, p.avg_price]) };
  };
  const idx = data.equity.filter((r) => r.market === m.name && r.index_close != null).sort((a, b) => new Date(a.time) - new Date(b.time));
  return { market: m.name, main: book("main"), factor: book("factor"), index: idx.length ? { key: `${m.name}:${YAHOO_INDEX[m.name]}`, base: idx[0].index_close, last: idx.at(-1).index_close } : null };
}

/** Every quote key the site shows live: open positions plus both indices. */
export function liveKeys(data) {
  const keys = new Set(data.positions.map((p) => `${p.market}:${p.symbol}`));
  for (const [mk, y] of Object.entries(YAHOO_INDEX)) keys.add(`${mk}:${y}`);
  return [...keys].sort();
}
