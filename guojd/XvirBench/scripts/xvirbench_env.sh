# XvirBench 公共路径（由编排脚本 source）
XVIRBENCH_ROOT="${XVIRBENCH_ROOT:-/data/user/guojindan/Projects/XvirBench}"
WORKFLOWS_ROOT="${WORKFLOWS_ROOT:-/data/user/guojindan/Projects/Workflows}"
BATCH_ID="${BATCH_ID:-vazyme_fragment_test}"
BATCH_DIR="${BATCH_DIR:-${XVIRBENCH_ROOT}/batches/${BATCH_ID}}"
COHORT_DIR="${COHORT_DIR:-${BATCH_DIR}/cohorts}"
RUN_DIR="${RUN_DIR:-${BATCH_DIR}/workflow_results}"
HARMONIZED_DIR="${HARMONIZED_DIR:-${BATCH_DIR}/harmonized}"
# 兼容旧变量名
if [[ ! -d "$RUN_DIR" && -d "${BATCH_DIR}/runs" ]]; then
  RUN_DIR="${BATCH_DIR}/runs"
fi
