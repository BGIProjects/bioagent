#!/usr/bin/env bash
# 基于 allsampleinfo.txt 跑 W3：跳过已在 pxy 批次完成的 11 个样本，其余样本执行宿主鉴定。
#
# 用法:
#   bash run_w3_allsamples.sh --dry-run
#   bash run_w3_allsamples.sh --yes
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/xvirbench_env.sh"
ALLSAMPLEINFO="${ALLSAMPLEINFO:-${COHORT_DIR}/allsampleinfo.txt}"
JOBS="${JOBS_W3:-12}"

# 已在 pxy 测试批次完成 W3 的样本（不重跑 H1–H3）
SKIP_SAMPLES=(v61 v64 v67 v70 v73 v76 v78 v79 v82 v85 v88)

SKIP_CONFIRM=false
DRY_RUN=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --yes|-y) SKIP_CONFIRM=true; shift ;;
    --dry-run|-n) DRY_RUN=true; shift ;;
    *) echo "未知参数: $1" >&2; exit 1 ;;
  esac
done

log() { echo "[$(date '+%F %T')] $*"; }
die() { echo "错误: $*" >&2; exit 1; }

is_skipped() {
  local s="$1"
  for x in "${SKIP_SAMPLES[@]}"; do
    [[ "$x" == "$s" ]] && return 0
  done
  return 1
}

[[ -s "$ALLSAMPLEINFO" ]] || die "allsampleinfo.txt 为空或不存在，请先保存文件: $ALLSAMPLEINFO"

W1_PXY="${RUN_DIR}/workflow1_upstream"
W3_OUT="${RUN_DIR}/workflow3_hostid"
LIST_DIR="${RUN_DIR}/lists"
LOG_DIR="${RUN_DIR}/logs"
W3_SAMPLES="${LIST_DIR}/w3_samples_all.txt"
ASM_BASE="/data/user/pengxinyue/Workflows/workflow1_upstream/example/assembly"

mkdir -p "$LIST_DIR" "$LOG_DIR" "${W3_OUT}/logs"
: >"$W3_SAMPLES"

PENDING=()
SKIPPED=()
ERR=0

while read -r sid r1 r2; do
  [[ -z "${sid// }" ]] && continue
  [[ "$sid" =~ ^# ]] && continue

  if is_skipped "$sid"; then
    r1="${W1_PXY}/merge/${sid}/cleanreads_r1.fq"
    r2="${W1_PXY}/merge/${sid}/cleanreads_r2.fq"
    contig="${W1_PXY}/assembly/${sid}/${sid}.contigs.1kb.renamed.fa"
    SKIPPED+=("$sid")
  else
    contig="${ASM_BASE}/${sid}/${sid}.contigs.1kb.renamed.fa"
    [[ -s "$contig" ]] || contig="${ASM_BASE}/${sid}/${sid}.contigs.fa"
    PENDING+=("$sid")
  fi

  if [[ ! -s "$r1" || ! -s "$r2" ]]; then
    echo "缺少 clean reads: $sid" >&2
    ERR=1
    continue
  fi
  if [[ ! -s "$contig" ]]; then
    echo "缺少 assembly: $sid ($contig)" >&2
    ERR=1
    continue
  fi
  printf '%s\t%s\t%s\t%s\n' "$sid" "$r1" "$r2" "$contig" >>"$W3_SAMPLES"
done < <(awk 'NF>=3 && $1!~/^#/{print $1,$2,$3}' "$ALLSAMPLEINFO")

[[ "$ERR" -eq 0 ]] || die "部分样本输入文件缺失，见上方列表"
[[ -s "$W3_SAMPLES" ]] || die "未生成样本列表"
sort -u -k1,1 -o "$W3_SAMPLES" "$W3_SAMPLES"
N_ALL=$(wc -l <"$W3_SAMPLES")

echo "================================================================================"
echo "W3 全样本宿主鉴定 | batch=${BATCH_ID}"
echo "  allsampleinfo 样本数: $N_ALL"
echo "  跳过(已完成): ${#SKIP_SAMPLES[@]} → ${SKIPPED[*]}"
echo "  待跑(新): ${#PENDING[@]}"
echo "  样本表: $W3_SAMPLES"
echo "  输出: $W3_OUT"
echo "================================================================================"

if ! $SKIP_CONFIRM && ! $DRY_RUN; then
  read -r -p "启动 Snakemake（约 ${#PENDING[@]} 个新样本 × H1–H3）? [y/N] " ans
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

LOGFILE="${LOG_DIR}/w3_allsamples.log"
(
  cd "${WORKFLOWS_ROOT}/workflow3_hostid"
  /data/user/guojindan/softwares/xvirmin/bin/snakemake "${SM_ARGS[@]}"
) 2>&1 | tee "$LOGFILE"

if $DRY_RUN; then
  log "dry-run 完成（未执行 Snakemake）。"
  exit 0
fi

log "Snakemake 结束，生成总报告..."
/data/user/guojindan/softwares/xvirmin/bin/python3 "${SCRIPT_DIR}/build_hostid_report.py" \
  --run-dir "$RUN_DIR" \
  --allsampleinfo "$ALLSAMPLEINFO" \
  --skip-samples "${SKIP_SAMPLES[@]}"
