# Contributing

Thanks for helping. This project trades (paper) money on its own, so changes are held to a simple rule:
**nothing that touches trading behaviour lands without a test, and nothing that changes strategy numbers
lands without evidence.**

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install            # optional: ruff on every commit
make test lint                # 66 offline tests, ruff
make web                      # the site, http://localhost:3000
```

## Ground rules

- **Tests stay offline.** No network or LLM calls in `tests/`; use the stubs in `tests/conftest.py`.
- **Safety first.** Changes to `engine.py`, `risk.py`, `strategy.py`, `costs.py` or `brokers/` need tests for
  the failure paths (partial fills, rejections, timeouts, kill switches), not just the happy path.
- **Strategy changes need evidence.** Stops, sizing, screen settings and veto thresholds change only with a
  backtest plus paper results, recorded in [`journal/changes.md`](journal/changes.md).
- **The LLM never gets more power.** It may veto or shrink; it must never add positions or raise risk.
- **No secrets.** Keys belong in `.env` or the environment, never in code, config or commits.
- **Desk data is append-only.** Do not rewrite `paper/`, `signals*/` or `journal/` history in a PR.

## Pull requests

1. Branch from `main`, keep the change focused, and describe *why*.
2. `make ci` must pass (lint, tests, skills tests, site build). CI runs the same on every PR.
3. Update the docs in `docs/` when behaviour or commands change, and add a line to `CHANGELOG.md`.

## Style

Python: ruff (`make format`), type hints on public functions, comments only where the code cannot say it.
Site: plain JavaScript, server components by default, no UI frameworks.

## Reporting bugs

Use the issue templates. For anything that could put money at risk (wrong orders, broken stops, leaked
keys), follow [SECURITY.md](SECURITY.md) instead of opening a public issue.
