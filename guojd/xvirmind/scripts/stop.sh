#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOGDIR="$ROOT/runs/logs"
for name in taxonomy annotation host; do
  pidfile="$LOGDIR/$name.pid"
  if [[ -f "$pidfile" ]]; then
    pid="$(cat "$pidfile")"
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" || true
    fi
    rm -f "$pidfile"
    echo "stopped $name ($pid)"
  fi
done
