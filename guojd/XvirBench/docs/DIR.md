# XvirBench 目录规范

> 最后更新：2026-05-26

---

## 一级目录

```
XvirBench/
├── README.md          # 项目入口（保留于根目录）
├── batches/           # 各 benchmark 项目（批次）
├── docs/              # 设计文档、schema、共享 cohort 模板
├── scripts/           # 标准化编排与抽取脚本（跨批次通用）
└── comparisons/       # 跨项目比较配置与聚合视图
```

| 目录 | 职责 |
|------|------|
| `batches/` | 每个子目录对应一个项目/批次，含元数据、流程结果引用、标准化表、分析报告 |
| `docs/` | `DESIGN.md`、分析计划、目录说明、`schema/`、共享 cohort 模板 |
| `scripts/` | `run_w1_to_w5.sh`、`extract_metrics.py`、`extract_io.py` 等 |
| `comparisons/` | 跨批次 join 配置、`harmonized_aggregate/` 聚合 TSV（可选） |

**不在一级目录的内容：**

- 大体积 workflow 输出仍落盘于 `Workflows/benchmark/test/runs/` 或项目自有目录，经 `workflow_results/` 软链引用
- 顶层 `cohorts/`、`harmonized/` 为**兼容软链**（分别指向 pxy 批次 cohorts 与 comparisons 聚合表）

---

## 二级目录（`batches/{batch_id}/`）

```
batches/{batch_id}/
├── manifest.yaml              # 批次 manifest（必需）
├── cohorts/                   # 样本/分组元数据、registry、输入列表
│   ├── sampleinfo.*
│   ├── samples_registry.tsv
│   └── lists/                 # Snakemake 样本列表等
├── workflow_results/          # 各 workflow 计算结果（软链为主）
│   ├── workflow1_upstream/
│   ├── workflow2_virusid/
│   ├── workflow3_hostid/
│   ├── workflow4_kraken_bracken/
│   ├── workflow5_virus_quantification/
│   ├── workflow7/             # 或 workflow7_fragmentation_benchmark/
│   └── logs/                  # 流程运行日志
├── harmonized/                # 标准化指标表（按 workflow 编号）
│   ├── workflow1/             # TSV 表 + workflow1_extracted.json
│   ├── workflow2/
│   └── ...
├── scripts/                   # 本批次个性化脚本
└── analysis/                  # 图表、Excel/Markdown 报告、计算计划
```

### 各子目录说明

| 子目录 | 内容 |
|--------|------|
| `cohorts/` | 样本表、分组信息、hostid manifest、`samples_registry.tsv` |
| `workflow_results/` | W1–W7 原始/流程输出；**不复制大文件**，使用绝对路径软链 |
| `harmonized/` | `extract_metrics.py` 产出的 TSV/parquet，按 `workflow1`…`workflow7` 分子目录 |
| `scripts/` | 如 `setup_batch_links.sh`、`run_phase1_w4_and_extract.sh` |
| `analysis/` | benchmark Excel、分组比较报告、图表、`COMPUTATION_PLAN.md` |

### 兼容软链（批次根目录，可选）

运行中的任务可能仍引用旧路径，批次内保留：

- `lists` → `cohorts/lists`
- `logs` → `workflow_results/logs`

---

## 当前批次

| batch_id | workflow_results 主路径 | 说明 |
|----------|-------------------------|------|
| `vazyme_fragment_test` | W1/W3/W4 软链至 `legacy_run_dir` + vazyme 按宿主 W2/W5/W7 | 60 样本（V350399508） |

`legacy_run_dir` = `Workflows/benchmark/test/runs/pxy_V350399508`（历史计算目录，非独立 XvirBench 批次）。

---

## 常用路径变量（`scripts/xvirbench_env.sh`）

```bash
XVIRBENCH_ROOT=/data/user/guojindan/Projects/XvirBench
BATCH_ID=vazyme_fragment_test
BATCH_DIR=$XVIRBENCH_ROOT/batches/$BATCH_ID
COHORT_DIR=$BATCH_DIR/cohorts
RUN_DIR=$BATCH_DIR/workflow_results      # 流程结果
HARMONIZED_DIR=$BATCH_DIR/harmonized     # 标准化表
```

---

## 迁移与维护

```bash
# 重建 vazyme 批次 workflow_results 软链
bash batches/vazyme_fragment_test/scripts/setup_batch_links.sh

# 抽取 harmonized（写入 batches/{id}/harmonized/workflowN/）
python3 scripts/extract_metrics.py --batch-id vazyme_fragment_test \
  --batch-yaml batches/vazyme_fragment_test/manifest.yaml
```
