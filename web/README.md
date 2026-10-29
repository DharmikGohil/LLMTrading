# llmtrading/desk: public site

A static Next.js site showing both paper desks: equity against the control
account and the index, every analyst call with sources, every order and
skipped buy, daily reviews and the lesson book.

Data comes from `../public/*.json` (written by `scripts/refresh_dashboard.sh`)
and the markdown notes in `journal/` and `signals*/`. `npm run sync` copies them
into `web/data/`, which is committed, so the site builds without the Python side.

```bash
npm install
npm run dev        # http://localhost:3000
npm run build      # all pages are static
```

## Deploy on Vercel
1. vercel.com → Add New → Project → import `DharmikGohil/LLMTrading`.
2. Framework preset: Next.js. **Root Directory: `web`**. No environment variables.
3. Settings → Git → Production Branch: `ccr-1574bece-7xdh0b` (or merge it into `main`).

Every scheduled desk run pushes fresh `web/data/`, and Vercel redeploys on that push.
