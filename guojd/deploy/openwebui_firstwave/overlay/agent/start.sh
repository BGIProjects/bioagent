#!/usr/bin/env bash

AGENT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
if [ -f "$AGENT_DIR/.env" ]; then
    set -a
    . "$AGENT_DIR/.env"
    set +a
fi

AGENT_PORT="${AGENT_PORT:-8001}"
export BIOAGENT_RUN_ROOT="${BIOAGENT_RUN_ROOT:-"/data/runs"}"
export BIOAGENT_WORKFLOW2_SOURCE="${BIOAGENT_WORKFLOW2_SOURCE:-"/data/user/guojindan/Projects/Workflows/workflow2_virusid"}"
export BIOAGENT_TESTDATA_ROOT="${BIOAGENT_TESTDATA_ROOT:-"/data/user/guojindan/Projects/XvirMind/testdata"}"
export XVIRMIND_TAXONOMY_MCP="${XVIRMIND_TAXONOMY_MCP:-"http://127.0.0.1:8766"}"
export XVIRMIND_ANNOTATION_MCP="${XVIRMIND_ANNOTATION_MCP:-"http://127.0.0.1:8767"}"
mkdir -p "$BIOAGENT_RUN_ROOT"
cd "$AGENT_DIR"
exec uvicorn adapter:app --host 127.0.0.1 --port "$AGENT_PORT"
