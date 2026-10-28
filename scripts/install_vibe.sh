#!/usr/bin/env bash
# Install HKUDS/Vibe-Trading into its OWN virtualenv (it cannot share one with
# TradingAgents: both ship a top-level `cli` package), then validate the
# indtrader preset. Usage: scripts/install_vibe.sh [venv-dir]   (default ~/vibe-venv)
set -euo pipefail
VENV="${1:-$HOME/vibe-venv}"
PY="${PYTHON:-python3}"
"$PY" -m venv "$VENV"
"$VENV/bin/pip" install --upgrade pip >/dev/null
"$VENV/bin/pip" install "vibe-trading-ai[anthropic]"
echo
echo "Installed. Set in config/config.yaml:"
echo "  second_opinion: {enabled: true, vibe_python: $VENV/bin/python}"
echo "and in .env the LLM Vibe-Trading should use, e.g.:"
echo "  LANGCHAIN_PROVIDER=anthropic  LANGCHAIN_MODEL_NAME=claude-sonnet-5  ANTHROPIC_API_KEY=..."
echo
cd "$(dirname "$0")/.." && "$VENV/bin/python" indtrader/vibe/runner.py --preset-file indtrader/vibe/indtrader_india_committee.yaml \
  --target RELIANCE.NS --market "India (NSE)" --as-of "$(date +%F)" --check
