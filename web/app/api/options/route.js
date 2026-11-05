// Live Nifty option quotes from NSE's public option chain, for the paper desk's open legs.
// GET /api/options?expiry=2026-11-10&legs=CE24450,PE23400  ->  { spot, ts, legs: { CE24450: { bid, ask, ltp } }, at }
// NSE wants a browser-like session cookie, so the first request primes one. Runs in Mumbai (bom1) to stay close to
// NSE. If NSE refuses (it blocks many cloud addresses), the answer is { error } and the page falls back to the
// desk's last synced marks. The CDN caches each answer for 15 s.
export const dynamic = "force-dynamic";
export const preferredRegion = "bom1";

const UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36";
const HEADERS = { "User-Agent": UA, Accept: "application/json, text/plain, */*", "Accept-Language": "en-US,en;q=0.9", Referer: "https://www.nseindia.com/option-chain" };
const MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

let jar = { cookie: "", at: 0 };

async function prime() {
  const r = await fetch("https://www.nseindia.com/option-chain", { headers: { "User-Agent": UA, Accept: "text/html" }, cache: "no-store", signal: AbortSignal.timeout(8000) });
  const set = typeof r.headers.getSetCookie === "function" ? r.headers.getSetCookie() : [r.headers.get("set-cookie") || ""];
  jar = { cookie: set.map((c) => c.split(";")[0]).filter(Boolean).join("; "), at: Date.now() };
}

async function chain(expiry) {
  const d = new Date(`${expiry}T00:00:00Z`);
  const exp = `${String(d.getUTCDate()).padStart(2, "0")}-${MON[d.getUTCMonth()]}-${d.getUTCFullYear()}`;
  const url = `https://www.nseindia.com/api/option-chain-v3?type=Indices&symbol=NIFTY&expiry=${exp}`;
  for (let i = 0; i < 2; i++) {
    if (!jar.cookie || Date.now() - jar.at > 5 * 60 * 1000 || i === 1) await prime();
    const r = await fetch(url, { headers: { ...HEADERS, Cookie: jar.cookie }, cache: "no-store", signal: AbortSignal.timeout(8000) });
    if (r.ok) return (await r.json())?.records;
    if (![401, 403].includes(r.status)) throw new Error(`NSE ${r.status}`);
  }
  throw new Error("NSE refused the session");
}

export async function GET(req) {
  const q = new URL(req.url).searchParams;
  const expiry = q.get("expiry") || "";
  const want = (q.get("legs") || "").split(",").map((x) => x.trim()).filter((x) => /^(CE|PE)\d{4,6}$/.test(x)).slice(0, 12);
  const cache = { "Cache-Control": "public, s-maxage=15, stale-while-revalidate=30" };
  if (!/^\d{4}-\d{2}-\d{2}$/.test(expiry) || !want.length) return Response.json({ error: "bad request" }, { status: 400 });
  try {
    const rec = await chain(expiry);
    const legs = {};
    for (const row of rec?.data || []) {
      for (const kind of ["CE", "PE"]) {
        const key = `${kind}${Math.round(row.strikePrice)}`;
        const o = row[kind];
        if (o && want.includes(key)) legs[key] = { bid: o.buyPrice1 ?? null, ask: o.sellPrice1 ?? null, ltp: o.lastPrice ?? null };
      }
    }
    return Response.json({ spot: rec?.underlyingValue ?? null, ts: rec?.timestamp ?? null, legs, at: Date.now() }, { headers: cache });
  } catch (e) {
    return Response.json({ error: String(e.message || e), at: Date.now() }, { headers: { "Cache-Control": "public, s-maxage=30" } });
  }
}
