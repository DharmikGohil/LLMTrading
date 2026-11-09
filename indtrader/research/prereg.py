"""Pre-registration and the trial ledger (docs/test-plan.md, P0-B).

Every test writes its hypothesis, exact rule, data, costs, variants and pass/fail lines to
research/prereg/<id>.json and commits it BEFORE any test-period result is computed. A study script calls
`require_committed(id)` before it touches the test period: it refuses if the file is missing, not committed, or
changed since its commit. Every run, design or test, appends one row to research/trials.csv with `log_trial`, so the
deflated Sharpe can count every try.
"""

from __future__ import annotations

import csv
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PREREG = ROOT / "research" / "prereg"
TRIALS = ROOT / "research" / "trials.csv"
TRIAL_COLS = ["time", "commit", "test", "variant", "period", "asset", "kind", "n", "metric", "value", "t", "note"]

# Crypto periods (docs/test-plan.md section 1.0): design up to 2022, test 2023 to the fixed end date, run once.
CRYPTO_DESIGN_END = "2022-12-31"
CRYPTO_TEST_START = "2023-01-01"
CRYPTO_TEST_END = "2026-10-31"


class NotPreregistered(RuntimeError):
    pass


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=False).stdout.strip()


def load(test_id: str) -> dict:
    f = PREREG / f"{test_id}.json"
    if not f.exists():
        raise NotPreregistered(f"{f} does not exist: write and commit the pre-registration first")
    return json.loads(f.read_text())


def require_committed(test_id: str) -> dict:
    """The pre-registration, if it is committed and unchanged since; otherwise refuse to run the test period."""
    rel = f"research/prereg/{test_id}.json"
    spec = load(test_id)
    if not _git("log", "-1", "--format=%H", "--", rel):
        raise NotPreregistered(f"{rel} is not committed: commit it before running the test period")
    if _git("status", "--porcelain", "--", rel):
        raise NotPreregistered(f"{rel} has uncommitted changes: the rules cannot change after registration")
    spec["_registered_commit"] = _git("log", "-1", "--format=%H", "--", rel)
    spec["_registered_at"] = _git("log", "-1", "--format=%cI", "--", rel)
    return spec


def log_trial(test: str, variant: str, period: str, metric: str, value: float | None, *, t: float | None = None,
              n: int | None = None, asset: str = "crypto", kind: str = "test", note: str = "") -> None:
    """Append one row to the trial ledger. kind: design | test | exploratory | past (variants tried before P0-B)."""
    TRIALS.parent.mkdir(parents=True, exist_ok=True)
    new = not TRIALS.exists()
    with TRIALS.open("a", newline="") as fh:
        w = csv.DictWriter(fh, TRIAL_COLS)
        if new:
            w.writeheader()
        w.writerow({"time": datetime.now(UTC).isoformat(timespec="seconds"), "commit": _git("rev-parse", "--short", "HEAD"),
                    "test": test, "variant": variant, "period": period, "asset": asset, "kind": kind,
                    "n": "" if n is None else n, "metric": metric,
                    "value": "" if value is None else round(float(value), 6),
                    "t": "" if t is None else round(float(t), 3), "note": note})


def trial_count(asset: str = "crypto") -> int:
    """Distinct (test, variant) pairs tried for an asset class: the n_trials for the deflated Sharpe."""
    if not TRIALS.exists():
        return 0
    rows = list(csv.DictReader(TRIALS.open()))
    return len({(r["test"], r["variant"]) for r in rows if r["asset"] == asset})
