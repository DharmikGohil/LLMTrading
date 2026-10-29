// Copies the desk's data from the repo (written by the scheduled runs) into web/data/,
// so the site builds from web/ alone. On Vercel the parent folders may be absent:
// then the committed web/data/ snapshot is used as is.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const web = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const repo = path.resolve(web, "..");
const out = path.join(web, "data");
fs.mkdirSync(out, { recursive: true });

const publicDir = path.join(repo, "public");
if (!fs.existsSync(publicDir)) {
  console.log("sync-data: repo data not found, using committed web/data snapshot");
  process.exit(0);
}

for (const name of ["summary", "positions", "trades", "decisions", "signals", "equity", "journal", "lessons", "backtests", "research"]) {
  const f = path.join(publicDir, `${name}.json`);
  if (fs.existsSync(f)) fs.copyFileSync(f, path.join(out, `${name}.json`));
}

// full markdown of daily reviews and analyst reports
const docs = [];
const daily = path.join(repo, "journal", "daily");
if (fs.existsSync(daily)) {
  for (const f of fs.readdirSync(daily).filter((x) => x.endsWith(".md"))) {
    const [y, m, d, ...rest] = f.replace(/\.md$/, "").split("-");
    docs.push({ id: `review-${f.replace(/\.md$/, "")}`, kind: "review", date: `${y}-${m}-${d}`,
      market: rest.join("-") === "us" ? "US" : "India", body: fs.readFileSync(path.join(daily, f), "utf8") });
  }
}
for (const [dir, market] of [["signals", "India"], ["signals_us", "US"]]) {
  const root = path.join(repo, dir);
  if (!fs.existsSync(root)) continue;
  for (const day of fs.readdirSync(root)) {
    const rep = path.join(root, day, "REPORT.md");
    if (fs.existsSync(rep)) docs.push({ id: `report-${market.toLowerCase()}-${day}`, kind: "report", date: day, market, body: fs.readFileSync(rep, "utf8") });
  }
}
const changes = path.join(repo, "journal", "changes.md");
if (fs.existsSync(changes)) docs.push({ id: "changes", kind: "changes", date: "", market: "all", body: fs.readFileSync(changes, "utf8") });
docs.sort((a, b) => (b.date || "").localeCompare(a.date || ""));
fs.writeFileSync(path.join(out, "docs.json"), JSON.stringify(docs, null, 1));
fs.writeFileSync(path.join(out, "meta.json"), JSON.stringify({ synced_at: new Date().toISOString() }, null, 1));
console.log(`sync-data: ${docs.length} documents, data -> web/data`);
