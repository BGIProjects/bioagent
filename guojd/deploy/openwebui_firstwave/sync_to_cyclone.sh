#!/usr/bin/env bash
set -euo pipefail
# Copy first-wave overlay into cyclone live Open WebUI / agent.
# Must be run by an account that can write /data/bioagent (currently lihuyang).

SRC="$(cd "$(dirname "$0")" && pwd)/overlay"
DST_AGENT="${DST_AGENT:-/data/bioagent/agent}"
DST_OWUI="${DST_OWUI:-/data/bioagent/open-webui}"
STAMP="$(date +%Y%m%d-%H%M%S)"

if [[ ! -w "$DST_AGENT" || ! -w "$DST_OWUI" ]]; then
  echo "No write access to $DST_AGENT or $DST_OWUI."
  echo "Run this as the cyclone owner (lihuyang), then restart 5173/8080/8001."
  exit 1
fi

mkdir -p "$DST_AGENT.bak.$STAMP" "$DST_OWUI.bak.$STAMP/analysis-src" "$DST_OWUI.bak.$STAMP/analysis-backend"
cp -a "$DST_AGENT"/*.py "$DST_AGENT.bak.$STAMP/" 2>/dev/null || true
cp -a "$DST_OWUI/src/lib/components/analysis" "$DST_OWUI.bak.$STAMP/analysis-src/" 2>/dev/null || true
cp -a "$DST_OWUI/backend/open_webui/routers/analysis.py" "$DST_OWUI.bak.$STAMP/analysis-backend/" 2>/dev/null || true
cp -a "$DST_OWUI/backend/open_webui/utils/analysis_datasets.py" "$DST_OWUI.bak.$STAMP/analysis-backend/" 2>/dev/null || true

rsync -a --exclude '__pycache__/' --exclude '*.pyc' --exclude 'logs/' --exclude 'results/' \
  "$SRC/agent/" "$DST_AGENT/"

mkdir -p "$DST_OWUI/src/lib/components/analysis" "$DST_OWUI/src/lib/apis/analysis" \
  "$DST_OWUI/backend/open_webui/routers" "$DST_OWUI/backend/open_webui/utils"

rsync -a "$SRC/open-webui/src/lib/components/analysis/" "$DST_OWUI/src/lib/components/analysis/"
rsync -a "$SRC/open-webui/src/lib/apis/analysis/" "$DST_OWUI/src/lib/apis/analysis/"
rsync -a "$SRC/open-webui/backend/open_webui/routers/analysis.py" "$DST_OWUI/backend/open_webui/routers/"
rsync -a "$SRC/open-webui/backend/open_webui/utils/analysis_datasets.py" "$DST_OWUI/backend/open_webui/utils/"
rsync -a "$SRC/open-webui/backend/open_webui/utils/analysis_knowledge.py" "$DST_OWUI/backend/open_webui/utils/"

if [[ -f "$SRC/agent/.env.example" && ! -f "$DST_AGENT/.env" ]]; then
  cp "$SRC/agent/.env.example" "$DST_AGENT/.env"
fi

if [[ -f "$DST_AGENT/.env" ]]; then
  grep -q BIOAGENT_WORKFLOW2_SOURCE "$DST_AGENT/.env" || echo 'BIOAGENT_WORKFLOW2_SOURCE=/data/user/guojindan/Projects/Workflows/workflow2_virusid' >> "$DST_AGENT/.env"
  grep -q BIOAGENT_TESTDATA_ROOT "$DST_AGENT/.env" || echo 'BIOAGENT_TESTDATA_ROOT=/data/user/guojindan/Projects/XvirMind/testdata' >> "$DST_AGENT/.env"
  grep -q XVIRMIND_TAXONOMY_MCP "$DST_AGENT/.env" || echo 'XVIRMIND_TAXONOMY_MCP=http://127.0.0.1:8766' >> "$DST_AGENT/.env"
  grep -q XVIRMIND_ANNOTATION_MCP "$DST_AGENT/.env" || echo 'XVIRMIND_ANNOTATION_MCP=http://127.0.0.1:8767' >> "$DST_AGENT/.env"
  sed -i 's#workflow2_virusid_2026db#workflow2_virusid#g' "$DST_AGENT/.env" || true
fi


OWUI_ENV="${OWUI_ENV:-/data/bioagent/env/open-webui.env}"
if [[ -f "$OWUI_ENV" && -w "$OWUI_ENV" ]]; then
  grep -q BIOAGENT_TESTDATA_ROOT "$OWUI_ENV" || echo 'BIOAGENT_TESTDATA_ROOT=/data/user/guojindan/Projects/XvirMind/testdata' >> "$OWUI_ENV"
  grep -q XVIRMIND_TAXONOMY_MCP "$OWUI_ENV" || echo 'XVIRMIND_TAXONOMY_MCP=http://127.0.0.1:8766' >> "$OWUI_ENV"
  grep -q XVIRMIND_ANNOTATION_MCP "$OWUI_ENV" || echo 'XVIRMIND_ANNOTATION_MCP=http://127.0.0.1:8767' >> "$OWUI_ENV"
fi

echo "Synced overlay to cyclone."
echo "Backup: $DST_AGENT.bak.$STAMP and $DST_OWUI.bak.$STAMP"
echo "Restart Open WebUI :5173, backend :8080, adapter :8001."
echo "Keep taxonomy/annotation MCP on :8766/:8767 (xvirmind/scripts/start.sh)."
