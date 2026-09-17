# 工作流完成后分析：标准化建设方案

**版本**：1.0（2026-09-16）  
**用途**：把「计算流程 → 指标提取 → 提示词约束 → 结构化报告」拆成可迁移的标准层，供其他平台复用。  
**参考实现**：宏转录组 / 宏病毒组七流程（W1–W7）及 XvirBench 后分析包。  
**本仓库规范原文**（提示词全文 + 源码附录）：`FULL_PIPELINE_ANALYSIS_SYSTEM.md` / `.html`。

本文写**逻辑与文件对应**，不替代各流程的 Snakemake 计算规范。计算侧换工具、换物种、换平台时，应保留本文的分层与契约，只替换「目录名 / 提取器 / 指标字典 / 生物学问题清单」。

---

## 1. 三层分离（其他平台必须保留）

| 层 | 做什么 | 不做什么 | 本仓库落点 |
|----|--------|----------|------------|
| **计算流程** | 对原始数据跑分析，写出各流程结果目录 | 不写解读、不画 SCI 报告图 | `Workflows/workflowN_*/` 的 Snakemake 产物 |
| **提取** | 把异构结果解析成统一长表 + 样本主表 | 不编造缺失字段；不把「没跑」写成失败 | 各流程 `scripts/extract_results.py` + `benchmark/package/xvir_full/extract.py` |
| **规范 + 报告** | 提示词约束统计/作图/生物学讨论；输出 TSV、自包含 HTML、横向 PDF | 不手改报告字节；图必须能离开原目录打开 | `package/SPEC.md` → `narrative.py` / `biology.py` / `report.py` |

三条硬边界：

1. **计算与提取解耦**：报告程序只认 `extract_all(result_dir) -> {tables: {表名: [行]}}`，不直接解析 BAM/FASTQ。
2. **提示词与生成器同源**：口径写在提示词里，实现写在脚本里；改版面先改提示词和脚本，再重跑，禁止手工改 `report.html` / `report.pdf`。
3. **缺失是状态不是事故**：某流程未运行 → 整章跳过并写原因；不得补零、不得画空图框。

---

## 2. 逻辑总图

```
原始数据
    │
    ▼
【计算流程】W1 上游 →（W2 病毒鉴定 ∥ W3 宿主 ∥ W4 微生物谱）→ W5 定量 → W6 注释
            W7 建库方法学（并行，不替代上游）
    │  产物：各 workflowN_*/ 结果目录 + 可选 groupinfo/sampleinfo
    ▼
【发现】哪些流程真实存在？样本 ID / 宿主 / 方法？哪些因子可以分组？
    │
    ▼
【提取】对每个存在的流程调用 extract_results.py
    │  产物：extracted/W1…W7/*.tsv
    │        失败时可回退 reports/*benchmark_metrics.xlsx
    ▼
【汇总】coverage.tsv（流程×表覆盖）
        master_sample_metrics.tsv（样本一行）
    │
    ▼
【统计】总体描述；仅当分组可用时 KW + MW(BH) + 效应量
【绘图】ggplot2 SCI 风格，缺数据则 skip
【叙述】结果数字 + 绑图绑表的生物学讨论
    │
    ▼
【报告】report.html（图 base64 嵌入）
        report.pdf（同源 HTML → A4 横向）
        tables/  figures/  r/
```

数据只沿箭头向下走：报告不得回写计算目录；生物学段落必须能回溯到某张图或某张 TSV。

---

## 3. 计算流程（本参考实现）

病毒分析主链推荐顺序：**W1 →（W2 ∥ W3 ∥ W4）→ W5 → W6**。W7 为建库打断方法学，与主链并行。

| ID | 计算目录 | 定位 | 典型输入 | 典型输出（提取器去读的） |
|----|----------|------|----------|--------------------------|
| W1 | `workflow1_upstream` | 质控、去 rRNA、合并、组装 | 原始 PE FASTQ | `filter/` `merge/` `assembly/` |
| W2 | `workflow2_virusid` | HMM 病毒鉴定 + 聚类 | W1 contigs | `downstream/` `summary/` |
| W3 | `workflow3_hostid` | 线粒体标记宿主鉴定 | W1 clean reads / contigs | `by_sample_v3/` `reports/` |
| W4 | `workflow4_kraken_bracken` | Kraken2 + Bracken 微生物谱 | W1 clean reads | `results/kraken2/` `results/bracken/` |
| W5 | `workflow5_virus_quantification` | 病毒 contig RPM | W2 参考 + W1 clean reads | `results/summary/` `results/coverage/` |
| W6 | `workflow6_virus_annotation` | CheckV / 功能注释 | W2 序列 | `results/checkv/` `results/function/` |
| W7 | `workflow7_fragmentation_benchmark` | RNA vs cDNA 打断比较 | clean PE + 宿主参考 | `summary/` `metrics/` |

**存在性判定**（`xvir_full/discover.py`）：`run-dir/<dirname>/` 存在，且至少命中 `config.py` 里该流程的一个 marker 子路径；空目录视为未运行。

**指标字典规模**（设计口径，见 `Workflows/docs/WORKFLOW_SUMMARY.md` 或 `XvirBench/docs/WORKFLOW_SUMMARY.md`）：W1 25、W2 18、W3 11、W4 8、W5 11、W6 10、W7 21。提取器实际落表可以更多或更少；**覆盖矩阵记录的是非空表，不是字典条数**。

其他平台对应关系：把上表的「计算目录 / 定位 / 输入输出」换成该平台的 pipeline 名称即可，ID 仍建议稳定（W1…Wn 或模块短名），便于报告章节与图号绑定。

---

## 4. 提取方法

### 4.1 统一调用约定

每个计算流程必须提供：

```
<workflows-root>/<workflow_dir>/scripts/extract_results.py
```

入口函数：

```python
def extract_all(result_dir: Path) -> dict:
    # 返回
    # {
    #   "workflow": "...",
    #   "version": "1.0.0",
    #   "result_dir": "...",
    #   "extracted_at": ISO-8601,
    #   "tables": { "<table_key>": [ {col: val, ...}, ... ] }
    # }
```

W1 额外接受样本清单：`extract_all(result_dir, sample_list=None)`，用于 run → 生物学样本映射。

公共读写（本仓库）：`XvirBench/scripts/extract_io.py`  
`base_payload()` / `read_tsv_safe()` / `df_records()` / `write_json()` / `write_xlsx()`。

后分析包加载方式（`xvir_full/extract.py`）：`importlib` 按路径加载提取器，把 `tables` 写成 `extracted/<SHORT>/<table_key>.tsv`，完整 payload 写成 `*_extracted.json`（**JSON 只落盘，不进报告**）。提取器崩溃时尝试 `run-dir/reports/*benchmark_metrics.xlsx` 按工作表名回退。

### 4.2 本实现：流程 → 提取器 → 表键

| 流程 | 提取脚本 | 关键 `tables` 键 | 进入样本主表的优先列 |
|------|----------|------------------|----------------------|
| W1 | `Workflows/workflow1_upstream/scripts/extract_results.py` | `run_qc`, `samples`, `summary` | `merge_r1_reads`, `q30`, `contigs_ge1kb_n`, fastp/rRNA 保留率 |
| W2 | `…/workflow2_virusid/scripts/extract_results.py` | `contigs`, `cluster_members`, `cluster_summary`, `sample_cluster`, `hmm_iterations` | `n_putative_viral_contigs`, `n_high_quality`, `n_clusters` |
| W3 | `…/workflow3_hostid/scripts/extract_results.py` | `host_contig`, `host_sample`, `host_top_species`, `marker_coverage` | `n_species_inferred`, `top_host_species` |
| W4 | `…/workflow4_kraken_bracken/scripts/extract_results.py` | `sample_qc`, `bracken_top15_species`, `combined_species` | `kraken_unclassified_frac`, `bracken_species_taxa` |
| W5 | `…/workflow5_virus_quantification/scripts/extract_results.py` | `sample_summary`, `rpm_full`, `top20_rpm`, `cleanreads` | `mapping_rate_pct`, `max_rpm`, `median_rpm` |
| W6 | `…/workflow6_virus_annotation/scripts/extract_results.py` | `checkv`, `annotation_summary` | （可无样本级列） |
| W7 | `…/workflow7_fragmentation_benchmark/scripts/extract_results.py` | `comparison`, `method_summary` | STAR/Picard 百分率 |

编排器：`benchmark/package/xvir_full/extract.py`（`extract_one` / `extract_all_present`）。  
流程清单与 marker：`benchmark/package/xvir_full/config.py` 中 `WORKFLOWS`。

### 4.3 样本 Meta 与分组

| 输入 | 格式 | 作用 |
|------|------|------|
| `cohorts/groupinfo.txt` 或上级 `groupinfo.txt` | 无表头、制表符：原始编号、SN、宿主、建库方法 | 生物学样本、host、method；`61` 规范为 `v61` |
| `cohorts/sampleinfo.txt` | 无表头：run_id、sample_id、fq1、fq2 | n_runs、W1 run 映射 |
| `lists/w1_samples.txt` | 可选 | W1 提取器的样本清单 |

分组检测顺序（`GROUP_CANDIDATES`）：`method`, `host`, `group`, `treatment`, `condition`, `library`, `batch`。  
**可用因子**：水平 ≥2，且至少两个水平 n≥2。全队列同一宿主 → 该因子不做组间检验。  
实现：`xvir_full/discover.py`。

低深度规则（本领域缺省，其他平台应改成自己的阈值）：合并 R1 < 5×10^6 reads → `low_depth=True`；RPM、物种数、contig 数不得单独解释为生物学差异。

### 4.4 汇总表（提取之后、报告之前）

| 产物 | 生成模块 | 含义 |
|------|----------|------|
| `tables/coverage.tsv` | `tables.py` `coverage_matrix` | 每个流程 extracted / missing / empty |
| `tables/master_sample_metrics.tsv` | `tables.py` `master_sample_table` | 生物学样本一行，左联 Meta + 各流程样本级列 |
| `tables/W*_*.tsv` | `plots_r.py` `stage_tables` | 供 R 作图的 staged 长表 |
| `tables/stats/overall_core.tsv` | `stats.py` | 核心队列描述统计 |
| `tables/stats/by_group.tsv` | `stats.py` | 分组描述 |
| `tables/stats/tests.tsv` | `stats.py` | Kruskal–Wallis、Mann–Whitney BH、ε²、rank-biserial |

统计协议：永远先总体；有可用分组才做非参数检验；p 与效应量必须一起出现；不得把 p≥0.05 写成方法等价。实现：`xvir_full/stats.py`。

---

## 5. 提示词（规范层）

提示词不是聊天记录，而是**可复制的合格标准**。本体系把提示词写在 `package/SPEC.md` 第 1 节，再由 `build_system_document.py` 拼上全部脚本，生成单文件交付物：

- `benchmark/FULL_PIPELINE_ANALYSIS_SYSTEM.md`
- `benchmark/FULL_PIPELINE_ANALYSIS_SYSTEM.html`

### 5.1 给分析 AI 的总任务（可改写到其他平台）

在**计算已经完成（或只完成一部分）**之后，执行：发现 → 提取真实字段 → 统计与 SCI 作图 → 写自包含 HTML 与横向 PDF。顺序不可颠倒。

### 5.2 硬规则（跨平台建议原样保留语义）

| # | 规则 | 目的 |
|---|------|------|
| 1 | 不编造未提取字段 | 防止报告看起来「很全」实际是假数 |
| 2 | 缺失流程 ≠ 质控失败 | 部分运行仍可交付 |
| 3 | 分类器/比对结果不是诊断或分类终裁 | 合规 |
| 4 | 低深度样本单独标注 | 相对丰度分母效应 |
| 5 | 无分组只做总体 | 避免假比较 |
| 6 | 缺列就跳过该图 | 不画全 0 |
| 7 | 图必须能在绘图脚本里定位 | 可复现 |
| 8–10 | 计量、轴标题语言、只解释本批次 | 口径一致 |
| 11 | 图以 data URI 嵌入报告 | 单文件可转发 |
| 12–13 | 报告内无 JSON、无绝对路径 | 可读、可脱敏 |
| 14 | 小数位：整数 / 2 位 % / 4 位比例与 p | 禁止 IEEE 长尾 |
| 15 | 先改提示词和生成脚本，再重跑报告 | 禁止手改成品 |
| 16 | 生物学必须绑图绑表；与实验设计冲突的优势类群要写：冲突、机制、去除后格局、方法/深度是否改变 | 禁止空话 |

PDF 另有一节独立提示词（SPEC §1.4）：与 HTML **同一套数字**，A4 横向，HTML→PDF 引擎烘焙，禁止截图网页。

### 5.3 生物学讨论协议（各流程必须回答的问题）

实现：`xvir_full/biology.py`（由 `narrative.py` 填进各章）。模板可迁移：把「图号 + 必须回答的问题」换成新平台模块。

| 章节 | 默认图 | 必须用数据回答 |
|------|--------|----------------|
| Meta / 深度 | fig01 | 谁低于深度阈值？是个别样本还是某方法共有？ |
| W1 | fig02–fig05 | 保留率、Q30、rRNA 离群样本、contig 是否随深度上升 |
| W2 | fig06–fig08 | CheckV 各级条数；低深度样本病毒 contig 是否更少 |
| W3 | fig09 | 推断宿主是否与实验设计一致 |
| W4 | fig10–fig12 | 未分类比例；第一名若与宿主冲突则执行硬规则 16 的 (i)–(iv) |
| W5 | fig13–fig15 | 高 RPM 是否就是低深度样本（分母效应） |
| 跨流程 | 对照已有图 | W3 宿主 vs W4 人源；W1 深度 vs W5 RPM |

绘图视觉：`package/r/00_sci_theme.R`（Okabe–Ito、theme_classic）；图清单：`package/r/make_figures.R`。编排：`xvir_full/plots_r.py`。

---

## 6. 结构化报告

### 6.1 固定章节顺序（HTML 与 PDF 相同）

1. 执行摘要（n、已提取/跳过、分组决策、低深度名单、免责）  
2. 样本 Meta 与提取覆盖  
3. W1 … W7（缺失则一节「跳过」+ 原因，无空图）  
4. 跨流程衔接（至少两个下游流程存在时）  
5. 结构化表（coverage、主表、描述统计、检验；不要提取日志 JSON）  
6. 方法学摘要  
7. 附录：R 脚本（相对路径文件名）  
8. 页脚免责声明  

每章未跳过时三块齐全：**结果（数字）→ 图 → 生物学意义**。  
实现：`narrative.py` 组章节，`report.py` 渲染，`display.py` 管小数与路径缩短。

### 6.2 版式契约

| 项 | 规定 |
|----|------|
| HTML 图 | `<img src="data:image/png;base64,...">`，拷贝单文件仍能看图 |
| 图宽 | 约内容区 48%；连续两张 `table.fig-pair` 并排；单张 `table.fig-one` 居中 |
| HTML 表 | `.table-wrap { overflow-x: auto }` |
| PDF | `@page { size: A4 landscape }`，WeasyPrint 由 HTML 烘焙 |
| 路径 | 单元格相对尾路径；公共前缀写表注 |
| 风格 | 白底、无衬线、三线表；轴标题英文 |

### 6.3 一次运行的落盘

```
benchmark/runs/<batch_id>/
  report.html          # 自包含，给人读
  report.pdf           # 与 HTML 同源
  discovery.json       # 仅磁盘，不进报告
  extracted/W1…W7/*.tsv
  tables/coverage.tsv
  tables/master_sample_metrics.tsv
  tables/stats/{overall_core,by_group,tests}.tsv
  figures/*.png *.pdf
  r/00_sci_theme.R
  r/make_figures.R
```

入口：`benchmark/package/run_full_pipeline_analysis.py`  
`--run-dir` 计算产物根；`--out-dir` 分析输出；`--skip-extract` 复用已提取表后重做统计/图/报告。

示例批次：`benchmark/runs/pxy_V350399508/`（W1–W5 提取，W6/W7 跳过；11 个大鼠样本 × 3 种建库方法）。

---

## 7. 文件对照表（逻辑实体 → 路径）

### 7.1 规范与提示词

| 逻辑实体 | 文件 |
|----------|------|
| 入口说明 | `XvirBench/benchmark/README.md` |
| 提示词 + 硬规则 + 报告结构（源） | `benchmark/package/SPEC.md` |
| 单文件交付（SPEC + 全部脚本附录） | `benchmark/FULL_PIPELINE_ANALYSIS_SYSTEM.md` / `.html` |
| 从 SPEC 重建上述单文件 | `benchmark/package/build_system_document.py` |
| 指标 ID 字典（W1-R01…） | `Workflows/docs/WORKFLOW_SUMMARY.md`，副本 `XvirBench/docs/WORKFLOW_SUMMARY.md` |
| 仅 W1 的旧便携规范（本体系的前身） | `XvirBench/docs/w1_qc_portable/` |

### 7.2 计算与提取

| 逻辑实体 | 文件 |
|----------|------|
| 七流程计算代码与结果约定 | `Workflows/workflow{1–7}_*/` |
| 各流程提取器 | `Workflows/<workflow>/scripts/extract_results.py` |
| 提取器公共 IO | `XvirBench/scripts/extract_io.py` |
| 流程契约（目录名、marker、表键、跳过用语） | `benchmark/package/xvir_full/config.py` |
| 发现流程 + Meta + 分组 | `benchmark/package/xvir_full/discover.py` |
| 调用提取器、xlsx 回退 | `benchmark/package/xvir_full/extract.py` |

### 7.3 统计、图、叙述、报告

| 逻辑实体 | 文件 |
|----------|------|
| 覆盖矩阵 + 样本主表 | `benchmark/package/xvir_full/tables.py` |
| 描述统计与检验 | `benchmark/package/xvir_full/stats.py` |
| 调 R、staging 表 | `benchmark/package/xvir_full/plots_r.py` |
| ggplot2 主题 / 15 张默认图 | `benchmark/package/r/00_sci_theme.R`，`make_figures.R` |
| 结果段落（中位数、范围、p） | `benchmark/package/xvir_full/narrative.py` |
| 绑图生物学讨论 | `benchmark/package/xvir_full/biology.py` |
| 小数、路径脱敏 | `benchmark/package/xvir_full/display.py` |
| HTML/PDF | `benchmark/package/xvir_full/report.py` |
| 一键编排 | `benchmark/package/run_full_pipeline_analysis.py` |
| Python 依赖 | `benchmark/package/requirements.txt` |

### 7.4 与旧组件的边界（避免重复建设）

| 旧组件 | 关系 |
|--------|------|
| `docs/w1_qc_portable` | 只做 W1 评分与 4 张图；本方案扩展到 W1–W7，缺失整章跳过 |
| `XvirBench/scripts/extract_metrics.py` | 批次 harmonized TSV；本方案直接打运行根目录 |
| `scripts/analysis/run_analysis.py` | 旧分组 HTML（matplotlib）；本方案改为 ggplot2 + 强制跳过 |
| `scripts/build_harmonized_excel.py` | Excel 交付；本方案输出 HTML + TSV，不替代 Excel |

---

## 8. 迁到其他平台时改什么、不改什么

**建议原样保留**

- 三阶段顺序：发现/提取 → 统计作图叙述 → 结构化报告  
- `extract_all()` 返回 `tables` 字典  
- 覆盖矩阵 + 样本主表  
- 「缺失跳过、不编造、不诊断、先改规范再重跑」  
- 自包含 HTML + 同源横向 PDF  
- 生物学绑图：(i) 冲突 (ii) 机制 (iii) 去除后格局 (iv) 方法/深度  

**必须按新平台替换**

| 替换项 | 改哪里 |
|--------|--------|
| 流程名称、目录、marker | `config.py` 的 `WORKFLOWS`（或等价注册表） |
| 结果解析 | 各 `extract_results.py` |
| 指标字典与 ID | 该平台的 SUMMARY/数据字典，对齐提取表键 |
| 样本 Meta 列 | `discover.py` 的 groupinfo 契约 |
| 低深度/质控阈值 | `config.py` 的阈值 + 生物学问题清单 |
| 默认图与必须回答的问题 | `make_figures.R` + `biology.py` + SPEC §8 |
| 配色与分组因子 | 主题 R 脚本；`GROUP_CANDIDATES` |
| 免责与领域用语 | `report.py` 页脚；提示词第 1 节角色描述 |

**落地检查清单（新平台第一条批次）**

1. 只跑部分流程时，报告是否整章跳过且不出现空图。  
2. 拷贝 `report.html` 到无 `figures/` 的目录，图是否仍在。  
3. 表中是否无绝对路径、无 JSON、小数位符合规范。  
4. 生物学每一段是否出现图号或样本级数字。  
5. 改一句提示词后，是否只能通过重跑生成器看到报告变化。

---

## 9. 推荐阅读顺序

1. 本文（分层与文件对应）  
2. `FULL_PIPELINE_ANALYSIS_SYSTEM.md` 第 1 节（可复制提示词）与第 3–9 节（决策树、契约、报告结构）  
3. `docs/WORKFLOW_SUMMARY.md`（计算侧指标 ID）  
4. 示例 `runs/pxy_V350399508/report.html`  
5. 改口径时：先改 `package/SPEC.md` 与对应 `.py`/`.R`，运行 `build_system_document.py`，再 `run_full_pipeline_analysis.py`

运行示例：

```bash
export XVIRBENCH_ROOT=/path/to/XvirBench
export PYTHONPATH=$XVIRBENCH_ROOT/benchmark/package:$XVIRBENCH_ROOT/scripts
python3 $XVIRBENCH_ROOT/benchmark/package/run_full_pipeline_analysis.py \
  --run-dir /path/to/runs/<batch_id> \
  --out-dir $XVIRBENCH_ROOT/benchmark/runs/<batch_id> \
  --batch-id <batch_id>
```
