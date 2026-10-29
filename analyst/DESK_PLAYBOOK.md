# Paper desks: playbook for scheduled Claude sessions

Two paper desks run in the cloud through scheduled Claude sessions on the
`main` branch. Each desk has an LLM-reviewed main account and an
"LLM off" control account. The question is whether the LLM review adds anything.

| Desk | Config | Capital | Runs (local exchange time) |
|---|---|---|---|
| **India (NSE)** | `config/india_paper.yaml` | ₹10,00,000 | analyst 07:40 IST (`analyst/PLAYBOOK.md`), **open 09:35**, **midday 12:35**, **close 15:05** |
| **US** | `config/us_paper.yaml` | $10,000 | **open 09:50 New York** (review + trade), **midday 12:50**, **close 15:45** |

State lives in git (`paper/india/`, `paper/us/`) because each run may start in a
fresh container. **Never place real orders; never edit code.**

## 0. Setup (every run)
```bash
cd /home/user/LLMTrading 2>/dev/null || { git clone https://github.com/DharmikGohil/LLMTrading /home/user/LLMTrading && cd /home/user/LLMTrading; }
git fetch origin main && git checkout main && git pull --ff-only origin main
pip install -q pandas numpy pydantic pyyaml python-dotenv requests typer yfinance && pip install -q --no-deps -e .
export INDTRADER_CONFIG=config/us_paper.yaml      # or config/india_paper.yaml for the India desk
indtrader is-trading-day || exit 0                # weekend/holiday on that exchange: do nothing
```
If a previous run left a live `indtrader run` process in this container, stop it first (only one writer per desk).

## Learning loop (read first, every run)
Run `indtrader lessons --market US` (or `India`) before any review. **Confirmed** lessons are rules for your
judgement; **hypotheses** are things to watch for. Lessons can make you more careful or more specific. They never
loosen risk limits, and they never change config numbers (stops, sizing, screen settings). Those change only
after a backtest plus paper evidence, logged in `journal/changes.md`.

## 1. Open run
- **US:** review first. Run `indtrader screen --save` and `indtrader recent-picks`, then `indtrader brief A,B,C`.
  Search the web for the last 7 days of news and **the next earnings date** of each candidate. Apply the red-flag
  rules of `analyst/PLAYBOOK.md` section 3 (US equivalents: SEC/FDA/FTC actions, guidance cuts, downgrade clusters,
  insider selling); earnings within 3 trading days = **Underweight**. Submit each rating with
  `indtrader submit-signal SYMBOL --rating ... --confidence ... --thesis "... (source, date)"`, using the analysis
  date printed by `is-trading-day`.
- **India:** the 07:40 analyst run already reviewed the candidates into `signals/`. If `signals/<date>/` has no
  REPORT.md (the analyst run failed), do the review now following `analyst/PLAYBOOK.md` with
  `INDTRADER_CONFIG=config/analyst.yaml`, then switch back to `config/india_paper.yaml`.
- Then `indtrader trade` (main and control account).

## 2. Midday and close runs
```bash
indtrader monitor            # stops / targets for both accounts
indtrader eod                # close run only: daily equity record
indtrader review             # close run only: graded facts -> journal/daily/<date>-<market>.md
```
**Close run reflection** (after `indtrader review`): open the daily file and replace the Reflection placeholder with
5-10 lines covering:
- what the LLM-reviewed account did differently from the control today, and whether it helped
- each veto whose outcome is now known (from the vetoes table: negative excess = the veto helped)
- any stop-out, and whether the stop was reasonable
- calls that went clearly right or wrong, and why

Then update the lesson book, using facts only:
- a pattern seen again → `indtrader lesson evidence <id> --supports --example "<date> <symbol> <numbers>"`
- a pattern that failed → the same command with `--contradicts`
- a genuinely new pattern → `indtrader lesson add "<specific, testable lesson>" --market US --example "<case>"`

A lesson is confirmed only after 3 supporting cases, and is retired when contradicted.
Never write a lesson from a single day's P&L noise.

## 3. Refresh the public dashboard (every run)
```bash
scripts/refresh_dashboard.sh          # exports both desks into public/*.json and web/data/ (the Next.js site)
```
The public Next.js site (`web/`, hosted on Vercel) rebuilds by itself when step 4 pushes `web/data`.
Dashboard: https://claude.ai/artifact/AVbfJFgz75SiRsSwsd2Wvf (Dashboard type).
For each of `summary positions trades decisions signals equity journal lessons`:
1. Upload `public/<name>.json` with the Artifact tool (`url` = the dashboard, `file_path`, `asset: true`).
   Each JSON file goes in its own call.
2. Read `datasets/<name>` with ArtifactData `get` to get its `version`.
3. ArtifactData `batch` of `update` writes, one per dataset: `source: {kind: "file", url: <new /_blob url>,
   name: "<name>.json"}`, `updated: {at: <now ISO>, by: "Claude (scheduled run)"}`, each pinned with `if_version`.

## 4. Save state
```bash
git add paper signals signals_us public journal web/data && git commit -m "<desk> <run> <date>" && git push origin main
```
Retry the push up to 4 times with 2s/4s/8s/16s backoff on network errors. If the push is rejected because the
branch moved, `git pull --rebase origin main` and push again.

Finish with a 3-line summary: equity of both accounts vs the index, today's trades, anything unusual.
