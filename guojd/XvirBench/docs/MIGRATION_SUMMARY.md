# XvirBench 项目总结（迁站用）

编制：2026-08-26  
仓库：`/data/user/guojindan/Projects/XvirBench`  
关联执行层：`/data/user/guojindan/Projects/Workflows`（W1–W7 Snakemake，**不在本仓库内**）

XvirBench 是宏转录组的**比较与编排层**：不跑重计算，而是登记样本、软链流程结果、抽取统一指标（harmonized）、做分组比较。迁到新服务器时，要同时带上（1）本仓库代码与批次元数据，（2）各批次引用的原始/清洗 FASTQ，（3）若要复现计算，还要 Workflows 输出目录。

---

## 1. 项目在测什么

统一问题：**不同建库 / 试剂盒 / rRNA 策略，对宏转录组上游质量和下游病毒/微生物检出差在哪。**

| 流程 | 内容 | 在本项目中的角色 |
| --- | --- | --- |
| W1 | 质控、去 rRNA、多样本 run 合并、Megahit 组装 | 上游 QC + contig |
| W2 | 病毒鉴定（HMM / CheckV / BLAST） | 病毒检出 |
| W3 | 宿主鉴定（EukaMarker） | 宿主核对 |
| W4 | Kraken2 + Bracken | 微生物背景 |
| W5 | 病毒 RPM 定量 | 丰度比较 |
| W6 | 病毒注释 | 主批次未跑 |
| W7 | 宿主 STAR/Picard 建库质量 | 打断方法学主终点 |

当前三个实际批次，对应三条独立实验：

1. **建库打断方法**（Vazyme cDNA 酶切 vs RNA 热打断）
2. **蚊虫试剂盒 + 是否去 rRNA**（翌圣 vs 诺唯赞）
3. **大鼠 rRNA 去除方法**（LNA vs Control；RNaseH 目录为空）

---

## 2. 批次一览

| 批次 | 科学问题 | 样本 | 流程进度 | 迁站优先级 |
| --- | --- | --- | --- | --- |
| `vazyme_fragment_test` | 三种打断 × 三宿主 | 60 生物学样本（v61–v120），240 run | **主批次**：W1–W5、W7 均 60/60；harmonized + HTML 已完成 | 代码 + 指标 + 报告；FASTQ/计算结果在仓外 |
| `rRNA_test_mosquito` | 翌圣未去 rRNA vs 诺唯赞未去 / 去 rRNA | 48 样品 × 3 方法 = 144 文库 | 已建软链与 subsample；有 10/48 样本 HTML 评估 | 软链指向海南 + rRNA_test |
| `X_wangwen_rat` | 大鼠 LNA 去 rRNA vs Control | 27 大鼠（SC 10 + NM 17） | LNA 已有 W1 / W2 / W4 / MetaPhlAn；Control 仅 Rawdata；RNaseH 空 | 软链指向 `X_project`（对端已有） |
| `GZCDC_rat` | 占位 | 空目录 | 无 | 可忽略 |

跨批次比较目录 `comparisons/` 目前只有约定，尚未启用。

---

## 3. 涉及的数据（迁站时要对齐的路径）

XvirBench **几乎不存 FASTQ 实体**，`batches/*/…/Rawdata/*.fq.gz` 与 `workflow_results/` 都是**绝对路径软链**。迁站后必须改根路径或重链，表见 `Hainan_rsync搬迁/manifests/xvirbench_rawdata_association.tsv`（312 对）。

### 3.1 `vazyme_fragment_test`（建库打断）

| 类别 | 现网路径 | 说明 |
| --- | --- | --- |
| 样本表 | `Projects/vazyme/sampleinfo.tsv`（软链到批次 `cohorts/`） | 60 行：host × method |
| 清洗 FASTQ | `/data/NAS/users/pengxinyue/fragment_test_vazyme_2603/cleandata` | link_map 中的 original；**不在 Rawdata** |
| 原始 FASTQ | `/data/output_data/pxy/V350399508/` | manifest 中 `raw_fq_root` |
| W1 输出 | `/data/user/pengxinyue/Workflows/workflow1_upstream/example` | 60 样本 cleanreads + assembly |
| W3/W4 等 | `Projects/Workflows/benchmark/test/runs/pxy_V350399508` | `legacy_run_dir` |
| W2/W5/W7 | `Projects/vazyme/fragmentation_test` | 按宿主分目录 |
| 本仓库内 | `batches/vazyme_fragment_test/{harmonized,analysis,manifest.yaml}` | 可随 git 走的轻量产物 |

实验分组：

- **method**：`cDNA_Frag_30C5Min`（24）、`RNA_Frag_85C6Min`（24）、`RNA_Frag_94C7Min`（12）
- **host**：rat 30、tick 24、mosquito 6（蚊仅 cDNA / RNA_85）
- 测序：BGI PE150，芯片 **V350399508**
- 比较原则：method 比较以**宿主内分层**为主；W7 为 PRIMARY endpoint
- 已知 QC：部分样本 R1 < 5M reads（v63、v73、v88–v90）

### 3.2 `rRNA_test_mosquito`（试剂盒 / 去 rRNA）

48 个海南现场样品（库蚊 46、骚扰阿蚊 1、蚋 1），每个样品三种文库：

| 方法 | 试剂 | 原文位置 | 本次硬盘 |
| --- | --- | --- | --- |
| `Yeasen_noDeplete` | 翌圣，未去 rRNA | `Rawdata/Hainan/` 四条 lane：084、083、980、918 | **随海南盘迁移** |
| `Vazyme_noDeplete` | 诺唯赞，未去 rRNA | `Rawdata/rRNA_test/FP270013120_L01` | 只关联，不随盘 |
| `Vazyme_rRNADeplete` | 诺唯赞，去 rRNA | 同上芯片另一套 barcode | 只关联，不随盘 |

软链落点：

```
batches/rRNA_test_mosquito/<method>/Rawdata/<SN>_1.fq.gz
  →  NAS 原文
```

同目录还有 `subsample_50k/`（抽 50k reads 试跑）和 docs 里的评估 HTML（10 样本 / 48 样本）。`moredata_sampleinfo.tsv` 另记了同芯片乌干达蝙蝠加测，不是 48 蚊主队列。

### 3.3 `X_wangwen_rat`（大鼠 LNA）

| 类别 | 路径 | 说明 |
| --- | --- | --- |
| LNA 原文 | `Rawdata/X_project/X_wangwen/L01–L04` | 芯片 **V350399532**，每样本 4 lane；**对端已有，不拷贝** |
| 软链 | `…/LNA_method/Rawdata/<SN>_L0x_{1,2}.fq.gz` | 108 对；**NM_L5 / UDB-23 四 lane 缺失** |
| Control | `…/Control/Rawdata/` | 27 对；原文实际是 LNA 上游 **merge 后的 cleanreads**，不是第二套 raw |
| RNaseH | `…/RNaseH_method/` | 空，未开展 |
| 计算 | `LNA_method/workflow_results/` | W1、W2（2026db）、W4、workflow8 MetaPhlAn |

27 只大鼠：SC 10 + NM 17。LNA 侧 `harmonized/workflow1` 与 `analysis/w1_qc_rat` 已有；尚未做成 vazyme 那种全流程 HTML。

另：`LNA_method/Upstream/rawfile.txt` 还写过 `/data/Rawdata/X_project/X2_wangwen_failed/…`，是失败芯片路径，不要和 `X_wangwen/L01–L04` 混用。

### 3.4 本仓库内可随项目走的内容

- `docs/`：设计、W1–W7 指标字典、W1 QC 可移植包
- `scripts/`：`extract_metrics.py`、分组分析、W1 QC 报告
- `batches/*/harmonized/`、`analysis/report.html`（vazyme 已可离线打开）
- `batches/*/docs/rawdata_link_map.tsv`：原文 ↔ 软链对照
- 软链本身迁过去会断，需在新机跑 `setup_batch_links.sh` / `relink_xvirbench.py`

**不要指望只拷 XvirBench 目录就能重跑分析**：大文件都在 Workflows、vazyme、pengxinyue、NAS Rawdata。

---

## 4. 主要测试内容（按科学问题）

### 4.1 建库打断 Benchmark（主验证闭环）

**问**：cDNA 30°C 酶切 vs RNA 85°C / 94°C 热打断，对宿主 RNA-seq 质量（W7）和病毒/微生物检出（W2/W4/W5）差多少？

**设计**：60 样本，method × host；分析在宿主内做，避免物种混杂。

**已交付**：

- `batches/vazyme_fragment_test/analysis/report.html`
- `harmonized/workflow1` … `workflow7`
- `docs/vazyme_benchmark_metrics.xlsx`
- 与 `vazyme/fragmentation_test/analysis/rat/` 的 W7 数值交叉核对过

这是框架「登记 → 执行 → 抽取 → 比较」的完整样板。

### 4.2 蚊虫 rRNA / 试剂盒评估

**问**：翌圣未去 rRNA、诺唯赞未去 rRNA、诺唯赞去 rRNA，对同一批蚊虫样品的数据量与下游信号差多少？

**设计**：同一 48 个样品（HNSS-*）三套文库；Yeasen 走海南生产 lane，Vazyme 走 `rRNA_test` 加测芯片。

**已有**：144 对软链齐、`rawdata_link_map.tsv`、50k 抽平、docs 内 HTML 评估稿。全流程 W1–W7 尚未按 vazyme 批次那样闭环。

### 4.3 大鼠 LNA 去 rRNA

**问**：LNA 方法相对 Control（合并后的 clean reads）在大鼠宏转录组上的效果。

**设计**：27 样本 × 4 lane；NM_L5 原文缺失。RNaseH 预留未做。

**已有**：LNA 上游 + 病毒鉴定 + Kraken + MetaPhlAn；W1 QC 大鼠图。Control 只挂了数据，未对打全流程。

---

## 5. 新服务器建议带什么

| 优先级 | 带什么 | 用途 |
| --- | --- | --- |
| 必带 | XvirBench git（含 harmonized、report.html、link_map） | 看结果、改路径、继续抽指标 |
| 必带 | 海南 Yeasen 原文（随硬盘） | 蚊虫批次 Yeasen 臂 |
| 对端已有 | `Rawdata/X_project/X_wangwen` | 大鼠 LNA；不要重复拷 |
| 需要复现蚊 Vazyme 臂时 | `Rawdata/rRNA_test/FP270013120_L01` | 与海南样品配对 |
| 需要复现打断实验时 | pengxinyue cleandata + `Projects/vazyme` + `Workflows/.../pxy_V350399508` | 主批次计算依赖 |
| 需要重跑流程时 | `Projects/Workflows`、软件 `softwares/xvirmin`、conda `metatrans_compare` | 执行层 |

到新机后：

```bash
# 1. 代码放到 $NEW_XVIR
# 2. Rawdata 按相对路径就位（Hainan / 已有 X_project / 可选 rRNA_test）
python3 /path/to/Hainan_rsync搬迁/scripts/relink_xvirbench.py \
  --new-raw $NEW_RAW --new-xvir $NEW_XVIR --run

# 3. vazyme 计算软链
bash $NEW_XVIR/batches/vazyme_fragment_test/scripts/setup_batch_links.sh
```

`relink` 只处理 FASTQ 软链。vazyme 的 `workflow_results` 仍指向 pengxinyue / Workflows 绝对路径，那些树若也迁了，要改 `manifest.yaml` 里的 `legacy_*` 并重跑 `setup_batch_links.sh`。

---

## 6. 一句话对照

- **XvirBench**：指标框架 + 三个实验批次的元数据/报告。  
- **数据实体**：海南（翌圣蚊）、rRNA_test（诺唯赞蚊）、X_project（大鼠 LNA，对端已有）、pengxinyue/vazyme/Workflows（打断实验计算）。  
- **测完且可展示**：打断方法学 60 样本 W1–W5/W7。  
- **数据已挂、分析进行中**：蚊 144 文库、大鼠 27 样本 LNA。  
