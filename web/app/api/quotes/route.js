// Live quotes for the site, from Yahoo Finance's chart endpoint.
// GET /api/quotes?s=US:AAPL,India:HAL,India:^NSEI  ->  { quotes: { "US:AAPL": { p, pc, t } }, at }
// The CDN caches each answer for 10 s, so Yahoo sees one request per 10 s however many people watch.
export const dynamic = "force-dynamic";

const KEY = /^(US|India):\^?[A-Z0-9&.\-]{1,20}$/;
const yahoo = (k) => {
  const [mk, sym] = k.split(":");
  return sym.startsWith("^") || mk === "US" ? sym : `${sym}.NS`;
};

async function quote(k) {
  const url = `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(yahoo(k))}?interval=1d&range=1d`;
  const r = await fetch(url, { headers: { "User-Agent": "Mozilla/5.0 (llmtrading desk)" }, cache: "no-store", signal: AbortSignal.timeout(6000) });
  if (!r.ok) return null;
  const m = (await r.json())?.chart?.result?.[0]?.meta;
  if (!m || m.regularMarketPrice == null) return null;
  return { p: m.regularMarketPrice, pc: m.chartPreviousClose ?? m.previousClose ?? null, t: (m.regularMarketTime ?? 0) * 1000 };
}

export async function GET(req) {
  const keys = [...new Set((new URL(req.url).searchParams.get("s") || "").split(",").map((x) => x.trim()).filter((x) => KEY.test(x)))].slice(0, 60);
  const out = {};
  await Promise.all(keys.map(async (k) => {
    try {
      const q = await quote(k);
      if (q) out[k] = q;
    } catch {}
  }));
  return Response.json({ quotes: out, at: Date.now() }, {
    headers: { "Cache-Control": "public, s-maxage=10, stale-while-revalidate=20" },
  });
}
