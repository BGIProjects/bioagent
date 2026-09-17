#!/usr/bin/env bash
# 仅运行 Workflow 3 宿主鉴定：对 sampleinfo 中尚未完成 W3 的样本执行 Snakemake，并补跑不完整任务。
#
# 用法:
#   bash run_w3_hostid.sh
#   bash run_w3_hostid.sh --yes
#   bash run_w3_hostid.sh --dry-run
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/xvirbench_env.sh"
SAMPLEINFO="${SAMPLEINFO:-${COHORT_DIR}/sampleinfo.txt}"
JOBS="${JOBS_W3:-12}"

SKIP_CONFIRM=false
DRY_RUN=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --yes|-y) SKIP_CONFIRM=true; shift ;;
    --dry-run|-n) DRY_RUN=true; shift ;;
    --batch-id) BATCH_ID="$2"; RUN_DIR="${XVIRBENCH_ROOT}/batches/${BATCH_ID}/workflow_results"; shift 2 ;;
    --run-dir) RUN_DIR="$2"; shift 2 ;;
    *) echo "未知参数: $1" >&2; exit 1 ;;
  esac
done

log() { echo "[$(date '+%F %T')] $*"; }
die() { echo "错误: $*" >&2; exit 1; }

[[ -f "$SAMPLEINFO" ]] || die "找不到样本表: $SAMPLEINFO"

W1_OUT="${RUN_DIR}/workflow1_upstream"
W3_OUT="${RUN_DIR}/workflow3_hostid"
LIST_DIR="${RUN_DIR}/lists"
LOG_DIR="${RUN_DIR}/logs"
W3_SAMPLES="${LIST_DIR}/w3_samples.txt"
mkdir -p "$LIST_DIR" "$LOG_DIR" "${W3_OUT}/logs"

: >"$W3_SAMPLES"
mapfile -t SAMPLE_IDS < <(awk 'NF>=4 && $1!~/^#/{print $2}' "$SAMPLEINFO" | sort -u)
[[ ${#SAMPLE_IDS[@]} -gt 0 ]] || die "sampleinfo 中无有效样本"

for sample_id in "${SAMPLE_IDS[@]}"; do
  r1="${W1_OUT}/merge/${sample_id}/cleanreads_r1.fq"
  r2="${W1_OUT}/merge/${sample_id}/cleanreads_r2.fq"
  contig="${W1_OUT}/assembly/${sample_id}/${sample_id}.contigs.1kb.renamed.fa"
  [[ -s "$r1" && -s "$r2" && -s "$contig" ]] || die "W1 未就绪: $sample_id（需要 merge + assembly）"
  printf '%s\t%s\t%s\t%s\n' "$sample_id" "$r1" "$r2" "$contig" >>"$W3_SAMPLES"
done

PENDING=()
DONE=()
for sample_id in "${SAMPLE_IDS[@]}"; do
  cov="${W3_OUT}/EukaMarker_Mapping/2.filteredcoverage_q0/${sample_id}_coverage.txt"
  blast="${W3_OUT}/EukaMarker_megablast/2.result_filtered/${sample_id}.blastn"
  if [[ -s "$cov" && -s "$blast" ]]; then
    DONE+=("$sample_id")
  else
    PENDING+=("$sample_id")
  fi
done

echo "================================================================================"
echo "W3 宿主鉴定 | batch=${BATCH_ID}"
echo "  样本总数: ${#SAMPLE_IDS[@]}"
echo "  已完成中间结果: ${#DONE[@]} (${DONE[*]:-无})"
echo "  待跑 W3: ${#PENDING[@]} (${PENDING[*]:-无})"
echo "  输出目录: $W3_OUT"
echo "================================================================================"

if ! $SKIP_CONFIRM && ! $DRY_RUN; then
  read -r -p "继续执行 Snakemake W3? [y/N] " ans
  [[ "${ans,,}" == "y" || "${ans,,}" == "yes" ]] || exit 0
fi

SM_ARGS=(
  -s "${WORKFLOWS_ROOT}/workflow3_hostid/Snakefile"
  --configfile "${WORKFLOWS_ROOT}/workflow3_hostid/config/config.yaml"
  --scheduler greedy
  --config "outdir=${W3_OUT}" "samplelist=${W3_SAMPLES}"
  --rerun-incomplete
  -j "$JOBS"
)
$DRY_RUN && SM_ARGS+=(-n)

LOGFILE="${LOG_DIR}/w3_hostid.log"
(
  cd "${WORKFLOWS_ROOT}/workflow3_hostid"
  snakemake "${SM_ARGS[@]}"
) 2>&1 | tee -a "$LOGFILE"

log "W3 运行结束。生成汇总报告: python3 ${SCRIPT_DIR}/build_hostid_report.py --run-dir ${RUN_DIR}"
