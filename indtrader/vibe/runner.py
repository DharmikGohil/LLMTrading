"""Run one Vibe-Trading swarm and print the result as JSON.

Executed with Vibe-Trading's own Python interpreter (separate virtualenv), never
imported by indtrader: Vibe-Trading installs top-level packages named `src`,
`backtest` and `cli` that clash with TradingAgents' `cli` package, so the two
cannot share one environment.

Usage:
  <vibe-python> runner.py --preset-file PRESET.yaml --target RELIANCE.NS \
      --market "India (NSE)" --as-of 2026-10-27 [--timeout-min 45]

The last line of stdout is always one JSON object:
  {"ok": true, "status": "completed", "final_report": "...", "run_id": "...", "tokens": {...}}
  {"ok": false, "error": "..."}
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path


def _emit(obj: dict) -> None:
    sys.stdout.write("\n" + json.dumps(obj) + "\n")
    sys.stdout.flush()


def _install_preset(preset_file: Path) -> str:
    """Copy our preset into Vibe-Trading's user preset dir; return its name."""
    from src.swarm.presets import USER_PRESETS_DIR

    USER_PRESETS_DIR.mkdir(parents=True, exist_ok=True)
    dest = USER_PRESETS_DIR / preset_file.name
    if not dest.exists() or dest.read_bytes() != preset_file.read_bytes():
        shutil.copyfile(preset_file, dest)
    return preset_file.stem


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--preset-file", required=True, type=Path)
    ap.add_argument("--target", required=True)
    ap.add_argument("--market", required=True)
    ap.add_argument("--as-of", required=True)
    ap.add_argument("--timeout-min", type=float, default=45)
    ap.add_argument("--check", action="store_true", help="only validate the install and preset")
    args = ap.parse_args(argv)

    try:
        from src.config import load_swarm_agent_config
        from src.config.paths import get_swarm_runs_dir
        from src.swarm.models import RunStatus
        from src.swarm.presets import build_run_from_preset
        from src.swarm.runtime import SwarmRuntime
        from src.swarm.store import SwarmStore
    except Exception as exc:
        _emit({"ok": False, "error": f"Vibe-Trading not importable from {sys.executable}: {exc}"})
        return 2

    variables = {"target": args.target, "market": args.market, "as_of": args.as_of}
    try:
        name = _install_preset(args.preset_file)
        if args.check:
            from src.swarm.task_store import validate_dag

            validate_dag(build_run_from_preset(name, variables).tasks)
            _emit({"ok": True, "status": "checked", "preset": name})
            return 0
        store = SwarmStore(base_dir=get_swarm_runs_dir())
        runtime = SwarmRuntime(store=store, agent_config=load_swarm_agent_config())
        # include_shell_tools=False: workers get only the tools listed in the preset
        run = runtime.start_run(name, variables, include_shell_tools=False)
    except Exception as exc:
        _emit({"ok": False, "error": f"could not start swarm: {exc}"})
        return 1

    deadline = time.monotonic() + args.timeout_min * 60
    current = run
    while time.monotonic() < deadline:
        time.sleep(2)
        loaded = store.load_run(run.id)
        if loaded is not None:
            current = loaded
        if current.status in (RunStatus.completed, RunStatus.failed, RunStatus.cancelled):
            break
    else:
        runtime.cancel_run(run.id)
        _emit({"ok": False, "error": f"swarm timed out after {args.timeout_min} min", "run_id": run.id})
        return 1

    _emit({
        "ok": current.status == RunStatus.completed and bool(current.final_report),
        "status": current.status.value,
        "run_id": current.id,
        "final_report": current.final_report or "",
        "error": None if current.status == RunStatus.completed else f"swarm {current.status.value}",
        "tokens": {"input": current.total_input_tokens, "output": current.total_output_tokens},
        "model": getattr(current, "model", None),
    })
    return 0


if __name__ == "__main__":
    sys.exit(main())
