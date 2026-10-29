// Formatting helpers shared by server and client components (no Node imports here).
export const RATING_TONE = { Buy: "up", Overweight: "up", Hold: "flat", Underweight: "down", Sell: "down" };

const r0 = (v, d) => { const x = Number(v); return Math.abs(x) < 0.5 * 10 ** -d ? 0 : x; };
const nf = (d) => new Intl.NumberFormat("en-IN", { maximumFractionDigits: d, minimumFractionDigits: d });
export const fmt = {
  money: (v, sym = "", d = 2) => (v == null || v === "" ? "—" : `${Number(v) < 0 ? "−" : ""}${sym}${nf(d).format(Math.abs(Number(v)))}`),
  num: (v, d = 2) => (v == null || v === "" ? "—" : nf(d).format(Number(v))),
  pct: (v, d = 2) => {
    if (v == null || v === "" || Number.isNaN(Number(v))) return "—";
    const x = r0(v, d);
    return `${x > 0 ? "+" : x < 0 ? "−" : ""}${Math.abs(x).toFixed(d)}%`;
  },
  pp: (v) => {
    if (v == null || Number.isNaN(Number(v))) return "—";
    const x = r0(v, 2);
    return `${x > 0 ? "+" : x < 0 ? "−" : ""}${Math.abs(x).toFixed(2)} pp`;
  },
  time: (v, tz = "Asia/Kolkata", label = "IST") => {
    if (!v) return "—";
    const d = new Date(v);
    if (Number.isNaN(d.getTime())) return String(v);
    return `${d.toLocaleString("en-GB", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", hour12: false, timeZone: tz })} ${label}`;
  },
  clock: (v, tz = "Asia/Kolkata") => new Date(v).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", hour12: false, timeZone: tz }),
  day: (v) => {
    const d = new Date(`${v}T12:00:00Z`);
    return Number.isNaN(d.getTime()) ? v : d.toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
  },
  short: (v) => {
    const d = new Date(`${v}T12:00:00Z`);
    return Number.isNaN(d.getTime()) ? v : d.toLocaleDateString("en-GB", { day: "numeric", month: "short", timeZone: "UTC" });
  },
  tone: (v) => (v == null || Number.isNaN(Number(v)) || r0(v, 2) === 0 ? "" : Number(v) > 0 ? "up" : "down"),
};
