#!/usr/bin/env bash
# Export every configured market's accounts and merge them into public/ for the dashboard.
# Usage: scripts/refresh_dashboard.sh [config ...]   (default: config/us_paper.yaml)
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p public/raw
cfgs=("$@"); [ ${#cfgs[@]} -eq 0 ] && cfgs=(config/us_paper.yaml config/india_paper.yaml)
for cfg in "${cfgs[@]}"; do
  INDTRADER_CONFIG="$cfg" indtrader export-dashboard --out public/raw 2>/dev/null | tail -n +1
done
python3 scripts/combine_dashboard.py public/raw public >/dev/null
echo "dashboard data in public/: $(ls public/*.json | tr '\n' ' ')"
