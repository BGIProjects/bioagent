#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
HOST="${XVIRMIND_HOST:-127.0.0.1}"
WEB_PORT="${XVIRMIND_WEB_PORT:-3080}"
TAX_PORT="${XVIRMIND_TAXONOMY_PORT:-8766}"
ANN_PORT="${XVIRMIND_ANNOTATION_PORT:-8767}"
LOGDIR="$ROOT/runs/logs"
mkdir -p "$LOGDIR" "$ROOT/runs"

stop_pid() {
  local pidfile="$1"
  if [[ -f "$pidfile" ]]; then
    local pid
    pid="$(cat "$pidfile")"
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" || true
      sleep 0.4
    fi
    rm -f "$pidfile"
  fi
}

stop_pid "$LOGDIR/taxonomy.pid"
stop_pid "$LOGDIR/annotation.pid"
stop_pid "$LOGDIR/host.pid"

python3 -m uvicorn xvirmind.mcp.taxonomy_server:app --host "$HOST" --port "$TAX_PORT" --log-level warning \
  >"$LOGDIR/taxonomy.log" 2>&1 & echo $! >"$LOGDIR/taxonomy.pid"

python3 -m uvicorn xvirmind.mcp.annotation_server:app --host "$HOST" --port "$ANN_PORT" --log-level warning \
  >"$LOGDIR/annotation.log" 2>&1 & echo $! >"$LOGDIR/annotation.pid"

python3 -m uvicorn xvirmind.host.app:app --host "$HOST" --port "$WEB_PORT" --log-level warning \
  >"$LOGDIR/host.log" 2>&1 & echo $! >"$LOGDIR/host.pid"

sleep 1
echo "XvirMind v1.1 started"
echo "  Web / Host     http://$HOST:$WEB_PORT/"
echo "  Taxonomy MCP   http://$HOST:$TAX_PORT/mcp   (health /health)"
echo "  Annotation MCP http://$HOST:$ANN_PORT/mcp   (health /health)"
echo "  Logs           $LOGDIR"
