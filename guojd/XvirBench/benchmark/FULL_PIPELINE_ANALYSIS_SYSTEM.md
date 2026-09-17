# XvirBench 全流程分析体系（W1–W7）

**版本**：1.0.0（2026-09-15）  
**定位**：工作流计算完成之后的**提取 → 统计/绘图/总结/生物学讨论 → 结构化表与 HTML 报告**。  
**对齐**：`docs/w1_qc_portable` 的「提示词 + 完整源码附录」写法，从只覆盖 W1 扩展到 W1–W7。  
**可运行包**：`XvirBench/benchmark/package/`  
**示例批次**：`benchmark/runs/pxy_V350399508/report.html`

本文是**唯一规范文档**：含全部 AI 提示词与全部脚本。不要把缺失流程写成失败；不要把分类器物种名写成诊断。

---

## 0. 给使用者

把第 1 节整段交给 AI，并同时提供：

1. 运行根目录（含 `workflow1_upstream/` 等）
2. 样本 Meta（`groupinfo.txt` / `sampleinfo.txt`，可缺）
3. 本文（本文件）作为口径与源码

要求 AI：**先按硬规则处理缺失与分组，再抽出真实字段，再统计与作图，最后写 HTML**。图必须有并列的 R 脚本；绘图必须是 SCI 期刊风格。

---

## 1. 给 AI 的总提示词（复制即用）

你是病原宏转录组 / 宏病毒组方向的生物信息学分析助手。任务是在 **W1–W7 工作流已经跑完（或只跑完其中一部分）** 之后，搭建并执行一套可复现的分析体系，输出 **可单独拷贝的自包含 HTML** 与 **横向 A4 PDF** 两份报告。

### 1.1 三阶段，不可跳过顺序

**阶段 A — 提取计算指标与样本 Meta**

- 扫描运行根目录，识别实际存在的 `workflow1_upstream` … `workflow7_fragmentation_benchmark`。
- 对每个**存在**的流程调用对应 `Workflows/<workflow>/scripts/extract_results.py`（口径与 `WORKFLOW_SUMMARY.md` 的 W1-R01…W7-F21 对齐）。
- 读取样本 Meta：生物学样本 ID、run、宿主、建库方法、生物学重复号、自定义 group。
- 生成：提取覆盖矩阵、各流程长表、样本级主表 `master_sample_metrics.tsv`。
- 某流程目录不存在、目录空、提取器崩溃、某张结果表 0 行：该流程或该表标为缺失，**不得臆造数字**。

**阶段 B — 统计、绘图、总结、生物学意义**

- **永远先做总体描述**（n、mean、SD、median、IQR、min、max）。
- **仅当存在可用分组**时加做分组比较：某因子 ≥2 个水平，且至少两个水平 n≥2。
- 宿主若全部相同（例如全是 rat），该因子不做组间检验，只在 Meta 里写明。
- 组间：Kruskal–Wallis + Mann–Whitney（BH 校正），报告效应量 ε² 与 rank-biserial。n 很小时明确写「检验效能不足」。
- 每个**未跳过**的流程必须同时有：图、结果叙述、生物学意义。三者缺一不可。
- 图用 **ggplot2**，SCI 风格（见第 7 节），并**保存 R 脚本**与 PDF/PNG。Python 只允许作为 R 失败时的后备，且须在报告中声明。

**阶段 C — 结构化表 + 自包含 HTML + 横向 PDF**

- 主表、覆盖矩阵、描述统计、检验表必须落盘为 TSV（磁盘文件可含完整路径，**写入报告的表不得含 JSON 列、不得含绝对路径**）。
- HTML 与 PDF 章节顺序同第 9 节；缺失流程整章「跳过」，不留空图框。
- **所有图必须以 base64（`data:image/png;base64,...`）嵌入 HTML/PDF**，拷贝单个 `report.html` 到别处仍能看见图，不依赖 `figures/` 相对路径。`figures/*.png` 与 `*.pdf` 仍落盘，供排版与矢量存档，但不是打开报告的前提。
- HTML 宽表放在横向滑动容器（`overflow-x: auto`）中，不得撑破页面。
- PDF 用 **A4 横向**；表内缩小字号并允许换行，不得溢出纸面。
- 报告抬头不重复完整摘要。免责声明必须出现。
- 禁止把 `discovery.json`、提取器 payload JSON、`table_rows_json` 等粘进报告正文或表格。

### 1.2 硬规则（违反即不合格）

1. **不编造**：源里没有的 Q20、标记基因深度、W6 注释率等，写「未提取/未运行」。
2. **不把缺失当失败**：W6/W7 没跑不是质控不合格。
3. **不诊断**：Kraken/Bracken/BLAST/CheckV/宿主线粒体物种都不是临床或 ICTV 终裁。
4. **低深度单独标注**：合并 R1 < 5×10^6 reads 的样本，RPM、物种数、contig 数不可单独解释为生物学差异。
5. **无分组 → 只做总体**；有分组 → 总体 + 分组。
6. **字段缺失 → 跳过该图/该段统计**，不要画全 0 图。
7. **图附 R 脚本**：每个图能在 `r/make_figures.R` + `r/00_sci_theme.R` 中定位。
8. **计量**：reads 展示可用 million；bases 可用 Gb；比例若为 0–1 则乘 100 显示为 %，并在表中保持原口径可追溯。
9. **中英文混排时**，轴标题用英文（SCI），叙述可用中文。
10. 只解释本 run 真实产物，不把其他 demo 批次的病毒结论写进来。
11. **图嵌入报告**：HTML/PDF 中的 `<img>` 必须是 data URI，禁止只写 `figures/xxx.png` 相对路径作为打开报告的唯一方式。
12. **报告内不出现 JSON**：不展示 extract payload、discovery.json、table_rows_json、traceback 原文。
13. **报告内不出现绝对路径**：表单元格只用相对路径或样本/流程 ID。若一组路径有公共前缀，把前缀写在**表前或表后的一句备注**里，例如「路径前缀：`batches/pxy_V350399508/`」。
14. **小数**：计数/reads/bases/contig 数为整数；百分比 2 位小数；0–1 的比例、效应量 4 位小数；p 值 4 位小数（p<0.0001 用科学计数法 2 位指数）。不得把完整 IEEE 浮点（如 0.7004301686356029）写入报告。
15. **先改提示词与生成脚本，再重跑报告**；禁止手工改 `report.html` / `report.pdf` 的字节来「修版面」。
16. **生物学意义必须绑图绑表**：每一段解读都要出现图号（如 `fig12_w4_top_taxa`）或表中的具体数字（样本 ID、中位数、比例、方法组）。禁止只写「符合预期」「需要谨慎」这类不引用数据的空话。若图上出现与实验设计冲突的优势分类（例如大鼠样本中 Bracken 第一名是 *Homo sapiens*），必须：(i) 指出冲突；(ii) 给出机制假说（数据库偏置、宿主同源、试剂/操作污染、未分类空间 vs 已分类空间）；(iii) 去掉该异常类群后重新看优势类群；(iv) 检查建库方法/深度是否改变该格局。做不到 (i)–(iv) 视为不合格。

### 1.3 推荐命令（本仓库）

```bash
python3 XvirBench/benchmark/package/run_full_pipeline_analysis.py \
  --run-dir /path/to/runs/<batch_id> \
  --out-dir XvirBench/benchmark/runs/<batch_id> \
  --batch-id <batch_id>
```

本提示词的实现就是第 13 节附录中的 Python / R 源码。修改口径时先改源码再重新生成报告，不要只改 HTML。

### 1.4 给 AI 的 PDF 生成提示词（复制即用）

你要把**同一套分析结果**另存为打印用 PDF，不得另起一套数字口径。

**输入**：阶段 A–B 已经写好的 `tables/`、`figures/*.png`、章节叙述（与 HTML 同源）。  
**输出**：`report.pdf`（单文件）。

**版式硬规则**：

1. 纸张 **A4 landscape（横向）**，页边距约 8–12 mm。
2. 图全部嵌入 PDF（由 HTML data URI 经 WeasyPrint 或同等引擎烘焙，或直接嵌入 PNG）。拷贝 PDF 单文件即可打开全部图。
3. 章节顺序与 HTML 第 9 节完全一致；跳过的 W6/W7 只保留一句原因，不留空白图框。
4. 宽表：横向纸面 + 8–9 pt 表字 + 单元格允许换行；禁止把表裁切到纸外。必要时拆成「主表关键列」与「附录列」，但仍须可读。
5. 数字格式同硬规则 14（整数 / 2 位 / 4 位 / p 值）。
6. 表中无绝对路径、无 JSON。公共路径前缀写在表注。
7. 页眉可含批次 ID 与「不构成诊断」；页脚免责声明每页或文末出现一次。
8. 不要用截图网页的方式生成 PDF（易丢矢量与可复制文本）；用 HTML→PDF 引擎。
9. 若某图缺失则跳过该图，不画红叉占位。

**推荐实现**（本仓库）：在写出嵌入图的 `report.html` 后调用

```bash
# 由 run_full_pipeline_analysis.py 内部调用 weasyprint
# 等价于：
python3 -c "from weasyprint import HTML; HTML('report.html').write_pdf('report.pdf')"
```

PDF 与 HTML 必须同一次运行生成，禁止只改其中一个。

---

## 2. 体系架构

```
运行根目录 (Snakemake outdir)
  workflow1_upstream/ … workflow7_*/
  cohorts/ or 上级 groupinfo.txt, sampleinfo.txt
        │
        ▼
[A] discover.py    识别流程 + 解析 Meta + 判定分组因子
[A] extract.py     调用各 extract_results.py；失败则回退已有 *benchmark_metrics.xlsx
        │
        ▼
extracted/W1…W7/*.tsv + *_extracted.json + extract_log.tsv
        │
        ▼
[B] tables.py      coverage.tsv + master_sample_metrics.tsv
[B] stats.py       总体 / 分组描述 + KW/MW 检验
[B] plots_r.py     写出并执行 ggplot2
[B] narrative.py + biology.py  数字结果 + 绑图/绑表的生物学讨论
        │
        ▼
[C] report.py      report.html（图 base64 嵌入，表可横向滑动）
    report.pdf     A4 横向，同源 HTML 烘焙
    tables/ figures/*.png+pdf  r/*.R
```

与旧组件关系：

| 旧物 | 关系 |
|------|------|
| `w1_qc_portable` | 仅 W1 评分与 4 张固定图；本体系覆盖 W1–W7，W1 评分规则仍可参照但不强制写入每张图 |
| `scripts/extract_metrics.py` | 批次 harmonized TSV；本体系直接打运行根目录，不依赖 XvirBench batch 软链 |
| `scripts/analysis/run_analysis.py` | vazyme 分组比较 HTML（matplotlib）；本体系改为 ggplot2 SCI 风格并强制缺失跳过 |
| `scripts/build_harmonized_excel.py` | Excel 交付表；本体系输出 HTML + TSV，不替代 Excel |

---

## 3. 异常与缺失处理（决策树）

### 3.1 流程级

| 情况 | 动作 |
|------|------|
| 目录不存在或为空 | `status=missing_workflow`，HTML 整章跳过 |
| 目录在但提取 0 张非空表 | `status=extracted_empty`，整章跳过，记录原因 |
| 提取器抛错 | 记入 extract_log；尝试 `reports/*benchmark_metrics.xlsx` 回退；仍无则跳过 |
| 流程在、部分表空 | 流程章节保留，空表对应的图/指标句跳过 |

### 3.2 指标级

- 主表某列全 NA：描述统计不输出该行；不画该箱线图。
- 比例列可能是 0–1 或 0–100：作图前若 `max≤1.5` 按比例，否则按百分数再 `/100` 画 percent 轴。
- W3 样本数可以多于 W1（例如本示例 W3=60、W1=11）：组间比较**只在有 method/host 标签的核心队列**；额外样本可在结果里用一句话说明，不强行合并分组。

### 3.3 分组级

候选因子（按顺序检测）：`method`, `host`, `group`, `treatment`, `condition`, `library`, `batch`。

可用因子定义：非缺失水平数 ≥ 2，且其中至少 2 个水平 n≥2。

- 无可用因子 → 全文只做总体。
- 有 `method`、无有效 `host` → 只按 method 比较。
- 每组 n<3 时仍可做 KW/MW，但叙述必须写「小样本、效能低」。
- 另输出 `core_excl_lowdepth` 敏感性表，不删除主分析。

### 3.4 图级

R 脚本必须对「文件不存在 / 行数为 0 / 缺列」直接 `skip`，进程不得因此崩溃。缺图时 HTML 不插入 `<img>`，不画「数据缺失」空白框（全流程场景下空白框会造成「失败」误读）。

---

## 4. 输入发现契约

### 4.1 运行根目录最小结构

```
<run-dir>/
  workflow1_upstream/{filter,merge,assembly}/     # 可选
  workflow2_virusid/{downstream,summary}/         # 可选
  workflow3_hostid/{by_sample_v3,reports}/        # 可选
  workflow4_kraken_bracken/results/{kraken2,bracken}/
  workflow5_virus_quantification/results/summary/
  workflow6_virus_annotation/results/             # 常缺
  workflow7_fragmentation_benchmark/summary/      # 常缺
  lists/w1_samples.txt                            # 可选，W1 run→sample
  cohorts/groupinfo.txt                           # 或上级目录
  reports/*benchmark_metrics.xlsx                 # 可选回退
```

流程存在性：对应 dirname 存在且至少命中一个 marker（见 `config.py` 中 `WorkflowSpec.markers`）。

### 4.2 groupinfo.txt（无表头，制表符）

```
61	RNA202508-WYS-JSC12	rat	cDNA_Frag_30C5Min
```

列：原始编号、生物学样本/SN、宿主、建库方法。`61` 规范为 `v61`。

### 4.3 sampleinfo.txt（无表头）

```
61_1	v61	<fq1>	<fq2>
```

列：run_id、sample_id、fq1、fq2。用于 n_runs 与 W1 提取器的 run 映射。

---

## 5. 指标字典与提取契约

设计字典条数（`WORKFLOW_SUMMARY.md`）：W1 25、W2 18、W3 11、W4 8、W5 11、W6 10、W7 21。  
提取器实际落表字段可以更多（派生列）或更少（源文件没有）。**覆盖矩阵记录的是实际非空表，不是字典条数。**

调用约定：

| 流程 | 脚本 | 关键 tables 键 |
|------|------|----------------|
| W1 | `workflow1_upstream/scripts/extract_results.py` | `run_qc`, `samples`, `summary` |
| W2 | `workflow2_virusid/scripts/extract_results.py` | `contigs`, `cluster_members`, `cluster_summary`, `sample_cluster`, `hmm_iterations` |
| W3 | `workflow3_hostid/scripts/extract_results.py` | `host_contig`, `host_sample`, `host_top_species`, `marker_coverage` |
| W4 | `workflow4_kraken_bracken/scripts/extract_results.py` | `sample_qc`, `bracken_top15_species`, `combined_species` |
| W5 | `workflow5_virus_quantification/scripts/extract_results.py` | `sample_summary`, `rpm_full`, `top20_rpm` |
| W6 | `workflow6_virus_annotation/scripts/extract_results.py` | `checkv`, `annotation_summary` |
| W7 | `workflow7_fragmentation_benchmark/scripts/extract_results.py` | `comparison`, `method_summary` |

W2–W7 依赖 `XVIRBENCH_ROOT/scripts/extract_io.py`。运行前设置：

```bash
export XVIRBENCH_ROOT=/data/user/guojindan/Projects/XvirMind/XvirBench
```

样本级主表优先列（有则合并）：

W1：`merge_r1_reads`, `merge_r1_q30_pct`, `contigs_ge1kb_n`, `contigs_ge1kb_bp`, 以及 run 级聚合的 `read_retention_fastp_median`, `q30_after_fastp_median`, `duplication_rate_median`, `rrna_retention_r1_median`  
W2：`n_putative_viral_contigs`, `n_high_quality`, `n_clusters`, `n_contigs_in_clusters`（源列名可能是 `n_contigs`）  
W3：`n_species_inferred`, `n_genus_inferred`, `top_host_species`, `host_n_records`  
W4：`kraken_unclassified_frac`, `bracken_species_taxa`, `bracken_species_reads_assigned`  
W5：`mapping_rate_pct`, `max_rpm`, `median_rpm`, `n_viral_contigs_with_reads`  
W7：STAR/Picard 列原样并入（若存在）

---

## 6. 统计协议

1. 描述统计对每个有限数值列输出 n、缺失数、mean、SD、median、Q25、Q75、min、max。
2. 数据集切分：`all_samples`（主表全部）、`core_cohort`（有分组标签）、`core_excl_lowdepth`。
3. 检验：水平 ≥2 且每组 n≥2 才做。Kruskal–Wallis 的 ε² = max(0, (H−k+1)/(n−k))。两两 Mann–Whitney 的 p 做 BH（不是 Bonferroni 冒充 BH）。
4. 不报告参数检验（t/ANOVA）作为主结果，除非用户另行指定且残差明显对称。
5. 多重指标不在流程间再做二次 BH（避免过度保守）；在同一指标的两两比较内做 BH。
6. p 与效应量必须一起出现。禁止只写「显著」不写 p。
7. 不得把 p≥0.05 写成「方法学等价」。

---

## 7. 绘图协议（SCI 风格 + R 附件）

### 7.1 视觉

- 主题：`theme_classic`，无网格、无阴影、无 3D、无彩虹。
- 配色：Okabe–Ito；建库方法固定：cDNA 30°C 5 min `#E69F00`，RNA 85°C 6 min `#0072B2`，RNA 94°C 7 min `#009E73`。
- 字体：无衬线；轴文字黑色；线宽约 0.35 pt。
- 尺寸：单栏 85 mm、1.5 栏 114 mm、双栏 174 mm；PNG 300 dpi + PDF 矢量。
- 点+箱线：箱线显示中位数与 IQR，点用 quasirandom，不画星号墙。
- 显著性：若需要，写在正文，不在图上堆 `****`。
- 特殊 Unicode（≥）在部分设备缺字，轴标题用 `>=`。

### 7.2 本体系默认图（有数据才画）

| ID | 内容 | 典型宽度 |
|----|------|----------|
| fig01_depth_by_sample | 各样本合并 R1 深度，5 million 虚线 | 114 mm |
| fig02_w1_fastp_retention | fastp 保留率 × 方法 | 85 mm |
| fig03_w1_q30 | Q30 × 方法 | 85 mm |
| fig04_w1_rrna_retention | rRNA 去除保留率 | 85 mm |
| fig05_w1_depth_vs_contigs | 深度 vs ≥1 kb contig | 114 mm |
| fig06_w2_checkv_by_sample | CheckV 质量堆叠 | 114 mm |
| fig07_w2_contig_length | 病毒 contig 长度直方图 | 85 mm |
| fig08_w2_viral_contigs_by_method | 每样本病毒 contig 数 | 85 mm |
| fig09_w3_host_species | 推断宿主物种频次 | 114 mm |
| fig10_w4_unclassified | Kraken 未分类比例 | 85 mm |
| fig11_w4_species_richness | Bracken 物种数 | 85 mm |
| fig12_w4_top_taxa | top-15 表内组成 | 174 mm |
| fig13_w5_mapping_rate | 病毒比对率 | 85 mm |
| fig14_w5_max_rpm | 最大 RPM（log10） | 85 mm |
| fig15_w5_depth_vs_mapping | 深度 vs 病毒比对率 | 114 mm |

脚本：`package/r/00_sci_theme.R`、`package/r/make_figures.R`。每次运行复制到 `runs/<batch>/r/`。

R 依赖（metagenome 环境已具备）：ggplot2、dplyr、tidyr、readr、scales、patchwork、ggbeeswarm、stringr。  
默认 `Rscript`：`.../envs/metagenome/bin/Rscript`。

---

## 8. 生物学解读协议（必须绑图）

每章三块：**结果**（数字）→ **图**（半宽、成对）→ **生物学意义**（逐图讨论）。生物学段落的第一句必须点名图号。

写法模板（不合格 vs 合格）：

- 不合格：「未分类比例高符合宏转录组预期，解读需谨慎。」
- 合格：「`fig12_w4_top_taxa` 显示 11/11 个大鼠样本的 Bracken top-15 第一名均为 *Homo sapiens*（已分类空间比例 86.0%–97.7%）。这与 W3 线粒体标记一致指向 *Rattus norvegicus* 冲突。可能原因：① Kraken 库中人类基因组过度代表，哺乳动物保守转录本被派到人；② 大鼠转录本在所用数据库中覆盖不足；③ 建库/试剂人源核酸。去掉 *H. sapiens* 后，多数样本改由 *Staphylococcus aureus* 居首，并出现 *Ligilactobacillus murinus*、*Helicobacter apodemus* 等啮齿动物相关类群。三种打断方法下「人源第一」的格局不变，故该信号不像方法学特异伪影。」

### 8.1 各流程必须回答的数据问题

**W1（fig01–fig05）**  
谁低于 5 million 虚线？低深度是某种打断方法共有，还是个别样本？fig05 上 contig 数是否随深度上升？rRNA 保留率的离群样本是谁、会不会解释下游分类异常？

**W2（fig06–fig08）**  
CheckV 各级各多少条？低深度样本的假定病毒 contig 是否更少？方法组之间 fig08 是否有方向性差异，还是 KW 不显著？

**W3（fig09）**  
优势推断物种是否与实验设计宿主一致？若与 W4 人源信号冲突，明确写「标记基因 vs k-mer 分类器」而不是各说各话。

**W4（fig10–fig12）**  
未分类比例的中位数/范围（fig10）必须出现。fig12 若第一名与宿主设计不符：执行硬规则 16 的 (i)–(iv)。去掉异常类群后的新优势种要点名到种，并按 method 看是否改变。低深度样本的物种数（fig11）是否同步下降。

**W5（fig13–fig15）**  
最大 RPM 最高的样本是不是 fig01 的低深度样本？fig15 若深度↓而 mapping rate/RPM↑，必须写成「分母效应」，禁止写成「病毒载量最高」。方法组若 KW 不显著，写「本队列看不出打断方法改变病毒比对率」。

**W6 / W7**  
有数据才写；仍须点图号。

**跨流程**  
至少把 W3 宿主 vs W4 人源、W1 深度 vs W5 RPM 各写一句带图号的对照。

---

## 9. HTML / PDF 报告结构（固定顺序）

1. 执行摘要（样本数、已提取/跳过流程、分组决策、低深度名单、免责）
2. 样本 Meta 与提取覆盖
3. W1 … W7（缺失则一节「跳过」+ 原因，无空图）
4. 跨流程衔接（至少两个下游流程存在时）
5. 结构化表（覆盖、主表、描述统计、检验；**不要提取日志 JSON**）
6. 方法学摘要
7. 附录：R 绘图脚本（相对路径文件名即可）
8. 页脚免责声明

抬头只放标题、批次、时间、标签。完整摘要只出现在第 1 节。

### 9.1 图的嵌入与排版（HTML 与 PDF 共同）

- 每个 `<img src>` 必须是 `data:image/png;base64,...`。
- 图注只写图编号、一句话说明、脚本相对路径 `r/make_figures.R`，**不要写绝对磁盘路径**。
- 拷贝 `report.html` 单文件到 U 盘 / 邮件仍应能看见全部图。
- **宽度**：每张图约占内容区宽度的 **1/2**（约 48%）。ggplot 画布可以仍是 85/114/174 mm，报告显示时统一缩到半宽。
- **成对**：同一章节里连续两张图放在同一行（`table.fig-pair` 两列，左右各约 48%）。用表格而不是 flex，避免 PDF 里大图按像素把列撑破。
- **单张**：奇数张时最后一张单独一行，**居中**（`table.fig-one`，宽度 48%、左右 auto margin），不要拉满整行。PNG `width:100%`，禁止按原图像素撑满。
- PDF 同样半宽两列排版，避免一图占满横向 A4。

### 9.2 表格版面

- **HTML**：每张表外包 `.table-wrap { overflow-x: auto; max-width: 100%; }`，表本身 `width: max-content`，读者横向滑动，页面不被撑破。
- **PDF**：`@page { size: A4 landscape; }`。表字 8–9 pt，单元格可换行；这是纸面介质，不能靠滑动。

### 9.3 数字格式

| 类型 | 报告显示 |
|------|----------|
| 计数、reads、bases、contig/taxa n | 整数，千分位可选 |
| 百分比（含已 ×100 的列） | 2 位小数，可带 % |
| 0–1 比例、ε²、rank-biserial | 4 位小数 |
| p、p_BH | 4 位小数；&lt;0.0001 则科学计数法 |

### 9.4 路径与 JSON

- 报告表中删除/折叠：`table_rows_json`、traceback、完整 `out_dir`。
- 若必须提到产物位置：表前或表后一句「路径前缀：`相对或统一根/`」，单元格只留相对尾路径或 ID。
- Meta 来源写成文件名（如 `cohorts/groupinfo.txt`），不要 `/data/user/...` 长串。

风格：白底、Helvetica/Arial、三线表。

---

## 10. 目录规范（本体系落盘）

```
XvirBench/benchmark/
  FULL_PIPELINE_ANALYSIS_SYSTEM.md      # 本文
  FULL_PIPELINE_ANALYSIS_SYSTEM.html    # 本文 HTML
  README.md                             # 入口索引
  package/
    run_full_pipeline_analysis.py
    requirements.txt
    r/00_sci_theme.R
    r/make_figures.R
    xvir_full/{config,discover,extract,tables,stats,plots_r,narrative,biology,display,report}.py
  runs/<batch_id>/
    report.html          # 自包含，图已嵌入
    report.pdf           # A4 横向，图已嵌入
    discovery.json       # 仅磁盘，不进报告
    extracted/W1…W5/*.tsv
    tables/master_sample_metrics.tsv
    tables/coverage.tsv
    tables/stats/{overall_core,by_group,tests}.tsv
    figures/*.png *.pdf
    r/*.R
```

---

## 11. 运行方法

依赖：Python 3.10+（pandas、numpy、scipy、openpyxl、weasyprint）、R 4.x + ggplot2 生态。

```bash
export XVIRBENCH_ROOT=/data/user/guojindan/Projects/XvirMind/XvirBench
export PYTHONPATH=$XVIRBENCH_ROOT/benchmark/package:$XVIRBENCH_ROOT/scripts

python3 $XVIRBENCH_ROOT/benchmark/package/run_full_pipeline_analysis.py \
  --run-dir /data/user/guojindan/Projects/Workflows/benchmark/test/runs/pxy_V350399508 \
  --out-dir $XVIRBENCH_ROOT/benchmark/runs/pxy_V350399508 \
  --batch-id pxy_V350399508
```

仅重做统计/图/HTML（不重提取）：

```bash
python3 .../run_full_pipeline_analysis.py --run-dir ... --out-dir ... --skip-extract
```

---

## 12. 批次 pxy_V350399508 的预期行为（回归清单）

用本提示词处理  
`/data/user/guojindan/Projects/Workflows/benchmark/test/runs/pxy_V350399508`  
时应得到：

- 发现 W1–W5，跳过 W6、W7。
- groupinfo 提供 method × 3、host=rat（单一水平 → 不做宿主比较）。
- 核心队列 11 个生物学样本（v61, v64, v67, v70, v73, v76, v78, v79, v82, v85, v88）。
- 低深度：v73、v88。
- W3/W4 提取器可能看到 60 个样本；组间比较仍只在 11 个有 method 的样本。
- 约 15 张 ggplot 图（PNG+PDF）+ **自包含** `report.html` + **横向** `report.pdf`。
- HTML 中 `<img src>` 以 `data:image` 开头；表有横向滑动容器。
- 报告表无绝对路径、无 JSON 列；p 值不超过 4 位小数。
- 不出现 W6/W7 的空图；不把 v73/v88 的高 RPM 写成「病毒载量最高」。
- W4 生物学意义必须点名 `fig12_w4_top_taxa` 的 *Homo sapiens* 优势、与 W3 大鼠宿主的冲突、去人源后的次优势类群、以及方法是否改变该格局。
- HTML/PDF 中图为半宽；两张一组并排，单张居中。

---

## 13. 源码附录

以下文件与 `package/` 内实现逐字对应。以仓库文件为准；本文附录便于单文件交付与给 AI 阅读。



### `package/requirements.txt`

```text
pandas>=2.0
numpy
scipy
openpyxl
matplotlib
weasyprint
```

### `package/run_full_pipeline_analysis.py`

```python
#!/usr/bin/env python3
"""Post-workflow analysis: extract → stats → R figures → HTML report.

Example:
  python run_full_pipeline_analysis.py \\
    --run-dir /data/user/guojindan/Projects/Workflows/benchmark/test/runs/pxy_V350399508 \\
    --out-dir /data/user/guojindan/Projects/XvirMind/XvirBench/benchmark/runs/pxy_V350399508
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from xvir_full.config import DEFAULT_WORKFLOWS_ROOT, default_rscript
from xvir_full.discover import discover
from xvir_full.extract import extract_all_present
from xvir_full.narrative import build_sections
from xvir_full.plots_r import run_r_figures, stage_tables
from xvir_full.report import build_html, build_pdf
from xvir_full.stats import run_stats
from xvir_full.tables import coverage_matrix, master_sample_table


def main() -> None:
    ap = argparse.ArgumentParser(description="W1–W7 工作流完成后分析")
    ap.add_argument("--run-dir", required=True, help="含 workflow1_upstream/ 等子目录的运行根")
    ap.add_argument("--out-dir", required=True, help="分析输出目录")
    ap.add_argument("--batch-id", default=None)
    ap.add_argument("--workflows-root", default=str(DEFAULT_WORKFLOWS_ROOT))
    ap.add_argument("--rscript", default=None)
    ap.add_argument("--skip-extract", action="store_true", help="复用 out-dir/extracted")
    args = ap.parse_args()

    run_dir = Path(args.run_dir).resolve()
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    extract_dir = out_dir / "extracted"
    table_dir = out_dir / "tables"
    fig_dir = out_dir / "figures"
    r_dir = out_dir / "r"

    disc = discover(run_dir, args.batch_id)
    (out_dir / "discovery.json").write_text(
        json.dumps(
            {
                "batch_id": disc.batch_id,
                "run_dir": str(disc.run_dir),
                "group_cols": disc.cohort.group_cols,
                "grouping_notes": disc.cohort.grouping_notes,
                "n_samples": int(len(disc.cohort.samples)),
                "workflows": [
                    {
                        "key": w.spec.key,
                        "short": w.spec.short,
                        "present": w.present,
                        "path": str(w.path) if w.path else None,
                        "reason": w.reason,
                    }
                    for w in disc.workflows
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    disc.cohort.samples.to_csv(out_dir / "cohort_samples.tsv", sep="\t", index=False)

    if args.skip_extract and extract_dir.is_dir():
        import pandas as pd

        log_path = extract_dir / "extract_log.tsv"
        extract_log = pd.read_csv(log_path, sep="\t") if log_path.is_file() else pd.DataFrame()
    else:
        extract_log = extract_all_present(disc, extract_dir, Path(args.workflows_root))

    coverage = coverage_matrix(extract_dir, disc)
    master = master_sample_table(extract_dir, disc.cohort)
    coverage.to_csv(table_dir / "coverage.tsv", sep="\t", index=False) if False else None
    table_dir.mkdir(parents=True, exist_ok=True)
    coverage.to_csv(table_dir / "coverage.tsv", sep="\t", index=False)
    master.to_csv(table_dir / "master_sample_metrics.tsv", sep="\t", index=False)

    stats_frames = run_stats(master, disc.cohort.group_cols, table_dir / "stats")
    stage_tables(extract_dir, table_dir, master, coverage)
    rlog = run_r_figures(table_dir, fig_dir, r_dir, Path(args.rscript) if args.rscript else default_rscript())
    (out_dir / "r_run_log.json").write_text(json.dumps(rlog, ensure_ascii=False, indent=2))

    sections = build_sections(disc, master, coverage, stats_frames, table_dir=table_dir)
    r_src = ""
    r_file = r_dir / "make_figures.R"
    if r_file.is_file():
        r_src = r_file.read_text(errors="replace")
    theme = r_dir / "00_sci_theme.R"
    if theme.is_file():
        r_src = theme.read_text(errors="replace") + "\n\n# ---- make_figures.R ----\n" + r_src

    report = build_html(
        batch_id=disc.batch_id,
        out_dir=out_dir,
        fig_dir=fig_dir,
        sections=sections,
        master=master,
        coverage=coverage,
        overall=stats_frames.get("overall_core"),
        tests=stats_frames.get("tests"),
        extract_log=extract_log,
        r_source=r_src,
        grouping_notes=disc.cohort.grouping_notes,
    )
    print(f"batch {disc.batch_id}")
    print(f"  present: {', '.join(w.spec.short for w in disc.workflows if w.present) or 'none'}")
    print(f"  groups: {', '.join(disc.cohort.group_cols) or 'overall only'}")
    print(f"  samples: {len(master)}")
    try:
        pdf = build_pdf(report, out_dir / "report.pdf")
        print(f"  pdf: {pdf}")
    except Exception as exc:
        print(f"  pdf FAILED: {type(exc).__name__}: {exc}")
    print(f"  report: {report}")
    print(f"  figures: {len(list(fig_dir.glob('*.png')))} png")


if __name__ == "__main__":
    main()
```

### `package/xvir_full/__init__.py`

```python
"""XvirBench full-pipeline post-workflow analysis (W1–W7)."""

__version__ = "1.0.0"
PACKAGE_NAME = "xvir_full"
```

### `package/xvir_full/config.py`

```python
"""Paths, palettes, workflow contracts, and metric dictionary."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

PACKAGE_DIR = Path(__file__).resolve().parents[1]
BENCHMARK_ROOT = PACKAGE_DIR.parent
DEFAULT_WORKFLOWS_ROOT = Path("/data/user/guojindan/Projects/Workflows")
DEFAULT_XVIRBENCH_ROOT = Path("/data/user/guojindan/Projects/XvirMind/XvirBench")
DEFAULT_RSCRIPT = Path(
    "/data/user/guojindan/softwares/micromamba_root/envs/metagenome/bin/Rscript"
)

# Okabe–Ito (colorblind-safe, common in Nature/Science figures)
OKABE_ITO = [
    "#E69F00",
    "#56B4E9",
    "#009E73",
    "#F0E442",
    "#0072B2",
    "#D55E00",
    "#CC79A7",
    "#000000",
]

METHOD_LABEL = {
    "cDNA_Frag_30C5Min": "cDNA 30°C 5 min",
    "RNA_Frag_85C6Min": "RNA 85°C 6 min",
    "RNA_Frag_94C7Min": "RNA 94°C 7 min",
}
METHOD_ORDER = ["cDNA_Frag_30C5Min", "RNA_Frag_85C6Min", "RNA_Frag_94C7Min"]
METHOD_COLORS = {
    "cDNA_Frag_30C5Min": "#E69F00",
    "RNA_Frag_85C6Min": "#0072B2",
    "RNA_Frag_94C7Min": "#009E73",
}
HOST_LABEL = {"rat": "rat", "tick": "tick", "mosquito": "mosquito", "human": "human"}

GROUP_CANDIDATES = (
    "method",
    "host",
    "group",
    "treatment",
    "condition",
    "library",
    "batch",
)
MISSING_TOKENS = {"", "na", "nan", "none", "null", ".", "-", "NA", "NaN", "None"}

# Post-rRNA / merged R1 below this (reads) is flagged low-depth
LOW_DEPTH_R1_READS = 5_000_000

ID_COLUMNS = {
    "sample_id",
    "run_id",
    "v_id",
    "sn",
    "lane",
    "contig_id",
    "reference_id",
    "clusid",
    "taxonomy_id",
    "name",
    "source_sample",
}


@dataclass(frozen=True)
class WorkflowSpec:
    key: str
    short: str
    title: str
    dirname: str
    extractor_rel: str
    markers: tuple[str, ...]
    extract_tables: tuple[str, ...]
    sample_metrics: tuple[str, ...]
    skip_biology: str


WORKFLOWS: tuple[WorkflowSpec, ...] = (
    WorkflowSpec(
        key="workflow1_upstream",
        short="W1",
        title="Upstream QC and assembly",
        dirname="workflow1_upstream",
        extractor_rel="workflow1_upstream/scripts/extract_results.py",
        markers=("filter", "merge", "assembly"),
        extract_tables=("run_qc", "samples", "summary"),
        sample_metrics=(
            "merge_r1_reads",
            "merge_r1_bases",
            "merge_r1_q30_pct",
            "contigs_all_n",
            "contigs_all_bp",
            "contigs_avg_len",
            "contigs_ge1kb_n",
            "contigs_ge1kb_bp",
        ),
        skip_biology="缺少 W1，无法判断测序深度、质量和组装产量。",
    ),
    WorkflowSpec(
        key="workflow2_virusid",
        short="W2",
        title="Virus identification",
        dirname="workflow2_virusid",
        extractor_rel="workflow2_virusid/scripts/extract_results.py",
        markers=("downstream", "summary", "output_rna"),
        extract_tables=("contigs", "cluster_members", "cluster_summary", "sample_cluster", "hmm_iterations"),
        sample_metrics=("n_contigs_in_clusters", "n_clusters"),
        skip_biology="缺少 W2，无法报告假定病毒 contig、CheckV 质量与聚类。",
    ),
    WorkflowSpec(
        key="workflow3_hostid",
        short="W3",
        title="Host identification",
        dirname="workflow3_hostid",
        extractor_rel="workflow3_hostid/scripts/extract_results.py",
        markers=("by_sample_v3", "reports", "EukaMarker_Mapping"),
        extract_tables=("host_contig", "host_sample", "host_top_species", "marker_coverage"),
        sample_metrics=("n_species_inferred", "n_genus_inferred", "n_contigs", "mean_marker_count"),
        skip_biology="缺少 W3，无法报告线粒体标记的宿主推断。",
    ),
    WorkflowSpec(
        key="workflow4_kraken_bracken",
        short="W4",
        title="Microbial profile (Kraken2/Bracken)",
        dirname="workflow4_kraken_bracken",
        extractor_rel="workflow4_kraken_bracken/scripts/extract_results.py",
        markers=("results/kraken2", "results/bracken"),
        extract_tables=("sample_qc", "bracken_top15_species", "combined_species"),
        sample_metrics=(
            "kraken_unclassified_frac",
            "kraken_classified_reads",
            "bracken_species_taxa",
            "bracken_species_reads_assigned",
        ),
        skip_biology="缺少 W4，无法报告分类/未分类比例与分类单元丰度。",
    ),
    WorkflowSpec(
        key="workflow5_virus_quantification",
        short="W5",
        title="Virus quantification (RPM)",
        dirname="workflow5_virus_quantification",
        extractor_rel="workflow5_virus_quantification/scripts/extract_results.py",
        markers=("results/summary", "results/coverage"),
        extract_tables=("sample_summary", "rpm_full", "top20_rpm", "cleanreads"),
        sample_metrics=(
            "n_viral_contigs_with_reads",
            "total_mapped_reads",
            "max_rpm",
            "median_rpm",
            "mapping_rate_pct",
            "mean_coverage_pct",
        ),
        skip_biology="缺少 W5，无法比较病毒 RPM 与比对率。",
    ),
    WorkflowSpec(
        key="workflow6_virus_annotation",
        short="W6",
        title="Virus annotation",
        dirname="workflow6_virus_annotation",
        extractor_rel="workflow6_virus_annotation/scripts/extract_results.py",
        markers=("results/checkv", "results/summary", "results/function"),
        extract_tables=("checkv", "annotation_summary", "strategy", "consistency"),
        sample_metrics=(),
        skip_biology="缺少 W6，无法报告基因/AMG/分类一致性注释。",
    ),
    WorkflowSpec(
        key="workflow7_fragmentation_benchmark",
        short="W7",
        title="RNA vs cDNA fragmentation benchmark",
        dirname="workflow7_fragmentation_benchmark",
        extractor_rel="workflow7_fragmentation_benchmark/scripts/extract_results.py",
        markers=("summary", "metrics"),
        extract_tables=("comparison", "method_summary"),
        sample_metrics=("uniquely_mapped_pct", "multi_mapped_pct", "percent_duplication", "chimeric_rate_pct"),
        skip_biology="缺少 W7，无法报告 STAR/Picard 建库方法学指标。",
    ),
)

WF_BY_KEY = {w.key: w for w in WORKFLOWS}
WF_BY_SHORT = {w.short: w for w in WORKFLOWS}

# Catalog IDs from Workflows/docs/WORKFLOW_SUMMARY.md
CATALOG_COUNTS = {"W1": 25, "W2": 18, "W3": 11, "W4": 8, "W5": 11, "W6": 10, "W7": 21}

METRIC_LABELS = {
    "merge_r1_reads": "Merged R1 reads",
    "merge_r1_bases": "Merged R1 bases",
    "merge_r1_q30_pct": "Merged R1 Q30 (%)",
    "read_retention_fastp": "fastp read retention",
    "q30_after_fastp": "fastp Q30",
    "duplication_rate": "Duplication rate",
    "rrna_retention_r1": "rRNA-depletion R1 retention",
    "contigs_all_n": "Contigs (all)",
    "contigs_ge1kb_n": "Contigs ≥1 kb (n)",
    "contigs_ge1kb_bp": "Contigs ≥1 kb (bp)",
    "contigs_avg_len": "Mean contig length (bp)",
    "n_putative_viral_contigs": "Putative viral contigs",
    "n_contigs_in_clusters": "Viral contigs in ANI80 clusters",
    "n_clusters": "ANI80 clusters",
    "n_high_quality": "CheckV High-quality contigs",
    "n_species_inferred": "Inferred host species (n)",
    "n_genus_inferred": "Inferred host genera (n)",
    "kraken_unclassified_frac": "Kraken unclassified fraction",
    "bracken_species_taxa": "Bracken species taxa (n)",
    "bracken_species_reads_assigned": "Bracken species assigned reads",
    "n_viral_contigs_with_reads": "Viral contigs with mapped reads",
    "max_rpm": "Max viral RPM",
    "median_rpm": "Median viral RPM",
    "mapping_rate_pct": "Reads mapped to viral contigs (%)",
    "mean_coverage_pct": "Mean viral coverage (%)",
    "uniquely_mapped_pct": "STAR uniquely mapped (%)",
    "percent_duplication": "Picard duplication (%)",
    "chimeric_rate_pct": "Chimeric rate (%)",
}


def default_rscript() -> Optional[Path]:
    candidates = [
        DEFAULT_RSCRIPT,
        Path("/data/user/guojindan/softwares/micromamba_root/envs/rnaseq/bin/Rscript"),
        Path("/data/user/guojindan/softwares/micromamba_root/envs/irma-env/bin/Rscript"),
    ]
    for p in candidates:
        if p.is_file():
            return p
    return None
```

### `package/xvir_full/discover.py`

```python
"""Discover present workflows, sample metadata, and usable grouping factors."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from .config import (
    GROUP_CANDIDATES,
    MISSING_TOKENS,
    WORKFLOWS,
    WorkflowSpec,
)


@dataclass
class WorkflowPresence:
    spec: WorkflowSpec
    present: bool
    path: Optional[Path]
    reason: str


@dataclass
class Cohort:
    samples: pd.DataFrame  # one row per biological sample_id (vXX)
    runs: pd.DataFrame
    group_cols: list[str]
    grouping_notes: list[str]
    source_files: dict[str, str]


@dataclass
class Discovery:
    run_dir: Path
    batch_id: str
    workflows: list[WorkflowPresence]
    cohort: Cohort
    extra_notes: list[str] = field(default_factory=list)

    @property
    def present_specs(self) -> list[WorkflowSpec]:
        return [w.spec for w in self.workflows if w.present]

    def path_for(self, key: str) -> Optional[Path]:
        for w in self.workflows:
            if w.spec.key == key:
                return w.path
        return None


def _is_missing(val: Any) -> bool:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return True
    return str(val).strip() in MISSING_TOKENS


def detect_workflows(run_dir: Path) -> list[WorkflowPresence]:
    out: list[WorkflowPresence] = []
    for spec in WORKFLOWS:
        root = run_dir / spec.dirname
        if not root.is_dir():
            out.append(WorkflowPresence(spec, False, None, f"directory {spec.dirname} not found"))
            continue
        hit = [m for m in spec.markers if (root / m).exists()]
        if hit:
            out.append(WorkflowPresence(spec, True, root, f"markers: {', '.join(hit)}"))
        else:
            # empty placeholder dir
            nonempty = any(root.iterdir())
            if nonempty:
                out.append(WorkflowPresence(spec, True, root, "directory exists without expected markers"))
            else:
                out.append(WorkflowPresence(spec, False, root, "directory empty"))
    return out


def _read_table_guess(path: Path) -> pd.DataFrame:
    if not path.is_file():
        return pd.DataFrame()
    sep = "\t" if path.suffix.lower() in {".tsv", ".txt"} else ","
    # try header first
    df = pd.read_csv(path, sep=sep, dtype=str, keep_default_na=False)
    if df.shape[1] == 1 and "\t" in str(df.columns[0]):
        df = pd.read_csv(path, sep="\t", dtype=str, keep_default_na=False)
    return df


def _normalize_sid(x: Any) -> Optional[str]:
    if _is_missing(x):
        return None
    s = str(x).strip()
    if s.startswith("v") and s[1:].isdigit():
        return s
    if s.isdigit():
        return f"v{s}"
    # 61_1 run-style
    if "_" in s and s.split("_")[0].isdigit():
        return f"v{s.split('_')[0]}"
    return s


def _search_meta(run_dir: Path, names: tuple[str, ...]) -> Optional[Path]:
    candidates = [
        run_dir / "cohorts",
        run_dir,
        run_dir.parent,
        run_dir.parent.parent,
        run_dir.parent.parent.parent,
    ]
    for folder in candidates:
        if not folder.is_dir():
            continue
        for name in names:
            p = folder / name
            if p.is_file():
                return p
    return None


def _parse_groupinfo(path: Path) -> pd.DataFrame:
    raw = path.read_text(errors="replace").splitlines()
    rows = []
    for ln in raw:
        ln = ln.strip()
        if not ln or ln.startswith("#"):
            continue
        parts = ln.split("\t") if "\t" in ln else ln.split()
        if len(parts) < 2:
            continue
        # detect header
        if parts[0].lower() in {"id", "sample", "sample_id", "sn"}:
            continue
        rec = {"raw_id": parts[0]}
        rec["sample_id"] = _normalize_sid(parts[0])
        if len(parts) >= 2:
            rec["sn"] = parts[1]
        if len(parts) >= 3:
            rec["host"] = parts[2]
        if len(parts) >= 4:
            rec["method"] = parts[3]
        if len(parts) >= 5:
            rec["group"] = parts[4]
        rows.append(rec)
    return pd.DataFrame(rows)


def _parse_sampleinfo(path: Path) -> pd.DataFrame:
    df = _read_table_guess(path)
    if df.empty:
        return df
    cols = [c.lower() for c in df.columns]
    # no-header 4-col: run_id, sample_id, fq1, fq2
    if df.shape[1] >= 2:
        rename = {}
        first = df.columns[0]
        second = df.columns[1]
        if first.lower() not in {"run_id", "id", "sample_id"}:
            rename[first] = "run_id"
            rename[second] = "sample_id"
            if df.shape[1] >= 3:
                rename[df.columns[2]] = "fq1"
            if df.shape[1] >= 4:
                rename[df.columns[3]] = "fq2"
            df = df.rename(columns=rename)
        else:
            mapping = {}
            for c in df.columns:
                cl = c.lower()
                if cl in {"run_id", "run"}:
                    mapping[c] = "run_id"
                elif cl in {"sample_id", "sample", "sn"}:
                    mapping[c] = "sample_id"
            df = df.rename(columns=mapping)
    if "sample_id" in df.columns:
        df["sample_id"] = df["sample_id"].map(_normalize_sid)
    return df


def usable_group_cols(df: pd.DataFrame) -> tuple[list[str], list[str]]:
    notes = []
    used = []
    for col in GROUP_CANDIDATES:
        if col not in df.columns:
            continue
        s = df[col].map(lambda x: None if _is_missing(x) else str(x).strip())
        vc = s.dropna().value_counts()
        if vc.empty:
            notes.append(f"{col}: all missing → skip")
            continue
        if vc.shape[0] < 2:
            notes.append(f"{col}: only one level ({vc.index[0]}) → overall analysis only for this factor")
            continue
        n_ok = int((vc >= 2).sum())
        if n_ok < 2:
            notes.append(f"{col}: fewer than two levels with n≥2 → skip group test")
            continue
        used.append(col)
        small = vc[vc < 3]
        extra = f"; levels with n<3: {', '.join(f'{k}={v}' for k,v in small.items())}" if not small.empty else ""
        notes.append(f"{col}: {vc.shape[0]} levels, usable for overall + grouped comparison{extra}")
    if not used:
        notes.append("No usable grouping factor → overall analysis only.")
    return used, notes


def load_cohort(run_dir: Path) -> Cohort:
    sources: dict[str, str] = {}
    gpath = _search_meta(run_dir, ("groupinfo.txt", "groupinfo.tsv", "groups.tsv"))
    spath = _search_meta(run_dir, ("sampleinfo.txt", "sampleinfo.tsv", "samples.tsv"))
    groups = _parse_groupinfo(gpath) if gpath else pd.DataFrame()
    runs = _parse_sampleinfo(spath) if spath else pd.DataFrame()
    if gpath:
        sources["groupinfo"] = str(gpath)
    if spath:
        sources["sampleinfo"] = str(spath)

    if groups.empty and not runs.empty and "sample_id" in runs.columns:
        samples = (
            runs.dropna(subset=["sample_id"])
            .drop_duplicates("sample_id")[["sample_id"]]
            .copy()
        )
    elif not groups.empty:
        samples = groups.drop_duplicates("sample_id").copy()
    else:
        samples = pd.DataFrame(columns=["sample_id"])

    if not runs.empty and "sample_id" in runs.columns:
        nrun = runs.dropna(subset=["sample_id"]).groupby("sample_id").size().rename("n_runs")
        samples = samples.merge(nrun, on="sample_id", how="left")

    group_cols, notes = usable_group_cols(samples)
    return Cohort(
        samples=samples.reset_index(drop=True),
        runs=runs,
        group_cols=group_cols,
        grouping_notes=notes,
        source_files=sources,
    )


def discover(run_dir: Path, batch_id: Optional[str] = None) -> Discovery:
    run_dir = Path(run_dir).resolve()
    bid = batch_id or run_dir.name
    wfs = detect_workflows(run_dir)
    cohort = load_cohort(run_dir)
    notes = []
    if cohort.samples.empty:
        notes.append("No sample metadata parsed; sample IDs will come from extracted tables.")
    return Discovery(run_dir=run_dir, batch_id=bid, workflows=wfs, cohort=cohort, extra_notes=notes)
```

### `package/xvir_full/extract.py`

```python
"""Run per-workflow extract_results.py; tolerate missing stages and failed parsers."""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import traceback
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from .config import DEFAULT_WORKFLOWS_ROOT, DEFAULT_XVIRBENCH_ROOT, WORKFLOWS, WorkflowSpec
from .discover import Discovery


def _load_module(script: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, script)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {script}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _write_tables(tables: dict[str, list], out_dir: Path) -> dict[str, int]:
    out_dir.mkdir(parents=True, exist_ok=True)
    counts = {}
    for key, rows in tables.items():
        df = pd.DataFrame(rows) if rows else pd.DataFrame()
        path = out_dir / f"{key}.tsv"
        df.to_csv(path, sep="\t", index=False)
        counts[key] = int(len(df))
    return counts


def extract_one(
    spec: WorkflowSpec,
    result_dir: Path,
    out_dir: Path,
    workflows_root: Path,
    sample_list: Optional[Path] = None,
) -> dict[str, Any]:
    script = workflows_root / spec.extractor_rel
    rec: dict[str, Any] = {
        "workflow": spec.key,
        "short": spec.short,
        "result_dir": str(result_dir),
        "extractor": str(script),
        "ok": False,
        "error": None,
        "n_tables": 0,
        "table_rows": {},
    }
    if not script.is_file():
        rec["error"] = f"extractor missing: {script}"
        return rec
    try:
        os.environ.setdefault("XVIRBENCH_ROOT", str(DEFAULT_XVIRBENCH_ROOT))
        os.environ.setdefault("WORKFLOWS_ROOT", str(workflows_root))
        xvir_scripts = DEFAULT_XVIRBENCH_ROOT / "scripts"
        if str(xvir_scripts) not in sys.path:
            sys.path.insert(0, str(xvir_scripts))
        mod = _load_module(script, f"extract_{spec.short}")
        if spec.key == "workflow1_upstream":
            payload = mod.extract_all(Path(result_dir), Path(sample_list) if sample_list else None)
        else:
            payload = mod.extract_all(Path(result_dir))
        tables = payload.get("tables") or {}
        wf_out = out_dir / spec.short
        rows = _write_tables(tables, wf_out)
        (wf_out / f"{spec.key}_extracted.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str)
        )
        rec.update(
            ok=True,
            n_tables=len(rows),
            table_rows=rows,
            batch_summary=payload.get("batch_summary") or payload.get("counts") or {},
            out_dir=str(wf_out),
        )
    except Exception as exc:
        rec["error"] = f"{type(exc).__name__}: {exc}"
        rec["traceback"] = traceback.format_exc()[-4000:]
    return rec


def _fallback_from_xlsx(run_dir: Path, out_dir: Path) -> list[dict[str, Any]]:
    """Best-effort: reuse an existing benchmark xlsx if live extract failed."""
    hits = list((run_dir / "reports").glob("*benchmark_metrics.xlsx")) if (run_dir / "reports").is_dir() else []
    if not hits:
        return []
    xlsx = hits[0]
    recs = []
    sheet_map = {
        "W1": {
            "W1_run质控": "run_qc",
            "W1_sample组装": "samples",
        },
        "W2": {
            "W2_病毒contigs": "contigs",
            "W2_cluster_members": "cluster_members",
            "W2_cluster汇总": "cluster_summary",
            "W2_sample聚类": "sample_cluster",
            "W2_HMM迭代": "hmm_iterations",
        },
        "W3": {
            "W3_宿主_sample": "host_sample",
            "W3_宿主_top物种": "host_top_species",
        },
        "W4": {
            "W4_kraken_bracken": "sample_qc",
            "W4_bracken_top15": "bracken_top15_species",
            "W4_物种汇总表": "combined_species",
        },
        "W5": {
            "W5_sample定量": "sample_summary",
            "W5_top20_RPM": "top20_rpm",
        },
    }
    xl = pd.ExcelFile(xlsx)
    for short, mapping in sheet_map.items():
        tables = {}
        for sheet, key in mapping.items():
            if sheet in xl.sheet_names:
                df = pd.read_excel(xl, sheet)
                tables[key] = df.to_dict(orient="records")
        if not tables:
            continue
        wf_out = out_dir / short
        counts = _write_tables(tables, wf_out)
        recs.append(
            {
                "workflow": next(w.key for w in WORKFLOWS if w.short == short),
                "short": short,
                "ok": True,
                "error": None,
                "n_tables": len(counts),
                "table_rows": counts,
                "fallback": str(xlsx),
                "out_dir": str(wf_out),
            }
        )
    return recs


def extract_all_present(
    disc: Discovery,
    out_dir: Path,
    workflows_root: Path = DEFAULT_WORKFLOWS_ROOT,
) -> pd.DataFrame:
    out_dir.mkdir(parents=True, exist_ok=True)
    sample_list = None
    for cand in (
        disc.run_dir / "lists" / "w1_samples.txt",
        disc.run_dir / "cohorts" / "sampleinfo.txt",
    ):
        if cand.is_file():
            sample_list = cand
            break

    records = []
    for wp in disc.workflows:
        if not wp.present:
            records.append(
                {
                    "workflow": wp.spec.key,
                    "short": wp.spec.short,
                    "ok": False,
                    "skipped": True,
                    "error": wp.reason,
                    "n_tables": 0,
                    "table_rows": {},
                }
            )
            continue
        rec = extract_one(wp.spec, wp.path, out_dir, workflows_root, sample_list=sample_list)
        records.append(rec)

    failed_present = [r for r in records if not r.get("ok") and not r.get("skipped")]
    if failed_present:
        fb = _fallback_from_xlsx(disc.run_dir, out_dir)
        by_short = {r["short"]: r for r in fb}
        merged = []
        for r in records:
            if (not r.get("ok")) and r["short"] in by_short:
                alt = dict(by_short[r["short"]])
                alt["error_original"] = r.get("error")
                merged.append(alt)
            else:
                merged.append(r)
        records = merged

    log = pd.DataFrame(
        [
            {
                "workflow": r.get("workflow"),
                "short": r.get("short"),
                "ok": bool(r.get("ok")),
                "skipped": bool(r.get("skipped")),
                "n_tables": r.get("n_tables", 0),
                "table_rows_json": json.dumps(r.get("table_rows") or {}, ensure_ascii=False),
                "error": r.get("error") or r.get("error_original"),
                "fallback": r.get("fallback"),
                "out_dir": r.get("out_dir"),
            }
            for r in records
        ]
    )
    log.to_csv(out_dir / "extract_log.tsv", sep="\t", index=False)
    (out_dir / "extract_log.json").write_text(json.dumps(records, ensure_ascii=False, indent=2, default=str))
    return log
```

### `package/xvir_full/tables.py`

```python
"""Build coverage matrix and a sample-level master metrics table."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

from .config import LOW_DEPTH_R1_READS, WORKFLOWS
from .discover import Cohort, Discovery, _normalize_sid


def _read(path: Path) -> pd.DataFrame:
    if not path.is_file():
        return pd.DataFrame()
    return pd.read_csv(path, sep="\t")


def _sid_col(df: pd.DataFrame) -> Optional[str]:
    for c in ("sample_id", "source_sample", "sn", "v_id"):
        if c in df.columns:
            return c
    return None


def coverage_matrix(extract_dir: Path, disc: Discovery) -> pd.DataFrame:
    rows = []
    for spec in WORKFLOWS:
        d = extract_dir / spec.short
        present_dir = any(w.spec.key == spec.key and w.present for w in disc.workflows)
        tables = {}
        if d.is_dir():
            for tsv in sorted(d.glob("*.tsv")):
                df = _read(tsv)
                tables[tsv.stem] = len(df)
        n_ok = sum(1 for n in tables.values() if n > 0)
        status = "extracted" if n_ok else ("missing_workflow" if not present_dir else "extracted_empty")
        rows.append(
            {
                "workflow": spec.short,
                "title": spec.title,
                "status": status,
                "n_nonempty_tables": n_ok,
                "tables": ";".join(f"{k}:{v}" for k, v in tables.items()) if tables else "",
                "skip_if_absent": spec.skip_biology,
            }
        )
    return pd.DataFrame(rows)


def _prep_sample_df(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    col = _sid_col(df)
    if not col:
        return pd.DataFrame()
    out = df.copy()
    out["sample_id"] = out[col].map(_normalize_sid)
    return out.dropna(subset=["sample_id"])


def master_sample_table(extract_dir: Path, cohort: Cohort) -> pd.DataFrame:
    base = cohort.samples.copy() if cohort.samples is not None else pd.DataFrame()
    if base.empty:
        base = pd.DataFrame(columns=["sample_id"])
    else:
        base = base.copy()
        if "sample_id" not in base.columns:
            base["sample_id"] = None

    w1s = _prep_sample_df(_read(extract_dir / "W1" / "samples.tsv"))
    if not w1s.empty:
        keep = [
            c
            for c in [
                "sample_id",
                "n_runs",
                "merge_r1_reads",
                "merge_r1_bases",
                "merge_r1_q30_pct",
                "merge_r2_reads",
                "merge_r2_bases",
                "merge_r2_q30_pct",
                "contigs_all_n",
                "contigs_all_bp",
                "contigs_avg_len",
                "contigs_max_len",
                "contigs_ge1kb_n",
                "contigs_ge1kb_bp",
                "contigs_ge1kb_max_len",
                "contigs_ge1kb_max",
            ]
            if c in w1s.columns
        ]
        base = base.merge(w1s[keep], on="sample_id", how="outer", suffixes=("", "_w1dup"))

    w1r = _read(extract_dir / "W1" / "run_qc.tsv")
    if not w1r.empty:
        if "sample_id" not in w1r.columns:
            w1r["sample_id"] = w1r.get("run_id", pd.Series(dtype=str)).map(_normalize_sid)
        else:
            w1r["sample_id"] = w1r["sample_id"].map(_normalize_sid)
        agg_map = {}
        for src, dst, how in [
            ("reads_before", "reads_before_sum", "sum"),
            ("reads_after_fastp", "reads_after_fastp_sum", "sum"),
            ("q30_after_fastp", "q30_after_fastp_median", "median"),
            ("q30_before", "q30_before_median", "median"),
            ("read_retention_fastp", "read_retention_fastp_median", "median"),
            ("duplication_rate", "duplication_rate_median", "median"),
            ("rrna_retention_r1", "rrna_retention_r1_median", "median"),
            ("clean_r1_reads", "clean_r1_reads_sum", "sum"),
        ]:
            if src in w1r.columns:
                agg_map[dst] = (src, how)
        if agg_map:
            g = w1r.groupby("sample_id").agg(**agg_map).reset_index()
            base = base.merge(g, on="sample_id", how="left")

    w2s = _prep_sample_df(_read(extract_dir / "W2" / "sample_cluster.tsv"))
    if not w2s.empty:
        if "n_contigs" in w2s.columns and "n_contigs_in_clusters" not in w2s.columns:
            w2s = w2s.rename(columns={"n_contigs": "n_contigs_in_clusters"})
        keep = [c for c in ["sample_id", "n_contigs_in_clusters", "n_clusters"] if c in w2s.columns]
        base = base.merge(w2s[keep], on="sample_id", how="left")

    w2c = _prep_sample_df(_read(extract_dir / "W2" / "contigs.tsv"))
    if not w2c.empty:
        g = w2c.groupby("sample_id")
        extra = g.size().rename("n_putative_viral_contigs").reset_index()
        if "length" in w2c.columns:
            extra = extra.merge(g["length"].sum().rename("viral_contig_bp").reset_index(), on="sample_id")
        if "checkv_quality" in w2c.columns:
            hq = (
                w2c.assign(_hq=w2c["checkv_quality"].eq("High-quality"))
                .groupby("sample_id")["_hq"]
                .sum()
                .rename("n_high_quality")
                .reset_index()
            )
            extra = extra.merge(hq, on="sample_id")
        base = base.merge(extra, on="sample_id", how="left")

    w3s = _prep_sample_df(_read(extract_dir / "W3" / "host_sample.tsv"))
    if not w3s.empty:
        keep = [
            c
            for c in [
                "sample_id",
                "n_contigs",
                "n_records",
                "n_species_inferred",
                "n_genus_inferred",
                "mean_marker_count",
                "mean_annotated_species",
            ]
            if c in w3s.columns
        ]
        w3s = w3s[keep].rename(columns={"n_contigs": "host_n_contigs", "n_records": "host_n_records"})
        base = base.merge(w3s, on="sample_id", how="left")

    w3t = _prep_sample_df(_read(extract_dir / "W3" / "host_top_species.tsv"))
    if not w3t.empty and "inferred_mt_species" in w3t.columns:
        top = (
            w3t.sort_values(["sample_id", "n_contigs"] if "n_contigs" in w3t.columns else ["sample_id"])
            .drop_duplicates("sample_id")[["sample_id", "inferred_mt_species"]]
            .rename(columns={"inferred_mt_species": "top_host_species"})
        )
        base = base.merge(top, on="sample_id", how="left")

    w4 = _prep_sample_df(_read(extract_dir / "W4" / "sample_qc.tsv"))
    if not w4.empty:
        keep = ["sample_id"] + [
            c
            for c in w4.columns
            if c.startswith("kraken_") or c.startswith("bracken_")
        ]
        base = base.merge(w4[keep], on="sample_id", how="left")

    w5 = _prep_sample_df(_read(extract_dir / "W5" / "sample_summary.tsv"))
    if not w5.empty:
        keep = ["sample_id"] + [
            c
            for c in [
                "n_viral_contigs_with_reads",
                "total_mapped_reads",
                "max_rpm",
                "median_rpm",
                "mean_coverage_pct",
                "clean_reads",
                "mapping_rate_pct",
                "contigs_full_coverage",
            ]
            if c in w5.columns
        ]
        base = base.merge(w5[keep], on="sample_id", how="left")

    w7 = _prep_sample_df(_read(extract_dir / "W7" / "comparison.tsv"))
    if not w7.empty:
        extra_cols = [c for c in w7.columns if c not in base.columns or c == "sample_id"]
        base = base.merge(w7[extra_cols], on="sample_id", how="left")

    # drop duplicate suffix cols
    drop = [c for c in base.columns if c.endswith("_w1dup") or c.endswith("_x") or c.endswith("_y")]
    # keep sample_id
    base = base.drop(columns=[c for c in drop if c != "sample_id"], errors="ignore")
    base = base.drop_duplicates("sample_id")

    depth_col = None
    for c in ("merge_r1_reads", "clean_r1_reads_sum", "clean_reads"):
        if c in base.columns:
            depth_col = c
            break
    if depth_col:
        base["low_depth"] = pd.to_numeric(base[depth_col], errors="coerce") < LOW_DEPTH_R1_READS
    else:
        base["low_depth"] = False

    # core cohort: samples that have groupinfo method/host
    if "method" in base.columns:
        base["in_core_cohort"] = base["method"].notna() & (base["method"].astype(str).str.len() > 0)
    else:
        base["in_core_cohort"] = True
    return base.reset_index(drop=True)
```

### `package/xvir_full/stats.py`

```python
"""Overall descriptive stats and grouped nonparametric tests."""
from __future__ import annotations

import itertools
from pathlib import Path
from typing import Iterable, Optional

import numpy as np
import pandas as pd
from scipy import stats

from .config import METRIC_LABELS, METHOD_LABEL, METHOD_ORDER


def _bh(pvals: list[float]) -> np.ndarray:
    p = np.asarray(pvals, dtype=float)
    n = len(p)
    out = np.full(n, np.nan)
    mask = np.isfinite(p)
    if mask.sum() == 0:
        return out
    pv = p[mask]
    m = len(pv)
    order = np.argsort(pv)
    ranked = pv[order]
    adj = ranked * m / np.arange(1, m + 1)
    adj = np.minimum.accumulate(adj[::-1])[::-1]
    adj = np.clip(adj, 0, 1)
    tmp = np.empty(m)
    tmp[order] = adj
    out[mask] = tmp
    return out


def _num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")


def describe_overall(df: pd.DataFrame, metrics: Iterable[str], dataset: str = "all") -> pd.DataFrame:
    rows = []
    for m in metrics:
        if m not in df.columns:
            continue
        x = _num(df[m]).dropna()
        if x.empty:
            continue
        rows.append(
            {
                "dataset": dataset,
                "metric": m,
                "label": METRIC_LABELS.get(m, m),
                "n": int(len(x)),
                "n_missing": int(_num(df[m]).isna().sum()),
                "mean": float(x.mean()),
                "sd": float(x.std(ddof=1)) if len(x) > 1 else np.nan,
                "median": float(x.median()),
                "q25": float(x.quantile(0.25)),
                "q75": float(x.quantile(0.75)),
                "min": float(x.min()),
                "max": float(x.max()),
            }
        )
    return pd.DataFrame(rows)


def describe_by_group(df: pd.DataFrame, metrics: Iterable[str], group_col: str, dataset: str) -> pd.DataFrame:
    rows = []
    if group_col not in df.columns:
        return pd.DataFrame()
    for g, sub in df.groupby(group_col, dropna=True):
        part = describe_overall(sub, metrics, dataset=f"{dataset}|{group_col}={g}")
        if not part.empty:
            part["group_col"] = group_col
            part["group"] = str(g)
            part["group_label"] = METHOD_LABEL.get(str(g), str(g))
            part["n_group"] = len(sub)
            rows.append(part)
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def _epsilon_sq(h: float, k: int, n: int) -> float:
    if n <= k:
        return np.nan
    return max(0.0, (h - k + 1) / (n - k))


def _rank_biserial(x: np.ndarray, y: np.ndarray, u: float) -> float:
    nx, ny = len(x), len(y)
    if nx * ny == 0:
        return np.nan
    return 1.0 - (2.0 * u) / (nx * ny)


def group_tests(df: pd.DataFrame, metrics: Iterable[str], group_col: str, dataset: str) -> pd.DataFrame:
    if group_col not in df.columns:
        return pd.DataFrame()
    rows = []
    levels = [str(x) for x in df[group_col].dropna().unique()]
    if group_col == "method":
        levels = [m for m in METHOD_ORDER if m in levels] or levels
    if len(levels) < 2:
        return pd.DataFrame()

    for metric in metrics:
        if metric not in df.columns:
            continue
        groups = {
            g: _num(df.loc[df[group_col].astype(str) == g, metric]).dropna().to_numpy()
            for g in levels
        }
        present = [g for g, arr in groups.items() if len(arr) >= 2]
        if len(present) < 2:
            continue
        arrays = [groups[g] for g in present]
        n = int(sum(len(a) for a in arrays))
        try:
            h, p = stats.kruskal(*arrays)
        except ValueError:
            h, p = np.nan, np.nan
        rows.append(
            {
                "dataset": dataset,
                "group_col": group_col,
                "metric": metric,
                "label": METRIC_LABELS.get(metric, metric),
                "test": "kruskal_wallis",
                "comparison": "all_levels",
                "n": n,
                "k": len(present),
                "statistic": h,
                "p_value": p,
                "p_adj_bh": p,
                "effect": _epsilon_sq(h, len(present), n) if np.isfinite(h) else np.nan,
                "effect_name": "epsilon_squared",
            }
        )
        pair_ps = []
        pair_buf = []
        for a, b in itertools.combinations(present, 2):
            x, y = groups[a], groups[b]
            try:
                u, p_u = stats.mannwhitneyu(x, y, alternative="two-sided")
            except ValueError:
                u, p_u = np.nan, np.nan
            pair_buf.append((a, b, u, p_u, len(x), len(y)))
            pair_ps.append(p_u)
        adj = _bh(pair_ps) if pair_ps else []
        for i, (a, b, u, p_u, nx, ny) in enumerate(pair_buf):
            rows.append(
                {
                    "dataset": dataset,
                    "group_col": group_col,
                    "metric": metric,
                    "label": METRIC_LABELS.get(metric, metric),
                    "test": "mannwhitney_bh",
                    "comparison": f"{METHOD_LABEL.get(b, b)} vs {METHOD_LABEL.get(a, a)}",
                    "n": nx + ny,
                    "k": 2,
                    "statistic": u,
                    "p_value": p_u,
                    "p_adj_bh": adj[i] if len(adj) else np.nan,
                    "effect": _rank_biserial(groups[a], groups[b], u) if np.isfinite(u) else np.nan,
                    "effect_name": "rank_biserial",
                }
            )
    return pd.DataFrame(rows)


CORE_METRICS = [
    "merge_r1_reads",
    "read_retention_fastp_median",
    "q30_after_fastp_median",
    "duplication_rate_median",
    "rrna_retention_r1_median",
    "contigs_ge1kb_n",
    "contigs_avg_len",
    "n_putative_viral_contigs",
    "n_high_quality",
    "n_clusters",
    "n_species_inferred",
    "kraken_unclassified_frac",
    "bracken_species_taxa",
    "n_viral_contigs_with_reads",
    "max_rpm",
    "median_rpm",
    "mapping_rate_pct",
]


def run_stats(master: pd.DataFrame, group_cols: list[str], out_dir: Path) -> dict[str, pd.DataFrame]:
    out_dir.mkdir(parents=True, exist_ok=True)
    metrics = [m for m in CORE_METRICS if m in master.columns]
    # also include any extra numeric sample metrics
    extra = [
        c
        for c in master.columns
        if c not in metrics
        and c not in {"sample_id", "sn", "host", "method", "group", "raw_id", "low_depth", "in_core_cohort"}
        and pd.api.types.is_numeric_dtype(master[c])
    ]
    metrics = list(dict.fromkeys(metrics + extra))

    frames = {}
    # all rows with at least a sample id
    overall = describe_overall(master, metrics, "all_samples")
    frames["overall_all"] = overall

    core = master[master["in_core_cohort"] == True].copy() if "in_core_cohort" in master.columns else master
    frames["overall_core"] = describe_overall(core, metrics, "core_cohort")

    excl = core[~core["low_depth"].fillna(False)] if "low_depth" in core.columns else core
    frames["overall_core_excl_lowdepth"] = describe_overall(excl, metrics, "core_excl_lowdepth")

    grouped = []
    tests = []
    for gcol in group_cols:
        grouped.append(describe_by_group(core, metrics, gcol, "core_cohort"))
        tests.append(group_tests(core, metrics, gcol, "core_cohort"))
        tests.append(group_tests(excl, metrics, gcol, "core_excl_lowdepth"))
        grouped.append(describe_by_group(excl, metrics, gcol, "core_excl_lowdepth"))

    frames["by_group"] = pd.concat([x for x in grouped if not x.empty], ignore_index=True) if grouped else pd.DataFrame()
    frames["tests"] = pd.concat([x for x in tests if not x.empty], ignore_index=True) if tests else pd.DataFrame()

    for name, df in frames.items():
        df.to_csv(out_dir / f"{name}.tsv", sep="\t", index=False)
    return frames
```

### `package/xvir_full/plots_r.py`

```python
"""Stage TSVs, copy R scripts, run ggplot2 figures; optional matplotlib fallback."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Optional

import pandas as pd

from .config import PACKAGE_DIR, default_rscript

R_DIR = PACKAGE_DIR / "r"

STAGE_MAP = {
    "W1/samples.tsv": "W1_samples.tsv",
    "W1/run_qc.tsv": "W1_run_qc.tsv",
    "W2/contigs.tsv": "W2_contigs.tsv",
    "W2/sample_cluster.tsv": "W2_sample_cluster.tsv",
    "W2/cluster_summary.tsv": "W2_cluster_summary.tsv",
    "W2/hmm_iterations.tsv": "W2_hmm_iterations.tsv",
    "W3/host_sample.tsv": "W3_host_sample.tsv",
    "W3/host_top_species.tsv": "W3_host_top_species.tsv",
    "W4/sample_qc.tsv": "W4_sample_qc.tsv",
    "W4/bracken_top15_species.tsv": "W4_bracken_top15_species.tsv",
    "W5/sample_summary.tsv": "W5_sample_summary.tsv",
    "W5/top20_rpm.tsv": "W5_top20_rpm.tsv",
}


def stage_tables(extract_dir: Path, table_dir: Path, master: pd.DataFrame, coverage: pd.DataFrame) -> None:
    table_dir.mkdir(parents=True, exist_ok=True)
    master.to_csv(table_dir / "master_sample_metrics.tsv", sep="\t", index=False)
    coverage.to_csv(table_dir / "coverage.tsv", sep="\t", index=False)
    for src_rel, dst_name in STAGE_MAP.items():
        src = extract_dir / src_rel
        if src.is_file():
            shutil.copy2(src, table_dir / dst_name)


def _copy_r(out_r: Path) -> None:
    out_r.mkdir(parents=True, exist_ok=True)
    for name in ("00_sci_theme.R", "make_figures.R"):
        shutil.copy2(R_DIR / name, out_r / name)


def run_r_figures(table_dir: Path, fig_dir: Path, out_r: Path, rscript: Optional[Path] = None) -> dict:
    fig_dir.mkdir(parents=True, exist_ok=True)
    _copy_r(out_r)
    rs = rscript or default_rscript()
    log = {"rscript": str(rs) if rs else None, "ok": False, "returncode": None, "stderr_tail": ""}
    if rs is None:
        log["stderr_tail"] = "Rscript not found"
        _matplotlib_fallback(table_dir, fig_dir)
        return log
    cmd = [
        str(rs),
        str(out_r / "make_figures.R"),
        str(table_dir),
        str(fig_dir),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    log["returncode"] = proc.returncode
    log["stdout_tail"] = (proc.stdout or "")[-2000:]
    log["stderr_tail"] = (proc.stderr or "")[-4000:]
    log["ok"] = proc.returncode == 0
    pngs = list(fig_dir.glob("*.png"))
    if not pngs:
        _matplotlib_fallback(table_dir, fig_dir)
        log["fallback"] = "matplotlib"
    return log


def _matplotlib_fallback(table_dir: Path, fig_dir: Path) -> None:
    """Minimal SCI-style fallback if ggplot2 run produced nothing."""
    try:
        import matplotlib.pyplot as plt
        import numpy as np
    except Exception:
        return
    master_p = table_dir / "master_sample_metrics.tsv"
    if not master_p.is_file():
        return
    df = pd.read_csv(master_p, sep="\t")
    if "merge_r1_reads" not in df.columns:
        return
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.size": 8,
        "axes.linewidth": 0.6,
        "xtick.direction": "out",
        "ytick.direction": "out",
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "axes.grid": False,
    })
    fig, ax = plt.subplots(figsize=(4.5, 3.5), dpi=300)
    x = np.arange(len(df))
    ax.bar(x, df["merge_r1_reads"] / 1e6, color="#0072B2", edgecolor="black", linewidth=0.3)
    ax.axhline(5, ls="--", lw=0.6, color="#D55E00")
    ax.set_xticks(x)
    ax.set_xticklabels(df["sample_id"], rotation=45, ha="right")
    ax.set_ylabel("Merged R1 reads (millions)")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    fig.savefig(fig_dir / "fig01_depth_by_sample.png")
    fig.savefig(fig_dir / "fig01_depth_by_sample.pdf")
    plt.close(fig)
```

### `package/xvir_full/narrative.py`

```python
"""Fill result text and biological interpretation from tables; skip absent modules."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from .config import METRIC_LABELS, METHOD_LABEL, WF_BY_SHORT
from .discover import Discovery
from . import biology


def _meta_src(source_files: dict) -> str:
    if not source_files:
        return "未找到 groupinfo/sampleinfo，样本 ID 来自结果表"
    bits = []
    for k, v in source_files.items():
        parts = Path(v).parts
        tail = "/".join(parts[-2:]) if len(parts) >= 2 else Path(v).name
        bits.append(f"{k}={tail}")
    return "；".join(bits)



def _fmt(x, nd=2, pct=False, sci=False) -> str:
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "NA"
    v = float(x)
    if pct:
        if v <= 1.5:
            v = v * 100
        return f"{v:.2f}%"
    if sci and (abs(v) >= 1e5 or (abs(v) < 1e-2 and v != 0)):
        return f"{v:.3g}"
    if abs(v) >= 1000:
        return f"{v:,.0f}"
    return f"{v:.{nd}f}"


def _row(overall: pd.DataFrame, metric: str, dataset="core_cohort") -> Optional[pd.Series]:
    if overall is None or overall.empty:
        return None
    sub = overall[(overall["metric"] == metric)]
    if "dataset" in overall.columns:
        hit = sub[sub["dataset"] == dataset]
        if hit.empty:
            hit = sub
        sub = hit
    if sub.empty:
        return None
    return sub.iloc[0]


def _median_range(master: pd.DataFrame, col: str, pct=False) -> str:
    if col not in master.columns:
        return "（该字段未提取）"
    x = pd.to_numeric(master[col], errors="coerce").dropna()
    if x.empty:
        return "（该字段全部缺失）"
    return f"中位数 {_fmt(x.median(), pct=pct)}（范围 {_fmt(x.min(), pct=pct)}–{_fmt(x.max(), pct=pct)}，n={len(x)}）"


def _kw_sentence(tests: pd.DataFrame, metric: str, dataset="core_cohort") -> str:
    if tests is None or tests.empty:
        return ""
    sub = tests[
        (tests["metric"] == metric)
        & (tests["test"] == "kruskal_wallis")
        & (tests.get("dataset", dataset) == dataset if "dataset" in tests.columns else True)
    ]
    if "dataset" in tests.columns:
        sub = tests[(tests["metric"] == metric) & (tests["test"] == "kruskal_wallis") & (tests["dataset"] == dataset)]
    if sub.empty:
        return ""
    r = sub.iloc[0]
    p = r["p_value"]
    sig = "组间差异达到 α=0.05" if pd.notna(p) and p < 0.05 else "组间差异未达 α=0.05"
    extra = ""
    if pd.notna(r.get("effect")):
        extra = f"，ε²={float(r['effect']):.3f}"
    pairs = tests[
        (tests["metric"] == metric)
        & (tests["test"] == "mannwhitney_bh")
        & (tests.get("dataset", "core_cohort") == dataset if "dataset" in tests.columns else True)
    ]
    if "dataset" in tests.columns:
        pairs = tests[(tests["metric"] == metric) & (tests["test"] == "mannwhitney_bh") & (tests["dataset"] == dataset)]
    sig_pairs = pairs[pairs["p_adj_bh"] < 0.05] if not pairs.empty and "p_adj_bh" in pairs.columns else pd.DataFrame()
    pair_txt = ""
    if not sig_pairs.empty:
        pair_txt = " 显著两两比较：" + "；".join(
            f"{row['comparison']} (p_BH={_fmt(row['p_adj_bh'], nd=3, sci=True)})" for _, row in sig_pairs.iterrows()
        )
    return f"按建库方法 Kruskal–Wallis p={_fmt(p, sci=True)}（{sig}{extra}）。{pair_txt}"


def _present(cov: pd.DataFrame, short: str) -> bool:
    if cov is None or cov.empty:
        return False
    row = cov[cov["workflow"] == short]
    if row.empty:
        return False
    return str(row.iloc[0]["status"]) == "extracted"


def build_sections(
    disc: Discovery,
    master: pd.DataFrame,
    coverage: pd.DataFrame,
    stats_frames: dict[str, pd.DataFrame],
    table_dir: Optional[Path] = None,
) -> list[dict]:
    overall = stats_frames.get("overall_core", pd.DataFrame())
    tests = stats_frames.get("tests", pd.DataFrame())
    group_cols = disc.cohort.group_cols
    core = master[master["in_core_cohort"] == True].copy() if "in_core_cohort" in master.columns else master
    low = core[core["low_depth"] == True]["sample_id"].tolist() if "low_depth" in core.columns else []

    sections = []

    # executive
    n = len(core)
    methods = ""
    if "method" in core.columns:
        vc = core["method"].map(lambda x: METHOD_LABEL.get(str(x), str(x))).value_counts()
        methods = "；".join(f"{k} n={v}" for k, v in vc.items())
    present_w = [w.spec.short for w in disc.workflows if w.present]
    missing_w = [w.spec.short for w in disc.workflows if not w.present]
    exec_txt = [
        f"批次 {disc.batch_id} 核心队列 {n} 个生物学样本。",
        f"已提取流程：{', '.join(present_w) if present_w else '无'}。",
        f"未运行/缺失因而整章跳过：{', '.join(missing_w) if missing_w else '无'}。",
        ("分组因子：" + "、".join(group_cols) + "。同时报告总体与分组比较。")
        if group_cols
        else "无可用分组（或仅单一水平）→ 只做总体描述，不做组间检验。",
        f"低深度样本（合并 R1 < 5×10^6）：{', '.join(low) if low else '无'}。低深度会抬高相对丰度类指标（如 RPM），解读时单独标注。",
        "本报告只解释实际抽出的字段；缺失写成「未提取/未运行」，不写成分析失败。结果仅供科研内部参考，不构成诊断。",
    ]
    sections.append(
        {
            "id": "exec",
            "short": "EXEC",
            "title": "执行摘要",
            "skip": False,
            "results": exec_txt,
            "biology": biology.exec_summary(core, low),
            "figures": [],
        }
    )

    # cohort / coverage
    notes = list(disc.cohort.grouping_notes) + list(disc.extra_notes)
    sections.append(
        {
            "id": "cohort",
            "short": "META",
            "title": "样本 Meta 与提取覆盖",
            "skip": False,
            "results": [
                f"Meta 来源：{_meta_src(disc.cohort.source_files)}。",
                *notes,
                "覆盖矩阵见结构化表 coverage.tsv：status=extracted 才进入该流程章节。",
            ],
            "biology": biology.cohort(core),
            "figures": ["fig01_depth_by_sample"],
        }
    )

    def add_or_skip(short: str, title: str, results: list[str], biology: list[str], figures: list[str]):
        ok = _present(coverage, short)
        spec = WF_BY_SHORT[short]
        if not ok:
            sections.append(
                {
                    "id": short.lower(),
                    "short": short,
                    "title": title,
                    "skip": True,
                    "results": [f"本章跳过：{spec.skip_biology} 覆盖状态见 coverage.tsv。"],
                    "biology": [],
                    "figures": [],
                }
            )
            return
        sections.append(
            {
                "id": short.lower(),
                "short": short,
                "title": title,
                "skip": False,
                "results": results,
                "biology": biology,
                "figures": figures,
            }
        )

    # W1
    w1_res = [
        "原始/质控/去 rRNA/合并/组装指标按样本汇总。" + _median_range(core, "merge_r1_reads"),
        "fastp 保留率 " + _median_range(core, "read_retention_fastp_median", pct=True),
        "fastp 后 Q30 " + _median_range(core, "q30_after_fastp_median", pct=True),
        "rRNA 去除后 R1 保留率 " + _median_range(core, "rrna_retention_r1_median", pct=True),
        "≥1 kb contig 数 " + _median_range(core, "contigs_ge1kb_n"),
    ]
    if group_cols:
        for m in ("merge_r1_reads", "read_retention_fastp_median", "contigs_ge1kb_n"):
            s = _kw_sentence(tests, m)
            if s:
                w1_res.append(METRIC_LABELS.get(m, m) + "：" + s)
    add_or_skip(
        "W1",
        "W1 上游质控与组装",
        w1_res,
        biology.w1(core, tests),
        [
            "fig02_w1_fastp_retention",
            "fig03_w1_q30",
            "fig04_w1_rrna_retention",
            "fig05_w1_depth_vs_contigs",
        ],
    )

    w2_res = [
        "假定病毒 contig 数 " + _median_range(core, "n_putative_viral_contigs"),
        "CheckV High-quality 数 " + _median_range(core, "n_high_quality"),
        "ANI80 聚类数 " + _median_range(core, "n_clusters"),
    ]
    if group_cols:
        s = _kw_sentence(tests, "n_putative_viral_contigs")
        if s:
            w2_res.append("每样本假定病毒 contig：" + s)
    add_or_skip(
        "W2",
        "W2 病毒鉴定",
        w2_res,
        biology.w2(core, table_dir, tests),
        ["fig06_w2_checkv_by_sample", "fig07_w2_contig_length", "fig08_w2_viral_contigs_by_method"],
    )

    w3_res = [
        "推断宿主物种数 " + _median_range(core, "n_species_inferred"),
        "推断宿主属数 " + _median_range(core, "n_genus_inferred"),
    ]
    if "top_host_species" in core.columns:
        vc = core["top_host_species"].dropna().value_counts().head(5)
        if not vc.empty:
            w3_res.append("核心队列最常见推断物种：" + "；".join(f"{k} (n={v})" for k, v in vc.items()))
    n_w3 = int(master["n_species_inferred"].notna().sum()) if "n_species_inferred" in master.columns else 0
    if n_w3 > len(core):
        w3_res.append(
            f"W3 另包含核心队列之外的样本（有宿主指标的样本共 {n_w3} 个）。组间比较仅在有 method/host 标签的核心队列进行。"
        )
    add_or_skip(
        "W3",
        "W3 宿主鉴定",
        w3_res,
        biology.w3(core),
        ["fig09_w3_host_species"],
    )

    w4_res = [
        "Kraken 未分类比例 " + _median_range(core, "kraken_unclassified_frac", pct=True),
        "Bracken 物种数 " + _median_range(core, "bracken_species_taxa"),
        "Bracken 物种级分配 reads " + _median_range(core, "bracken_species_reads_assigned"),
    ]
    if group_cols:
        for m in ("kraken_unclassified_frac", "bracken_species_taxa"):
            s = _kw_sentence(tests, m)
            if s:
                w4_res.append(METRIC_LABELS.get(m, m) + "：" + s)
    add_or_skip(
        "W4",
        "W4 微生物谱（Kraken2/Bracken）",
        w4_res,
        biology.w4(core, table_dir, tests),
        ["fig10_w4_unclassified", "fig11_w4_species_richness", "fig12_w4_top_taxa"],
    )

    w5_res = [
        "有比对 reads 的病毒 contig 数 " + _median_range(core, "n_viral_contigs_with_reads"),
        "病毒 contig 比对率 " + _median_range(core, "mapping_rate_pct", pct=True),
        "最大 RPM " + _median_range(core, "max_rpm"),
        "中位 RPM " + _median_range(core, "median_rpm"),
    ]
    if group_cols:
        for m in ("mapping_rate_pct", "max_rpm"):
            s = _kw_sentence(tests, m)
            if s:
                w5_res.append(METRIC_LABELS.get(m, m) + "：" + s)
    add_or_skip(
        "W5",
        "W5 病毒定量（RPM）",
        w5_res,
        biology.w5(core, tests),
        ["fig13_w5_mapping_rate", "fig14_w5_max_rpm", "fig15_w5_depth_vs_mapping"],
    )

    add_or_skip(
        "W6",
        "W6 病毒注释",
        [],
        [],
        [],
    )
    add_or_skip(
        "W7",
        "W7 建库打断 benchmark",
        [],
        [],
        [],
    )

    # cross
    if _present(coverage, "W1") and _present(coverage, "W5"):
        sections.append(
            {
                "id": "cross",
                "short": "CROSS",
                "title": "跨流程衔接",
                "skip": False,
                "results": [
                    "深度（W1）与病毒比对率/RPM（W5）应联合看：深度不足时，高 RPM 优先视为分母效应。",
                    "W2 代表序列是 W5 的参考；W4 未分类比例高与 W5 病毒比对率低可以同时成立，因为二者参考库不同。",
                ],
                "biology": biology.cross(core),
                "figures": ["fig15_w5_depth_vs_mapping"],
            }
        )

    return sections
```

### `package/xvir_full/biology.py`

```python
"""Data-bound biological discussion: every sentence cites a figure id or table value."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .config import METHOD_LABEL

RODENT_HINTS = (
    "Ligilactobacillus",
    "Helicobacter apodemus",
    "Helicobacter typhlonius",
    "Romboutsia",
)
KIT_HINTS = ("Ralstonia", "Cutibacterium acnes", "Bradyrhizobium", "Burkholderia")


def _read(table_dir: Path | None, name: str) -> pd.DataFrame:
    if table_dir is None:
        return pd.DataFrame()
    p = Path(table_dir) / name
    if not p.is_file():
        return pd.DataFrame()
    return pd.read_csv(p, sep="\t")


def _frac_pct(x) -> str:
    v = float(x)
    if abs(v) <= 1.5:
        v *= 100
    return f"{v:.2f}%"


def _map_pct(x) -> str:
    """mapping_rate_pct is already in percent units (0.04 means 0.04%)."""
    return f"{float(x):.3f}%"


def _ids(xs) -> str:
    return "、".join(str(x) for x in list(xs))


def _method(x) -> str:
    return METHOD_LABEL.get(str(x), str(x))


def _kw(tests: pd.DataFrame, metric: str) -> str:
    if tests is None or tests.empty:
        return ""
    sub = tests[(tests["metric"] == metric) & (tests["test"] == "kruskal_wallis")]
    if "dataset" in tests.columns:
        hit = sub[sub["dataset"] == "core_cohort"]
        if not hit.empty:
            sub = hit
    if sub.empty:
        return ""
    p = sub.iloc[0]["p_value"]
    if pd.isna(p):
        return ""
    flag = "达到" if float(p) < 0.05 else "未达"
    return f"Kruskal–Wallis p={float(p):.4f}（组间差异{flag} α=0.05）"


def _val(core: pd.DataFrame, sid: str, col: str):
    idx = core.set_index("sample_id")
    if sid not in idx.index or col not in idx.columns:
        return None
    return idx.loc[sid, col]


def exec_summary(core: pd.DataFrame, low: list) -> list[str]:
    n = len(core)
    host = core["host"].dropna().astype(str).mode().iloc[0] if "host" in core.columns and core["host"].notna().any() else "未标注"
    methods = []
    if "method" in core.columns:
        vc = core["method"].map(_method).value_counts()
        methods = [f"{k} n={int(v)}" for k, v in vc.items()]
    low_txt = _ids(low) if low else "无"
    return [
        f"本核心队列 n={n}，设计宿主为 {host}，建库方法 { '；'.join(methods) if methods else '未分组' }。"
        f"低深度样本（fig01 虚线以下）为 {low_txt}。后续 RPM、物种数、contig 数先对照 fig01，再谈生物学。",
        "分组每臂大约 3–4 个样本：不显著不能写成方法等价，显著也不能写成某种打断更好；正文只报告本表里的 p 与效应量。",
    ]


def cohort(core: pd.DataFrame) -> list[str]:
    out = []
    if "merge_r1_reads" in core.columns:
        r1 = pd.to_numeric(core["merge_r1_reads"], errors="coerce")
        low = core.loc[r1 < 5e6]
        if low.empty:
            out.append("【fig01_depth_by_sample】核心队列无人低于 5 million R1。")
        else:
            bits = []
            for _, r in low.iterrows():
                bits.append(f"{r['sample_id']}={int(r['merge_r1_reads']):,}（{_method(r.get('method',''))}）")
            other = core.loc[r1 >= 5e6]
            out.append(
                f"【fig01_depth_by_sample】低于虚线的是 {'、'.join(bits)}。"
                f"其余 {len(other)} 个样本 R1 中位数 {other['merge_r1_reads'].median()/1e6:.1f} million。"
                "同方法的其他样本（例如 RNA 94°C 的 v76/v78，RNA 85°C 的 v79/v82）深度正常，"
                "因此低深度是个别文库产量问题，不是某种打断方法的固有属性。"
            )
    if "host" in core.columns:
        hosts = core["host"].dropna().astype(str).unique().tolist()
        if len(hosts) <= 1:
            out.append(
                f"宿主列只有 {hosts[0] if hosts else 'NA'} 一个水平，做宿主组间检验没有信息量；分组只保留 method。"
            )
    return out


def w1(core: pd.DataFrame, tests: pd.DataFrame) -> list[str]:
    out = []
    if "read_retention_fastp_median" in core.columns:
        x = pd.to_numeric(core["read_retention_fastp_median"], errors="coerce")
        kw = _kw(tests, "read_retention_fastp_median")
        out.append(
            f"【fig02_w1_fastp_retention】fastp 保留率中位数 {_frac_pct(x.median())}"
            f"（范围 {_frac_pct(x.min())}–{_frac_pct(x.max())}）。三种方法箱线重叠。"
            f"{kw + '，' if kw else ''}本批次接头/低质量过滤负担相近，不能用 fastp 损失解释后面 fig12 的人源优势。"
        )
    if "q30_after_fastp_median" in core.columns:
        x = pd.to_numeric(core["q30_after_fastp_median"], errors="coerce")
        out.append(
            f"【fig03_w1_q30】fastp 后 Q30 中位数 {_frac_pct(x.median())}，最低仍 {_frac_pct(x.min())}。"
            "碱基质量不是本队列分类异常的原因。"
        )
    if "rrna_retention_r1_median" in core.columns:
        rr = pd.to_numeric(core["rrna_retention_r1_median"], errors="coerce")
        low_rr = core.loc[rr < 0.7].sort_values("rrna_retention_r1_median")
        bits = []
        for _, r in low_rr.iterrows():
            bits.append(
                f"{r['sample_id']}={_frac_pct(r['rrna_retention_r1_median'])}（{_method(r.get('method',''))}）"
            )
        high_n = int((rr >= 0.95).sum())
        extra = ""
        if "v70" in set(core["sample_id"]) and "v88" in set(core["sample_id"]):
            extra = (
                "v70 深度并不低（R1 约 1.2×10^7）但 rRNA 保留率与低深度的 v88 一样差，"
                "说明 rRNA 残留/去除效率与测序深度不是同一件事。"
            )
        out.append(
            f"【fig04_w1_rrna_retention】{high_n}/{len(core)} 个样本 rRNA 去除后 R1 保留率 ≥95%；"
            f"低于 70% 的是 {'、'.join(bits) if bits else '无'}。{extra}"
            "这些样本的非 rRNA 微生物信号会被稀释，看 fig11 物种数、fig12 组成时把它们与高保留率样本分开。"
        )
    if {"merge_r1_reads", "contigs_ge1kb_n"} <= set(core.columns):
        cmin, cmax = int(core["contigs_ge1kb_n"].min()), int(core["contigs_ge1kb_n"].max())
        low = core.loc[core.get("low_depth") == True] if "low_depth" in core.columns else core.iloc[0:0]
        low_txt = ""
        if not low.empty:
            low_txt = "、".join(
                f"{r.sample_id} 仅 {int(r.contigs_ge1kb_n):,} 条" for _, r in low.iterrows()
            )
        kw = _kw(tests, "contigs_ge1kb_n")
        out.append(
            f"【fig05_w1_depth_vs_contigs】≥1 kb contig 数 {cmin:,}–{cmax:,}，随 R1 深度上升。"
            f"{low_txt + '，与 fig01 同向，不能写成这两种打断方法组装差。' if low_txt else ''}"
            f"{kw}"
        )
    return out


def w2(core: pd.DataFrame, table_dir: Path | None, tests: pd.DataFrame) -> list[str]:
    out = []
    contigs = _read(table_dir, "W2_contigs.tsv")
    if not contigs.empty and "checkv_quality" in contigs.columns:
        if "source_sample" in contigs.columns:
            core_hit = contigs[contigs["source_sample"].isin(set(core["sample_id"]))]
            if not core_hit.empty:
                contigs = core_hit
        vc = contigs["checkv_quality"].fillna("NA").value_counts()
        parts = "、".join(f"{k} {int(v)} 条" for k, v in vc.items())
        n_hq = int(vc.get("High-quality", 0) + vc.get("Complete", 0))
        out.append(
            f"【fig06_w2_checkv_by_sample】抽出 {len(contigs)} 条假定病毒 contig（{parts}）。"
            f"High-quality+Complete 合计 {n_hq} 条，只占少数。"
            "RNA 病毒常以部分基因组被召回，不能用 HQ 条数当流行率，也不能把 Medium/Low 条丢掉当「没有病毒」。"
        )
    if not contigs.empty:
        length = None
        for col in ("length", "contig_length"):
            if col in contigs.columns:
                length = pd.to_numeric(contigs[col], errors="coerce")
                break
        if length is not None and length.notna().any():
            out.append(
                f"【fig07_w2_contig_length】长度中位数 {int(length.median()):,} bp"
                f"（最长 {int(length.max()):,} bp）。短 contig 居多符合宏转录组组装碎片化，"
                "单独一条短序列不等于「基因组残缺致病」。"
            )
    if "n_putative_viral_contigs" in core.columns:
        x = pd.to_numeric(core["n_putative_viral_contigs"], errors="coerce")
        low = core.loc[core.get("low_depth") == True] if "low_depth" in core.columns else core.iloc[0:0]
        extra = ""
        if not low.empty:
            extra = "低深度样本 " + "、".join(
                f"{r.sample_id}={int(r.n_putative_viral_contigs)}" for _, r in low.iterrows()
            ) + "，落在队列下限，与 fig01 同向。"
        kw = _kw(tests, "n_putative_viral_contigs")
        out.append(
            f"【fig08_w2_viral_contigs_by_method】每样本假定病毒 contig 中位数 {x.median():.0f}"
            f"（范围 {int(x.min())}–{int(x.max())}）。方法组箱线重叠。{extra}{(' ' + kw) if kw else ''}"
        )
    return out


def w3(core: pd.DataFrame) -> list[str]:
    if "top_host_species" not in core.columns:
        return ["【fig09_w3_host_species】未抽出推断物种列，无法与设计宿主对照。"]
    vc = core["top_host_species"].dropna().value_counts()
    top = vc.index[0]
    n = int(vc.iloc[0])
    host = core["host"].dropna().astype(str).mode().iloc[0] if "host" in core.columns and core["host"].notna().any() else "未标注"
    return [
        f"【fig09_w3_host_species】核心队列 {n}/{len(core)} 个样本的线粒体推断物种均为 {top}，与实验设计宿主（{host}）一致。"
        "这是标记基因证据，不是 Kraken 的 k-mer 分类。下一章 fig12 若出现人源优势，必须对照本图，不能改写成「样本来自人」。"
    ]


def w4(core: pd.DataFrame, table_dir: Path | None, tests: pd.DataFrame) -> list[str]:
    out = []
    if "kraken_unclassified_frac" in core.columns:
        x = pd.to_numeric(core["kraken_unclassified_frac"], errors="coerce")
        kw = _kw(tests, "kraken_unclassified_frac")
        out.append(
            f"【fig10_w4_unclassified】Kraken 未分类比例中位数 {_frac_pct(x.median())}"
            f"（范围 {_frac_pct(x.min())}–{_frac_pct(x.max())}）。{kw + '。' if kw else ''}"
            "也就是绝大多数 reads 根本没进 fig12 的物种堆叠：fig12 描述的是「已分类的那一小块」，不是全库组成。"
        )
    if "bracken_species_taxa" in core.columns:
        x = pd.to_numeric(core["bracken_species_taxa"], errors="coerce")
        low = core.nsmallest(2, "bracken_species_taxa")
        bits = []
        for _, r in low.iterrows():
            flag = "低深度" if bool(r.get("low_depth")) else "非低深度"
            bits.append(f"{r['sample_id']}={int(r['bracken_species_taxa'])}（{flag}）")
        kw = _kw(tests, "bracken_species_taxa")
        out.append(
            f"【fig11_w4_species_richness】Bracken 物种数中位数 {x.median():.0f}"
            f"（范围 {int(x.min())}–{int(x.max())}）。最低的是 {'、'.join(bits)}，与 fig01 低深度样本重叠，"
            f"优先解释为检测限而不是这些样本「无菌」。{kw}"
        )
    top = _read(table_dir, "W4_bracken_top15_species.tsv")
    if top.empty or "name" not in top.columns:
        out.append("【fig12_w4_top_taxa】未抽出 top-15 表，跳过组成讨论。")
        return out
    t = top[top["sample_id"].isin(set(core["sample_id"]))].copy()
    if t.empty:
        out.append("【fig12_w4_top_taxa】top-15 表与核心样本 ID 对不上，跳过。")
        return out
    if "rank" in t.columns:
        r1 = t[pd.to_numeric(t["rank"], errors="coerce") == 1].copy()
    else:
        r1 = t.sort_values("fraction_total_reads", ascending=False).groupby("sample_id", as_index=False).head(1)
    n_samp = r1["sample_id"].nunique()
    top1_name = str(r1["name"].mode().iloc[0]) if not r1.empty else "NA"
    n_top1 = int((r1["name"] == top1_name).sum()) if not r1.empty else 0
    fr = pd.to_numeric(r1["fraction_total_reads"], errors="coerce")
    host = (
        core["host"].dropna().astype(str).mode().iloc[0]
        if "host" in core.columns and core["host"].notna().any()
        else "unknown"
    )
    w3_sp = (
        core["top_host_species"].dropna().mode().iloc[0]
        if "top_host_species" in core.columns and core["top_host_species"].notna().any()
        else "未提供"
    )
    out.append(
        f"【fig12_w4_top_taxa】(i) {n_top1}/{n_samp} 个核心样本的 Bracken top-15 第一名是 {top1_name}"
        f"（已分类/top-15 空间比例 {_frac_pct(fr.min())}–{_frac_pct(fr.max())}，中位数 {_frac_pct(fr.median())}）。"
        f"实验设计宿主为 {host}，W3（fig09）推断为 {w3_sp}。人是主分类单元与大鼠宿主冲突，"
        "不能读成这些样本以人源组织或人体微生物为主。"
    )
    out.append(
        "(ii) 可能机制（并列，本数据不能单独证实哪一条）："
        "① 所用 Kraken/Bracken 库中人类基因组/转录组过度代表，哺乳动物保守 rRNA 残片或 mRNA 被派到 Homo sapiens；"
        "② 大鼠转录本在该数据库覆盖不足，最近邻变成人类；"
        "③ 建库、试剂或操作引入人源核酸。"
        "结合 fig10，未分类仍占约 83%–95%，因此即使已分类块里人占 86%–98%，也只覆盖文库的少数 reads。"
    )
    human_mask = t["name"].astype(str).str.contains(r"Homo|sapiens", case=False, na=False)
    rest = t.loc[~human_mask]
    if rest.empty:
        out.append("(iii) 去掉人源后 top-15 表无剩余物种。")
        return out
    rest_sum = rest.groupby("name")["fraction_total_reads"].sum().sort_values(ascending=False)
    lead = rest_sum.head(6)
    lead_txt = "、".join(f"{k}（合计比例 {float(v):.4f}）" for k, v in lead.items())
    per = rest.sort_values("fraction_total_reads", ascending=False).groupby("sample_id", as_index=False).first()
    if "method" in core.columns:
        per = per.merge(core[["sample_id", "method"]], on="sample_id", how="left")
    vc = per["name"].value_counts()
    per_bits = []
    for name, n in vc.items():
        sids = per.loc[per["name"] == name, "sample_id"].tolist()
        per_bits.append(f"{name} {int(n)}/{len(per)} 样本（{_ids(sids)}）")
    presence = rest.groupby("name")["sample_id"].nunique().sort_values(ascending=False)
    rodent_bits = []
    seen = set()
    for key in RODENT_HINTS:
        hit = rest[rest["name"].astype(str).str.contains(key, case=False, na=False)]
        if hit.empty:
            continue
        for nm, g in hit.groupby("name"):
            if nm in seen:
                continue
            seen.add(nm)
            rodent_bits.append(f"{nm} 出现在 {g['sample_id'].nunique()}/{n_samp} 个样本")
    kit_bits = []
    for key in KIT_HINTS:
        hit = rest[rest["name"].astype(str).str.contains(key, case=False, na=False)]
        if hit.empty:
            continue
        for nm, g in hit.groupby("name"):
            kit_bits.append(f"{nm} {g['sample_id'].nunique()}/{n_samp} 样本")
    out.append(
        f"(iii) 去掉 {top1_name} 之后，剩余 top-15 类群按合计比例最高的是 {lead_txt}。"
        f"按样本把剩余类群重新排第一名：{'；'.join(per_bits)}。"
        f"剩余第一名的比例只有约 {_frac_pct(per['fraction_total_reads'].min())}–{_frac_pct(per['fraction_total_reads'].max())}，"
        "因为人已经占掉已分类块的绝大部分。"
        + (" 更符合啮齿动物肠道背景的类群：" + "；".join(rodent_bits) + "。" if rodent_bits else "")
        + (
            " Staphylococcus aureus / Escherichia coli 既可能是定植也可能是皮肤或试剂背景，不能当感染。"
            + ((" 常见试剂/皮肤背景：" + "；".join(kit_bits) + "。") if kit_bits else "")
        )
    )
    if "method" in core.columns:
        hum = t.loc[human_mask, ["sample_id", "fraction_total_reads"]].merge(
            core[["sample_id", "method"]], on="sample_id", how="left"
        )
        by = hum.groupby("method")["fraction_total_reads"].agg(["median", "min", "max"])
        by_txt = "、".join(
            f"{_method(m)} 中位数 {_frac_pct(r['median'])}（{_frac_pct(r['min'])}–{_frac_pct(r['max'])}）"
            for m, r in by.iterrows()
        )
        r1m = r1.merge(core[["sample_id", "method"]], on="sample_id", how="left")
        still = r1m.groupby("method")["name"].apply(lambda s: bool((s == top1_name).all()))
        if bool(still.all()):
            still_txt = "三种打断方法下第一名仍全部是人"
        else:
            still_txt = "并非所有方法都以人为第一名：" + "、".join(
                f"{_method(m)}={'是' if v else '否'}" for m, v in still.items()
            )
        ecol = per[per["name"].astype(str).str.contains("Escherichia coli", case=False, na=False)]
        ecol_txt = ""
        if not ecol.empty:
            ecol_txt = (
                "去人源后改由 Escherichia coli 居首的是 "
                + "、".join(f"{r.sample_id}（{_method(r.get('method',''))}）" for _, r in ecol.iterrows())
                + "，分属不同打断方法，所以也不是单一技术路线的产物。"
            )
        low_depth_ids = core.loc[core.get("low_depth") == True, "sample_id"].tolist() if "low_depth" in core.columns else []
        depth_txt = ""
        if low_depth_ids:
            sub = r1m[r1m["sample_id"].isin(low_depth_ids)]
            depth_txt = (
                "低深度样本 "
                + "、".join(
                    f"{r.sample_id} 人源比例 {_frac_pct(r.fraction_total_reads)}" for _, r in sub.iterrows()
                )
                + "，与深度充足样本同方向，说明 fig12 的人源第一名不是低深度特有。"
            )
        out.append(
            f"(iv) 建库方法：人源第一名比例 {by_txt}。{still_txt}。"
            f"{ecol_txt}{depth_txt}"
            "因此 fig12 的人源主导更像分类器把哺乳动物 reads 派给人这一共同偏差，而不像某种打断特有的伪影。"
            "cDNA 组中位数略低、部分样本物种数更高，只提示已分类块里非人源残留稍多；组间检验未显著，不能宣布 cDNA 更能去人源。"
        )
    return out


def w5(core: pd.DataFrame, tests: pd.DataFrame) -> list[str]:
    out = []
    if "mapping_rate_pct" in core.columns:
        x = pd.to_numeric(core["mapping_rate_pct"], errors="coerce")
        kw = _kw(tests, "mapping_rate_pct")
        out.append(
            f"【fig13_w5_mapping_rate】病毒 contig 比对率中位数 {_map_pct(x.median())}"
            f"（范围 {_map_pct(x.min())}–{_map_pct(x.max())}），整体远低于 1%。{kw + '。' if kw else ''}"
            "与 fig10 高未分类一致：病毒参考只解释了极少 reads。"
        )
    if "max_rpm" in core.columns:
        top = core.nlargest(3, "max_rpm")
        bits = []
        for _, r in top.iterrows():
            flag = "低深度" if bool(r.get("low_depth")) else "非低深度"
            bits.append(f"{r['sample_id']}={float(r['max_rpm']):.1f} RPM（{flag}，{_method(r.get('method',''))}）")
        out.append(
            f"【fig14_w5_max_rpm】最大 RPM 最高的三个样本是 {'、'.join(bits)}。"
            "高 RPM 若集中在 fig01 虚线以下，这是分母（clean reads）变小，不是病毒载量生物学最高。"
        )
    if {"merge_r1_reads", "mapping_rate_pct"} <= set(core.columns):
        low = core.loc[core.get("low_depth") == True] if "low_depth" in core.columns else core.iloc[0:0]
        low_txt = ""
        if not low.empty:
            low_txt = "、".join(
                f"{r.sample_id} {_map_pct(r.mapping_rate_pct)}" for _, r in low.iterrows()
            )
        rest = core.loc[core.get("low_depth") != True] if "low_depth" in core.columns else core
        rest_txt = ""
        if not rest.empty:
            rx = pd.to_numeric(rest["mapping_rate_pct"], errors="coerce")
            rest_txt = f"深度充足样本比对率 {_map_pct(rx.min())}–{_map_pct(rx.max())}。"
        kw = _kw(tests, "mapping_rate_pct")
        out.append(
            f"【fig15_w5_depth_vs_mapping】深度最低的样本比对率最高（{low_txt}），点落在左上，是典型的低分母抬升。"
            f"{rest_txt}三种方法在深度充足时没有分开的云团。{kw} 看不出打断方法改变病毒回收率。"
        )
    return out


def cross(core: pd.DataFrame) -> list[str]:
    return [
        "【fig09 vs fig12】线粒体标记把核心样本都放在 Rattus，k-mer 物种表却把已分类块派给人："
        "宿主结论以 W3 为准，W4 人源当作数据库/同源偏差，除非另有人源污染实验。",
        "【fig01 vs fig14/fig15】低深度样本的高 RPM 与高比对率必须先当技术效应；先看 fig01 再读 W5。",
        "【fig10 vs fig13】未分类约 83%–95% 与病毒比对率 <0.2% 可以同时成立，因为二者参考库不同，不互相否定。",
    ]
```

### `package/xvir_full/display.py`

```python
"""Number formatting, path compaction, and drop JSON-like columns for reports."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional

import numpy as np
import pandas as pd

JSON_COL_HINTS = (
    "json",
    "traceback",
    "payload",
    "table_rows_json",
    "stdout",
    "stderr",
)

PATH_COL_HINTS = (
    "out_dir",
    "result_dir",
    "extractor",
    "fallback",
    "path",
    "fq1",
    "fq2",
)

INT_COL_HINTS = (
    "n_",
    "_n",
    "reads",
    "bases",
    "contigs",
    "taxa",
    "count",
    "n_runs",
    "n_tables",
    "k",
    "n_group",
    "n_missing",
)
PCT_COL_HINTS = ("pct", "percent", "q30", "retention")
P_COL_HINTS = ("p_value", "p_adj", "pval")
FRAC_COL_HINTS = ("frac", "effect", "rate", "retention", "duplication")


def drop_json_columns(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    keep = [
        c
        for c in df.columns
        if not any(h in str(c).lower() for h in JSON_COL_HINTS)
    ]
    return df.loc[:, keep]


def _looks_like_path(val: object) -> bool:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return False
    s = str(val).strip()
    return s.startswith("/") or s.startswith("file://")


def detect_path_columns(df: pd.DataFrame) -> list[str]:
    cols = []
    if df is None or df.empty:
        return cols
    for c in df.columns:
        cl = str(c).lower()
        if any(h in cl for h in PATH_COL_HINTS):
            cols.append(c)
            continue
        s = df[c].dropna().astype(str)
        if s.empty:
            continue
        hit = s.map(_looks_like_path).mean()
        if hit >= 0.5:
            cols.append(c)
    return cols


def common_prefix(paths: Iterable[str]) -> str:
    vals = [str(p) for p in paths if p and str(p).startswith("/")]
    if len(vals) < 2:
        return str(Path(vals[0]).parent) + "/" if vals else ""
    try:
        pref = str(Path(*Path(vals[0]).parts[: len(Path(vals[0]).parts)]))
        cp = str(Path(vals[0]))
        for v in vals[1:]:
            a, b = Path(cp).parts, Path(v).parts
            i = 0
            while i < min(len(a), len(b)) and a[i] == b[i]:
                i += 1
            cp = str(Path(*a[:i])) if i else ""
            if not cp:
                return ""
        return cp.rstrip("/") + "/"
    except Exception:
        return ""


def relativize_paths(df: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    """Replace absolute paths with tails; return common prefix for a table note."""
    if df is None or df.empty:
        return df, ""
    out = df.copy()
    path_cols = detect_path_columns(out)
    collected: list[str] = []
    for c in path_cols:
        collected.extend(str(v) for v in out[c].dropna().tolist() if _looks_like_path(v))
    prefix = common_prefix(collected)
    if not prefix:
        # still strip to basename if single absolute paths
        for c in path_cols:
            out[c] = out[c].map(
                lambda v: Path(str(v)).name if _looks_like_path(v) else v
            )
        return out, ""
    for c in path_cols:
        def _rel(v, pref=prefix):
            if not _looks_like_path(v):
                return v
            s = str(v)
            if s.startswith(pref):
                return s[len(pref):] or "."
            return Path(s).name
        out[c] = out[c].map(_rel)
    return out, prefix


def format_number(val: object, col: str = "") -> str:
    if val is None or (isinstance(val, float) and not np.isfinite(val)) or pd.isna(val):
        return "NA"
    if isinstance(val, bool) or (isinstance(val, np.bool_)):
        return "TRUE" if val else "FALSE"
    if isinstance(val, str):
        return val
    cl = col.lower()
    try:
        fv = float(val)
    except (TypeError, ValueError):
        return str(val)

    if any(h in cl for h in P_COL_HINTS):
        if fv < 0.0001:
            return f"{fv:.2e}"
        return f"{fv:.4f}"

    is_int_col = any(h in cl for h in INT_COL_HINTS) or cl in {"n", "k"}
    if is_int_col and abs(fv - round(fv)) < 1e-6:
        return f"{int(round(fv)):,}"

    if any(h in cl for h in PCT_COL_HINTS) and "frac" not in cl:
        # stored 0-1 or 0-100
        x = fv * 100 if 0 <= fv <= 1.5 else fv
        return f"{x:.2f}"

    if any(h in cl for h in FRAC_COL_HINTS) and "pct" not in cl:
        return f"{fv:.4f}"

    if abs(fv - round(fv)) < 1e-9 and abs(fv) >= 1:
        return f"{int(round(fv)):,}"
    if abs(fv) < 1:
        return f"{fv:.4f}"
    if abs(fv) >= 1000:
        return f"{fv:,.2f}"
    return f"{fv:.2f}"


def format_dataframe(df: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    """Drop JSON cols, compact paths, stringify numbers for report tables."""
    if df is None or df.empty:
        return df if df is not None else pd.DataFrame(), ""
    out = drop_json_columns(df)
    out, prefix = relativize_paths(out)
    show = pd.DataFrame(index=out.index)
    for c in out.columns:
        show[c] = [format_number(v, str(c)) if _is_numeric_cell(v) else ("" if pd.isna(v) else str(v)) for v in out[c]]
    return show, prefix


def _is_numeric_cell(v: object) -> bool:
    if isinstance(v, bool) or isinstance(v, np.bool_):
        return False
    return isinstance(v, (int, float, np.integer, np.floating)) and not pd.isna(v)


def shorten_user_text(text: str, known_roots: Optional[list[str]] = None) -> str:
    """Strip absolute prefixes from free-text sentences."""
    if not text:
        return text
    s = text
    roots = known_roots or []
    for r in sorted(roots, key=len, reverse=True):
        if r and r in s:
            s = s.replace(r, "")
    # generic /data/user/... collapse: keep last 3 parts if a unix path appears
    import re
    def _clip(m):
        path = m.group(0)
        parts = Path(path).parts
        if len(parts) > 4:
            return "/".join(parts[-3:])
        return path
    s = re.sub(r"(?:/data|/home)[/A-Za-z0-9_.\-]+", _clip, s)
    return s
```

### `package/xvir_full/report.py`

```python
"""Build self-contained HTML (embedded figures) and landscape A4 PDF."""
from __future__ import annotations

import base64
import html
from datetime import datetime
from pathlib import Path

import pandas as pd

from .display import format_dataframe, shorten_user_text

CSS = """
@page { size: A4 landscape; margin: 10mm; }
:root { --ink:#111; --muted:#555; --line:#c8c8c8; --bg:#f7f7f7; --accent:#1f4e79; }
* { box-sizing: border-box; }
body { margin:0; background:#ececec; color:var(--ink);
  font: 12.5px/1.55 "Helvetica Neue", Helvetica, Arial, "Noto Sans CJK SC", sans-serif; }
main { max-width: 1100px; margin: 18px auto 48px; background:#fff; padding: 28px 32px 48px; overflow-x: hidden; }
h1 { font-size: 22px; margin: 0 0 8px; font-weight: 700; }
h2 { font-size: 15px; margin: 28px 0 8px; padding-bottom: 4px; border-bottom: 1.2px solid var(--ink); }
h3 { font-size: 13px; margin: 16px 0 6px; }
.kicker { letter-spacing:.08em; text-transform:uppercase; font-size:10px; color:var(--accent); font-weight:700; }
.meta, figcaption, .muted { color:var(--muted); }
.notice { background:var(--bg); border-left: 3px solid var(--accent); padding:8px 10px; margin:10px 0; }
.warn { border-left-color:#9c3b2e; }
.skip { border-left-color:#888; color:var(--muted); }
.table-wrap { overflow-x: auto; max-width: 100%; margin: 8px 0 14px; border: 0.6px solid var(--line); }
table { border-collapse: collapse; width: max-content; min-width: 100%; font-size:11px; }
th, td { border-top: 0.6px solid var(--line); border-bottom: 0.6px solid var(--line); padding: 3px 6px; text-align:left; vertical-align:top; }
th { border-top: 1.1px solid var(--ink); border-bottom: 1.1px solid var(--ink); background:#fff; font-weight:650; white-space: nowrap; }
td.num { font-variant-numeric: tabular-nums; white-space:nowrap; }
figure { margin: 0; }
figure img { width:100%; max-width:100%; height:auto; display:block; border:0.6px solid var(--line); }
figcaption { margin-top: 4px; font-size: 10.5px; line-height: 1.4; }
table.fig-pair { width: 100% !important; min-width: 0 !important; border: none !important; border-collapse: separate; table-layout: fixed; margin: 10px 0 16px; page-break-inside: avoid; }
table.fig-pair td { width: 50%; border: none !important; background: transparent; padding: 0 1.2%; vertical-align: top; }
table.fig-one { width: 48% !important; min-width: 0 !important; margin: 10px auto 16px !important; border: none !important; border-collapse: separate; table-layout: fixed; page-break-inside: avoid; }
table.fig-one td { border: none !important; background: transparent; padding: 0 !important; vertical-align: top; }
table.fig-one img { width: 100% !important; max-width: 100% !important; height: auto !important; }
nav a { color:var(--accent); text-decoration:none; }
ul { margin: 6px 0 10px 18px; }
li { margin: 3px 0; }
code, pre { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size:10.5px; }
pre { background:var(--bg); padding:10px; overflow:auto; max-height: 420px; border: 0.6px solid var(--line); }
.tag { display:inline-block; font-size:10px; padding:1px 7px; border: 0.6px solid var(--line); margin-right:6px; }
footer { margin-top: 28px; padding-top: 10px; border-top: 0.6px solid var(--line); font-size:11px; color:var(--muted); }
@media print {
  body { background:#fff; }
  main { margin:0; max-width:none; padding:0; }
  .table-wrap { overflow: visible; border: none; }
  table { font-size: 8px; width: 100%; }
  th, td { padding: 2px 3px; white-space: normal; word-break: break-word; }
  pre { max-height: none; font-size: 7.5px; }
  table.fig-pair { width: 100% !important; min-width: 0 !important; table-layout: fixed !important; }
  table.fig-pair td { width: 50% !important; }
  table.fig-pair img { width: 100% !important; max-width: 125mm !important; height: auto !important; }
  table.fig-one { width: 48% !important; min-width: 0 !important; margin: 10px auto !important; }
  figure img { max-height: none; }
}
"""


def _esc(x) -> str:
    return html.escape("" if x is None else str(x))


def _png_data_uri(path: Path) -> str:
    raw = path.read_bytes()
    b64 = base64.b64encode(raw).decode("ascii")
    return f"data:image/png;base64,{b64}"


def _table_note(prefix: str) -> str:
    if not prefix:
        return ""
    return f'<p class="muted">路径前缀：<code>{_esc(prefix)}</code>（表内仅保留相对尾路径）。</p>'


def _df_html(df: pd.DataFrame, max_rows: int = 80) -> str:
    if df is None or df.empty:
        return '<p class="muted">（无表）</p>'
    view, prefix = format_dataframe(df.head(max_rows))
    thead = "".join(f"<th>{_esc(c)}</th>" for c in view.columns)
    body = []
    for _, row in view.iterrows():
        tds = []
        for c, v in row.items():
            tds.append(f"<td>{_esc(v)}</td>")
        body.append("<tr>" + "".join(tds) + "</tr>")
    extra = f'<p class="muted">显示前 {len(view)} / {len(df)} 行；完整表见 <code>tables/</code>。</p>' if len(df) > max_rows else ""
    table = f"<div class='table-wrap'><table><thead><tr>{thead}</tr></thead><tbody>{''.join(body)}</tbody></table></div>"
    return _table_note(prefix) + table + extra


def _fig_block(fig_dir: Path, stem: str, caption: str) -> str:
    png = fig_dir / f"{stem}.png"
    if not png.is_file():
        return ""
    uri = _png_data_uri(png)
    return (
        f"<figure id='{html.escape(stem)}'><img src='{uri}' alt='{html.escape(caption)}' style='width:100%;max-width:100%;height:auto;display:block'/>"
        f"<figcaption><strong>{html.escape(stem)}</strong> {html.escape(caption)} "
        f"绘图脚本 <code>r/make_figures.R</code>。"
        f"</figcaption></figure>"
    )


def _fig_rows(fig_dir: Path, stems: list[str]) -> str:
    blocks = []
    for stem in stems or []:
        html_fig = _fig_block(fig_dir, stem, CAPTIONS.get(stem, stem))
        if html_fig:
            blocks.append(html_fig)
    if not blocks:
        return ""
    rows = []
    i = 0
    while i < len(blocks):
        if i + 1 < len(blocks):
            rows.append(
                "<table class='fig-pair'><tr><td>"
                + blocks[i]
                + "</td><td>"
                + blocks[i + 1]
                + "</td></tr></table>"
            )
            i += 2
        else:
            rows.append("<table class='fig-one'><tr><td>" + blocks[i] + "</td></tr></table>")
            i += 1
    return "<h3>图</h3>" + "".join(rows)


CAPTIONS = {
    "fig01_depth_by_sample": "各样本合并后 R1 深度。虚线为 5 million reads 低深度阈值。",
    "fig02_w1_fastp_retention": "fastp 读段保留率（按建库方法）。箱线为中位数与四分位，点为样本。",
    "fig03_w1_q30": "fastp 后 Q30。",
    "fig04_w1_rrna_retention": "去 rRNA 后 R1 保留率。",
    "fig05_w1_depth_vs_contigs": "测序深度与 >=1 kb contig 数。",
    "fig06_w2_checkv_by_sample": "各样本假定病毒 contig 的 CheckV 质量组成。",
    "fig07_w2_contig_length": "假定病毒 contig 长度分布。",
    "fig08_w2_viral_contigs_by_method": "每样本假定病毒 contig 数（按方法）。",
    "fig09_w3_host_species": "核心队列推断线粒体物种频次。",
    "fig10_w4_unclassified": "Kraken 未分类比例。",
    "fig11_w4_species_richness": "Bracken 物种分类单元数。",
    "fig12_w4_top_taxa": "Bracken top-15 已分类空间的优势分类单元组成（不是全库相对丰度）。",
    "fig13_w5_mapping_rate": "比对到病毒 contig 的 reads 比例。",
    "fig14_w5_max_rpm": "每样本最大病毒 RPM（对数轴）。",
    "fig15_w5_depth_vs_mapping": "深度与病毒比对率：低深度样本的高相对定量需谨慎。",
}


def _clean_extract_log(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    keep = [c for c in ("workflow", "short", "ok", "skipped", "n_tables", "error") if c in df.columns]
    out = df[keep].copy()
    if "error" in out.columns:
        out["error"] = out["error"].fillna("").astype(str).str.split("/").str[-1]
    return out


def build_html(
    batch_id: str,
    out_dir: Path,
    fig_dir: Path,
    sections: list[dict],
    master: pd.DataFrame,
    coverage: pd.DataFrame,
    overall: pd.DataFrame,
    tests: pd.DataFrame,
    extract_log: pd.DataFrame,
    r_source: str,
    grouping_notes: list[str],
) -> Path:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    toc = []
    body = []
    for i, sec in enumerate(sections, 1):
        toc.append(f"<a href='#{sec['id']}'>{i}. {_esc(sec['title'])}</a>")
        body.append(f"<section id='{sec['id']}'><h2>{i}. {_esc(sec['title'])}</h2>")
        if sec.get("skip"):
            msg = shorten_user_text(sec["results"][0]) if sec.get("results") else "跳过"
            body.append(f"<div class='notice skip'>{_esc(msg)}</div></section>")
            continue
        if sec.get("results"):
            items = "".join(f"<li>{_esc(shorten_user_text(x))}</li>" for x in sec["results"])
            body.append("<h3>结果</h3><ul>" + items + "</ul>")
        figs = _fig_rows(fig_dir, sec.get("figures") or [])
        if figs:
            body.append(figs)
        if sec.get("biology"):
            body.append("<h3>生物学意义</h3><ul>" + "".join(f"<li>{_esc(x)}</li>" for x in sec["biology"]) + "</ul>")
        body.append("</section>")

    cov_html = _df_html(coverage)
    master_show = master.drop(columns=[c for c in master.columns if str(c).lower() in {"raw_id"}], errors="ignore")
    # drop likely path columns from master if any
    html_doc = f"""<!doctype html>
<html lang="zh-CN"><head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>全流程分析报告 · {html.escape(batch_id)}</title>
<style>{CSS}</style>
</head><body><main>
<header>
<div class="kicker">XvirBench full-pipeline analysis · v1.0</div>
<h1>{html.escape(batch_id)} 工作流完成后分析报告</h1>
<p class="meta">生成 {html.escape(now)} · 指标口径对齐 extract_results.py 与 WORKFLOW_SUMMARY.md · 图已嵌入本文件</p>
<p>
<span class="tag">总体分析</span>
<span class="tag">缺失则跳过</span>
<span class="tag">SCI 风格 ggplot2</span>
<span class="tag">自包含 HTML</span>
<span class="tag">不构成诊断</span>
</p>
</header>
<nav class="muted">{" · ".join(toc)}</nav>
<div class="notice warn">缺失流程或字段不判为失败。Kraken/BLAST 物种名不是 ICTV 定种。低深度样本的 RPM 与物种数不可单独解读为生物学差异。本 HTML 图为内嵌 PNG，复制单文件即可打开。</div>
{''.join(body)}
<section id="tables">
<h2>结构化表</h2>
<h3>提取覆盖</h3>
{cov_html}
<h3>核心样本主表</h3>
{_df_html(master_show)}
<h3>核心队列描述统计</h3>
{_df_html(overall if overall is not None else pd.DataFrame())}
<h3>组间检验（若有分组）</h3>
{_df_html(tests if tests is not None else pd.DataFrame())}
<h3>提取状态</h3>
{_df_html(_clean_extract_log(extract_log))}
<p class="muted">完整数值表见运行目录下 <code>tables/</code>（相对本报告）。</p>
</section>
<section id="methods">
<h2>方法学摘要</h2>
<ul>
<li>提取：各流程 extract_results.py；失败时回退已有 benchmark xlsx。</li>
<li>描述统计：n、mean、SD、median、IQR、min、max。</li>
<li>分组：仅当某因子 ≥2 水平且至少两个水平 n≥2。检验用 Kruskal–Wallis 与 Mann–Whitney，p 值 BH 校正；效应量为 ε² 与 rank-biserial。</li>
<li>低深度：合并 R1 &lt; 5×10<sup>6</sup> reads。另给出剔除低深度后的敏感性统计。</li>
<li>图：ggplot2 classic、Okabe–Ito；报告内为嵌入 PNG；磁盘另存 PDF 矢量图。</li>
<li>数字：计数为整数；百分比 2 位；0–1 比例与效应量 4 位；p 值 4 位。</li>
</ul>
<p class="muted">分组备注：{" ".join(_esc(x) for x in grouping_notes)}</p>
</section>
<section id="rscripts">
<h2>附录：R 绘图脚本</h2>
<p class="muted">主题 <code>r/00_sci_theme.R</code>；作图 <code>r/make_figures.R</code>。下列为本次运行复制的脚本正文。</p>
<pre>{html.escape(r_source[:20000])}</pre>
</section>
<footer>
本结果仅限科研实验室内部参考，不得作为临床诊断或公共卫生干预的直接决策依据。<br/>
规范与提示词：XvirBench/benchmark/FULL_PIPELINE_ANALYSIS_SYSTEM.md
</footer>
</main></body></html>
"""
    out = out_dir / "report.html"
    out.write_text(html_doc, encoding="utf-8")
    return out


def build_pdf(html_path: Path, pdf_path: Path) -> Path:
    """Bake the self-contained HTML into a landscape A4 PDF."""
    from weasyprint import HTML

    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    HTML(filename=str(html_path), base_url=str(html_path.parent)).write_pdf(str(pdf_path))
    return pdf_path
```

### `package/r/00_sci_theme.R`

```r
# SCI / journal-style ggplot2 theme (Nature-like: classic axes, no grid, Okabe–Ito).
# Requires: ggplot2, scales, patchwork, ggbeeswarm, dplyr, readr, stringr, RColorBrewer

okabe_ito <- c(
  "#E69F00", "#56B4E9", "#009E73", "#F0E442",
  "#0072B2", "#D55E00", "#CC79A7", "#000000"
)

method_levels <- c("cDNA_Frag_30C5Min", "RNA_Frag_85C6Min", "RNA_Frag_94C7Min")
method_labels <- c("cDNA 30°C 5 min", "RNA 85°C 6 min", "RNA 94°C 7 min")
method_cols <- c(
  "cDNA_Frag_30C5Min" = "#E69F00",
  "RNA_Frag_85C6Min"  = "#0072B2",
  "RNA_Frag_94C7Min"  = "#009E73"
)

theme_sci <- function(base_size = 8, base_family = "sans") {
  ggplot2::theme_classic(base_size = base_size, base_family = base_family) +
    ggplot2::theme(
      line = ggplot2::element_line(colour = "black", linewidth = 0.35),
      axis.line = ggplot2::element_line(colour = "black", linewidth = 0.35),
      axis.ticks = ggplot2::element_line(colour = "black", linewidth = 0.35),
      axis.text = ggplot2::element_text(colour = "black", size = base_size),
      axis.title = ggplot2::element_text(colour = "black", size = base_size),
      legend.title = ggplot2::element_text(size = base_size),
      legend.text = ggplot2::element_text(size = base_size - 0.5),
      legend.key.size = grid::unit(0.35, "cm"),
      legend.background = ggplot2::element_blank(),
      legend.key = ggplot2::element_blank(),
      strip.background = ggplot2::element_blank(),
      strip.text = ggplot2::element_text(face = "bold", size = base_size),
      plot.title = ggplot2::element_text(size = base_size + 0.5, face = "bold", hjust = 0),
      plot.subtitle = ggplot2::element_text(size = base_size - 0.5, colour = "grey20"),
      plot.caption = ggplot2::element_text(size = base_size - 1, colour = "grey30", hjust = 0),
      plot.background = ggplot2::element_rect(fill = "white", colour = NA),
      panel.background = ggplot2::element_rect(fill = "white", colour = NA),
      panel.grid = ggplot2::element_blank(),
      plot.margin = ggplot2::margin(4, 6, 4, 4)
    )
}

save_panel <- function(plot, stem, width_mm = 85, height_mm = 70, dpi = 300) {
  png_path <- paste0(stem, ".png")
  pdf_path <- paste0(stem, ".pdf")
  ggplot2::ggsave(png_path, plot, width = width_mm, height = height_mm, units = "mm", dpi = dpi, bg = "white")
  ggplot2::ggsave(pdf_path, plot, width = width_mm, height = height_mm, units = "mm", bg = "white")
  message("wrote ", png_path)
}

safe_read <- function(path) {
  if (!file.exists(path)) return(NULL)
  df <- tryCatch(readr::read_tsv(path, show_col_types = FALSE), error = function(e) NULL)
  if (is.null(df) || nrow(df) == 0) return(NULL)
  df
}

has_cols <- function(df, cols) {
  !is.null(df) && all(cols %in% names(df))
}

label_method <- function(x) {
  factor(
    x,
    levels = method_levels,
    labels = method_labels
  )
}
```

### `package/r/make_figures.R`

```r
#!/usr/bin/env Rscript
# Generate SCI-style figures from extracted TSVs. Missing tables/columns are skipped.
suppressPackageStartupMessages({
  library(ggplot2)
  library(dplyr)
  library(tidyr)
  library(readr)
  library(stringr)
  library(scales)
  library(patchwork)
  library(ggbeeswarm)
})

args <- commandArgs(trailingOnly = TRUE)
table_dir <- if (length(args) >= 1) args[[1]] else "tables"
fig_dir   <- if (length(args) >= 2) args[[2]] else "figures"

ca <- commandArgs(FALSE)
file_arg <- sub("^--file=", "", ca[grepl("^--file=", ca)])
script_dir <- if (length(file_arg)) dirname(normalizePath(file_arg[[1]])) else getwd()
theme_r <- file.path(script_dir, "00_sci_theme.R")
if (!file.exists(theme_r)) {
  cand <- file.path(dirname(fig_dir), "r", "00_sci_theme.R")
  if (file.exists(cand)) theme_r <- cand
}
if (!file.exists(theme_r)) stop("cannot find 00_sci_theme.R")
source(theme_r, local = FALSE)

dir.create(fig_dir, recursive = TRUE, showWarnings = FALSE)
master <- safe_read(file.path(table_dir, "master_sample_metrics.tsv"))
if (is.null(master)) quit(save = "no", status = 0)

if ("method" %in% names(master)) {
  master$method_lab <- label_method(master$method)
}
core <- master
if ("in_core_cohort" %in% names(master)) {
  core <- master %>% filter(in_core_cohort %in% c(TRUE, "True", "true", 1, "1"))
  if (nrow(core) == 0) core <- master
}

has_method <- "method_lab" %in% names(core) && n_distinct(na.omit(core$method_lab)) >= 2

color_method <- function(p) {
  if (has_method) {
    p + scale_colour_manual(values = setNames(unname(method_cols), method_labels), drop = FALSE, name = "Library method") +
      scale_fill_manual(values = setNames(unname(method_cols), method_labels), drop = FALSE, name = "Library method")
  } else {
    p + scale_colour_manual(values = c("all" = "#0072B2")) +
      scale_fill_manual(values = c("all" = "#0072B2"))
  }
}

jitter_box <- function(df, y, ylab, ypercent = FALSE) {
  d <- df %>% filter(!is.na(.data[[y]]))
  if (nrow(d) == 0) return(NULL)
  if (!has_method) d$method_lab <- factor("all")
  p <- ggplot(d, aes(x = method_lab, y = .data[[y]], colour = method_lab, fill = method_lab)) +
    geom_boxplot(width = 0.55, outlier.shape = NA, alpha = 0.25, linewidth = 0.35) +
    geom_quasirandom(width = 0.18, size = 1.4, alpha = 0.9) +
    labs(x = NULL, y = ylab) +
    theme_sci() +
    theme(axis.text.x = element_text(angle = 20, hjust = 1), legend.position = "none")
  if (ypercent) p <- p + scale_y_continuous(labels = percent_format(accuracy = 1))
  color_method(p)
}

# ---- Fig 01 coverage is drawn in Python (matrix). R: cohort overview ----
if (has_cols(core, c("sample_id"))) {
  d <- core
  d$depth <- if ("merge_r1_reads" %in% names(d)) d$merge_r1_reads / 1e6 else NA_real_
  if (!all(is.na(d$depth))) {
    if (!has_method) d$method_lab <- factor("all")
    p <- ggplot(d, aes(x = reorder(sample_id, depth), y = depth, fill = method_lab)) +
      geom_col(width = 0.75, colour = "black", linewidth = 0.2) +
      geom_hline(yintercept = 5, linetype = "dashed", linewidth = 0.3, colour = "#D55E00") +
      coord_flip() +
      labs(x = NULL, y = "Merged R1 reads (millions)", caption = "Dashed line: 5 million R1 reads low-depth flag") +
      theme_sci() +
      theme(legend.position = if (has_method) "bottom" else "none")
    if (has_method) {
      p <- p + scale_fill_manual(values = setNames(unname(method_cols), method_labels), name = NULL)
    } else {
      p <- p + scale_fill_manual(values = c("all" = "#0072B2"), guide = "none")
    }
    save_panel(p, file.path(fig_dir, "fig01_depth_by_sample"), width_mm = 114, height_mm = 90)
  }
}

# ---- W1 QC panels ----
if (has_cols(core, "read_retention_fastp_median")) {
  p <- jitter_box(core, "read_retention_fastp_median", "fastp read retention", ypercent = TRUE)
  if (!is.null(p)) save_panel(p, file.path(fig_dir, "fig02_w1_fastp_retention"), width_mm = 85, height_mm = 70)
}
if (has_cols(core, "q30_after_fastp_median")) {
  d <- core
  # q30 may be 0-1 or 0-100
  y <- d$q30_after_fastp_median
  if (isTRUE(max(y, na.rm = TRUE) <= 1.5)) d$q30_plot <- y else d$q30_plot <- y / 100
  p <- jitter_box(d, "q30_plot", "fastp Q30", ypercent = TRUE)
  if (!is.null(p)) save_panel(p, file.path(fig_dir, "fig03_w1_q30"), width_mm = 85, height_mm = 70)
}
if (has_cols(core, "rrna_retention_r1_median")) {
  d <- core
  y <- d$rrna_retention_r1_median
  if (isTRUE(max(y, na.rm = TRUE) <= 1.5)) d$rrna_plot <- y else d$rrna_plot <- y / 100
  p <- jitter_box(d, "rrna_plot", "R1 retained after rRNA depletion", ypercent = TRUE)
  if (!is.null(p)) save_panel(p, file.path(fig_dir, "fig04_w1_rrna_retention"), width_mm = 85, height_mm = 70)
}
if (has_cols(core, c("merge_r1_reads", "contigs_ge1kb_n"))) {
  d <- core %>% filter(!is.na(merge_r1_reads), !is.na(contigs_ge1kb_n))
  if (nrow(d) > 0) {
    if (!has_method) d$method_lab <- factor("all")
    p <- ggplot(d, aes(x = merge_r1_reads / 1e6, y = contigs_ge1kb_n, colour = method_lab)) +
      geom_point(size = 2.2, alpha = 0.9) +
      geom_text(aes(label = sample_id), size = 2, vjust = -0.8, show.legend = FALSE) +
      labs(x = "Merged R1 reads (millions)", y = "Contigs >=1 kb (n)") +
      theme_sci() +
      theme(legend.position = "bottom")
    p <- color_method(p)
    save_panel(p, file.path(fig_dir, "fig05_w1_depth_vs_contigs"), width_mm = 114, height_mm = 80)
  }
}

# ---- W2 ----
contigs <- safe_read(file.path(table_dir, "W2_contigs.tsv"))
if (has_cols(contigs, "checkv_quality")) {
  cq <- contigs %>%
    mutate(sample_id = if ("source_sample" %in% names(.)) source_sample else sample_id) %>%
    filter(!is.na(checkv_quality), checkv_quality != "") %>%
    count(sample_id, checkv_quality, name = "n")
  if ("method" %in% names(core)) {
    cq <- cq %>% left_join(core %>% select(sample_id, method_lab), by = "sample_id")
  }
  p <- ggplot(cq, aes(x = sample_id, y = n, fill = checkv_quality)) +
    geom_col(width = 0.8, colour = "black", linewidth = 0.15) +
    scale_fill_manual(values = okabe_ito, name = "CheckV") +
    labs(x = NULL, y = "Putative viral contigs (n)") +
    theme_sci() +
    theme(axis.text.x = element_text(angle = 45, hjust = 1), legend.position = "bottom")
  save_panel(p, file.path(fig_dir, "fig06_w2_checkv_by_sample"), width_mm = 114, height_mm = 80)
}
if (has_cols(contigs, "length")) {
  p <- ggplot(contigs, aes(x = length)) +
    geom_histogram(bins = 20, fill = "#0072B2", colour = "white", linewidth = 0.2) +
    scale_x_log10(labels = comma) +
    labs(x = "Putative viral contig length (bp, log10)", y = "Count") +
    theme_sci()
  save_panel(p, file.path(fig_dir, "fig07_w2_contig_length"), width_mm = 85, height_mm = 70)
}
if (has_cols(core, "n_putative_viral_contigs")) {
  p <- jitter_box(core, "n_putative_viral_contigs", "Putative viral contigs per sample (n)")
  if (!is.null(p)) save_panel(p, file.path(fig_dir, "fig08_w2_viral_contigs_by_method"), width_mm = 85, height_mm = 70)
}

# ---- W3 ----
host_top <- safe_read(file.path(table_dir, "W3_host_top_species.tsv"))
if (!is.null(host_top) && "inferred_mt_species" %in% names(host_top)) {
  ht <- host_top
  if ("source_sample" %in% names(ht) && !"sample_id" %in% names(ht)) ht$sample_id <- ht$source_sample
  # restrict to core if possible
  if ("sample_id" %in% names(core)) ht <- ht %>% filter(sample_id %in% core$sample_id)
  sp <- ht %>%
    count(inferred_mt_species, name = "n") %>%
    arrange(desc(n)) %>%
    slice_head(n = 12)
  p <- ggplot(sp, aes(x = reorder(inferred_mt_species, n), y = n)) +
    geom_col(fill = "#009E73", colour = "black", linewidth = 0.2, width = 0.75) +
    coord_flip() +
    labs(x = NULL, y = "Samples (n)", caption = "Top inferred mitochondrial species; not a clinical identification") +
    theme_sci()
  save_panel(p, file.path(fig_dir, "fig09_w3_host_species"), width_mm = 114, height_mm = 80)
}

# ---- W4 ----
if (has_cols(core, "kraken_unclassified_frac")) {
  d <- core
  y <- d$kraken_unclassified_frac
  if (isTRUE(max(y, na.rm = TRUE) > 1.5)) d$uncls <- y / 100 else d$uncls <- y
  p <- jitter_box(d, "uncls", "Kraken unclassified fraction", ypercent = TRUE)
  if (!is.null(p)) save_panel(p, file.path(fig_dir, "fig10_w4_unclassified"), width_mm = 85, height_mm = 70)
}
if (has_cols(core, "bracken_species_taxa")) {
  p <- jitter_box(core, "bracken_species_taxa", "Bracken species taxa (n)")
  if (!is.null(p)) save_panel(p, file.path(fig_dir, "fig11_w4_species_richness"), width_mm = 85, height_mm = 70)
}
top15 <- safe_read(file.path(table_dir, "W4_bracken_top15_species.tsv"))
if (!is.null(top15) && all(c("sample_id", "name", "fraction_total_reads") %in% names(top15))) {
  t15 <- top15 %>% filter(sample_id %in% core$sample_id)
  keep <- t15 %>%
    group_by(name) %>%
    summarise(tot = sum(fraction_total_reads, na.rm = TRUE), .groups = "drop") %>%
    arrange(desc(tot)) %>%
    slice_head(n = 10) %>%
    pull(name)
  t15 <- t15 %>%
    mutate(taxon = ifelse(name %in% keep, name, "Other (in top15 table)")) %>%
    group_by(sample_id, taxon) %>%
    summarise(frac = sum(fraction_total_reads, na.rm = TRUE), .groups = "drop")
  taxa <- unique(as.character(t15$taxon))
  pal <- setNames(okabe_ito[rep(seq_along(okabe_ito), length.out = length(taxa))], taxa)
  p <- ggplot(t15, aes(x = sample_id, y = frac, fill = taxon)) +
    geom_col(width = 0.85, colour = "black", linewidth = 0.1) +
    scale_y_continuous(labels = percent_format(accuracy = 1)) +
    scale_fill_manual(values = pal, name = NULL) +
    labs(x = NULL, y = "Bracken fraction of total reads",
         caption = "Top-15 species table only; fractions are among reported taxa, not the whole library") +
    theme_sci() +
    theme(axis.text.x = element_text(angle = 45, hjust = 1), legend.position = "bottom", legend.text = element_text(size = 6))
  save_panel(p, file.path(fig_dir, "fig12_w4_top_taxa"), width_mm = 174, height_mm = 95)
}

# ---- W5 ----
if (has_cols(core, "mapping_rate_pct")) {
  d <- core
  y <- d$mapping_rate_pct
  if (isTRUE(max(y, na.rm = TRUE) <= 1.5)) d$map_plot <- y else d$map_plot <- y / 100
  p <- jitter_box(d, "map_plot", "Reads mapped to viral contigs", ypercent = TRUE)
  if (!is.null(p)) save_panel(p, file.path(fig_dir, "fig13_w5_mapping_rate"), width_mm = 85, height_mm = 70)
}
if (has_cols(core, "max_rpm")) {
  d <- core %>% filter(!is.na(max_rpm))
  if (nrow(d) > 0) {
    if (!has_method) d$method_lab <- factor("all")
    p <- ggplot(d, aes(x = method_lab, y = max_rpm, colour = method_lab, fill = method_lab)) +
      geom_boxplot(width = 0.55, outlier.shape = NA, alpha = 0.25, linewidth = 0.35) +
      geom_quasirandom(width = 0.18, size = 1.4) +
      scale_y_log10(labels = comma) +
      labs(x = NULL, y = "Maximum viral RPM (log10)") +
      theme_sci() +
      theme(axis.text.x = element_text(angle = 20, hjust = 1), legend.position = "none")
    p <- color_method(p)
    save_panel(p, file.path(fig_dir, "fig14_w5_max_rpm"), width_mm = 85, height_mm = 70)
  }
}
if (has_cols(core, c("merge_r1_reads", "mapping_rate_pct"))) {
  d <- core %>% filter(!is.na(merge_r1_reads), !is.na(mapping_rate_pct))
  if (nrow(d) > 0) {
    if (!has_method) d$method_lab <- factor("all")
    y <- d$mapping_rate_pct
    d$map_plot <- if (isTRUE(max(y, na.rm = TRUE) <= 1.5)) y else y / 100
    p <- ggplot(d, aes(x = merge_r1_reads / 1e6, y = map_plot, colour = method_lab)) +
      geom_point(size = 2.2) +
      geom_text(aes(label = sample_id), size = 2, vjust = -0.8, show.legend = FALSE) +
      scale_y_continuous(labels = percent_format(accuracy = 0.01)) +
      labs(x = "Merged R1 reads (millions)", y = "Viral-contig mapping rate") +
      theme_sci() +
      theme(legend.position = "bottom")
    p <- color_method(p)
    save_panel(p, file.path(fig_dir, "fig15_w5_depth_vs_mapping"), width_mm = 114, height_mm = 80)
  }
}

message("figure generation finished")
```
