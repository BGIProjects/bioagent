#!/usr/bin/env bash
# Workflow3 V3：按样本指定门（taxfilter）运行宿主鉴定，结果写入
#   workflow3_hostid/by_sample_v3/<sample_id>/
# 不修改/删除根目录下既有 final_results.xlsx、depths.txt 等批次结果。
#
# 用法:
#   python3 build_hostid_manifest.py
#   bash run_w3_v3_per_sample.sh --dry-run
#   bash run_w3_v3_per_sample.sh --yes
#   bash run_w3_v3_per_sample.sh --yes --only-missing   # 仅跑尚无结果的样本
#   bash run_w3_v3_per_sample.sh --yes --samples v91,v92
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/xvirbench_env.sh"
MANIFEST="${MANIFEST:-${COHORT_DIR}/hostid_sample_manifest.tsv}"
W3_ROOT="${W3_ROOT:-${RUN_DIR}/workflow3_hostid}"
SHARED_W3="${W3_ROOT}"
OUT_BASE="${W3_ROOT}/by_sample_v3"
LOG_DIR="${W3_ROOT}/logs"
WORKFLOWS_ROOT="${WORKFLOWS_ROOT:-/data/user/guojindan/Projects/Workflows}"
PYTHON="${PYTHON:-/data/user/guojindan/softwares/xvirmin/bin/python}"
SUMMARIZE="${SUMMARIZE:-/data/user/guojindan/Databases/EukaMarker_information/result_summarize_V3.py}"
TAXONOMY="/data/user/guojindan/Databases/EukaMarker_information/full.csv"
TAXONOMY_CN="/data/user/guojindan/Databases/EukaMarker_information/yunnan_speciesindex.xlsx"
COVERAGE_CUTOFF="${COVERAGE_CUTOFF:-40}"

SKIP_CONFIRM=false
DRY_RUN=false
ONLY_MISSING=false
SAMPLE_FILTER=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --yes|-y) SKIP_CONFIRM=true; shift ;;
    --dry-run|-n) DRY_RUN=true; shift ;;
    --only-missing) ONLY_MISSING=true; shift ;;
    --samples) SAMPLE_FILTER="$2"; shift 2 ;;
    *) echo "未知参数: $1" >&2; exit 1 ;;
  esac
done

log() { echo "[$(date '+%F %T')] $*"; }
die() { echo "错误: $*" >&2; exit 1; }

[[ -s "$MANIFEST" ]] || die "请先生成: python3 ${SCRIPT_DIR}/build_hostid_manifest.py"

mkdir -p "$OUT_BASE" "$LOG_DIR"
[[ -s "$SHARED_W3/depths.txt" && -s "$SHARED_W3/blastresult.full.txt" ]] || \
  die "共享中间文件缺失，请先完成批次 W3 H1–H4: $SHARED_W3"

should_run_sample() {
  local sn="$1"
  if [[ -n "$SAMPLE_FILTER" ]]; then
    local found=0
    IFS=',' read -ra _slist <<< "$SAMPLE_FILTER"
    for x in "${_slist[@]}"; do
      [[ "$x" == "$sn" ]] && found=1 && break
    done
    [[ "$found" -eq 1 ]] || return 1
  fi
  if $ONLY_MISSING; then
    [[ -s "$OUT_BASE/$sn/HostIdentification_result.xlsx" ]] && return 1
  fi
  return 0
}

N_TOTAL=0
N_RUN=0
while IFS=$'\t' read -r sn fq1 fq2 assembly host host_type phylum taxfilter; do
  [[ "$sn" == "sn" ]] && continue
  N_TOTAL=$((N_TOTAL + 1))
  should_run_sample "$sn" || continue
  N_RUN=$((N_RUN + 1))
done < "$MANIFEST"

echo "================================================================================"
echo "W3 V3 按样本宿主鉴定（指定门）"
echo "  样本表: $MANIFEST"
echo "  共享 H4: $SHARED_W3/{depths,blastresult.full}.txt"
echo "  每样本输出: $OUT_BASE/<sn>/"
echo "  计划运行: $N_RUN / $N_TOTAL"
echo "================================================================================"

if ! $SKIP_CONFIRM && ! $DRY_RUN; then
  read -r -p "继续? [y/N] " ans
  [[ "${ans,,}" == "y" || "${ans,,}" == "yes" ]] || exit 0
fi

MASTER_LOG="${LOG_DIR}/w3_v3_per_sample.log"
: >"$MASTER_LOG"

while IFS=$'\t' read -r sn fq1 fq2 assembly host host_type phylum taxfilter; do
  [[ "$sn" == "sn" ]] && continue
  should_run_sample "$sn" || continue

  OUT="${OUT_BASE}/${sn}"
  mkdir -p "$OUT"

  log "[$sn] host=$host_type phylum=$phylum taxfilter=$taxfilter -> $OUT" | tee -a "$MASTER_LOG"

  if $DRY_RUN; then
    continue
  fi

  awk -v s="$sn" 'BEGIN{FS=OFS="\t"} $1==s' "$SHARED_W3/depths.txt" > "$OUT/depths.txt"
  awk -v s="$sn" 'BEGIN{FS=OFS="\t"} $1==s' "$SHARED_W3/blastresult.full.txt" > "$OUT/blastresult.full.txt"

  if [[ ! -s "$OUT/depths.txt" || ! -s "$OUT/blastresult.full.txt" ]]; then
    log "  [$sn] 共享文件中无数据，尝试单样本 Snakemake H1–H5..." | tee -a "$MASTER_LOG"
    LIST="${OUT}/samples.txt"
    printf '%s\t%s\t%s\t%s\n' "$sn" "$fq1" "$fq2" "$assembly" >"$LIST"
    (
      cd "${WORKFLOWS_ROOT}/workflow3_hostid"
      snakemake -s Snakefile \
        --configfile config/config.yaml \
        --scheduler greedy \
        --config "outdir=${OUT}" "samplelist=${LIST}" "hostid.taxfilter=${taxfilter}" \
        -j 4
    ) >> "${LOG_DIR}/w3_v3_${sn}.log" 2>&1
    continue
  fi

  META="${OUT}/samples.txt"
  printf '%s\t%s\t%s\t%s\n' "$sn" "$fq1" "$fq2" "$assembly" >"$META"

  "$PYTHON" "$SUMMARIZE" \
    --coverage "$OUT/depths.txt" \
    --blast "$OUT/blastresult.full.txt" \
    --metadata "$META" \
    --taxonomy "$TAXONOMY" \
    --taxonomy-chinese "$TAXONOMY_CN" \
    --taxfilter "$taxfilter" \
    --coverage-cutoff "$COVERAGE_CUTOFF" \
    --extract-marker-seqs \
    -o "$OUT" >> "${LOG_DIR}/w3_v3_${sn}.log" 2>&1

  log "  [$sn] 完成 -> $OUT/HostIdentification_result.xlsx" | tee -a "$MASTER_LOG"
done < "$MANIFEST"

if $DRY_RUN; then
  log "dry-run 结束"
  exit 0
fi

log "汇总合并表..."
"$PYTHON" "${SCRIPT_DIR}/merge_hostid_v3_reports.py" \
  --manifest "$MANIFEST" \
  --by-sample-dir "$OUT_BASE" \
  --output-dir "${W3_ROOT}/reports" \
  2>&1 | tee -a "$MASTER_LOG"

log "全部完成。根目录历史结果未改动；新结果见 $OUT_BASE"
