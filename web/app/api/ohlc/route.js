// Daily candles for the price chart, from Yahoo Finance's chart endpoint.
// GET /api/ohlc?s=India:HAL&range=2y  ->  { bars: [{ t, o, h, l, c, v }], symbol, currency, at }
// The CDN caches each answer for 5 minutes during the day, so Yahoo sees few requests however many people watch.
export const dynamic = "force-dynamic";

const KEY = /^(US|India):\^?[A-Z0-9&.\-]{1,20}$/;
const RANGES = new Set(["6mo", "1y", "2y", "5y"]);

export async function GET(req) {
  const q = new URL(req.url).searchParams;
  const key = q.get("s") || "";
  const range = RANGES.has(q.get("range")) ? q.get("range") : "2y";
  if (!KEY.test(key)) return Response.json({ error: "bad symbol" }, { status: 400 });
  const [mk, sym] = key.split(":");
  const ticker = sym.startsWith("^") || mk === "US" ? sym : `${sym}.NS`;
  try {
    const url = `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(ticker)}?interval=1d&range=${range}`;
    const r = await fetch(url, { headers: { "User-Agent": "Mozilla/5.0 (llmtrading desk)" }, cache: "no-store", signal: AbortSignal.timeout(8000) });
    if (!r.ok) throw new Error(`Yahoo ${r.status}`);
    const res = (await r.json())?.chart?.result?.[0];
    const ts = res?.timestamp || [];
    const qd = res?.indicators?.quote?.[0] || {};
    const bars = [];
    for (let i = 0; i < ts.length; i++) {
      const o = qd.open?.[i], h = qd.high?.[i], l = qd.low?.[i], c = qd.close?.[i];
      if ([o, h, l, c].some((x) => x == null)) continue;
      bars.push({ t: ts[i] * 1000, o, h, l, c, v: qd.volume?.[i] ?? 0 });
    }
    return Response.json({ bars, symbol: sym, currency: res?.meta?.currency ?? null, at: Date.now() },
      { headers: { "Cache-Control": "public, s-maxage=300, stale-while-revalidate=600" } });
  } catch (e) {
    return Response.json({ error: String(e.message || e), bars: [] }, { headers: { "Cache-Control": "public, s-maxage=60" } });
  }
}
