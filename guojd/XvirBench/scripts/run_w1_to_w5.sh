#!/usr/bin/env bash
# 自动化运行 Workflow 1→5（上游 → 病毒鉴定/宿主/Kraken → 病毒定量）
# 样本表: XvirBench/cohorts/sampleinfo.txt  (run_id  sample_id  fq1  fq2)
#
# 用法:
#   bash run_w1_to_w5.sh                    # 生成配置并询问确认后运行
#   bash run_w1_to_w5.sh --dry-run          # 仅准备文件 + snakemake -n
#   bash run_w1_to_w5.sh --yes              # 跳过确认（慎用）
#   bash run_w1_to_w5.sh --prepare-only     # 只生成列表与配置，不运行
#   bash run_w1_to_w5.sh --from-w2 --yes    # 跳过 W1，从 W2 续跑（需 W1 已完成）
#   bash run_w1_to_w5.sh --from-w3 --yes    # 跳过 W1–W2，从 W3 续跑
#   bash run_w1_to_w5.sh --from-w4 --yes    # 跳过 W1–W3，从 W4 续跑
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=xvirbench_env.sh
source "${SCRIPT_DIR}/xvirbench_env.sh"
SAMPLEINFO="${SAMPLEINFO:-${COHORT_DIR}/sampleinfo.txt}"

JOBS_W1="${JOBS_W1:-16}"
JOBS_W2="${JOBS_W2:-32}"
JOBS_W3="${JOBS_W3:-12}"
JOBS_W4="${JOBS_W4:-16}"
JOBS_W5="${JOBS_W5:-8}"

DRY_RUN=false
SKIP_CONFIRM=false
PREPARE_ONLY=false
FROM_W2=false
FROM_W3=false
FROM_W4=false
RERUN_INCOMPLETE=false

usage() {
  sed -n '2,12p' "$0"
  echo ""
  echo "环境变量: SAMPLEINFO BATCH_ID RUN_DIR JOBS_W1..JOBS_W5"
  exit "${1:-0}"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help) usage 0 ;;
    --dry-run) DRY_RUN=true; shift ;;
    --yes|-y) SKIP_CONFIRM=true; shift ;;
    --prepare-only) PREPARE_ONLY=true; shift ;;
    --from-w2) FROM_W2=true; RERUN_INCOMPLETE=true; shift ;;
    --from-w3) FROM_W3=true; RERUN_INCOMPLETE=true; shift ;;
    --from-w4) FROM_W4=true; RERUN_INCOMPLETE=true; shift ;;
    --sampleinfo) SAMPLEINFO="$2"; shift 2 ;;
    --batch-id) BATCH_ID="$2"; RUN_DIR="${XVIRBENCH_ROOT}/batches/${BATCH_ID}/workflow_results"; shift 2 ;;
    --run-dir) RUN_DIR="$2"; shift 2 ;;
    *) echo "未知参数: $1" >&2; usage 1 ;;
  esac
done

log() { echo "[$(date '+%F %T')] $*"; }
die() { echo "错误: $*" >&2; exit 1; }

# W2 部分规则会 cd 到 wdir 后执行 ../scripts/xxx.py，因此需在 RUN_DIR 下提供 scripts 链接
prepare_w2_scripts_link() {
  local link="${RUN_DIR}/scripts"
  local target="${WORKFLOWS_ROOT}/workflow2_virusid/scripts"
  [[ -d "$target" ]] || die "W2 scripts 目录不存在: $target"
  ln -sfn "$target" "$link"
  log "W2 scripts 链接: $link -> $target"
}

[[ -f "$SAMPLEINFO" ]] || die "找不到样本表: $SAMPLEINFO"
[[ -s "$SAMPLEINFO" ]] || die "样本表为空，请先在编辑器中保存: $SAMPLEINFO"

# ---------- 解析 sampleinfo（列: run_id  sample_id  fq1  fq2，空白分隔）----------
LIST_DIR="${RUN_DIR}/lists"
LOG_DIR="${RUN_DIR}/logs"
W1_OUT="${RUN_DIR}/workflow1_upstream"
W2_OUT="${RUN_DIR}/workflow2_virusid"
W3_OUT="${RUN_DIR}/workflow3_hostid"
W4_OUT="${RUN_DIR}/workflow4_kraken_bracken"
W5_OUT="${RUN_DIR}/workflow5_virus_quantification"

mkdir -p "$LIST_DIR" "$LOG_DIR"

W1_SAMPLES="${LIST_DIR}/w1_samples.txt"
W2_CONTIGS="${LIST_DIR}/w2_contigs_list.txt"
W3_SAMPLES="${LIST_DIR}/w3_samples.txt"
W4_SAMPLES="${LIST_DIR}/w4_samples.txt"
W5_SAMPLES="${LIST_DIR}/w5_samples.txt"

: >"$W1_SAMPLES"
RUN_COUNT=0
MISSING_FQ=()

while read -r run_id sample_id fq1 fq2; do
  [[ -z "${run_id// }" ]] && continue
  [[ "$run_id" =~ ^# ]] && continue
  printf '%s\t%s\t%s\t%s\n' "$run_id" "$sample_id" "$fq1" "$fq2" >>"$W1_SAMPLES"
  RUN_COUNT=$((RUN_COUNT + 1))
  for f in "$fq1" "$fq2"; do
    [[ -f "$f" ]] || MISSING_FQ+=("$f")
  done
done < <(awk 'NF>=4 && $1 !~ /^#/ {print $1,$2,$3,$4}' "$SAMPLEINFO")

[[ "$RUN_COUNT" -gt 0 ]] || die "样本表为空: $SAMPLEINFO"

mapfile -t SAMPLE_IDS < <(awk '{print $2}' "$W1_SAMPLES" | sort -u)
SAMPLE_COUNT=${#SAMPLE_IDS[@]}
[[ "$SAMPLE_COUNT" -gt 0 ]] || die "未解析到 sample_id"

# ---------- 基于 W1 预期输出生成 W2–W5 列表 ----------
for sample_id in "${SAMPLE_IDS[@]}"; do
  contig="${W1_OUT}/assembly/${sample_id}/${sample_id}.contigs.1kb.renamed.fa"
  r1="${W1_OUT}/merge/${sample_id}/cleanreads_r1.fq"
  r2="${W1_OUT}/merge/${sample_id}/cleanreads_r2.fq"
  printf '%s\t%s\n' "$sample_id" "$contig" >>"$W2_CONTIGS"
  printf '%s\t%s\t%s\t%s\n' "$sample_id" "$r1" "$r2" "$contig" >>"$W3_SAMPLES"
  printf '%s\t%s\t%s\n' "$sample_id" "$r1" "$r2" >>"$W4_SAMPLES"
  printf '%s\t%s\t%s\n' "$sample_id" "$r1" "$r2" >>"$W5_SAMPLES"
done

sort -o "$W2_CONTIGS" "$W2_CONTIGS"
sort -u -k1,1 -o "$W3_SAMPLES" "$W3_SAMPLES"
sort -u -k1,1 -o "$W4_SAMPLES" "$W4_SAMPLES"
sort -u -k1,1 -o "$W5_SAMPLES" "$W5_SAMPLES"

W2_VIRAL_REF="${W2_OUT}/downstream/sequences/putative_viralcontigs/putative_viralcontigs.fna"

# ---------- 打印运行计划 ----------
echo "================================================================================"
echo " Workflows W1→W5 自动化运行计划"
echo "================================================================================"
echo " 批次 ID     : $BATCH_ID"
echo " 样本表     : $SAMPLEINFO"
echo " 输出根目录 : $RUN_DIR"
echo " 测序 run 数: $RUN_COUNT"
echo " 生物学样本 : $SAMPLE_COUNT  →  ${SAMPLE_IDS[*]:-（无）}"
echo "--------------------------------------------------------------------------------"
echo " 步骤与线程:"
echo "   W1 上游预处理     jobs=$JOBS_W1   → $W1_OUT"
echo "   W2 病毒鉴定       jobs=$JOBS_W2   → $W2_OUT"
echo "   W3 宿主鉴定       jobs=$JOBS_W3   → $W3_OUT"
echo "   W4 Kraken/Bracken jobs=$JOBS_W4   → $W4_OUT"
echo "   W5 病毒定量       jobs=$JOBS_W5   → $W5_OUT"
echo "              (参考序列: W2 putative_viralcontigs.fna)"
echo "--------------------------------------------------------------------------------"
echo " 已生成列表:"
echo "   $W1_SAMPLES"
echo "   $W2_CONTIGS"
echo "   $W3_SAMPLES / $W4_SAMPLES / $W5_SAMPLES"
echo "================================================================================"

if [[ ${#MISSING_FQ[@]} -gt 0 ]]; then
  echo ""
  echo "警告: 下列 FASTQ 不存在（共 ${#MISSING_FQ[@]} 个）:"
  printf '  %s\n' "${MISSING_FQ[@]:0:10}"
  [[ ${#MISSING_FQ[@]} -gt 10 ]] && echo "  ... 其余省略"
  echo ""
fi

if $PREPARE_ONLY; then
  log "仅准备模式，已退出。"
  exit 0
fi

# ---------- 运行前确认 ----------
if ! $SKIP_CONFIRM; then
  echo ""
  read -r -p "确认开始运行？输入 yes 继续，其他键取消: " ans
  if [[ "$ans" != "yes" ]]; then
    echo "已取消。可使用 --prepare-only 仅生成列表，或 --yes 跳过确认。"
    exit 0
  fi
fi

run_snakemake() {
  local name="$1" workdir="$2" snakefile="$3" configfile="$4"
  shift 4
  local extra_config=("$@")
  local logfile="${LOG_DIR}/${name}.log"
  local sm_args=(
    -s "$snakefile"
    --configfile "$configfile"
    --scheduler greedy
    "${extra_config[@]}"
    -j "$jobs"
  )
  if $RERUN_INCOMPLETE; then
    sm_args+=(--rerun-incomplete)
  fi
  if $DRY_RUN; then
    sm_args=(-n "${sm_args[@]}")
  fi
  log ">>> $name  (cwd=$workdir)  日志: $logfile"
  (
    cd "$workdir"
    snakemake "${sm_args[@]}" 2>&1 | tee "$logfile"
  )
}

# 检查 W1 组装产物
check_w1_outputs() {
  for sample_id in "${SAMPLE_IDS[@]}"; do
    c="${W1_OUT}/assembly/${sample_id}/${sample_id}.contigs.1kb.renamed.fa"
    [[ -s "$c" ]] || die "W1 未生成 contigs: $c"
  done
}

if $FROM_W4; then
  FROM_W3=true
  FROM_W2=true
elif $FROM_W3; then
  FROM_W2=true
fi

W3_FINAL="${W3_OUT}/final_results.xlsx"

if $FROM_W4; then
  log "跳过 W1–W3（--from-w4），检查已有产物..."
  check_w1_outputs
  [[ -f "$W2_VIRAL_REF" ]] || die "W2 未生成病毒参考序列: $W2_VIRAL_REF"
  [[ -f "$W3_FINAL" ]] || die "W3 未生成宿主鉴定结果: $W3_FINAL"
  log "W1/W2/W3 产物检查通过（${SAMPLE_COUNT} 个样本）。"
elif $FROM_W3; then
  log "跳过 W1–W2（--from-w3），检查已有产物..."
  check_w1_outputs
  [[ -f "$W2_VIRAL_REF" ]] || die "W2 未生成病毒参考序列: $W2_VIRAL_REF"
  log "W1/W2 产物检查通过（${SAMPLE_COUNT} 个样本）。"
elif $FROM_W2; then
  log "跳过 W1（--from-w2），检查已有上游结果..."
  check_w1_outputs
  log "W1 产物检查通过（${SAMPLE_COUNT} 个样本）。"
else
  # ---------- W1 ----------
  jobs=$JOBS_W1
  run_snakemake "w1_upstream" \
    "${WORKFLOWS_ROOT}/workflow1_upstream" \
    "${WORKFLOWS_ROOT}/workflow1_upstream/Snakefile" \
    "${WORKFLOWS_ROOT}/workflow1_upstream/config/config.yaml" \
    --config "output_dir=${W1_OUT}" "sample_list=${W1_SAMPLES}"

  if $DRY_RUN; then
    log "dry-run 完成（未执行 W2–W5）。"
    exit 0
  fi

  check_w1_outputs
  log "W1 完成，已检查 ${SAMPLE_COUNT} 个样本的 contigs。"
fi

if $DRY_RUN; then
  prepare_w2_scripts_link
  log "dry-run：将从 W2 开始检查 DAG。"
  jobs=$JOBS_W2
  run_snakemake "w2_virusid" \
    "${WORKFLOWS_ROOT}/workflow2_virusid" \
    "${WORKFLOWS_ROOT}/workflow2_virusid/Snakefile" \
    "${WORKFLOWS_ROOT}/workflow2_virusid/config/config.yaml" \
    --config "wdir=${W2_OUT}" "input_list=${W2_CONTIGS}"
  exit 0
fi

# ---------- W2 ----------
if ! $FROM_W3; then
  prepare_w2_scripts_link
  jobs=$JOBS_W2
  run_snakemake "w2_virusid" \
    "${WORKFLOWS_ROOT}/workflow2_virusid" \
    "${WORKFLOWS_ROOT}/workflow2_virusid/Snakefile" \
    "${WORKFLOWS_ROOT}/workflow2_virusid/config/config.yaml" \
    --config "wdir=${W2_OUT}" "input_list=${W2_CONTIGS}"

  [[ -f "$W2_VIRAL_REF" ]] || die "W2 未生成病毒参考序列: $W2_VIRAL_REF（W5 需要此文件）"
  log "W2 完成，病毒参考: $W2_VIRAL_REF"
else
  log "跳过 W2，使用已有参考: $W2_VIRAL_REF"
fi

# ---------- W3 & W4（顺序执行，避免同时占满 IO）----------
if ! $FROM_W4; then
  jobs=$JOBS_W3
  run_snakemake "w3_hostid" \
    "${WORKFLOWS_ROOT}/workflow3_hostid" \
    "${WORKFLOWS_ROOT}/workflow3_hostid/Snakefile" \
    "${WORKFLOWS_ROOT}/workflow3_hostid/config/config.yaml" \
    --config "outdir=${W3_OUT}" "samplelist=${W3_SAMPLES}"
else
  log "跳过 W3，使用已有结果: $W3_FINAL"
fi

jobs=$JOBS_W4
run_snakemake "w4_kraken" \
  "${WORKFLOWS_ROOT}/workflow4_kraken_bracken" \
  "${WORKFLOWS_ROOT}/workflow4_kraken_bracken/Snakefile" \
  "${WORKFLOWS_ROOT}/workflow4_kraken_bracken/config/config.yaml" \
  --config "outdir=${W4_OUT}" "sample_list=${W4_SAMPLES}"

# ---------- W5 ----------
jobs=$JOBS_W5
run_snakemake "w5_quant" \
  "${WORKFLOWS_ROOT}/workflow5_virus_quantification" \
  "${WORKFLOWS_ROOT}/workflow5_virus_quantification/Snakefile" \
  "${WORKFLOWS_ROOT}/workflow5_virus_quantification/config/config.yaml" \
  --config "outdir=${W5_OUT}" "sample_list=${W5_SAMPLES}" "reference_fasta=${W2_VIRAL_REF}"

log "全部完成。主要结果:"
echo "  W1 assembly : ${W1_OUT}/assembly/"
echo "  W2 summary  : ${W2_OUT}/summary/"
echo "  W3 host     : ${W3_OUT}/final_results.xlsx"
echo "  W4 kraken   : ${W4_OUT}/results/summary/"
echo "  W5 RPM      : ${W5_OUT}/results/summary/rpm.csv"
