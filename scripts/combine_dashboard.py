"""Merge per-market exports (us_*.json, india_*.json) into the dashboard's dataset files."""
import json
import sys
from pathlib import Path

src, dst = Path(sys.argv[1]), Path(sys.argv[2])
dst.mkdir(parents=True, exist_ok=True)
for name in ("summary", "positions", "trades", "decisions", "signals", "equity"):
    rows = []
    for market in ("us", "india"):
        f = src / f"{market}_{name}.json"
        if f.exists():
            rows += json.loads(f.read_text())
    (dst / f"{name}.json").write_text(json.dumps(rows, indent=1))
    print(name, len(rows))
