#!/usr/bin/env bash
# Start the one-minute options monitor (indtrader live) unless it is already running. Paper only.
set -euo pipefail
cd "$(dirname "$0")/.."
pidfile=paper/options/live.pid
if [ -f "$pidfile" ] && kill -0 "$(cat "$pidfile")" 2>/dev/null; then
  echo "live monitor already running (pid $(cat "$pidfile"))"
  exit 0
fi
mkdir -p paper/options
nohup indtrader live >> paper/options/live.log 2>&1 &
echo $! > "$pidfile"
echo "live monitor started (pid $!)"
