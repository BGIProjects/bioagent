# W1 上游数据质量报告 — 跨平台复现指南（含完整脚本）

> **文档版本**：2.2（最新版报告规范 + 可移植包 + 完整源码）  
> **阈值版本**：1.0  
> **参考实现**：`w1_qc_portable/`；厦大批量报告脚本为 `scripts/generate_batch_qc_reports.py`  
> **目标**：将本目录拷到任意平台，按相同输入规范运行，得到与现行最新版一致的 W1 下机-QC-组装 HTML 报告。

---

## 0. 最快上手（其他平台）

### 0.1 拷贝什么

二选一：

1. 整个目录 `docs/w1_qc_portable/`
2. 或解压 `docs/w1_qc_portable.tar.gz`

```bash
tar -xzf w1_qc_portable.tar.gz
cd w1_qc_portable
pip install -r requirements.txt
```

### 0.2 准备批次目录

```text
my_batch/
├── cohorts/sampleinfo.tsv          # 或根目录 sampleinfo.tsv
├── harmonized/workflow1/
│   ├── qc_upstream_run.tsv
│   └── qc_upstream_sample.tsv
└── workflow_results/workflow1_upstream/   # 可选，提供 fastp.json 时剔除原因更全
    └── filter/<run_id>/01_fastp.json
```

也可用扁平布局：把两个 `qc_upstream_*.tsv` 和 `sampleinfo.tsv` 直接放在 `my_batch/` 根目录。

### 0.3 运行

```bash
python run_w1_qc_report.py \
  --batch-id my_batch \
  --batch-dir /path/to/my_batch \
  --host rat \
  --out-dir /path/to/my_batch/analysis/w1_qc_rat
```

输出：`report_internal.html`、`report_delivery.html`、`report_delivery.md`、`tables/`、`figures/fig01–fig04.png`（HTML 图已 Base64 内嵌，可离线打开）。厦大项目批量生成时输出到 `outputs/批次下机与QC组装报告_YYYYMMDD/`，每个批次一个 HTML，并同步输出标准化 TSV 明细表。

在 XvirBench 仓库内仍可用原命令：

```bash
python3 scripts/analysis/run_w1_qc_report.py --batch-id vazyme_fragment_test --host rat
```

---

## 1. 依赖

```text
pandas>=1.5
numpy>=1.22
matplotlib>=3.6
seaborn>=0.12
Python >= 3.9
```

可选中文字体（报告 HTML 用系统字体；图默认 Arial/DejaVu）。

---

## 2. 输入字段与规范摘要

### 2.1 sampleinfo.tsv

| 列 | 必需 | 说明 |
|----|------|------|
| id | 是 | 数字 ID → sample_id=`v{id}` |
| sn | 建议 | 样本名 |
| host | 是 | `--host` 过滤键 |
| method | 是 | 建库方法代码 |
| fq1/fq2 | 否 | 路径可不填 |

内置方法代码（可在 `plot_meta.py` / `cohort.py` 扩展）：

- `cDNA_Frag_30C5Min`
- `RNA_Frag_85C6Min`
- `RNA_Frag_94C7Min`

### 2.2 计量

| 类型 | 规则 |
|------|------|
| reads | Mb（÷1e6），2 位小数 |
| bases | Gb（÷1e9），2 位小数 |
| 比例 | %（×100），2 位小数 |
| 整数 | 千分位 |

### 2.3 关键口径

| 指标 | 公式 |
|------|------|
| fastp 保留率 | after/before（分母 raw） |
| rRNA 保留率 | `clean_r1 / fastp_r1`（分母 **fastp**，非 raw） |
| 低深度 | R1 &lt; 5 Mb |
| `contigs_ge1kb_n` | ≥1 kb contig **条数** |
| `contigs_ge1kb_bp` | ≥1 kb contig **总碱基**（报告 Gb） |

### 2.4 评分（见 `w1_qc/standards.py`）

- 权重：S3 深度 30%、S1 25%、S2 15%、S4 30%
- 优≥3.5 / 良≥3.0 / 可接受≥2.0 / 需关注≥1.0 / 否则不建议下游
- 批次通过：≥80% 良及以上，且不建议下游 ≤10%

详细阈值表见报告内嵌「评分标准」章节或源码 `scoring_doc.py`。

### 2.5 图件（仅此 4 张）

| 文件 | 内容 |
|------|------|
| fig01_stage_yield.png | 各阶段 R1 reads / bases |
| fig02_fastp_qc.png | fastp 保留率、重复率及可用过滤指标；若源表含剔除原因，则展示剔除组成 |
| fig03_rrna_qc.png | rRNA 保留率 + Post-rRNA 深度 |
| fig04_assembly.png | 2×2：散点、条数、平均长度、≥1kb% |

最新版要求：

- 每个报告固定保留 fig01-fig04 四个图位；如果某阶段缺少可绘图字段，不删除图件章节，而是在对应图位显示“当前批次未提供字段”的说明。
- 如果没有有效分组信息，所有样本按“整体”绘图，不再因为缺少分组字段导致图件缺失。
- 图表采用白底、简洁坐标轴、无衬线字体和 SCI 汇报风格配色；避免过度装饰。
- 图件标题、章节标题和摘要中的单位必须一致：reads=Mb，bases=Gb，比例=%。

### 2.6 执行摘要最新版模板

每个 HTML 报告只保留正文 `1. 执行摘要` 中的一段完整摘要；项目抬头或摘要框只放批次评价、样本数、等级分布、低深度样本、需关注样本和阶段完整性，不再重复整段摘要。

推荐句式如下，缺失字段按“当前源表未提供……”描述，不把缺失阶段视为失败：

```text
本批次共评估{样本类型} {样本数} 个（{批次ID}）。以样本为单位汇总各 lane 后，单样本原始 reads 中位数为 {median} Mb（范围 {min}-{max} Mb），原始碱基量中位数为 {median} Gb（范围 {min}-{max} Gb），原始 Q30 中位数为 {median}%。
fastp 后样本级 reads 保留率中位数为 {median}%（{min}%-{max}%），fastp 后 Q30 中位数为 {median}%。剔除 reads 的主要来源为「{主要来源}」；若源表未拆分剔除原因，则写明“当前源表未拆分到具体原因”。
rRNA 去除后平均保留率为 {mean}%（中位数 {median}%），样本级 Post-rRNA R1 深度中位数为 {median} Mb（范围 {min}-{max} Mb；本批次与 merge/clean 结果一致）。
de novo 组装 ≥1 kb contig 中位数为 {median} 条（范围 {min}-{max} 条）。
综合评级：优 {n} 个、良 {n} 个、可接受 {n} 个、需关注 {n} 个、不建议下游 {n} 个；批次总体达到批次质控要求/需结合缺失阶段或关注样本复核。低深度样本（Post-rRNA R1 < 5 Mb）：{样本列表或无}。需重点关注：{样本列表或无}。
```

### 2.7 厦大批量报告生成要求

`scripts/generate_batch_qc_reports.py` 是当前厦大合作项目的批量报告入口，需遵守以下规则：

- 自动扫描并整理候鸟、天津粪便测试、媒介蚊虫、V350399514 和媒介鼠蜱相关批次。
- 每个批次独立生成 HTML，章节顺序固定为：执行摘要、S0 原始数据、S1 fastp、S2 rRNA 去除、S3 样本汇总/加测合并、S4 组装、样本综合 QC、评分标准、图件、附录。
- 阶段缺失只标记“未提供/未完成”，不作为失败处理。
- 低深度阈值固定为 Post-rRNA R1 < 5 Mb。
- 报告末尾必须附带免责声明：本结果仅限科研实验室内部参考，不得作为临床诊断或公共卫生干预的直接决策依据。

---

## 3. 文件清单（可移植包）

```text
w1_qc_portable/
├── run_w1_qc_report.py      # CLI 入口
├── requirements.txt
├── cohort.py                # sampleinfo 加载 + LOW_DEPTH
├── plot_meta.py             # 方法名/颜色
├── SAMPLEINFO.example.tsv
└── w1_qc/
    ├── __init__.py
    ├── standards.py         # 阈值
    ├── units.py             # Mb/Gb/% 格式
    ├── compute.py           # 统计与打分
    ├── plots.py             # 作图
    ├── reports.py           # HTML/MD
    ├── narrative.py         # 文字摘要
    └── scoring_doc.py       # 评分说明块
```

---

## 4. 与 XvirBench 仓库内脚本的关系

| 仓库路径 | 可移植包 |
|----------|----------|
| `scripts/analysis/run_w1_qc_report.py` | `run_w1_qc_report.py`（增加 `--batch-dir`） |
| `scripts/analysis/w1_qc/*` | `w1_qc/*` |
| `scripts/analysis/cohort.py` | `cohort.py` |
| `plot_styles.py`（配色） | `plot_meta.py` |

跨平台请用**可移植包**，不要依赖 `XvirBench/batches/...` 硬编码路径。

---

## 5. 完整源码附录

下列源码与 `docs/w1_qc_portable/` **逐字一致**（生成时自动嵌入）。拷贝附录即可重建整个工具包。


### A. `requirements.txt`

```text
pandas>=1.5
numpy>=1.22
matplotlib>=3.6
seaborn>=0.12
```

### A. `run_w1_qc_report.py`

```python
#!/usr/bin/env python3
"""
W1 上游 QC 报告（可移植版）。

用法（目录模式，推荐跨平台）:
  python run_w1_qc_report.py --batch-dir /path/to/batch --host rat

batch-dir 需包含:
  cohorts/sampleinfo.tsv  或  sampleinfo.tsv
  harmonized/workflow1/qc_upstream_run.tsv + qc_upstream_sample.tsv
    或根目录下同名 TSV
  可选: workflow_results/workflow1_upstream/filter/<run>/01_fastp.json

兼容 XvirBench:
  python run_w1_qc_report.py --batch-id vazyme_fragment_test --host rat
  （需在 XvirBench 仓库根目录运行，或同时给 --batch-dir）
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from w1_qc.compute import run_w1_qc_pipeline


def main() -> None:
    ap = argparse.ArgumentParser(description="W1 上游 QC 报告（portable）")
    ap.add_argument("--batch-id", default="batch", help="批次名（写入报告元数据）")
    ap.add_argument("--batch-dir", type=Path, default=None, help="批次根目录（跨平台必填）")
    ap.add_argument("--wf1-dir", type=Path, default=None, help="workflow1_upstream 结果目录（可选）")
    ap.add_argument("--out-dir", type=Path, default=None, help="输出目录（默认 batch-dir/analysis/w1_qc_<host>）")
    ap.add_argument("--host", default="rat", help="rat / tick / mosquito / all")
    args = ap.parse_args()
    host = None if args.host == "all" else args.host
    if args.batch_dir is None and not (Path.cwd() / "batches" / args.batch_id).is_dir():
        ap.error("请提供 --batch-dir，或在 XvirBench 仓库根目录使用 --batch-id")
    result = run_w1_qc_pipeline(
        args.batch_id,
        host=host,
        batch_dir=args.batch_dir,
        wf1_dir=args.wf1_dir,
        out_dir=args.out_dir,
    )
    print(f"W1 QC 完成: {result.out_dir}")
    print(f"  样本数: {result.batch_summary['n_samples']}")
    print(f"  批次通过: {result.batch_summary['batch_pass']}")
    print(f"  等级分布: {result.batch_summary['rating_counts']}")
    for k in ("report_internal.html", "report_delivery.html", "report_delivery.md"):
        p = result.out_dir / k
        if p.exists():
            print(f"  {k}: {p}")


if __name__ == "__main__":
    main()
```

### A. `cohort.py`

```python
"""加载批次 cohort 元数据。"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

METHOD_ORDER = ["cDNA_Frag_30C5Min", "RNA_Frag_85C6Min", "RNA_Frag_94C7Min"]
METHOD_LABEL = {
    "cDNA_Frag_30C5Min": "cDNA 30°C 5min",
    "RNA_Frag_85C6Min": "RNA 85°C 6min",
    "RNA_Frag_94C7Min": "RNA 94°C 7min",
}
HOST_ORDER = ["rat", "tick", "mosquito"]
LOW_DEPTH_READS = 5_000_000


def load_sampleinfo(cohort_dir: Path) -> pd.DataFrame:
    path = cohort_dir / "sampleinfo.tsv"
    if not path.is_file():
        raise FileNotFoundError(path)
    df = pd.read_csv(path, sep="\t")
    df["sample_id"] = "v" + df["id"].astype(str)
    df["method"] = pd.Categorical(df["method"], categories=METHOD_ORDER, ordered=True)
    df["method_label"] = df["method"].map(METHOD_LABEL)
    df["host"] = pd.Categorical(df["host"], categories=HOST_ORDER, ordered=True)
    return df


def cohort_overview(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for meth in METHOD_ORDER:
        sub = df[df["method"] == meth]
        for host in HOST_ORDER:
            h = sub[sub["host"] == host]
            rows.append(
                {
                    "method": meth,
                    "method_label": METHOD_LABEL[meth],
                    "host": host,
                    "n": len(h),
                    "sample_ids": ",".join(sorted(h["sample_id"])),
                }
            )
    return pd.DataFrame(rows)
```

### A. `plot_meta.py`

```python
"""Method labels/colors for portable W1 QC (no XvirBench dependency)."""
METHOD_ORDER = ["cDNA_Frag_30C5Min", "RNA_Frag_85C6Min", "RNA_Frag_94C7Min"]
METHOD_LABEL = {
    "cDNA_Frag_30C5Min": "cDNA 30°C 5min",
    "RNA_Frag_85C6Min": "RNA 85°C 6min",
    "RNA_Frag_94C7Min": "RNA 94°C 7min",
}
METHOD_COLORS = {
    "cDNA_Frag_30C5Min": "#66c2a5",
    "RNA_Frag_94C7Min": "#fc8d62",
    "RNA_Frag_85C6Min": "#8da0cb",
}
HOST_ORDER = ["rat", "tick", "mosquito"]
HOST_LABEL = {"rat": "大鼠", "tick": "蜱", "mosquito": "蚊虫"}
```

### A. `SAMPLEINFO.example.tsv`

```tsv
id	sn	host	method	fq1	fq2
61	SAMPLE_A	rat	cDNA_Frag_30C5Min	.	.
62	SAMPLE_B	rat	RNA_Frag_85C6Min	.	.
```

### A. `w1_qc/__init__.py`

```python
"""W1 upstream QC report package."""
from .compute import run_w1_qc_pipeline

__all__ = ["run_w1_qc_pipeline"]
```

### A. `w1_qc/standards.py`

```python
"""W1 QC thresholds and rating logic."""
from __future__ import annotations

from typing import Literal

THRESHOLD_VERSION = "1.0"

Grade = Literal["A", "B", "C", "D", "F"]
OverallRating = Literal["优", "良", "可接受", "需关注", "不建议下游"]

GRADE_SCORE = {"A": 4, "B": 3, "C": 2, "D": 1, "F": 0}
GRADE_LABEL = {4: "A", 3: "B", 2: "C", 1: "D", 0: "F"}

STAGE_WEIGHTS = {
    "S3_depth": 0.30,
    "S1_quality": 0.25,
    "S2_rrna": 0.15,
    "S4_assembly": 0.30,
}


def _tier(value: float, cutoffs: list[float], higher_is_better: bool = True) -> Grade:
    labels: list[Grade] = ["A", "B", "C", "D", "F"]
    if higher_is_better:
        for i, lo in enumerate(cutoffs):
            if value >= lo:
                return labels[i]
        return "F"
    for i, hi in enumerate(cutoffs):
        if value <= hi:
            return labels[i]
    return "F"


def grade_merge_depth(reads: float) -> Grade:
    return _tier(reads / 1e6, [15, 10, 5, 2])


def grade_fastp_retention(rate: float) -> Grade:
    return _tier(rate, [0.85, 0.80, 0.70, 0.60])


def grade_q30(q30: float) -> Grade:
    return _tier(q30, [0.92, 0.90, 0.85, 0.80])


def grade_duplication(dup: float) -> Grade:
    return _tier(dup, [0.15, 0.20, 0.30, 0.40], higher_is_better=False)


def grade_rrna_retention(rate: float) -> Grade:
    if 0.75 <= rate <= 0.98:
        return "A"
    if 0.65 <= rate <= 0.99:
        return "B"
    if 0.50 <= rate <= 0.99:
        return "C"
    if 0.40 <= rate <= 0.99:
        return "D"
    return "F"


def grade_contigs_ge1kb(n: float) -> Grade:
    return _tier(n, [8000, 5000, 3000, 1000])


def grade_s1_combined(retention: float, q30: float, dup: float) -> Grade:
    scores = [
        GRADE_SCORE[grade_fastp_retention(retention)],
        GRADE_SCORE[grade_q30(q30)],
        GRADE_SCORE[grade_duplication(dup)],
    ]
    return GRADE_LABEL[round(sum(scores) / len(scores))]  # type: ignore


def overall_rating(weighted_score: float) -> OverallRating:
    if weighted_score >= 3.5:
        return "优"
    if weighted_score >= 3.0:
        return "良"
    if weighted_score >= 2.0:
        return "可接受"
    if weighted_score >= 1.0:
        return "需关注"
    return "不建议下游"


def batch_pass(ratings: list[str]) -> bool:
    n = len(ratings) or 1
    good = sum(1 for r in ratings if r in ("优", "良"))
    bad = sum(1 for r in ratings if r == "不建议下游")
    return good / n >= 0.8 and bad / n <= 0.1
```

### A. `w1_qc/units.py`

```python
"""Read/base units and display formatting for W1 QC."""
from __future__ import annotations

from typing import Any

import pandas as pd

READ_DIVISOR = 1e6
READ_SUFFIX = "Mb"
BASE_DIVISOR = 1e9
BASE_SUFFIX = "Gb"

READ_COLS = {
    "reads_before", "reads_after_fastp", "reads_removed_fastp", "raw_reads_sum",
    "reads_before_sum", "reads_after_fastp_sum", "removed_sum", "fastp_r1_reads",
    "clean_r1_reads", "fastp_r1_sum", "clean_r1_sum", "merge_r1_reads", "merge_r2_reads",
    "rrna_removed_r1", "rrna_removed_sum", "loss_low_quality", "loss_too_short",
    "loss_adapter", "too_many_N_reads", "low_complexity_reads", "adapter_dimer_reads",
    "too_long_reads", "loss_unaccounted", "loss_low_quality_sum", "loss_too_short_sum",
    "loss_adapter_sum", "too_many_N_sum", "low_complexity_sum", "adapter_dimer_sum",
    "too_long_sum", "loss_unaccounted_sum", "corrected_reads", "passed_filter_reads",
    "bases_after_fastp_sum",  # not a read col - remove later
}

# only actual read counts
READ_COLS = {c for c in READ_COLS if "bases" not in c}

BASE_COLS = {
    "bases_before", "raw_bases_sum", "merge_r1_bases", "merge_r2_bases",
    "contigs_all_bp", "contigs_ge1kb_bp", "bases_after_fastp", "bases_after_fastp_sum",
    "clean_r1_bases", "clean_r1_bases_sum", "fastp_r1_bases", "fastp_r1_bases_sum",
}

# fraction (0-1) → percent columns
PCT_FRAC_COLS = {
    "q30_before", "q20_before", "gc_before", "q30_after_fastp", "q20_after_fastp",
    "gc_after_fastp", "read_retention_fastp", "read_retention_fastp_agg",
    "mean_retention_fastp", "mean_q30_after_fastp", "mean_dup", "duplication_rate",
    "rrna_retention_r1", "rrna_retention_r2", "rrna_retention_mean",
    "mean_rrna_retention", "rrna_removed_pct", "rrna_removed_pct_agg",
    "raw_q30_mean", "raw_gc_mean", "merge_loss_pct",
}

# already stored as percent 0-100
PCT_ALREADY_COLS = {"merge_r1_q30_pct", "merge_r1_gc_pct", "merge_r2_q30_pct", "merge_r2_gc_pct"}

INT_COUNT_COLS = {
    "n", "n_runs", "contigs_all_n", "contigs_ge1kb_n", "contigs_min_len",
    "contigs_max_len", "contigs_ge1kb_max_len",
}

METRIC_LABELS = {
    "reads_before_Mb": "reads_before (Mb)",
    "reads_after_fastp_Mb": "reads_after_fastp (Mb)",
    "reads_after_fastp_sum_Mb": "reads_after_sum (Mb)",
    "reads_removed_fastp_Mb": "reads_removed_fastp (Mb)",
    "raw_reads_sum_Mb": "raw_reads_sum (Mb)",
    "raw_bases_sum_Gb": "raw_bases_sum (Gb)",
    "bases_before_Gb": "bases_before (Gb)",
    "bases_after_fastp_sum_Gb": "bases_after_fastp_sum (Gb)",
    "clean_r1_bases_sum_Gb": "clean_r1_bases_sum (Gb)",
    "reads_before_sum_Mb": "reads_before_sum (Mb)",
    "removed_sum_Mb": "removed_sum (Mb)",
    "merge_r1_reads_Mb": "merge_r1_reads (Mb)",
    "merge_r1_Mreads": "merge_r1_reads (Mb)",
    "merge_r1_bases_Gb": "merge_r1_bases (Gb)",
    "rrna_removed_sum_Mb": "rrna_removed_sum (Mb)",
    "rrna_removed_r1_Mb": "rrna_removed_r1 (Mb)",
    "fastp_r1_sum_Mb": "fastp_r1_sum (Mb)",
    "clean_r1_sum_Mb": "clean_r1_sum (Mb)",
    "contigs_ge1kb_Mbp": "contigs_ge1kb_bp (Mb)",
    "contigs_ge1kb_bp_Gb": "contigs_ge1kb_bp (Gb)",
    "contigs_all_bp_Gb": "contigs_all_bp (Gb)",
    "loss_low_quality_sum_Mb": "loss_low_quality_sum (Mb)",
    "loss_too_short_sum_Mb": "loss_too_short_sum (Mb)",
    "loss_adapter_sum_Mb": "loss_adapter_sum (Mb)",
    "loss_unaccounted_sum_Mb": "loss_unaccounted_sum (Mb)",
    "too_many_N_sum_Mb": "too_many_N_sum (Mb)",
    "q30_before_pct": "q30_before (%)",
    "gc_before_pct": "gc_before (%)",
    "raw_q30_mean_pct": "raw_q30_mean (%)",
    "raw_gc_mean_pct": "raw_gc_mean (%)",
    "q30_after_fastp_pct": "q30_after_fastp (%)",
    "mean_q30_after_fastp_pct": "mean_q30_after_fastp (%)",
    "read_retention_fastp_pct": "read_retention_fastp (%)",
    "read_retention_fastp_agg_pct": "read_retention_fastp_agg (%)",
    "duplication_rate_pct": "duplication_rate (%)",
    "mean_dup_pct": "mean_dup (%)",
    "rrna_retention_mean_pct": "rrna_retention_mean (%)",
    "mean_rrna_retention_pct": "mean_rrna_retention (%)",
    "merge_r1_q30_pct": "merge_r1_q30 (%)",
    "merge_r1_gc_pct": "merge_r1_gc (%)",
    "merge_loss_pct_pct": "merge_loss (%)",
}


def to_reads_mb(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce") / READ_DIVISOR


def to_bases_gb(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce") / BASE_DIVISOR


def frac_to_pct(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce") * 100.0


def format_number(val: Any, *, as_pct: bool = False, as_int: bool = False) -> str:
    """Unify display: Mb/Gb → 2 decimals; percent → XX.XX%; integers → thousands sep."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    try:
        x = float(val)
    except (TypeError, ValueError):
        return str(val)
    if as_pct:
        return f"{x:.2f}%"
    if as_int or (abs(x - round(x)) < 1e-9 and abs(x) >= 1):
        return f"{int(round(x)):,}"
    return f"{x:.2f}"


def format_cell(col: str, val: Any) -> str:
    c = str(col)
    if c.endswith("_pct") or c.endswith(" (%)") or "(%)" in c or c in PCT_ALREADY_COLS:
        # already percent units
        if pd.isna(val):
            return ""
        return f"{float(val):.2f}%"
    if c in INT_COUNT_COLS or c.endswith("_n") and "Mb" not in c and "Gb" not in c:
        return format_number(val, as_int=True)
    if c in ("n", "group", "metric", "sample_id", "run_id", "method", "method_label", "host", "sn"):
        if c == "n":
            return format_number(val, as_int=True)
        return "" if pd.isna(val) else str(val)
    # floats Mb/Gb/lengths
    try:
        x = float(val)
    except (TypeError, ValueError):
        return str(val)
    if abs(x - round(x)) < 1e-9 and ("len" in c or c.endswith("_n") or c in INT_COUNT_COLS):
        return f"{int(round(x)):,}"
    return f"{x:.2f}"


def add_unit_columns(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    out = df.copy()
    for c in READ_COLS:
        if c in out.columns:
            out[f"{c}_{READ_SUFFIX}"] = to_reads_mb(out[c])
    for c in BASE_COLS:
        if c in out.columns:
            out[f"{c}_{BASE_SUFFIX}"] = to_bases_gb(out[c])
    for c in PCT_FRAC_COLS:
        if c in out.columns:
            out[f"{c}_pct"] = frac_to_pct(out[c])
    return out


def _describe(vals: pd.Series) -> dict:
    s = pd.to_numeric(vals, errors="coerce").dropna()
    if s.empty:
        return {k: float("nan") for k in ("n", "min", "max", "mean", "median", "std", "q25", "q75")}
    return {
        "n": float(len(s)), "min": float(s.min()), "max": float(s.max()),
        "mean": float(s.mean()), "median": float(s.median()),
        "std": float(s.std(ddof=1)) if len(s) > 1 else 0.0,
        "q25": float(s.quantile(0.25)), "q75": float(s.quantile(0.75)),
    }


def summary_with_units(summary: pd.DataFrame, tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    if summary is None or summary.empty:
        return summary
    mapping = {
        "reads_before": ("stage_S0_raw_by_run", "reads_before", READ_SUFFIX),
        "bases_before": ("stage_S0_raw_by_run", "bases_before", BASE_SUFFIX),
        "raw_reads_sum": ("stage_S0_raw_by_sample", "raw_reads_sum", READ_SUFFIX),
        "raw_bases_sum": ("stage_S0_raw_by_sample", "raw_bases_sum", BASE_SUFFIX),
        "reads_removed_fastp": ("stage_S1_fastp_by_run", "reads_removed_fastp", READ_SUFFIX),
        "reads_before_sum": ("stage_S1_fastp_loss_by_sample", "reads_before_sum", READ_SUFFIX),
        "reads_after_fastp_sum": ("stage_S1_fastp_loss_by_sample", "reads_after_fastp_sum", READ_SUFFIX),
        "removed_sum": ("stage_S1_fastp_loss_by_sample", "removed_sum", READ_SUFFIX),
        "rrna_removed_r1": ("stage_S2_rrna_by_run", "rrna_removed_r1", READ_SUFFIX),
        "rrna_removed_sum": ("stage_S2_rrna_by_sample", "rrna_removed_sum", READ_SUFFIX),
        "merge_r1_reads": ("stage_S3_merge_sample", "merge_r1_reads", READ_SUFFIX),
        "merge_r1_bases": ("stage_S3_merge_sample", "merge_r1_bases", BASE_SUFFIX),
        "contigs_ge1kb_bp": ("stage_S4_assembly_sample", "contigs_ge1kb_bp", BASE_SUFFIX),
        "contigs_ge1kb_Mbp": ("stage_S4_assembly_sample", "contigs_ge1kb_bp", BASE_SUFFIX),
        # percent conversions
        "q30_before": ("stage_S0_raw_by_run", "q30_before", "pct"),
        "gc_before": ("stage_S0_raw_by_run", "gc_before", "pct"),
        "raw_q30_mean": ("stage_S0_raw_by_sample", "raw_q30_mean", "pct"),
        "raw_gc_mean": ("stage_S0_raw_by_sample", "raw_gc_mean", "pct"),
        "q30_after_fastp": ("stage_S1_fastp_by_run", "q30_after_fastp", "pct"),
        "mean_q30_after_fastp": ("stage_S1_fastp_loss_by_sample", "mean_q30_after_fastp", "pct"),
        "read_retention_fastp": ("stage_S1_fastp_by_run", "read_retention_fastp", "pct"),
        "read_retention_fastp_agg": ("stage_S1_fastp_loss_by_sample", "read_retention_fastp_agg", "pct"),
        "duplication_rate": ("stage_S1_fastp_by_run", "duplication_rate", "pct"),
        "mean_dup": ("stage_S1_fastp_loss_by_sample", "mean_dup", "pct"),
        "rrna_retention_mean": ("stage_S2_rrna_by_run", "rrna_retention_mean", "pct"),
        "mean_rrna_retention": ("stage_S2_rrna_by_sample", "mean_rrna_retention", "pct"),
        "merge_loss_pct": ("stage_S3_merge_sample", "merge_loss_pct", "pct"),
    }
    rows = []
    for _, r in summary.iterrows():
        metric = r["metric"]
        if metric == "merge_r1_Mreads":
            r = r.copy()
            r["metric"] = "merge_r1_reads (Mb)"
            rows.append(r)
            continue
        if metric in mapping:
            tname, col, suf = mapping[metric]
            src = tables.get(tname)
            if src is not None and not src.empty:
                enriched = add_unit_columns(src)
                sc = f"{col}_{suf}"
                if sc in enriched.columns:
                    r = r.copy()
                    r["metric"] = METRIC_LABELS.get(sc, f"{metric} ({'%' if suf == 'pct' else suf})")
                    r.update(_describe(enriched[sc]))
        rows.append(r)
    return pd.DataFrame(rows)


def enrich_all_tables(tables: dict[str, pd.DataFrame]) -> None:
    for key in list(tables.keys()):
        if key.endswith("_summary") or key.startswith("sample_qc"):
            continue
        tables[key] = add_unit_columns(tables[key])
    for key in [k for k in tables if k.endswith("_summary")]:
        tables[key] = summary_with_units(tables[key], tables)


def display_columns_for_report(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    meta = {"sample_id", "run_id", "method", "method_label", "host", "sn", "stage"}
    out_cols = []
    for c in cols:
        if c not in df.columns and f"{c}_{READ_SUFFIX}" not in df.columns and f"{c}_pct" not in df.columns:
            # allow alias
            aliases = {
                "reads_after_sum": "reads_after_fastp_sum",
            }
            c = aliases.get(c, c)
        if c in meta:
            if c in df.columns:
                out_cols.append(c)
            continue
        if f"{c}_{READ_SUFFIX}" in df.columns:
            out_cols.append(f"{c}_{READ_SUFFIX}")
        elif f"{c}_{BASE_SUFFIX}" in df.columns:
            out_cols.append(f"{c}_{BASE_SUFFIX}")
        elif f"{c}_pct" in df.columns:
            out_cols.append(f"{c}_pct")
        elif c in df.columns:
            out_cols.append(c)
    sub = df[out_cols].copy()
    rename = {c: METRIC_LABELS.get(c, c) for c in out_cols if c not in meta}
    # special alias for report column name
    rename["reads_after_fastp_sum_Mb"] = "reads_after_sum (Mb)"
    return sub.rename(columns=rename)


def _is_num(v: Any) -> bool:
    try:
        x = float(v)
        return not pd.isna(x)
    except Exception:
        return False


def format_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Return string-formatted dataframe for HTML/markdown."""
    if df is None or df.empty:
        return df
    text_cols = {
        "group", "metric", "sample_id", "run_id", "method", "method_label",
        "host", "sn", "overall_rating", "grade_S1", "grade_S2", "grade_S3", "grade_S4",
        "low_depth_flag",
    }
    out = pd.DataFrame(index=df.index)
    for c in df.columns:
        if c in text_cols:
            out[c] = ["" if pd.isna(v) else str(v) for v in df[c]]
            continue
        if c == "n":
            out[c] = [format_number(v, as_int=True) if _is_num(v) else str(v) for v in df[c]]
            continue
        if c == "weighted_score":
            out[c] = [f"{float(v):.2f}" if _is_num(v) else str(v) for v in df[c]]
            continue
        if c in ("min", "max", "mean", "median", "std", "q25", "q75") and "metric" in df.columns:
            vals = []
            for m, v in zip(df["metric"], df[c]):
                if not _is_num(v):
                    vals.append("" if pd.isna(v) else str(v))
                    continue
                ms = str(m)
                if "(%)" in ms or ms.endswith("%"):
                    vals.append(f"{float(v):.2f}%")
                elif any(k in ms for k in ("contigs_all_n", "contigs_ge1kb_n", "contigs_min_len", "contigs_max_len")) and "Gb" not in ms and "Mb" not in ms and "avg" not in ms:
                    vals.append(format_number(v, as_int=True))
                else:
                    vals.append(f"{float(v):.2f}")
            out[c] = vals
            continue
        # general column
        if "(%)" in str(c) or str(c).endswith("_pct") or str(c).endswith(" (%)"):
            out[c] = [f"{float(v):.2f}%" if _is_num(v) else ("" if pd.isna(v) else str(v)) for v in df[c]]
        elif any(str(c).endswith(s) for s in ("_n", "_len")) and "Mb" not in str(c) and "Gb" not in str(c) and "avg" not in str(c):
            out[c] = [format_number(v, as_int=True) if _is_num(v) else ("" if pd.isna(v) else str(v)) for v in df[c]]
        else:
            out[c] = [f"{float(v):.2f}" if _is_num(v) else ("" if pd.isna(v) else str(v)) for v in df[c]]
    return out
```

### A. `w1_qc/compute.py`

```python
"""Compute W1 QC tables and sample scores."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

from cohort import LOW_DEPTH_READS, load_sampleinfo
from w1_qc.standards import (
    GRADE_SCORE,
    STAGE_WEIGHTS,
    batch_pass,
    grade_contigs_ge1kb,
    grade_merge_depth,
    grade_rrna_retention,
    grade_s1_combined,
    overall_rating,
)


@dataclass
class W1QCResult:
    out_dir: Path
    tables: dict[str, Path]
    sample_scores: pd.DataFrame
    batch_summary: dict[str, Any]


# Portable: batch_dir can be set via run_w1_qc_pipeline(..., batch_dir=...)
_BATCH_DIR_OVERRIDE: Path | None = None
_WF1_DIR_OVERRIDE: Path | None = None
_OUT_DIR_OVERRIDE: Path | None = None


def _batch_root(batch_id: str) -> Path:
    if _BATCH_DIR_OVERRIDE is not None:
        return Path(_BATCH_DIR_OVERRIDE)
    # XvirBench layout fallback
    here = Path(__file__).resolve()
    for parents_up in (3, 4, 2):
        cand = here.parents[parents_up] / "batches" / batch_id
        if cand.is_dir():
            return cand
    return Path.cwd() / "batches" / batch_id


def _workflow1_dir(batch_id: str) -> Path:
    if _WF1_DIR_OVERRIDE is not None:
        return Path(_WF1_DIR_OVERRIDE)
    return _batch_root(batch_id) / "workflow_results" / "workflow1_upstream"


def _fastp_json_path(wf1: Path, run_id: str) -> Path:
    return wf1 / "filter" / run_id / "01_fastp.json"


def _load_fastp_extra(wf1: Path, run_id: str) -> dict[str, int]:
    p = _fastp_json_path(wf1, run_id)
    out = {
        "too_many_N_reads": 0,
        "low_complexity_reads": 0,
        "adapter_dimer_reads": 0,
        "too_long_reads": 0,
        "corrected_reads": 0,
    }
    if not p.is_file():
        return out
    try:
        fr = json.loads(p.read_text(encoding="utf-8")).get("filtering_result", {})
        for k in out:
            out[k] = int(fr.get(k, 0) or 0)
    except Exception:
        pass
    return out


def _describe_series(s: pd.Series) -> dict[str, float]:
    s = pd.to_numeric(s, errors="coerce").dropna()
    if s.empty:
        return {k: float("nan") for k in ("n", "min", "max", "mean", "median", "std", "q25", "q75")}
    return {
        "n": float(len(s)),
        "min": float(s.min()),
        "max": float(s.max()),
        "mean": float(s.mean()),
        "median": float(s.median()),
        "std": float(s.std(ddof=1)) if len(s) > 1 else 0.0,
        "q25": float(s.quantile(0.25)),
        "q75": float(s.quantile(0.75)),
    }


def _summary_block(df: pd.DataFrame, metrics: list[str], group: str = "batch") -> pd.DataFrame:
    rows = []
    for m in metrics:
        d = _describe_series(df[m])
        rows.append({"group": group, "metric": m, **d})
    return pd.DataFrame(rows)


def _filter_host(cohort: pd.DataFrame, host: Optional[str]) -> pd.DataFrame:
    if not host:
        return cohort.copy()
    return cohort[cohort["host"] == host].copy()


def build_stage_tables(
    batch_id: str,
    host: Optional[str] = None,
) -> tuple[dict[str, pd.DataFrame], pd.DataFrame, pd.DataFrame]:
    batch = _batch_root(batch_id)
    harm = batch / "harmonized" / "workflow1"
    if not harm.is_dir():
        # flat layout: batch_dir itself holds TSV
        if (batch / "qc_upstream_run.tsv").is_file():
            harm = batch
        else:
            raise FileNotFoundError(f"找不到 harmonized/workflow1 或 qc_upstream_*.tsv: {batch}")
    cohort_dir = batch / "cohorts"
    if not (cohort_dir / "sampleinfo.tsv").is_file() and (batch / "sampleinfo.tsv").is_file():
        cohort_dir = batch
    cohort = _filter_host(load_sampleinfo(cohort_dir), host)
    sample_ids = set(cohort["sample_id"])

    runs = pd.read_csv(harm / "qc_upstream_run.tsv", sep="\t")
    runs = runs[runs["sample_id"].isin(sample_ids)].copy()
    samples = pd.read_csv(harm / "qc_upstream_sample.tsv", sep="\t")
    samples = samples[samples["sample_id"].isin(sample_ids)].copy()

    wf1 = _workflow1_dir(batch_id)
    extras = []
    for _, row in runs.iterrows():
        e = _load_fastp_extra(wf1, str(row["run_id"]))
        e["run_id"] = row["run_id"]
        extras.append(e)
    if extras:
        runs = runs.merge(pd.DataFrame(extras), on="run_id", how="left")
    else:
        for c in ("too_many_N_reads", "low_complexity_reads", "adapter_dimer_reads", "too_long_reads", "corrected_reads"):
            runs[c] = 0

    runs["rrna_retention_mean"] = (pd.to_numeric(runs["rrna_retention_r1"], errors="coerce") + pd.to_numeric(runs["rrna_retention_r2"], errors="coerce")) / 2
    runs["rrna_removed_r1"] = pd.to_numeric(runs["fastp_r1_reads"], errors="coerce") - pd.to_numeric(runs["clean_r1_reads"], errors="coerce")
    runs["reads_removed_fastp"] = pd.to_numeric(runs["reads_before"], errors="coerce") - pd.to_numeric(runs["reads_after_fastp"], errors="coerce")
    runs["loss_low_quality"] = pd.to_numeric(runs["low_quality_reads"], errors="coerce").fillna(0)
    runs["loss_too_short"] = pd.to_numeric(runs["too_short_reads"], errors="coerce").fillna(0)
    runs["loss_adapter"] = pd.to_numeric(runs["adapter_trimmed_reads"], errors="coerce").fillna(0)
    runs["loss_accounted"] = (
        runs["loss_low_quality"] + runs["loss_too_short"] + runs["loss_adapter"]
        + runs["too_many_N_reads"] + runs["low_complexity_reads"] + runs["adapter_dimer_reads"] + runs["too_long_reads"]
    )
    runs["loss_unaccounted"] = runs["reads_removed_fastp"] - runs["loss_accounted"]

    # S0 by run
    s0_run = runs[
        ["run_id", "sample_id", "reads_before", "bases_before", "q20_before", "q30_before", "gc_before"]
    ].copy()
    s0_run = s0_run.merge(cohort[["sample_id", "host", "method", "method_label", "sn"]], on="sample_id", how="left")

    s0_sample = (
        runs.groupby("sample_id", as_index=False)
        .agg(
            raw_reads_sum=("reads_before", "sum"),
            raw_bases_sum=("bases_before", "sum"),
            raw_q30_mean=("q30_before", "mean"),
            raw_gc_mean=("gc_before", "mean"),
            n_runs=("run_id", "count"),
        )
    )
    s0_sample = s0_sample.merge(cohort[["sample_id", "host", "method", "method_label", "sn"]], on="sample_id", how="left")

    s0_summary = pd.concat([
        _summary_block(s0_run, ["reads_before", "bases_before", "q30_before", "gc_before"], "batch_run_level"),
        _summary_block(s0_sample, ["raw_reads_sum", "raw_bases_sum", "raw_q30_mean", "raw_gc_mean"], "batch_sample_level"),
    ], ignore_index=True)

    # S1 fastp
    s1_run = runs[
        [
            "run_id", "sample_id", "reads_before", "reads_after_fastp", "read_retention_fastp",
            "q30_after_fastp", "duplication_rate", "reads_removed_fastp",
            "loss_low_quality", "loss_too_short", "loss_adapter",
            "too_many_N_reads", "low_complexity_reads", "adapter_dimer_reads", "too_long_reads",
            "corrected_reads", "loss_accounted", "loss_unaccounted",
        ]
    ].copy()
    s1_run = s1_run.merge(cohort[["sample_id", "host", "method", "method_label"]], on="sample_id", how="left")

    s1_loss_run = s1_run[
        ["run_id", "sample_id", "method", "method_label", "reads_before", "reads_removed_fastp",
         "loss_low_quality", "loss_too_short", "loss_adapter", "too_many_N_reads",
         "low_complexity_reads", "adapter_dimer_reads", "too_long_reads", "loss_unaccounted"]
    ].copy()

    s1_sample = (
        runs.groupby("sample_id", as_index=False)
        .agg(
            reads_before_sum=("reads_before", "sum"),
            reads_after_fastp_sum=("reads_after_fastp", "sum"),
            bases_after_fastp_sum=("bases_after_fastp", "sum"),
            mean_retention_fastp=("read_retention_fastp", "mean"),
            mean_q30_after_fastp=("q30_after_fastp", "mean"),
            mean_dup=("duplication_rate", "mean"),
            removed_sum=("reads_removed_fastp", "sum"),
            loss_low_quality_sum=("loss_low_quality", "sum"),
            loss_too_short_sum=("loss_too_short", "sum"),
            loss_adapter_sum=("loss_adapter", "sum"),
            too_many_N_sum=("too_many_N_reads", "sum"),
            low_complexity_sum=("low_complexity_reads", "sum"),
            adapter_dimer_sum=("adapter_dimer_reads", "sum"),
            too_long_sum=("too_long_reads", "sum"),
            loss_unaccounted_sum=("loss_unaccounted", "sum"),
        )
    )
    s1_sample["read_retention_fastp_agg"] = s1_sample["reads_after_fastp_sum"] / s1_sample["reads_before_sum"]
    s1_sample = s1_sample.merge(cohort[["sample_id", "host", "method", "method_label", "sn"]], on="sample_id", how="left")

    s1_summary = pd.concat([
        _summary_block(runs, ["read_retention_fastp", "q30_after_fastp", "duplication_rate", "reads_removed_fastp"], "batch_run_level"),
        _summary_block(s1_sample, ["read_retention_fastp_agg", "mean_q30_after_fastp", "mean_dup"], "batch_sample_level"),
    ], ignore_index=True)

    # S2 rRNA
    s2_run = runs[
        ["run_id", "sample_id", "fastp_r1_reads", "clean_r1_reads", "rrna_removed_r1",
         "rrna_retention_r1", "rrna_retention_r2", "rrna_retention_mean"]
    ].copy()
    s2_run["rrna_removed_pct"] = 1 - s2_run["rrna_retention_mean"]
    s2_run = s2_run.merge(cohort[["sample_id", "host", "method", "method_label"]], on="sample_id", how="left")

    s2_sample = (
        runs.groupby("sample_id", as_index=False)
        .agg(
            fastp_r1_sum=("fastp_r1_reads", "sum"),
            clean_r1_sum=("clean_r1_reads", "sum"),
            clean_r1_bases_sum=("clean_r1_bases", "sum"),
            mean_rrna_retention=("rrna_retention_mean", "mean"),
            rrna_removed_sum=("rrna_removed_r1", "sum"),
        )
    )
    s2_sample["rrna_removed_pct_agg"] = 1 - s2_sample["mean_rrna_retention"]
    s2_sample = s2_sample.merge(cohort[["sample_id", "host", "method", "method_label", "sn"]], on="sample_id", how="left")

    s2_summary = pd.concat([
        _summary_block(runs, ["rrna_retention_mean", "rrna_removed_r1"], "batch_run_level"),
        _summary_block(s2_sample, ["mean_rrna_retention", "rrna_removed_sum"], "batch_sample_level"),
    ], ignore_index=True)

    # S3 merge
    s3 = samples[
        ["sample_id", "n_runs", "merge_r1_reads", "merge_r1_bases", "merge_r1_q30_pct", "merge_r1_gc_pct",
         "merge_r2_reads", "merge_r2_bases"]
    ].copy()
    s3 = s3.merge(cohort[["sample_id", "host", "method", "method_label", "sn"]], on="sample_id", how="left")
    s3 = s3.merge(s1_sample[["sample_id", "reads_after_fastp_sum"]], on="sample_id", how="left")
    s3["merge_r1_Mreads"] = pd.to_numeric(s3["merge_r1_reads"], errors="coerce") / 1e6
    s3["merge_loss_pct"] = 1 - pd.to_numeric(s3["merge_r1_reads"], errors="coerce") / pd.to_numeric(s3["reads_after_fastp_sum"], errors="coerce")
    s3["low_depth"] = pd.to_numeric(s3["merge_r1_reads"], errors="coerce") < LOW_DEPTH_READS

    s3_summary = _summary_block(s3, ["merge_r1_reads", "merge_r1_Mreads", "merge_r1_q30_pct", "merge_r1_gc_pct", "merge_loss_pct"], "batch_sample_level")

    # S4 assembly
    s4 = samples[
        ["sample_id", "contigs_all_n", "contigs_all_bp", "contigs_avg_len", "contigs_min_len", "contigs_max_len",
         "contigs_ge1kb_n", "contigs_ge1kb_bp", "contigs_ge1kb_avg_len", "contigs_ge1kb_max_len"]
    ].copy()
    s4 = s4.merge(cohort[["sample_id", "host", "method", "method_label", "sn"]], on="sample_id", how="left")

    s4_summary = _summary_block(s4, ["contigs_all_n", "contigs_ge1kb_n", "contigs_avg_len", "contigs_max_len", "contigs_ge1kb_bp"], "batch_sample_level")

    tables = {
        "stage_S0_raw_by_run": s0_run,
        "stage_S0_raw_summary": s0_summary,
        "stage_S0_raw_by_sample": s0_sample,
        "stage_S1_fastp_by_run": s1_run,
        "stage_S1_fastp_loss_by_run": s1_loss_run,
        "stage_S1_fastp_summary": s1_summary,
        "stage_S1_fastp_loss_by_sample": s1_sample,
        "stage_S2_rrna_by_run": s2_run,
        "stage_S2_rrna_summary": s2_summary,
        "stage_S2_rrna_by_sample": s2_sample,
        "stage_S3_merge_sample": s3,
        "stage_S3_merge_summary": s3_summary,
        "stage_S4_assembly_sample": s4,
        "stage_S4_assembly_summary": s4_summary,
    }

    flags, scores = _build_scores(cohort, s1_sample, s2_sample, s3, s4)
    tables["sample_qc_flags"] = flags
    tables["sample_qc_scores"] = scores

    from w1_qc.units import enrich_all_tables
    enrich_all_tables(tables)

    return tables, flags, scores


def _build_scores(
    cohort: pd.DataFrame,
    s1_sample: pd.DataFrame,
    s2_sample: pd.DataFrame,
    s3: pd.DataFrame,
    s4: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = cohort[["sample_id", "host", "method", "method_label", "sn"]].copy()
    df = df.merge(
        s1_sample[["sample_id", "read_retention_fastp_agg", "mean_q30_after_fastp", "mean_dup"]],
        on="sample_id", how="left",
    )
    df = df.merge(s2_sample[["sample_id", "mean_rrna_retention"]], on="sample_id", how="left")
    df = df.merge(s3[["sample_id", "merge_r1_reads", "merge_r1_Mreads", "low_depth"]], on="sample_id", how="left")
    df = df.merge(s4[["sample_id", "contigs_ge1kb_n"]], on="sample_id", how="left")

    flags = df[["sample_id", "host", "method", "method_label", "sn"]].copy()
    flags["grade_S1"] = df.apply(
        lambda r: grade_s1_combined(r["read_retention_fastp_agg"], r["mean_q30_after_fastp"], r["mean_dup"]), axis=1
    )
    flags["grade_S2"] = df["mean_rrna_retention"].map(grade_rrna_retention)
    flags["grade_S3"] = df["merge_r1_reads"].map(grade_merge_depth)
    flags["grade_S4"] = df["contigs_ge1kb_n"].map(grade_contigs_ge1kb)
    flags["low_depth_flag"] = df["low_depth"]

    scores = flags.copy()
    scores["score_S1"] = scores["grade_S1"].map(GRADE_SCORE)
    scores["score_S2"] = scores["grade_S2"].map(GRADE_SCORE)
    scores["score_S3"] = scores["grade_S3"].map(GRADE_SCORE)
    scores["score_S4"] = scores["grade_S4"].map(GRADE_SCORE)
    scores["weighted_score"] = (
        scores["score_S3"] * STAGE_WEIGHTS["S3_depth"]
        + scores["score_S1"] * STAGE_WEIGHTS["S1_quality"]
        + scores["score_S2"] * STAGE_WEIGHTS["S2_rrna"]
        + scores["score_S4"] * STAGE_WEIGHTS["S4_assembly"]
    )
    scores["overall_rating"] = scores["weighted_score"].map(overall_rating)
    return flags, scores


def run_w1_qc_pipeline(
    batch_id: str,
    host: Optional[str] = None,
    batch_dir: Optional[Path] = None,
    wf1_dir: Optional[Path] = None,
    out_dir: Optional[Path] = None,
) -> W1QCResult:
    global _BATCH_DIR_OVERRIDE, _WF1_DIR_OVERRIDE, _OUT_DIR_OVERRIDE
    _BATCH_DIR_OVERRIDE = Path(batch_dir) if batch_dir else None
    _WF1_DIR_OVERRIDE = Path(wf1_dir) if wf1_dir else None
    _OUT_DIR_OVERRIDE = Path(out_dir) if out_dir else None
    host_tag = host or "all"
    out_dir = _OUT_DIR_OVERRIDE or (_batch_root(batch_id) / "analysis" / f"w1_qc_{host_tag}")
    tab_dir = out_dir / "tables"
    fig_dir = out_dir / "figures"
    tab_dir.mkdir(parents=True, exist_ok=True)
    fig_dir.mkdir(parents=True, exist_ok=True)

    tables, flags, scores = build_stage_tables(batch_id, host=host)
    written: dict[str, Path] = {}
    for name, df in tables.items():
        p = tab_dir / f"{name}.tsv"
        df.to_csv(p, sep="\t", index=False)
        written[name] = p

    from w1_qc.plots import generate_all_figures
    from w1_qc.reports import write_reports

    fig_paths = generate_all_figures(tables, fig_dir)
    ratings = scores["overall_rating"].tolist()
    batch_summary = {
        "batch_id": batch_id,
        "host": host_tag,
        "n_samples": len(scores),
        "threshold_version": __import__("w1_qc.standards", fromlist=["THRESHOLD_VERSION"]).THRESHOLD_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "batch_pass": batch_pass(ratings),
        "rating_counts": scores["overall_rating"].value_counts().to_dict(),
        "low_depth_samples": flags.loc[flags["low_depth_flag"] == True, "sample_id"].tolist() if "low_depth_flag" in flags.columns else [],
    }

    write_reports(out_dir, batch_summary, tables, fig_paths, internal=True)
    write_reports(out_dir, batch_summary, tables, fig_paths, internal=False)

    return W1QCResult(out_dir=out_dir, tables=written, sample_scores=scores, batch_summary=batch_summary)
```

### A. `w1_qc/plots.py`

```python
"""W1 QC figures (SCI style)."""
from __future__ import annotations

from pathlib import Path

import matplotlib as mpl
import matplotlib.ticker as mticker
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

from plot_meta import METHOD_ORDER, METHOD_COLORS, METHOD_LABEL
from w1_qc.units import BASE_DIVISOR, READ_DIVISOR, to_reads_mb

DPI = 300
LOSS_COLORS = {
    "Low quality": "#E69F00",
    "Too short": "#56B4E9",
    "Adapter": "#009E73",
    "High N": "#F0E442",
    "Low complexity": "#0072B2",
    "Adapter dimer": "#D55E00",
    "Too long": "#CC79A7",
    "Unassigned": "#999999",
}


def method_codes_order(df: pd.DataFrame, col: str = "method") -> list[str]:
    present = set(df[col].astype(str).unique())
    return [m for m in METHOD_ORDER if m in present]


def apply_sci_theme() -> None:
    mpl.rcParams.update({
        "figure.dpi": DPI,
        "savefig.dpi": DPI,
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
        "font.size": 8,
        "axes.labelsize": 9,
        "axes.titlesize": 9,
        "axes.linewidth": 0.8,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "xtick.labelsize": 8,
        "ytick.labelsize": 8,
        "legend.fontsize": 7,
        "legend.frameon": False,
        "axes.unicode_minus": False,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
    })


def _save(fig, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=DPI, bbox_inches="tight", pad_inches=0.08, facecolor="white")
    plt.close(fig)
    return path


def _boxplot_by_method(ax, df: pd.DataFrame, y: str, ylabel: str) -> None:
    order = method_codes_order(df)
    data = [df.loc[df["method"].astype(str) == m, y].dropna().values for m in order]
    bp = ax.boxplot(
        data, patch_artist=True, widths=0.55,
        medianprops=dict(color="black", linewidth=1.2),
        whiskerprops=dict(linewidth=0.8, color="#333"),
        capprops=dict(linewidth=0.8, color="#333"),
        flierprops=dict(marker="o", markersize=3, markerfacecolor="#666", alpha=0.6, linewidth=0),
    )
    for patch, m in zip(bp["boxes"], order):
        patch.set_facecolor(METHOD_COLORS.get(m, "#BBB"))
        patch.set_edgecolor("#333")
        patch.set_alpha(0.85)
    for i, vals in enumerate(data, start=1):
        if len(vals):
            jitter = np.random.default_rng(42).uniform(-0.12, 0.12, len(vals))
            ax.scatter(np.full(len(vals), i) + jitter, vals, s=12, c="#333", alpha=0.55, zorder=3, linewidths=0)
    ax.set_xticks(range(1, len(order) + 1))
    ax.set_xticklabels([METHOD_LABEL.get(m, m) for m in order], rotation=20, ha="right")
    ax.set_ylabel(ylabel)


def _stage_boxplot(ax, plot_df: pd.DataFrame, value_col: str, ylabel: str, title: str) -> None:
    stages = list(plot_df["stage"].unique())
    # preserve expected order if present
    pref = ["Raw", "Post-fastp", "Post-rRNA"]
    stages = [s for s in pref if s in set(plot_df["stage"])] or stages
    meth_order = method_codes_order(plot_df)
    width = 0.2
    offsets = np.linspace(-(len(meth_order) - 1) / 2, (len(meth_order) - 1) / 2, len(meth_order)) * 0.22
    for off, meth in zip(offsets, meth_order):
        for i, stage in enumerate(stages):
            vals = plot_df[(plot_df.stage == stage) & (plot_df.method == meth)][value_col].dropna().values
            if len(vals) == 0:
                continue
            bp = ax.boxplot(
                vals, positions=[i + off], widths=width, patch_artist=True,
                medianprops=dict(color="black", linewidth=1.0),
                whiskerprops=dict(linewidth=0.8), capprops=dict(linewidth=0.8),
                flierprops=dict(markersize=2.5, markerfacecolor="#666", alpha=0.5),
            )
            bp["boxes"][0].set_facecolor(METHOD_COLORS.get(meth, "#BBB"))
            bp["boxes"][0].set_edgecolor("#333")
            bp["boxes"][0].set_alpha(0.85)
    ax.set_xticks(range(len(stages)))
    ax.set_xticklabels(stages)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    handles = [Patch(facecolor=METHOD_COLORS.get(m, "#BBB"), edgecolor="#333", label=METHOD_LABEL.get(m, m)) for m in meth_order]
    ax.legend(handles=handles, title="Library method", loc="upper right", frameon=True, fancybox=False, edgecolor="#CCC")


def fig01_stage_yield(tables: dict[str, pd.DataFrame], out: Path) -> Path | None:
    """F01: left reads (Mb), right bases (Gb); sample-level stage aggregates."""
    s0 = tables["stage_S0_raw_by_sample"]
    s1 = tables["stage_S1_fastp_loss_by_sample"]
    s2 = tables["stage_S2_rrna_by_sample"]
    read_rows, base_rows = [], []
    # R1-consistent sample-level: Raw≈PE/2, Post-fastp=fastp R1, Post-rRNA=clean R1
    for _, r in s0.iterrows():
        read_rows.append({"sample_id": r["sample_id"], "method": str(r["method"]), "stage": "Raw",
                          "value": float(r["raw_reads_sum"]) / 2.0 / READ_DIVISOR})
        base_rows.append({"sample_id": r["sample_id"], "method": str(r["method"]), "stage": "Raw",
                          "value": float(r["raw_bases_sum"]) / 2.0 / BASE_DIVISOR})
    for _, r in s2.iterrows():
        read_rows.append({"sample_id": r["sample_id"], "method": str(r["method"]), "stage": "Post-fastp",
                          "value": float(r["fastp_r1_sum"]) / READ_DIVISOR})
        read_rows.append({"sample_id": r["sample_id"], "method": str(r["method"]), "stage": "Post-rRNA",
                          "value": float(r["clean_r1_sum"]) / READ_DIVISOR})
        if "clean_r1_bases_sum" in r.index and pd.notna(r["clean_r1_bases_sum"]):
            # approximate post-fastp R1 bases from PE after /2 if needed
            base_rows.append({"sample_id": r["sample_id"], "method": str(r["method"]), "stage": "Post-rRNA",
                              "value": float(r["clean_r1_bases_sum"]) / BASE_DIVISOR})
    s1i = s1.set_index("sample_id")
    for _, r in s2.iterrows():
        sid = r["sample_id"]
        if sid in s1i.index and "bases_after_fastp_sum" in s1i.columns:
            base_rows.append({"sample_id": sid, "method": str(r["method"]), "stage": "Post-fastp",
                              "value": float(s1i.loc[sid, "bases_after_fastp_sum"]) / 2.0 / BASE_DIVISOR})
    rdf, bdf = pd.DataFrame(read_rows), pd.DataFrame(base_rows)
    if rdf.empty:
        return None
    fig, axes = plt.subplots(1, 2, figsize=(11.0, 3.8))
    _stage_boxplot(axes[0], rdf, "value", "Reads (Mb)", "A. Read depth by stage")
    if not bdf.empty:
        _stage_boxplot(axes[1], bdf, "value", "Bases (Gb)", "B. Base yield by stage")
    else:
        axes[1].text(0.5, 0.5, "No bases data", ha="center", va="center")
        axes[1].set_axis_off()
    fig.suptitle("Fig01 Pipeline yield across stages (sample-level R1)", y=1.02, fontsize=10)
    fig.tight_layout()
    return _save(fig, out)


def fig02_fastp_qc(tables: dict[str, pd.DataFrame], out: Path) -> Path | None:
    """Fig02: fastp retention + loss composition (all samples)."""
    df = tables["stage_S1_fastp_loss_by_sample"].copy()
    if df.empty:
        return None
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 5.2), gridspec_kw={"width_ratios": [1, 1.35]})

    # Left: F02
    ax = axes[0]
    _boxplot_by_method(ax, df, "read_retention_fastp_agg", "Retention (%)")
    # convert to percent on plot
    order = method_codes_order(df)
    data = [df.loc[df["method"].astype(str) == m, "read_retention_fastp_agg"].dropna().values * 100 for m in order]
    ax.clear()
    bp = ax.boxplot(
        data, patch_artist=True, widths=0.55,
        medianprops=dict(color="black", linewidth=1.2),
        whiskerprops=dict(linewidth=0.8, color="#333"),
        capprops=dict(linewidth=0.8, color="#333"),
        flierprops=dict(marker="o", markersize=3, markerfacecolor="#666", alpha=0.6, linewidth=0),
    )
    for patch, m in zip(bp["boxes"], order):
        patch.set_facecolor(METHOD_COLORS.get(m, "#BBB"))
        patch.set_edgecolor("#333")
        patch.set_alpha(0.85)
    for i, vals in enumerate(data, start=1):
        if len(vals):
            jitter = np.random.default_rng(42).uniform(-0.12, 0.12, len(vals))
            ax.scatter(np.full(len(vals), i) + jitter, vals, s=12, c="#333", alpha=0.55, zorder=3, linewidths=0)
    ax.axhline(85, ls="--", c="#666", lw=0.9, zorder=0)
    ax.set_xticks(range(1, len(order) + 1))
    ax.set_xticklabels([METHOD_LABEL.get(m, m) for m in order], rotation=20, ha="right")
    ax.set_ylabel("Retention (%)")
    ax.set_title("A. fastp read retention")

    # Right: F03 all samples
    ax = axes[1]
    cols = {
        "loss_low_quality_sum": "Low quality", "loss_too_short_sum": "Too short",
        "loss_adapter_sum": "Adapter", "too_many_N_sum": "High N",
        "low_complexity_sum": "Low complexity", "adapter_dimer_sum": "Adapter dimer",
        "too_long_sum": "Too long", "loss_unaccounted_sum": "Unassigned",
    }
    all_df = df.sort_values("sample_id").set_index("sample_id")
    samples = all_df.index.tolist()
    count_mat = np.column_stack([
        pd.to_numeric(all_df.get(col, 0), errors="coerce").fillna(0).values for col in cols
    ])
    row_sum = count_mat.sum(axis=1, keepdims=True)
    row_sum = np.where(row_sum > 0, row_sum, 1)
    pct_mat = 100 * count_mat / row_sum
    y_pos = np.arange(len(samples))
    left = np.zeros(len(samples))
    for j, (_, label) in enumerate(cols.items()):
        ax.barh(y_pos, pct_mat[:, j], left=left, color=LOSS_COLORS.get(label, "#AAA"),
                edgecolor="white", linewidth=0.2, label=label, height=0.78)
        left += pct_mat[:, j]
    ax.set_yticks(y_pos)
    ax.set_yticklabels(samples, fontsize=5.5)
    ax.set_xlabel("Fraction of removed reads (%)")
    ax.set_xlim(0, 100)
    ax.set_title("B. fastp loss composition (all samples)")
    ax.legend(loc="center left", bbox_to_anchor=(1.01, 0.5), frameon=True, fancybox=False, edgecolor="#CCC", fontsize=6)

    fig.suptitle("Fig02 fastp QC", y=1.01, fontsize=10)
    fig.tight_layout()
    return _save(fig, out)


def fig03_rrna_qc(tables: dict[str, pd.DataFrame], out: Path) -> Path | None:
    """Fig03: rRNA retention (denom=fastp R1) + post-rRNA depth."""
    df = tables["stage_S2_rrna_by_sample"].copy()
    if df.empty:
        return None
    s3 = tables["stage_S3_merge_sample"]
    merged = df.merge(s3[["sample_id", "merge_r1_reads"]], on="sample_id", how="left")
    unequal = (pd.to_numeric(merged["merge_r1_reads"], errors="coerce") - pd.to_numeric(merged["clean_r1_sum"], errors="coerce")).abs()
    use_note = "Post-rRNA R1 reads (equal to merge in this batch)" if (unequal.fillna(0) < 1).all() else "Post-rRNA R1 reads (sample-level)"

    fig, axes = plt.subplots(1, 2, figsize=(12.0, 4.0), gridspec_kw={"width_ratios": [1, 1.5]})

    # Left retention as %
    ax = axes[0]
    order = method_codes_order(df)
    data = [df.loc[df["method"].astype(str) == m, "mean_rrna_retention"].dropna().values * 100 for m in order]
    bp = ax.boxplot(
        data, patch_artist=True, widths=0.55,
        medianprops=dict(color="black", linewidth=1.2),
        whiskerprops=dict(linewidth=0.8, color="#333"),
        capprops=dict(linewidth=0.8, color="#333"),
        flierprops=dict(marker="o", markersize=3, markerfacecolor="#666", alpha=0.6, linewidth=0),
    )
    for patch, m in zip(bp["boxes"], order):
        patch.set_facecolor(METHOD_COLORS.get(m, "#BBB"))
        patch.set_edgecolor("#333")
        patch.set_alpha(0.85)
    for i, vals in enumerate(data, start=1):
        if len(vals):
            jitter = np.random.default_rng(42).uniform(-0.12, 0.12, len(vals))
            ax.scatter(np.full(len(vals), i) + jitter, vals, s=12, c="#333", alpha=0.55, zorder=3, linewidths=0)
    ax.axhspan(75, 98, alpha=0.08, color="#009E73", zorder=0)
    ax.set_xticks(range(1, len(order) + 1))
    ax.set_xticklabels([METHOD_LABEL.get(m, m) for m in order], rotation=20, ha="right")
    ax.set_ylabel("rRNA retention (%)")
    ax.set_title("A. rRNA removal efficiency")

    # Right bars
    ax = axes[1]
    d = df.sort_values("sample_id").copy()
    d["reads_Mb"] = to_reads_mb(d["clean_r1_sum"])
    colors = [METHOD_COLORS.get(str(m), "#BBB") for m in d["method"]]
    ax.bar(d["sample_id"], d["reads_Mb"], color=colors, edgecolor="#333", linewidth=0.3, width=0.82)
    ax.axhline(5.0, ls="--", c="#666", lw=0.9)
    low = d[d["reads_Mb"] < 5]
    if not low.empty:
        ax.scatter(low["sample_id"], low["reads_Mb"], s=45, facecolors="none", edgecolors="#000", linewidths=1.2, zorder=4)
    ax.set_ylabel("Post-rRNA R1 reads (Mb)")
    ax.set_xlabel("Sample")
    ax.set_title(f"B. {use_note}")
    ax.tick_params(axis="x", rotation=90, labelsize=5.5)
    meth_handles = [Patch(facecolor=METHOD_COLORS.get(m, "#BBB"), edgecolor="#333", label=METHOD_LABEL.get(m, m)) for m in order]
    extra = [Line2D([0], [0], color="#666", ls="--", lw=0.9, label="5 Mb threshold")]
    if not low.empty:
        extra.append(Line2D([0], [0], marker="o", linestyle="None", markerfacecolor="none", markeredgecolor="#000", markersize=6, label="Low depth (<5 Mb)"))
    ax.legend(handles=meth_handles + extra, loc="upper right", frameon=True, fancybox=False, edgecolor="#CCC", fontsize=6)

    fig.suptitle("Fig03 rRNA removal (retention = clean / fastp)", y=1.01, fontsize=10)
    fig.tight_layout()
    return _save(fig, out)


def fig04_assembly(tables: dict[str, pd.DataFrame], out: Path) -> Path | None:
    """Fig04: 2x2 assembly — scatter, contig counts, mean length, >=1kb percent."""
    s4 = tables["stage_S4_assembly_sample"].copy()
    s2 = tables["stage_S2_rrna_by_sample"][["sample_id", "clean_r1_sum", "method"]].copy()
    df = s4.merge(s2, on="sample_id", how="left", suffixes=("", "_s2"))
    if "method_s2" in df.columns:
        df["method"] = df["method"].fillna(df["method_s2"])
    df["reads_Mb"] = to_reads_mb(df["clean_r1_sum"])
    df["low_depth"] = df["reads_Mb"] < 5
    df["ge1kb_pct"] = 100.0 * pd.to_numeric(df["contigs_ge1kb_n"], errors="coerce") / pd.to_numeric(df["contigs_all_n"], errors="coerce").replace(0, pd.NA)
    df["avg_len"] = pd.to_numeric(df["contigs_avg_len"], errors="coerce")
    if df.empty:
        return None

    fig, axes = plt.subplots(2, 2, figsize=(12.5, 8.2))

    # A: scatter
    ax = axes[0, 0]
    for meth in method_codes_order(df):
        sub = df[df.method.astype(str) == meth]
        ax.scatter(sub["reads_Mb"], sub["contigs_ge1kb_n"], s=36, alpha=0.82,
                   c=METHOD_COLORS.get(meth, "#BBB"), edgecolors="#333", linewidths=0.4,
                   label=METHOD_LABEL.get(meth, meth))
    low = df[df["low_depth"]]
    if not low.empty:
        ax.scatter(low["reads_Mb"], low["contigs_ge1kb_n"], s=60, facecolors="none",
                   edgecolors="#000", linewidths=1.2, label="Low depth (<5 Mb)")
    ax.set_xlabel("Post-rRNA R1 reads (Mb)")
    ax.set_ylabel("Contigs >= 1 kb (n)")
    ax.set_title("A. Assembly yield vs depth")
    ax.legend(loc="lower right", frameon=True, fancybox=False, edgecolor="#CCC", fontsize=6)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{int(v):,}"))

    # B: counts
    ax = axes[0, 1]
    d = df.sort_values("sample_id")
    x = np.arange(len(d))
    w = 0.38
    ax.bar(x - w / 2, d["contigs_all_n"], width=w, color="#56B4E9", edgecolor="#333", linewidth=0.2, label="All contigs (n)")
    ax.bar(x + w / 2, d["contigs_ge1kb_n"], width=w, color="#009E73", edgecolor="#333", linewidth=0.2, label="Contigs >= 1 kb (n)")
    ax.set_xticks(x)
    ax.set_xticklabels(d["sample_id"], rotation=90, fontsize=5.5)
    ax.set_ylabel("Count")
    ax.set_title("B. Contig counts per sample")
    ax.legend(loc="upper right", frameon=True, fancybox=False, edgecolor="#CCC")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{int(v):,}"))

    # C: mean length
    ax = axes[1, 0]
    colors = [METHOD_COLORS.get(str(m), "#BBB") for m in d["method"]]
    ax.bar(d["sample_id"], d["avg_len"], color=colors, edgecolor="#333", linewidth=0.3, width=0.82)
    ax.set_ylabel("Mean contig length (bp)")
    ax.set_xlabel("Sample")
    ax.set_title("C. Mean contig length per sample")
    ax.tick_params(axis="x", rotation=90, labelsize=5.5)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{int(v):,}"))
    meth_handles = [Patch(facecolor=METHOD_COLORS.get(m, "#BBB"), edgecolor="#333", label=METHOD_LABEL.get(m, m))
                    for m in method_codes_order(d)]
    ax.legend(handles=meth_handles, loc="upper right", frameon=True, fancybox=False, edgecolor="#CCC", fontsize=6)

    # D: >=1kb percent
    ax = axes[1, 1]
    ax.bar(d["sample_id"], d["ge1kb_pct"], color=colors, edgecolor="#333", linewidth=0.3, width=0.82)
    ax.set_ylabel("Contigs >= 1 kb (%)")
    ax.set_xlabel("Sample")
    ax.set_title("D. Percent of contigs >= 1 kb")
    ax.tick_params(axis="x", rotation=90, labelsize=5.5)
    ax.set_ylim(0, max(100.0, float(d["ge1kb_pct"].max()) * 1.1))
    ax.legend(handles=meth_handles, loc="upper right", frameon=True, fancybox=False, edgecolor="#CCC", fontsize=6)

    fig.suptitle("Fig04 Assembly", y=1.01, fontsize=10)
    fig.tight_layout()
    return _save(fig, out)


def generate_all_figures(tables: dict[str, pd.DataFrame], fig_dir: Path) -> dict[str, Path]:
    apply_sci_theme()
    mapping = {
        "fig01_stage_yield": fig01_stage_yield,
        "fig02_fastp_qc": fig02_fastp_qc,
        "fig03_rrna_qc": fig03_rrna_qc,
        "fig04_assembly": fig04_assembly,
    }
    # remove any previous figure files in this directory
    if fig_dir.is_dir():
        for old in fig_dir.glob("*.png"):
            try:
                old.unlink()
            except OSError:
                pass
    out: dict[str, Path] = {}
    for key, fn in mapping.items():
        p = fig_dir / f"{key}.png"
        try:
            res = fn(tables, p)
            if res:
                out[key] = res
        except Exception as e:
            print(f"warn: figure {key} failed: {e}")
    return out
```

### A. `w1_qc/reports.py`

```python
"""HTML and Markdown W1 QC reports."""
from __future__ import annotations

import base64
import html
from pathlib import Path
from typing import Any

import pandas as pd

from w1_qc.narrative import build_narrative
from w1_qc.scoring_doc import scoring_criteria_html
from w1_qc.units import (
    METRIC_LABELS,
    display_columns_for_report,
    format_cell,
    format_dataframe,
    format_number,
    summary_with_units,
)

HOST_LABEL = {"rat": "大鼠", "tick": "蜱", "mosquito": "蚊虫"}

FIG_ORDER = [
    "fig01_stage_yield",
    "fig02_fastp_qc",
    "fig03_rrna_qc",
    "fig04_assembly",
]


def _df_html(df: pd.DataFrame, max_rows: int | None = None) -> str:
    if df is None or df.empty:
        return "<p><em>无数据</em></p>"
    sub = df if max_rows is None else df.head(max_rows)
    # rename then format
    rename = {c: METRIC_LABELS.get(c, c) for c in sub.columns}
    view = sub.rename(columns=rename)
    fmt = format_dataframe(view)
    return fmt.to_html(index=False, border=0, classes="dataframe", escape=True)


def _img_embed(path: Path, alt: str = "") -> str:
    if not path.is_file():
        return ""
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    label = alt or path.stem
    return (
        f'<figure style="margin:18px 0">'
        f'<img src="data:image/png;base64,{data}" alt="{html.escape(label)}" '
        f'style="max-width:100%;height:auto;border:1px solid #e0e0e0"/>'
        f'<figcaption style="font-size:12px;color:#666;margin-top:4px">{html.escape(label)}</figcaption>'
        f"</figure>"
    )


def _summary_stats_table(summary: pd.DataFrame, metrics: list[str], tables: dict[str, pd.DataFrame]) -> str:
    sub = summary_with_units(summary, tables)
    keys = set(metrics)
    for m in metrics:
        keys.add(METRIC_LABELS.get(m, m))
        keys.add(f"{m} (%)")
        keys.add(f"{m}_pct")
    # match scaled names
    mask = sub["metric"].apply(
        lambda x: any(
            k == x or k in str(x) or str(x).startswith(k.split(" ")[0])
            for k in metrics
        ) or x in keys or any(METRIC_LABELS.get(m, m) == x for m in metrics)
    )
    # simpler: select by original metric names after conversion
    want_labels = set()
    for m in metrics:
        want_labels.add(m)
        want_labels.add(METRIC_LABELS.get(m, m))
        want_labels.add(METRIC_LABELS.get(f"{m}_Mb", ""))
        want_labels.add(METRIC_LABELS.get(f"{m}_Gb", ""))
        want_labels.add(METRIC_LABELS.get(f"{m}_pct", ""))
        want_labels.add(f"{m} (%)")
        want_labels.add(f"{m} (Mb)")
        want_labels.add(f"{m} (Gb)")
    want_labels.discard("")
    picked = sub[sub["metric"].isin(want_labels)].copy()
    if picked.empty:
        # fallback fuzzy
        picked = sub[sub["metric"].apply(lambda x: any(m in str(x) for m in metrics))].copy()
    return _df_html(picked)


def write_reports(
    out_dir: Path,
    batch_summary: dict[str, Any],
    tables: dict[str, pd.DataFrame],
    fig_paths: dict[str, Path],
    internal: bool = True,
) -> Path:
    host = batch_summary.get("host", "all")
    host_cn = HOST_LABEL.get(host, host)
    scores = tables["sample_qc_scores"]
    s1_sum = tables["stage_S1_fastp_summary"]
    s3_sum = tables["stage_S3_merge_summary"]
    s4_sum = tables["stage_S4_assembly_summary"]
    pass_txt = "通过" if batch_summary.get("batch_pass") else "需复核"
    rating_counts = batch_summary.get("rating_counts", {})
    low_depth = batch_summary.get("low_depth_samples", [])
    concern = scores[scores["overall_rating"].isin(["需关注", "不建议下游"])]["sample_id"].tolist()
    narrative = html.escape(build_narrative(batch_summary, tables, host_cn))
    scoring_block = scoring_criteria_html()

    s1_loss_display = display_columns_for_report(
        tables["stage_S1_fastp_loss_by_sample"],
        [
            "sample_id", "method_label",
            "reads_before_sum", "reads_after_fastp_sum", "removed_sum",
            "loss_low_quality_sum", "loss_too_short_sum", "loss_adapter_sum",
            "too_many_N_sum", "loss_unaccounted_sum",
        ],
    )

    fig_block = "".join(
        _img_embed(fig_paths[k] if k in fig_paths else out_dir / "figures" / f"{k}.png", k)
        for k in FIG_ORDER
        if (k in fig_paths) or (out_dir / "figures" / f"{k}.png").exists()
    )

    if internal:
        title = f"W1 上游 QC 内部报告 — {batch_summary['batch_id']} ({host_cn})"
        fname = out_dir / "report_internal.html"
        loss_run = display_columns_for_report(
            tables["stage_S1_fastp_loss_by_run"],
            ["run_id", "sample_id", "method_label", "reads_before", "reads_removed_fastp",
             "loss_low_quality", "loss_too_short", "loss_adapter", "too_many_N_reads", "loss_unaccounted"],
        )
        extra = f"""
        <h2>附录</h2>
        <p>阈值版本: {batch_summary.get('threshold_version')} · 生成时间: {batch_summary.get('generated_at')}</p>
        <p>命令: <code>python3 scripts/analysis/run_w1_qc_report.py --batch-id {batch_summary['batch_id']} --host {host}</code></p>
        <p>说明: 图片已 Base64 内嵌；reads 统一 Mb（×10⁶），bases 统一 Gb（×10⁹）；比例类指标以百分比显示（保留 2 位小数）；数值保留 2 位小数；整数使用千分位。</p>
        <p>说明: 本批次各样本 merge R1 reads 与 rRNA 去除后 clean R1 一致，深度图以样本级 Post-rRNA 汇总为准（raw/fastp/rRNA 已按 run 合并到样本）。</p>
        <h3>逐 run fastp 剔除明细</h3>
        {_df_html(loss_run, None)}
        """
    else:
        title = f"W1 上游数据质量报告 — {host_cn}样本"
        fname = out_dir / "report_delivery.html"
        extra = ""

    body = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"/>
<title>{html.escape(title)}</title>
<style>
body{{font-family:"Noto Sans CJK SC",sans-serif;max-width:1180px;margin:24px auto;padding:0 16px;line-height:1.5;color:#222}}
h1{{border-bottom:2px solid #1565c0;padding-bottom:8px}}
h2{{color:#1565c0;margin-top:28px}}
table.dataframe{{border-collapse:collapse;width:100%;font-size:12px}}
table.dataframe th,table.dataframe td{{border:1px solid #ddd;padding:4px 6px;text-align:right}}
table.dataframe th:first-child,table.dataframe td:first-child,
table.dataframe th:nth-child(2),table.dataframe td:nth-child(2){{text-align:left}}
table.dataframe th{{background:#e3f2fd}}
code{{background:#f5f5f5;padding:2px 4px}}
.summary-box{{background:#f8f9fa;border-left:4px solid #1565c0;padding:12px 16px;margin:16px 0}}
.narrative{{text-indent:2em}}
</style></head><body>
<h1>{html.escape(title)}</h1>
<div class="summary-box">
<p><strong>批次总体评价：</strong> {pass_txt}</p>
<p><strong>样本数：</strong> {batch_summary.get('n_samples')} · <strong>等级分布：</strong> {html.escape(str(rating_counts))}</p>
<p><strong>低深度样本：</strong> {', '.join(low_depth) or '无'}</p>
<p><strong>需关注样本：</strong> {', '.join(concern) or '无'}</p>
</div>

<h2>1. 执行摘要</h2>
<p class="narrative">{narrative}</p>
<p>本报告覆盖 Workflow1 上游：原始测序 (S0)、fastp 质控 (S1)、rRNA 去除 (S2)、样本级汇总/加测合并 (S3)、de novo 组装 (S4)。
reads 以 Mb、bases 以 Gb 计；Q30/GC/保留率为百分比。</p>

<h2>2. S0 原始数据</h2>
{_summary_stats_table(tables['stage_S0_raw_summary'], ['reads_before','bases_before','q30_before','gc_before','raw_reads_sum','raw_bases_sum','raw_q30_mean','raw_gc_mean'], tables)}

<h2>3. S1 fastp 质控</h2>
<p>剔除原因包括：低质量、过短、接头、N 过多、低复杂度、接头二聚体、过长及未归类（reads 以 Mb 计）。</p>
{_summary_stats_table(s1_sum, ['read_retention_fastp','q30_after_fastp','duplication_rate','read_retention_fastp_agg','mean_q30_after_fastp','reads_removed_fastp','mean_dup'], tables)}
<h3>样本级剔除汇总（全部样本）</h3>
{_df_html(s1_loss_display, None)}

<h2>4. S2 rRNA 去除</h2>
<p><strong>rrna_retention 计算：</strong>保留率 = clean_r1_reads / fastp_r1_reads（分母为 <em>fastp 质控后</em> 的 R1 reads，不是 raw data）。</p>
{_summary_stats_table(tables['stage_S2_rrna_summary'], ['rrna_retention_mean','mean_rrna_retention','rrna_removed_sum','rrna_removed_r1'], tables)}

<h2>5. S3 样本汇总 / 加测合并</h2>
<p>S3 为样本级结果文件合并（应对加测）。本批次 merge 与 rRNA 去除后 clean reads 一致，以下为样本级统计。</p>
{_summary_stats_table(s3_sum, ['merge_r1_reads','merge_r1_Mreads','merge_r1_bases','merge_r1_q30_pct','merge_r1_gc_pct','merge_loss_pct'], tables)}

<h2>6. S4 组装</h2>
<p><strong>指标区分：</strong>
<code>contigs_ge1kb_n</code> = 长度 ≥1 kb 的 contig <em>条数</em>；
<code>contigs_ge1kb_bp</code>（报告中 Gb）= 这些 ≥1 kb contig 的 <em>总碱基数</em>。
二者不是同一量纲：前者计条目数，后者计碱基总量。</p>
{_summary_stats_table(s4_sum, ['contigs_all_n','contigs_ge1kb_n','contigs_avg_len','contigs_max_len','contigs_ge1kb_bp'], tables)}

<h2>7. 样本综合 QC</h2>
{_df_html(scores[['sample_id','method_label','grade_S1','grade_S2','grade_S3','grade_S4','weighted_score','overall_rating']], None)}

{scoring_block}
<h2>8. 图件</h2>
{fig_block}
{extra}
</body></html>"""
    fname.write_text(body, encoding="utf-8")

    if not internal:
        md = _delivery_markdown(batch_summary, tables, host_cn, pass_txt, rating_counts, low_depth, concern)
        (out_dir / "report_delivery.md").write_text(md, encoding="utf-8")
    return fname


def _delivery_markdown(batch_summary, tables, host_cn, pass_txt, rating_counts, low_depth, concern) -> str:
    s3 = summary_with_units(tables["stage_S3_merge_summary"], tables)
    s1 = summary_with_units(tables["stage_S1_fastp_summary"], tables)
    s0 = summary_with_units(tables["stage_S0_raw_summary"], tables)
    lines = [
        f"# W1 上游数据质量报告（{host_cn}）",
        "",
        f"- **批次**: {batch_summary['batch_id']}",
        f"- **样本数**: {batch_summary.get('n_samples')}",
        f"- **批次评价**: {pass_txt}",
        f"- **等级分布**: {rating_counts}",
        f"- **低深度样本**: {', '.join(low_depth) or '无'}",
        f"- **需关注样本**: {', '.join(concern) or '无'}",
        "",
        "> reads=Mb，bases=Gb；百分比用 % 且保留 2 位小数；其他数值保留 2 位小数；整数用千分位。HTML 图件已内嵌。",
        "",
        "## 数据描述",
        "",
        build_narrative(batch_summary, tables, host_cn),
        "",
        "## S0 原始数据摘要",
        "",
        format_dataframe(s0).to_markdown(index=False),
        "",
        "## S1 fastp 摘要",
        "",
        format_dataframe(s1).to_markdown(index=False),
        "",
        "## S3 样本汇总",
        "",
        format_dataframe(s3).to_markdown(index=False),
        "",
        "## 结论与建议",
        "",
        "1. 样本级 Post-rRNA 深度与 fastp 后 Q30 是下游病毒发现的质量基础。",
        "2. rRNA 保留率异常需结合宿主背景解读。",
        "3. 低深度或「需关注」样本建议谨慎进入定量比较。",
        "",
        "## 图件",
        "",
        "- fig01_stage_yield — 各阶段 R1 reads(Mb) / bases(Gb)",
        "- fig02_fastp_qc — fastp 保留率 + 全样本剔除组成",
        "- fig03_rrna_qc — rRNA 保留率（分母=fastp）+ Post-rRNA 深度",
        "- fig04_assembly — 组装散点/条数/平均长度/≥1kb 占比",
        "",
    ]
    return "\n".join(lines)
```

### A. `w1_qc/narrative.py`

```python
"""Generate prose summary for W1 QC reports."""
from __future__ import annotations

from typing import Any

import pandas as pd

from w1_qc.units import BASE_DIVISOR, READ_DIVISOR


def build_narrative(batch_summary: dict[str, Any], tables: dict[str, pd.DataFrame], host_cn: str) -> str:
    s0 = tables["stage_S0_raw_by_sample"]
    s1 = tables["stage_S1_fastp_loss_by_sample"]
    s2 = tables["stage_S2_rrna_by_sample"]
    s4 = tables["stage_S4_assembly_sample"]
    scores = tables["sample_qc_scores"]

    n = batch_summary.get("n_samples", len(scores))
    pass_txt = "达到批次质控要求" if batch_summary.get("batch_pass") else "未达到批次质控要求，建议复核"
    rc = batch_summary.get("rating_counts", {})
    low = batch_summary.get("low_depth_samples", [])
    concern = scores[scores["overall_rating"].isin(["需关注", "不建议下游"])]["sample_id"].tolist()

    raw_mb = pd.to_numeric(s0["raw_reads_sum"], errors="coerce") / READ_DIVISOR
    clean_mb = pd.to_numeric(s2["clean_r1_sum"], errors="coerce") / READ_DIVISOR
    raw_gb = pd.to_numeric(s0["raw_bases_sum"], errors="coerce") / BASE_DIVISOR
    ret = pd.to_numeric(s1["read_retention_fastp_agg"], errors="coerce") * 100
    q30 = pd.to_numeric(s1["mean_q30_after_fastp"], errors="coerce") * 100
    raw_q30 = pd.to_numeric(s0["raw_q30_mean"], errors="coerce") * 100
    rrna = pd.to_numeric(s2["mean_rrna_retention"], errors="coerce") * 100
    contigs = pd.to_numeric(s4["contigs_ge1kb_n"], errors="coerce")

    loss_cols = ["loss_low_quality_sum", "loss_too_short_sum", "loss_adapter_sum", "too_many_N_sum", "loss_unaccounted_sum"]
    loss_tot = s1[loss_cols].sum()
    loss_tot.index = ["低质量", "过短", "接头", "N碱基过多", "未归类"]
    top_loss = loss_tot.idxmax()

    para1 = (
        f"本批次共评估{host_cn}样本 {n} 个（{batch_summary.get('batch_id')}）。"
        f"以样本为单位汇总各 lane 后，单样本原始 reads 中位数为 {raw_mb.median():.2f} Mb"
        f"（范围 {raw_mb.min():.2f}–{raw_mb.max():.2f} Mb），"
        f"原始碱基量中位数为 {raw_gb.median():.2f} Gb（范围 {raw_gb.min():.2f}–{raw_gb.max():.2f} Gb），"
        f"原始 Q30 中位数为 {raw_q30.median():.2f}%。"
    )
    para2 = (
        f"fastp 后样本级 reads 保留率中位数为 {ret.median():.2f}%"
        f"（{ret.min():.2f}%–{ret.max():.2f}%），"
        f"fastp 后 Q30 中位数为 {q30.median():.2f}%。"
        f"剔除 reads 的主要来源为「{top_loss}」。"
    )
    para3 = (
        f"rRNA 去除后平均保留率为 {rrna.mean():.2f}%（中位数 {rrna.median():.2f}%），"
        f"样本级 Post-rRNA R1 深度中位数为 {clean_mb.median():.2f} Mb"
        f"（范围 {clean_mb.min():.2f}–{clean_mb.max():.2f} Mb；本批次与 merge 结果一致）。"
        f"de novo 组装 ≥1 kb contig 中位数为 {contigs.median():,.0f} 条"
        f"（范围 {contigs.min():,.0f}–{contigs.max():,.0f} 条）。"
    )
    para4 = (
        f"综合评级：优 {rc.get('优', 0)} 个、良 {rc.get('良', 0)} 个、"
        f"可接受 {rc.get('可接受', 0)} 个、需关注 {rc.get('需关注', 0)} 个、"
        f"不建议下游 {rc.get('不建议下游', 0)} 个；批次总体{pass_txt}。"
    )
    if low:
        para4 += f" 低深度样本（Post-rRNA R1 < 5 Mb）：{', '.join(low)}。"
    if concern:
        para4 += f" 需重点关注：{', '.join(concern)}。"
    return "".join([para1, para2, para3, para4])
```

### A. `w1_qc/scoring_doc.py`

```python
"""Scoring criteria HTML block for reports."""
from __future__ import annotations

from w1_qc.standards import STAGE_WEIGHTS, THRESHOLD_VERSION


def scoring_criteria_html() -> str:
    w = STAGE_WEIGHTS
    return f"""
<h2>评分标准（阈值版本 {THRESHOLD_VERSION}）</h2>
<h3>单指标等级（A–F）</h3>
<table class="dataframe">
<thead><tr><th>阶段</th><th>指标</th><th>A（优）</th><th>B（良）</th><th>C（可接受）</th><th>D（需关注）</th><th>F（不合格）</th></tr></thead>
<tbody>
<tr><td>S3 合并深度</td><td>merge R1 reads</td><td>≥15 Mb</td><td>≥10 Mb</td><td>≥5 Mb</td><td>≥2 Mb</td><td>&lt;2 Mb</td></tr>
<tr><td>S1 fastp</td><td>read 保留率</td><td>≥0.85</td><td>≥0.80</td><td>≥0.70</td><td>≥0.60</td><td>&lt;0.60</td></tr>
<tr><td>S1 fastp</td><td>Q30（过滤后）</td><td>≥0.92</td><td>≥0.90</td><td>≥0.85</td><td>≥0.80</td><td>&lt;0.80</td></tr>
<tr><td>S1 fastp</td><td>PCR 重复率</td><td>≤0.15</td><td>≤0.20</td><td>≤0.30</td><td>≤0.40</td><td>&gt;0.40</td></tr>
<tr><td>S2 rRNA</td><td>保留率</td><td>0.75–0.98</td><td>0.65–0.99</td><td>0.50–0.99</td><td>0.40–0.99</td><td>&lt;0.40 或 &gt;0.99</td></tr>
<tr><td>S4 组装</td><td>≥1 kb contigs</td><td>≥8000</td><td>≥5000</td><td>≥3000</td><td>≥1000</td><td>&lt;1000</td></tr>
</tbody>
</table>
<h3>样本综合评级（加权）</h3>
<p>S1 质量（保留率+Q30+重复率均值）权重 {w['S1_quality']:.0%}；
S2 rRNA 权重 {w['S2_rrna']:.0%}；
S3 深度权重 {w['S3_depth']:.0%}；
S4 组装权重 {w['S4_assembly']:.0%}。
各子项 A=4、B=3、C=2、D=1、F=0，加权均分映射为：
<strong>优</strong> ≥3.5、<strong>良</strong> 3.0–3.49、<strong>可接受</strong> 2.0–2.99、
<strong>需关注</strong> 1.0–1.99、<strong>不建议下游</strong> &lt;1.0。</p>
<h3>批次通过标准</h3>
<p>≥80% 样本为「良」及以上，且「不建议下游」占比 ≤10%。</p>
<h3>单位约定</h3>
<p>reads 统一为 <strong>Mb</strong>（×10⁶ reads）；bases 统一为 <strong>Gb</strong>（×10⁹ bp）；比例类指标以 <strong>%</strong> 显示（保留 2 位小数）；其他数值保留 2 位小数；整数使用千分位。</p>
"""
```

---

## 6. 维护

- 修改阈值：编辑 `w1_qc/standards.py`，同步本指南 §2.4，递增 `THRESHOLD_VERSION`。
- 修改图件：编辑 `w1_qc/plots.py` / `reports.py` 中 `FIG_ORDER`。
- 在本仓库更新可移植包后，请重新打包：

```bash
cd /path/to/XvirBench
tar -czf docs/w1_qc_portable.tar.gz -C docs w1_qc_portable
# 并重新运行本生成脚本以刷新本 md 附录（见 scripts 或 docs 维护说明）
```

旧文档 `W1_QC_STANDARD.md` 仅作跳转，以本文件 + `w1_qc_portable/` 为准。
