# XvirBench

跨批次宏转录组病毒分析的 **比较与编排层**。生信计算由 [Workflows](../Workflows) 下 W1–W7 Snakemake 流程执行；XvirBench 负责批次元数据、结果登记、指标标准化抽取、分组比较分析与报告汇总。

目录规范详见 [docs/DIR.md](docs/DIR.md)。

---

## 设计原则

| 层级 | 职责 | 位置 |
|------|------|------|
| **执行** | fastp、组装、病毒/宿主鉴定、Kraken、定量、建库 benchmark 等 | `Projects/Workflows/workflow{1-7}_*` |
| **比较** | manifest、cohorts、harmonized 表、分析报告 | `Projects/XvirBench/batches/{batch_id}/` |

- 大体积 workflow 输出**不复制**进 XvirBench，经 `workflow_results/` 软链引用
- 单批次 harmonized 表写入 `batches/{id}/harmonized/`；`comparisons/` 仅用于**跨批次**比较
- 每个批次自包含 `cohorts/`，样本元数据以批次目录为准

---

## 一级目录

```
XvirBench/
├── batches/       # 各 benchmark 项目
├── docs/          # 设计文档、schema、目录说明
├── scripts/       # 跨批次通用脚本（抽取、编排、分析）
└── comparisons/   # 跨项目比较（多批次时启用）
```

---

## 批次目录（`batches/{batch_id}/`）

```
batches/{batch_id}/
├── manifest.yaml           # 批次 manifest（样本、workflow 状态、legacy 路径）
├── cohorts/                # sampleinfo、registry、lists/
├── workflow_results/       # W1–W7 结果（软链）
├── harmonized/             # 标准化指标 workflow1/ … workflow7/
├── scripts/                # 批次个性化脚本
└── analysis/               # 分组比较报告、tables、figures
```

---

## 核心工作流

### 1. 指标抽取（harmonized）

从 `workflow_results/` 读取各流程产出，写入 `harmonized/workflowN/*.tsv`：

```bash
cd /data/user/guojindan/Projects/XvirBench/scripts

# 全量
python3 extract_metrics.py --batch-id vazyme_fragment_test --all

# 单流程
python3 extract_metrics.py --batch-id vazyme_fragment_test -w workflow4

# 批次快捷脚本
bash ../batches/vazyme_fragment_test/scripts/extract.sh all
```

实现：`extract_lib.py`（核心）+ `extract_metrics.py`（CLI）。

### 2. 分组比较分析

读 `cohorts/` + `harmonized/`，输出结构化表、图表与 HTML 报告到 `analysis/`：

```bash
python3 analysis/run_analysis.py --batch-id vazyme_fragment_test --all

# 或
bash batches/vazyme_fragment_test/scripts/run_analysis.sh all
```

### 3. 环境变量

```bash
source scripts/xvirbench_env.sh
# BATCH_ID=vazyme_fragment_test
# BATCH_DIR, COHORT_DIR, RUN_DIR, HARMONIZED_DIR
```

---

## 当前批次

| batch_id | 说明 | 状态 |
|----------|------|------|
| [vazyme_fragment_test](batches/vazyme_fragment_test/) | 60 样本（v61–v120），V350399508，三种建库打断 × 三宿主 | W1–W5、W7 完成 |

历史计算目录 `Workflows/benchmark/test/runs/pxy_V350399508/` 通过各批次 `manifest.yaml` 的 `legacy_run_dir` 引用，**不是**独立 XvirBench 批次。

---

## 脚本索引

| 脚本 | 用途 |
|------|------|
| `scripts/extract_metrics.py` | harmonized 指标抽取 |
| `scripts/generate_harmonized_metrics_doc.py` | 再生 `docs/HARMONIZED_METRICS_REFERENCE.md` |
| `scripts/build_harmonized_excel.py` | 从 harmonized 生成 `docs/vazyme_benchmark_metrics.xlsx` |
| `scripts/analysis/run_analysis.py` | 分组比较 + HTML 报告 |
| `scripts/analysis/run_w1_qc_report.py` | W1 上游分阶段 QC 报告（内部/交付） |
| `scripts/xvirbench_env.sh` | 路径环境变量 |
| `scripts/run_w1_to_w5.sh` | W1→W5 编排（legacy） |
| `batches/*/scripts/setup_batch_links.sh` | 重建 workflow_results 软链 |

---

## 相关文档

- [docs/DIR.md](docs/DIR.md) — 目录规范
- [docs/DESIGN.md](docs/DESIGN.md) — 架构设计
- [docs/WORKFLOW_SUMMARY.md](docs/WORKFLOW_SUMMARY.md) — W1–W7 指标说明
- [docs/W1_QC_REPORT_GUIDE.md](docs/W1_QC_REPORT_GUIDE.md) — W1 QC 跨平台复现指南（规范+完整源码）
- [docs/w1_qc_portable/](docs/w1_qc_portable/) — 可移植脚本包（[`w1_qc_portable.tar.gz`](docs/w1_qc_portable.tar.gz)）
- [docs/HARMONIZED_METRICS_REFERENCE.md](docs/HARMONIZED_METRICS_REFERENCE.md) — 已抽取 harmonized 指标字段说明（vazyme_fragment_test 示例）
- [docs/vazyme_benchmark_metrics.xlsx](docs/vazyme_benchmark_metrics.xlsx) — Excel 指标交付表
- [comparisons/README.md](comparisons/README.md) — 跨批次比较约定
- [batches/vazyme_fragment_test/README.md](batches/vazyme_fragment_test/README.md) — 当前主项目概览
