# US paper desk: playbook for scheduled Claude sessions

The US session runs in the Indian night. Three scheduled runs per US trading day,
all on the `ccr-1574bece-7xdh0b` branch with `config/us_paper.yaml` ($10k paper,
hybrid mode, plus an "LLM off" control account):

| Run (New York time) | What |
|---|---|
| **09:50 open** | Review the screen's candidates, submit ratings, trade, refresh the dashboard, save state |
| **12:50 midday** | Monitor stops/targets, refresh the dashboard, save state |
| **15:45 close** | Monitor, end-of-day equity record, refresh the dashboard, save state |

The paper account's state lives in git (`paper/us/`), because each scheduled run
may start in a fresh container. **Never place real orders; never edit code.**

## 0. Setup (every run)
```bash
cd /home/user/LLMTrading 2>/dev/null || { git clone https://github.com/DharmikGohil/LLMTrading /home/user/LLMTrading && cd /home/user/LLMTrading; }
git fetch origin ccr-1574bece-7xdh0b && git checkout ccr-1574bece-7xdh0b && git pull --ff-only origin ccr-1574bece-7xdh0b
pip install -q pandas numpy pydantic pyyaml python-dotenv requests typer yfinance && pip install -q --no-deps -e .
export INDTRADER_CONFIG=config/us_paper.yaml
indtrader is-trading-day || exit 0       # US weekend/holiday: do nothing
```

## 1. Open run (09:50 New York)
1. `indtrader screen --save` and `indtrader recent-picks`: review the top candidates plus recent picks.
2. `indtrader brief A,B,C`: trend, RSI, ATR, the SEPA checklist, relative strength vs the S&P 500.
3. For each stock, search the web for news from the last 7 days and **the next earnings date**. Follow the
   red-flag rules in `analyst/PLAYBOOK.md` section 3 (US equivalents: SEC/FDA/FTC actions, guidance cuts,
   downgrade clusters, insider selling). Earnings within 3 trading days = **Underweight** (binary gap risk).
4. Submit each rating with `indtrader submit-signal SYMBOL --rating ... --confidence ... --thesis "... (source, date)"`.
   Use the analysis date printed by `is-trading-day` (the previous trading day).
5. `indtrader trade`: trades the main and the control account.
6. Refresh the dashboard (section 3), then save state (section 4).

## 2. Midday and close runs
```bash
indtrader monitor            # stops / targets for both accounts
indtrader eod                # close run only: daily equity record
```
Then refresh the dashboard (section 3) and save state (section 4).

## 3. Refresh the public dashboard
```bash
scripts/refresh_dashboard.sh config/us_paper.yaml   # writes public/*.json
```
Dashboard: https://claude.ai/artifact/AVbfJFgz75SiRsSwsd2Wvf (Dashboard type).
For each of `summary positions trades decisions signals equity`:
1. Upload `public/<name>.json` with the Artifact tool (`url` = the dashboard, `file_path`, `asset: true`).
   Each JSON file goes in its own call.
2. Read `datasets/<name>` with ArtifactData `get` to get its `version`.
3. ArtifactData `batch` of `update` writes, one per dataset: `source: {kind: "file", url: <new /_blob url>,
   name: "<name>.json"}`, `updated: {at: <now ISO>, by: "Claude (scheduled run)"}`, each pinned with `if_version`.

## 4. Save state
```bash
git add paper/us signals_us && git commit -m "US paper desk: <run> <date>" && git push origin ccr-1574bece-7xdh0b
```
Retry the push up to 4 times with 2s/4s/8s/16s backoff on network errors. Finish with a 3-line summary:
equity of both accounts, today's trades, anything unusual.
