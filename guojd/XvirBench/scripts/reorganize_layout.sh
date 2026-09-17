#!/usr/bin/env bash
# 一次性迁移至新目录规范（见 docs/DIR.md）
set -euo pipefail

ROOT="/data/user/guojindan/Projects/XvirBench"
LEGACY_PXY="/data/user/guojindan/Projects/Workflows/benchmark/test/runs/pxy_V350399508"

cd "$ROOT"

mkdir -p docs/schema comparisons
mkdir -p batches/pxy_V350399508/{cohorts,workflow_results,harmonized,scripts,analysis}
mkdir -p batches/vazyme_fragment_test/{harmonized,analysis}

# --- docs ---
for f in DESIGN.md; do
  [[ -f "$f" && ! -f "docs/$f" ]] && mv "$f" "docs/$f"
done
[[ -d schema && ! -d docs/schema/samples_registry.example.tsv ]] && \
  cp -a schema/. docs/schema/ 2>/dev/null || true
[[ -f schema/samples_registry.example.tsv ]] && cp -f schema/samples_registry.example.tsv docs/schema/ 2>/dev/null || true

# --- 全局 cohorts → pxy 批次 cohorts（共享模板保留在 docs）---
mkdir -p docs/cohorts
if [[ -d cohorts ]]; then
  cp -an cohorts/. batches/pxy_V350399508/cohorts/ 2>/dev/null || cp -a cohorts/. batches/pxy_V350399508/cohorts/
  cp -an cohorts/. docs/cohorts/
  # 保留顶层 cohorts 为软链，兼容旧脚本
  rm -rf cohorts
  ln -s batches/pxy_V350399508/cohorts cohorts
fi

# --- pxy_V350399508：由整目录软链改为标准子目录 ---
if [[ -L batches/pxy_V350399508 ]]; then
  rm batches/pxy_V350399508
  mkdir -p batches/pxy_V350399508/{cohorts,workflow_results,harmonized,scripts,analysis}
fi
if [[ ! -f batches/pxy_V350399508/manifest.yaml && -f batches/pxy_V350399508.yaml ]]; then
  cp batches/pxy_V350399508.yaml batches/pxy_V350399508/manifest.yaml
fi
for wf in workflow1_upstream workflow2_virusid workflow3_hostid workflow4_kraken_bracken workflow5_virus_quantification; do
  dst="batches/pxy_V350399508/workflow_results/$wf"
  [[ -e "$dst" ]] || ln -s "$LEGACY_PXY/$wf" "$dst"
done
[[ -d "$LEGACY_PXY/reports" ]] && ln -sfn "$LEGACY_PXY/reports" batches/pxy_V350399508/analysis

# --- vazyme_fragment_test ---
VAZ_BATCH="batches/vazyme_fragment_test"
if [[ -d "$VAZ_BATCH/runs" && ! -d "$VAZ_BATCH/workflow_results" ]]; then
  mv "$VAZ_BATCH/runs" "$VAZ_BATCH/workflow_results"
fi
if [[ -d "$VAZ_BATCH/reports" && ! -d "$VAZ_BATCH/analysis" ]]; then
  mv "$VAZ_BATCH/reports" "$VAZ_BATCH/analysis"
fi
mkdir -p "$VAZ_BATCH/cohorts/lists"
if [[ -d "$VAZ_BATCH/lists" && ! -L "$VAZ_BATCH/lists" ]]; then
  shopt -s dotglob nullglob
  for f in "$VAZ_BATCH/lists"/*; do
    base=$(basename "$f")
    [[ -e "$VAZ_BATCH/cohorts/lists/$base" ]] || mv "$f" "$VAZ_BATCH/cohorts/lists/"
  done
  rmdir "$VAZ_BATCH/lists" 2>/dev/null || rm -rf "$VAZ_BATCH/lists"
fi
[[ ! -e "$VAZ_BATCH/lists" ]] && ln -s cohorts/lists "$VAZ_BATCH/lists"
mkdir -p "$VAZ_BATCH/workflow_results/logs"
if [[ -d "$VAZ_BATCH/logs" && ! -L "$VAZ_BATCH/logs" ]]; then
  shopt -s dotglob nullglob
  for f in "$VAZ_BATCH/logs"/*; do
    base=$(basename "$f")
    [[ -e "$VAZ_BATCH/workflow_results/logs/$base" ]] || mv "$f" "$VAZ_BATCH/workflow_results/logs/"
  done
  rmdir "$VAZ_BATCH/logs" 2>/dev/null || true
fi
[[ ! -e "$VAZ_BATCH/logs" ]] && ln -s workflow_results/logs "$VAZ_BATCH/logs"
[[ -f "$VAZ_BATCH/COMPUTATION_PLAN.md" ]] && \
  mv "$VAZ_BATCH/COMPUTATION_PLAN.md" "$VAZ_BATCH/analysis/COMPUTATION_PLAN.md"

# --- harmonized：按批次拆分 ---
python3 "$ROOT/scripts/split_harmonized_by_batch.py"

# 顶层 harmonized → comparisons 聚合视图（软链 + README）
if [[ -d harmonized && ! -L harmonized ]]; then
  mkdir -p comparisons/harmonized_aggregate
  for f in harmonized/*.tsv; do
    [[ -f "$f" ]] && mv "$f" "comparisons/harmonized_aggregate/$(basename "$f")"
  done
  rm -rf harmonized/extracted 2>/dev/null || true
  rmdir harmonized 2>/dev/null || rm -rf harmonized
fi
[[ ! -e harmonized ]] && ln -s comparisons/harmonized_aggregate harmonized

echo "Layout migration done."
