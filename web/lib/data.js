import fs from "node:fs";
import path from "node:path";

const DATA = path.join(process.cwd(), "data");

function read(name, fallback) {
  try {
    return JSON.parse(fs.readFileSync(path.join(DATA, `${name}.json`), "utf8"));
  } catch {
    return fallback;
  }
}

export const MARKETS = {
  us: { key: "us", name: "US", title: "US desk", index: "S&P 500", currency: "USD", symbol: "$", schedule: "Review + trade 09:50, monitor 12:50, close 15:45 New York time (19:20, 22:20, 01:15 IST)" },
  india: { key: "india", name: "India", title: "India desk", index: "Nifty 50", currency: "INR", symbol: "₹", schedule: "Analyst 07:40, trade 09:35, monitor 12:35, close 15:05 IST" },
};

export const BOOKS = { main: "LLM-reviewed", factor: "LLM off (control)" };

export function load() {
  return {
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
    meta: read("meta", {}),
  };
}

export function deskOf(data, market) {
  const m = MARKETS[market].name;
  const by = (rows) => rows.filter((r) => r.market === m);
  const main = data.summary.find((r) => r.market === m && r.book === "main");
  const control = data.summary.find((r) => r.market === m && r.book === "factor");
  return {
    ...MARKETS[market],
    main,
    control,
    edge: main && control ? Number(main.return_pct) - Number(control.return_pct) : null,
    positions: by(data.positions),
    trades: by(data.trades).sort((a, b) => String(b.time).localeCompare(String(a.time))),
    decisions: by(data.decisions).sort((a, b) => String(b.time).localeCompare(String(a.time))),
    signals: by(data.signals),
    equity: by(data.equity),
  };
}

/** Every event as one chronological thread: analyst calls, decisions, orders, reviews, reports. */
export function timeline(data) {
  const ev = [];
  for (const s of data.signals) {
    ev.push({ t: `${s.date}T23:59:00`, day: dayAfter(s.date), market: s.market, kind: "call",
      title: `${s.symbol}: ${s.rating}${s.confidence != null ? ` (${Math.round(s.confidence)}%)` : ""}`, body: s.thesis, symbol: s.symbol, rating: s.rating });
  }
  for (const d of data.decisions) {
    const veto = /veto|blocked|not adding|missing/.test(d.decision || "");
    if (!veto) continue;
    ev.push({ t: d.time, day: String(d.time).slice(0, 10), market: d.market, kind: "skip", book: d.book,
      title: `${d.symbol} not bought (${BOOKS[d.book] || d.book})`, body: cleanNote(d.decision), symbol: d.symbol });
  }
  for (const tr of data.trades) {
    ev.push({ t: tr.time, day: String(tr.time).slice(0, 10), market: tr.market, kind: "order", book: tr.book,
      title: `${tr.side} ${tr.qty} ${tr.symbol} @ ${tr.price ?? "—"} (${BOOKS[tr.book] || tr.book})`, body: cleanNote(tr.reason), symbol: tr.symbol, side: tr.side });
  }
  for (const doc of data.docs) {
    if (doc.kind === "changes") continue;
    ev.push({ t: `${doc.date}T${doc.kind === "report" ? "07:59" : "23:58"}:00`, day: doc.kind === "report" ? dayAfter(doc.date) : doc.date,
      market: doc.market, kind: doc.kind, title: doc.kind === "report" ? `Analyst report (data to ${doc.date})` : "Daily review", href: `/notes/${doc.id}` });
  }
  ev.sort((a, b) => String(b.t).localeCompare(String(a.t)));
  const days = new Map();
  for (const e of ev) {
    if (!days.has(e.day)) days.set(e.day, []);
    days.get(e.day).push(e);
  }
  return [...days.entries()];
}

function dayAfter(d) {
  // an analysis dated D (data to D's close) is acted on the next day; good enough for grouping
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

export const fmt = {
  money: (v, sym = "") => (v == null || v === "" ? "—" : `${sym}${Number(v).toLocaleString("en-IN", { maximumFractionDigits: 2, minimumFractionDigits: 2 })}`),
  num: (v, d = 2) => (v == null || v === "" ? "—" : Number(v).toLocaleString("en-IN", { maximumFractionDigits: d, minimumFractionDigits: d })),
  pct: (v, d = 2) => (v == null || v === "" || Number.isNaN(Number(v)) ? "—" : `${Number(v) > 0 ? "+" : ""}${Number(v).toFixed(d)}%`),
  pp: (v) => (v == null ? "—" : `${v > 0 ? "+" : ""}${Number(v).toFixed(2)} pp`),
  time: (v) => {
    if (!v) return "—";
    const d = new Date(v);
    return Number.isNaN(d.getTime()) ? String(v) : d.toLocaleString("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "Asia/Kolkata" }) + " IST";
  },
  day: (v) => {
    const d = new Date(`${v}T12:00:00Z`);
    return Number.isNaN(d.getTime()) ? v : d.toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short", year: "numeric" });
  },
  tone: (v) => (v == null || Number(v) === 0 ? "" : Number(v) > 0 ? "up" : "down"),
};
