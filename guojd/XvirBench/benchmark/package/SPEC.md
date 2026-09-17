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

