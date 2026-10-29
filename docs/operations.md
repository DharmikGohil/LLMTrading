# Operations

## The cloud desks

Both paper desks run through scheduled Claude sessions on the `main` branch. No machine of yours needs to be
on, and no LLM API key is used: the analysis runs on a Claude plan.

| Desk | Config | Capital | Runs |
|---|---|---|---|
| India (NSE) | `config/india_paper.yaml` | ₹10,00,000 | analyst 07:40 IST, trade 09:35, monitor 12:35, close 15:05 |
| US | `config/us_paper.yaml` | $10,000 | review + trade 09:50 New York, monitor 12:50, close 15:45 |

> The scheduled runs are **paused** while the Nifty options desk is designed (see [roadmap](roadmap.md)).

Each run follows a playbook:

- [`analyst/PLAYBOOK.md`](../analyst/PLAYBOOK.md): the India morning analyst (screen, brief, red flags,
  ratings, sourced `REPORT.md`; commits only `signals/`).
- [`analyst/DESK_PLAYBOOK.md`](../analyst/DESK_PLAYBOOK.md): every desk run (setup, trading-day check,
  lessons, review, trade, monitor, close review, site refresh, commit).

State is committed to git after every run (`paper/`, `signals*/`, `journal/`, `public/`, `web/data/`), so a
run can start in a fresh container and the history is auditable. Commits are authored as the repository
owner (the playbooks set the git identity).

## Running your own desk

```bash
cp config/config.example.yaml config/config.yaml
indtrader run                      # daily scheduler in IST: analysis, execution, monitoring, end of day
indtrader status                   # funds, positions, today's counters
indtrader halt / indtrader resume  # file-based kill switch, works while `run` is live
```

### Claude as the analyst (no API key)

On the trading machine, use ratings produced by the scheduled analyst instead of running TradingAgents:

```yaml
screen: {index: nifty200, top_n: 10, trend_template: true}
strategy: {signal_mode: hybrid}
shadow_arms: [factor]
signals_dir: signals
signal_sync: git           # git pull before using signals
llm: {signal_source: external}
broker: {name: paper}      # start with paper
```

### TradingAgents (API key)

`cp .env.example .env`, add an LLM provider key, set `llm.signal_source: tradingagents`, then
`indtrader analyze`. `llm.runs: 3` takes a majority vote; disagreement means Hold.

### Vibe-Trading second opinion (optional)

Vibe-Trading ships a top-level `cli` package that clashes with TradingAgents, so it lives in its own
virtualenv:

```bash
scripts/install_vibe.sh            # -> ~/vibe-venv, validates the read-only India committee preset
indtrader vibe-check
```

Set `second_opinion.enabled: true`. In `veto` mode a confident Underweight/Sell blocks a buy; in `confirm`
mode only a confident Buy/Overweight lets it through. Sells and holds are never changed. With
`LANGCHAIN_PROVIDER=claude-cli` it runs on a logged-in Claude CLI without an API key. Never use it in
backtests: its data tools return today's data.

## Site refresh

```bash
scripts/refresh_dashboard.sh       # export both desks -> public/*.json -> web/data/
```

Pushing `web/data/` to `main` redeploys https://llmtrading.dharmikgohil.in on Vercel.

## Secrets

Never commit keys. API keys go in `.env` (git-ignored) or the environment's settings. The SEC tools in
`.claude/skills/` read `SEC_USER_AGENT` or a git-ignored `trader/config.json`.
