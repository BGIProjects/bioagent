# XvirBench Harmonized 指标参考（vazyme_fragment_test）

> 生成日期：2026-06-24  
> 示例批次：`vazyme_fragment_test`  
> 指标字典：[WORKFLOW_SUMMARY.md](../../Workflows/docs/WORKFLOW_SUMMARY.md)  
> Excel 对照：[vazyme_benchmark_metrics.xlsx](vazyme_benchmark_metrics.xlsx)  
> harmonized 路径：`batches/vazyme_fragment_test/harmonized/workflowN/`

---

## 1. 项目摘要

| 项目 | 值 |
| --- | --- |
| 批次 ID | `vazyme_fragment_test` |
| 抽取命令 | `python3 scripts/extract_metrics.py --batch-id vazyme_fragment_test --all` |

### 1.1 流程完成状态

| Workflow | harmonized 目录 | 状态 | 完成样本 | 输出表数 |
| --- | --- | --- | --- | --- |
| W1 | `workflow1/` | ✅ 已完成 | 60 | 3 |
| W2 | `workflow2/` | ✅ 已完成 | 60 | 3 |
| W3 | `workflow3/` | ✅ 已完成 | 60 | 2 |
| W4 | `workflow4/` | ✅ 已完成 | 60 | 2 |
| W5 | `workflow5/` | ✅ 已完成 | 60 | 2 |
| W6 | `workflow6/` | ⏸ 未运行 | — | 0 |
| W7 | `workflow7/` | ✅ 已完成 | 60 | 2 |

### 1.2 与 Excel 交付表对应关系

| Excel sheet | harmonized 对应 |
| --- | --- |
| `03_主指标表` | 各 workflow sample 表 join |
| `W1_上游QC` | `workflow1/qc_upstream_sample.tsv` |
| `W2_病毒鉴定` | `workflow2/virus_identification_sample.tsv` |
| `W2_病毒contigs` | `workflow2/virus_identification_contigs.tsv` |
| `W3_宿主鉴定` | `workflow3/host_identification_contig.tsv` |
| `W4_Kraken_Bracken` | `workflow4/microbiome_bracken_sample.tsv` |
| `W5_病毒定量` | `workflow5/virus_quantification_sample.tsv` |
| `W5_RPM明细` | `workflow5/virus_quantification_rpm.tsv` |
| `W7_建库benchmark` | `workflow7/fragmentation_benchmark.tsv` |

---

## 2. W1 上游 QC 与组装

**目录**：`batches/vazyme_fragment_test/harmonized/workflow1/`

### 输出文件

| 文件 | 粒度 | 行数 |
| --- | --- | --- |
| `qc_upstream_run.tsv` | run | 240（240 run（60 样本 × 4 lane）） |
| `qc_upstream_sample.tsv` | sample | 60（60 样本） |
| `qc_upstream_summary.tsv` | sample | 60（60 样本（精简汇总）） |

### 字段说明

#### `qc_upstream_run.tsv`

| 列名 | metric_id | 指标含义 | 粒度 | 本批次数值范围 |
| --- | --- | --- | --- | --- |
| `batch_id` | — | XvirBench 批次 ID | run | — |
| `run_id` | — | 测序 run ID（lane 级） | run | 示例: 100_1, 100_2, 100_3 |
| `sample_id` | — | 生物学样本 ID（v61–v120） | run | 示例: v100, v101, v102 |
| `reads_before` | W1-R01 | 原始 reads 数（过滤前） | run | min=4.309e+05, median=1.193e+07, max=2.363e+07 (n=240) |
| `bases_before` | W1-R02 | 原始碱基数（过滤前） | run | min=6.463e+07, median=1.789e+09, max=3.545e+09 (n=240) |
| `q20_before` | — | 原始 Q20 比例（fastp before_filtering） | run | min=0.9094, median=0.9641, max=0.9759 (n=240) |
| `q30_before` | W1-R04 | 原始 Q30 比例 | run | min=0.8389, median=0.9216, max=0.9409 (n=240) |
| `gc_before` | — | 原始 GC 含量 | run | min=0.4762, median=0.5119, max=0.5945 (n=240) |
| `reads_after_fastp` | W1-R07 | fastp 后 reads 数 | run | min=4.19e+05, median=1.08e+07, max=1.927e+07 (n=240) |
| `bases_after_fastp` | W1-R08 | fastp 后碱基数 | run | min=5.536e+07, median=1.465e+09, max=2.689e+09 (n=240) |
| `q20_after_fastp` | — | fastp 后 Q20 比例 | run | min=0.9245, median=0.9712, max=0.9786 (n=240) |
| `q30_after_fastp` | W1-R09 | fastp 后 Q30 比例 | run | min=0.8579, median=0.9302, max=0.9486 (n=240) |
| `gc_after_fastp` | — | fastp 后 GC 含量 | run | min=0.4733, median=0.5133, max=0.5991 (n=240) |
| `read_retention_fastp` | — | fastp 读段保留率（after/before reads） | run | min=0.587, median=0.9415, max=0.9881 (n=240) |
| `passed_filter_reads` | W1-R10 | 通过过滤 reads 数 | run | min=4.197e+05, median=1.169e+07, max=2.329e+07 (n=240) |
| `low_quality_reads` | W1-R11 | 低质量/过短/低复杂度剔除数 | run | min=1182, median=9536, max=1.996e+04 (n=240) |
| `too_short_reads` | — | 过短 reads 剔除数 | run | min=9460, median=9.005e+04, max=2.241e+06 (n=240) |
| `adapter_trimmed_reads` | W1-R13 | 接头修剪 reads 数 | run | min=1.576e+05, median=3.464e+06, max=8.78e+06 (n=240) |
| `duplication_rate` | W1-R12 | 重复率 | run | min=0.0006659, median=0.03953, max=0.3045 (n=240) |
| `fastp_r1_reads` | W1-R14 | fastp 后 R1 reads（seqkit） | run | min=2.095e+05, median=5.401e+06, max=9.636e+06 (n=240) |
| `fastp_r1_bases` | — | — | run | min=2.759e+07, median=7.321e+08, max=1.343e+09 (n=240) |
| `fastp_r1_avg_len` | — | — | run | min=119.2, median=137.4, max=146.3 (n=240) |
| `fastp_r2_reads` | — | — | run | min=2.095e+05, median=5.401e+06, max=9.636e+06 (n=240) |
| `fastp_r2_bases` | — | — | run | min=2.777e+07, median=7.329e+08, max=1.345e+09 (n=240) |
| `fastp_r2_avg_len` | — | — | run | min=119.8, median=137.7, max=146.4 (n=240) |
| `clean_r1_reads` | W1-R15 | 去 rRNA 后 R1 reads | run | min=1.801e+05, median=4.598e+06, max=9.022e+06 (n=240) |
| `clean_r1_bases` | W1-R16 | 去 rRNA 后 R1 碱基 | run | min=2.438e+07, median=6.412e+08, max=1.201e+09 (n=240) |
| `clean_r1_avg_len` | — | — | run | min=119.4, median=138.6, max=146.7 (n=240) |
| `clean_r2_reads` | — | — | run | min=1.801e+05, median=4.598e+06, max=9.022e+06 (n=240) |
| `clean_r2_bases` | — | — | run | min=2.449e+07, median=6.418e+08, max=1.203e+09 (n=240) |
| `clean_r2_avg_len` | — | — | run | min=120, median=139.1, max=146.8 (n=240) |
| `rrna_retention_r1` | W1-R17 | 去 rRNA 保留率 | run | min=0.5006, median=0.8859, max=0.9841 (n=240) |
| `rrna_retention_r2` | — | R2 去 rRNA 保留率 | run | min=0.5006, median=0.8859, max=0.9841 (n=240) |
| `fastp_json_exists` | — | fastp JSON 是否存在（QC 门禁） | run | 示例: True |
| `cleanreads_stat_exists` | — | clean reads stat 文件是否存在 | run | 示例: True |
| `global_sample_id` | — | 跨批次全局样本 ID（batch_id__sample_id） | run | — |
| `extracted_at` | — | 指标抽取 UTC 时间戳 | run | — |

#### `qc_upstream_sample.tsv`

| 列名 | metric_id | 指标含义 | 粒度 | 本批次数值范围 |
| --- | --- | --- | --- | --- |
| `batch_id` | — | XvirBench 批次 ID | sample | — |
| `sample_id` | — | 生物学样本 ID（v61–v120） | sample | 示例: v100, v101, v102 |
| `n_runs` | — | 该样本合并的 sequencing run 数（通常 4） | sample | min=4, median=4, max=4 (n=60) |
| `run_ids` | — | 合并的 run ID 列表 | sample | — |
| `merge_r1_reads` | W1-R18 | 合并后 R1 reads | sample | min=7.902e+05, median=1.831e+07, max=3.423e+07 (n=60) |
| `merge_r1_bases` | — | 合并后 R1 碱基数 | sample | min=1.088e+08, median=2.562e+09, max=4.554e+09 (n=60) |
| `merge_r1_q30_pct` | W1-R09 | fastp 后 Q30 比例 | run | min=92.7, median=95.38, max=96.84 (n=60) |
| `merge_r1_gc_pct` | — | 合并后 R1 GC 含量（%） | sample | min=47.09, median=50.69, max=59.35 (n=60) |
| `merge_r2_reads` | W1-R19 | 合并后总 clean reads（双端） | sample | min=7.902e+05, median=1.831e+07, max=3.423e+07 (n=60) |
| `merge_r2_bases` | — | 合并后 R2 碱基数 | sample | min=1.093e+08, median=2.565e+09, max=4.561e+09 (n=60) |
| `merge_r2_q30_pct` | — | 合并后 R2 Q30（%） | sample | min=81.93, median=90.65, max=92.98 (n=60) |
| `merge_r2_gc_pct` | — | 合并后 R2 GC 含量（%） | sample | min=47.22, median=50.83, max=59.51 (n=60) |
| `contigs_all_n` | W1-R20 | 组装 contig 数 | sample | min=8339, median=9.302e+04, max=3.244e+05 (n=60) |
| `contigs_all_bp` | W1-R21 | 组装总碱基 | sample | min=5.622e+06, median=8.023e+07, max=3.844e+08 (n=60) |
| `contigs_avg_len` | W1-R22 | 组装平均 contig 长度 | sample | min=674.2, median=897.1, max=1231 (n=60) |
| `contigs_min_len` | — | 组装最短 contig 长度 | sample | min=300, median=300, max=322 (n=60) |
| `contigs_max_len` | W1-R23 | 组装最长 contig | sample | min=1.026e+04, median=2.469e+04, max=4.424e+04 (n=60) |
| `contigs_ge1kb_n` | W1-R24 | ≥1 kb contig 数 | sample | min=866, median=1.878e+04, max=1.155e+05 (n=60) |
| `contigs_ge1kb_bp` | W1-R25 | ≥1 kb 总碱基 | sample | min=1.368e+06, median=4.164e+07, max=2.61e+08 (n=60) |
| `contigs_ge1kb_avg_len` | — | ≥1 kb contig 平均长度 | sample | min=1521, median=1900, max=2345 (n=60) |
| `contigs_ge1kb_max_len` | — | ≥1 kb contig 最长序列 | sample | min=1.026e+04, median=2.469e+04, max=4.424e+04 (n=60) |
| `merge_r1_fq_path` | — | 合并后 R1 FASTQ 路径 | sample | 示例: /data/user/pengxinyue/Workflows/workflow1_upstream/example/merge/v100/cleanreads_r1.fq, /data/user/pengxinyue/Workflows/workflow1_upstream/example/merge/v101/cleanreads_r1.fq, /data/user/pengxinyue/Workflows/workflow1_upstream/example/merge/v102/cleanreads_r1.fq |
| `merge_r1_fq_exists` | — | — | sample | 示例: True |
| `merge_r2_fq_path` | — | — | sample | 示例: /data/user/pengxinyue/Workflows/workflow1_upstream/example/merge/v100/cleanreads_r2.fq, /data/user/pengxinyue/Workflows/workflow1_upstream/example/merge/v101/cleanreads_r2.fq, /data/user/pengxinyue/Workflows/workflow1_upstream/example/merge/v102/cleanreads_r2.fq |
| `merge_r2_fq_exists` | — | — | sample | 示例: True |
| `merge_r1_stat_path` | — | — | sample | 示例: /data/user/pengxinyue/Workflows/workflow1_upstream/example/merge/v100/cleanreads_r1.fq.stat.txt, /data/user/pengxinyue/Workflows/workflow1_upstream/example/merge/v101/cleanreads_r1.fq.stat.txt, /data/user/pengxinyue/Workflows/workflow1_upstream/example/merge/v102/cleanreads_r1.fq.stat.txt |
| `merge_r1_stat_exists` | — | — | sample | 示例: True |
| `merge_r2_stat_path` | — | — | sample | 示例: /data/user/pengxinyue/Workflows/workflow1_upstream/example/merge/v100/cleanreads_r2.fq.stat.txt, /data/user/pengxinyue/Workflows/workflow1_upstream/example/merge/v101/cleanreads_r2.fq.stat.txt, /data/user/pengxinyue/Workflows/workflow1_upstream/example/merge/v102/cleanreads_r2.fq.stat.txt |
| `merge_r2_stat_exists` | — | — | sample | 示例: True |
| `assembly_fa_path` | — | Megahit 组装 FASTA 路径 | sample | 示例: /data/user/pengxinyue/Workflows/workflow1_upstream/example/assembly/v100/v100.contigs.fa, /data/user/pengxinyue/Workflows/workflow1_upstream/example/assembly/v101/v101.contigs.fa, /data/user/pengxinyue/Workflows/workflow1_upstream/example/assembly/v102/v102.contigs.fa |
| `assembly_fa_exists` | — | — | sample | 示例: True |
| `assembly_stat_path` | — | — | sample | 示例: /data/user/pengxinyue/Workflows/workflow1_upstream/example/assembly/v100/v100.contigs.stat.txt, /data/user/pengxinyue/Workflows/workflow1_upstream/example/assembly/v101/v101.contigs.stat.txt, /data/user/pengxinyue/Workflows/workflow1_upstream/example/assembly/v102/v102.contigs.stat.txt |
| `assembly_stat_exists` | — | — | sample | 示例: True |
| `assembly_fa_1kb_renamed_path` | — | ≥1 kb 重命名 contig FASTA 路径 | sample | 示例: /data/user/pengxinyue/Workflows/workflow1_upstream/example/assembly/v100/v100.contigs.1kb.renamed.fa, /data/user/pengxinyue/Workflows/workflow1_upstream/example/assembly/v101/v101.contigs.1kb.renamed.fa, /data/user/pengxinyue/Workflows/workflow1_upstream/example/assembly/v102/v102.contigs.1kb.renamed.fa |
| `assembly_fa_1kb_renamed_exists` | — | — | sample | 示例: True |
| `global_sample_id` | — | 跨批次全局样本 ID（batch_id__sample_id） | sample | — |
| `extracted_at` | — | 指标抽取 UTC 时间戳 | sample | — |

#### `qc_upstream_summary.tsv`

| 列名 | metric_id | 指标含义 | 粒度 | 本批次数值范围 |
| --- | --- | --- | --- | --- |
| `batch_id` | — | XvirBench 批次 ID | sample | — |
| `sample_id` | — | 生物学样本 ID（v61–v120） | sample | 示例: v100, v101, v102 |
| `n_runs` | — | 该样本合并的 sequencing run 数（通常 4） | sample | min=4, median=4, max=4 (n=60) |
| `merged_reads_r1` | — | 汇总表：合并 R1 reads | sample | min=7.902e+05, median=1.831e+07, max=3.423e+07 (n=60) |
| `merged_reads_r2` | — | 汇总表：合并 R2 reads | sample | min=7.902e+05, median=1.831e+07, max=3.423e+07 (n=60) |
| `merged_read_pairs` | — | 汇总表：read pairs 数 | sample | min=7.902e+05, median=1.831e+07, max=3.423e+07 (n=60) |
| `merged_reads_total` | — | 汇总表：双端总 reads | sample | min=1.58e+06, median=3.663e+07, max=6.845e+07 (n=60) |
| `merged_bases_total` | — | 汇总表：双端总碱基 | sample | min=2.181e+08, median=5.128e+09, max=9.116e+09 (n=60) |
| `contigs_all_n` | W1-R20 | 组装 contig 数 | sample | min=8339, median=9.302e+04, max=3.244e+05 (n=60) |
| `contigs_all_bp` | W1-R21 | 组装总碱基 | sample | min=5.622e+06, median=8.023e+07, max=3.844e+08 (n=60) |
| `contigs_avg_len` | W1-R22 | 组装平均 contig 长度 | sample | min=674.2, median=897.1, max=1231 (n=60) |
| `contigs_ge1kb_n` | W1-R24 | ≥1 kb contig 数 | sample | min=866, median=1.878e+04, max=1.155e+05 (n=60) |
| `contigs_ge1kb_bp` | W1-R25 | ≥1 kb 总碱基 | sample | min=1.368e+06, median=4.164e+07, max=2.61e+08 (n=60) |
| `assembly_fa_1kb_renamed_exists` | — | — | sample | 示例: True |
| `assembly_fa_1kb_renamed_path` | — | ≥1 kb 重命名 contig FASTA 路径 | sample | 示例: /data/user/pengxinyue/Workflows/workflow1_upstream/example/assembly/v100/v100.contigs.1kb.renamed.fa, /data/user/pengxinyue/Workflows/workflow1_upstream/example/assembly/v101/v101.contigs.1kb.renamed.fa, /data/user/pengxinyue/Workflows/workflow1_upstream/example/assembly/v102/v102.contigs.1kb.renamed.fa |
| `global_sample_id` | — | 跨批次全局样本 ID（batch_id__sample_id） | sample | — |
| `extracted_at` | — | 指标抽取 UTC 时间戳 | sample | — |

### 分组比较分析使用的核心指标

用于 `scripts/analysis/run_analysis.py`：

- `merge_r1_reads`（W1-R18）：合并后 R1 reads
- `merge_r1_q30_pct`（W1-R09）：fastp 后 Q30 比例
- `rrna_retention_r1`（W1-R17）：去 rRNA 保留率
- `contigs_ge1kb_n`（W1-R24）：≥1 kb contig 数

---

## 3. W2 病毒鉴定

**目录**：`batches/vazyme_fragment_test/harmonized/workflow2/`

### 输出文件

| 文件 | 粒度 | 行数 |
| --- | --- | --- |
| `virus_identification_sample.tsv` | sample | 60（60 样本） |
| `virus_identification_contigs.tsv` | contig | 646（646 条假定病毒 contig） |
| `virus_identification_clusters.tsv` | cluster | 72（72 个 ANI80 聚类） |

### 字段说明

#### `virus_identification_sample.tsv`

| 列名 | metric_id | 指标含义 | 粒度 | 本批次数值范围 |
| --- | --- | --- | --- | --- |
| `batch_id` | — | XvirBench 批次 ID | sample | — |
| `sample_id` | — | 生物学样本 ID（v61–v120） | sample | 示例: v109, v110, v111 |
| `n_contigs` | W2-V01 | 候选病毒 contig 数 | sample | min=3, median=11, max=20 (n=60) |
| `n_clusters` | W2-V10 | ANI80 聚类簇数 | sample | min=3, median=11, max=19 (n=60) |
| `host_group` | — | 宿主分组（rat / tick / mosquito）；W2/W5/W7 按宿主参考分别计算 | sample | 示例: mosquito, rat, tick |
| `global_sample_id` | — | 跨批次全局样本 ID（batch_id__sample_id） | sample | — |
| `extracted_at` | — | 指标抽取 UTC 时间戳 | sample | — |

#### `virus_identification_contigs.tsv`

| 列名 | metric_id | 指标含义 | 粒度 | 本批次数值范围 |
| --- | --- | --- | --- | --- |
| `batch_id` | — | XvirBench 批次 ID | contig | — |
| `contig_id` | — | 病毒 contig 唯一 ID | contig | 示例: 97-97-k141_43096, 97-97-k141_10644, 97-97-k141_63055 |
| `length` | W2-V03 | 单条 contig 长度 | contig | min=1005, median=3324, max=1.904e+04 (n=646) |
| `source_sample` | — | contig 来源样本 ID | contig | 示例: v97, v98, v99 |
| `contig_length` | W2-V03 | 单条 contig 长度 | contig | min=1005, median=3324, max=1.904e+04 (n=646) |
| `provirus` | — | 是否为前病毒（CheckV provirus 标记） | contig | 示例: No, Yes |
| `proviral_length` | — | 前病毒区段长度（bp） | contig | min=1790, median=3523, max=1.559e+04 (n=3) |
| `gene_count` | — | CheckV 预测基因总数 | contig | min=1, median=1, max=8 (n=646) |
| `viral_genes` | W2-V07 | 病毒基因数 / 宿主基因数 | contig | min=0, median=1, max=4 (n=646) |
| `host_genes` | W2-V07 | 病毒基因数 / 宿主基因数 | contig | min=0, median=0, max=1 (n=646) |
| `checkv_quality` | W2-V05 | CheckV 质量等级 | contig | 示例: Not-determined, Medium-quality, Low-quality |
| `miuvig_quality` | W2-V05 | CheckV 质量等级 | contig | 示例: Genome-fragment, High-quality |
| `completeness` | W2-V04 | CheckV 完整度 | contig | min=0.05, median=53.35, max=100 (n=534) |
| `completeness_method` | — | CheckV 完整度估算方法 | contig | 示例: AAI-based (high-confidence), HMM-based (lower-bound), AAI-based (medium-confidence) |
| `contamination` | W2-V06 | CheckV 污染度 | contig | min=0, median=0, max=32.08 (n=646) |
| `kmer_freq` | — | CheckV k-mer 频率 | contig | min=1, median=1, max=1.13 (n=646) |
| `warnings` | — | CheckV 质量警告 | contig | 示例: no viral genes detected |
| `host_group` | — | 宿主分组（rat / tick / mosquito）；W2/W5/W7 按宿主参考分别计算 | contig | 示例: mosquito, rat, tick |
| `global_sample_id` | — | 跨批次全局样本 ID（batch_id__sample_id） | contig | — |
| `extracted_at` | — | 指标抽取 UTC 时间戳 | contig | — |

#### `virus_identification_clusters.tsv`

| 列名 | metric_id | 指标含义 | 粒度 | 本批次数值范围 |
| --- | --- | --- | --- | --- |
| `batch_id` | — | XvirBench 批次 ID | cluster | — |
| `clusid` | W2-V11 | 代表 contig ID | contig | 示例: clus_10, clus_11, clus_12 |
| `rep_seq` | W2-V11 | 代表 contig ID | contig | 示例: 109-109-k141_75512, 109-109-k141_16453, 109-109-k141_71639 |
| `n_members` | W2-V10 | ANI80 聚类簇数 | sample | min=1, median=6, max=32 (n=72) |
| `n_significant` | W2-V10 | ANI80 聚类簇数 | sample | min=1, median=1, max=1 (n=72) |
| `host_group` | — | 宿主分组（rat / tick / mosquito）；W2/W5/W7 按宿主参考分别计算 | cluster | 示例: mosquito, rat, tick |
| `extracted_at` | — | 指标抽取 UTC 时间戳 | cluster | — |

### 分组比较分析使用的核心指标

用于 `scripts/analysis/run_analysis.py`：

- `n_contigs`（W2-V01）：候选病毒 contig 数
- `n_clusters`（W2-V10）：ANI80 聚类簇数

---

## 4. W3 宿主鉴定

**目录**：`batches/vazyme_fragment_test/harmonized/workflow3/`

### 输出文件

| 文件 | 粒度 | 行数 |
| --- | --- | --- |
| `host_identification_sample.tsv` | sample | 60（60 样本） |
| `host_identification_contig.tsv` | sample | 60（60 样本（EukaMarker 汇总行）） |

### 字段说明

#### `host_identification_sample.tsv`

| 列名 | metric_id | 指标含义 | 粒度 | 本批次数值范围 |
| --- | --- | --- | --- | --- |
| `batch_id` | — | XvirBench 批次 ID | sample | — |
| `sample_id` | — | 生物学样本 ID（v61–v120） | sample | 示例: v100, v101, v102 |
| `n_records` | W3-H07 | 注释物种数 | sample | min=1, median=1, max=1 (n=60) |
| `n_species_inferred` | W3-H04 | 推断线粒体物种 | sample | min=1, median=1, max=1 (n=60) |
| `n_genus_inferred` | W3-H05 | 推断线粒体属 | sample | min=1, median=1, max=1 (n=60) |
| `global_sample_id` | — | 跨批次全局样本 ID（batch_id__sample_id） | sample | — |
| `extracted_at` | — | 指标抽取 UTC 时间戳 | sample | — |

#### `host_identification_contig.tsv`

| 列名 | metric_id | 指标含义 | 粒度 | 本批次数值范围 |
| --- | --- | --- | --- | --- |
| `batch_id` | — | XvirBench 批次 ID | sample | — |
| `sn` | — | W3 宿主鉴定内部样本编号（同 sample_id） | sample | 示例: v100, v101, v102 |
| `CYTB_species` | W3-H09 | ND1/CYTB/COI 物种与一致性 | sample | 示例: Rattus norvegicus, Capra hircus |
| `COI_species` | W3-H09 | ND1/CYTB/COI 物种与一致性 | sample | 示例: Rattus norvegicus bn/ssnhsdmcw |
| `ND1_species` | W3-H09 | ND1/CYTB/COI 物种与一致性 | sample | 示例: Rattus norvegicus bn/ssnhsdmcw, Capra hircus |
| `CYTB_pident` | W3-H09 | ND1/CYTB/COI 物种与一致性 | sample | min=97.65, median=98.56, max=100 (n=56) |
| `COI_pident` | W3-H09 | ND1/CYTB/COI 物种与一致性 | sample | min=99.11, median=99.22, max=99.73 (n=60) |
| `ND1_pident` | W3-H09 | ND1/CYTB/COI 物种与一致性 | sample | min=98.58, median=99.27, max=99.71 (n=32) |
| `CYTB_notbest_genus` | — | — | sample | min=0, median=0, max=1 (n=55) |
| `COI_notbest_genus` | — | — | sample | min=0, median=0, max=1 (n=60) |
| `ND1_notbest_genus` | — | — | sample | min=0, median=0, max=0 (n=32) |
| `CYTB_notbest_genuslist` | — | — | sample | 示例: Capra, Rattus |
| `COI_notbest_genuslist` | — | — | sample | 示例: Capra, Rattus |
| `ND1_notbest_genuslist` | — | — | sample | — |
| `inferred_mt_species` | W3-H04 | 推断线粒体物种 | sample | 示例: Rattus norvegicus bn/ssnhsdmcw, Capra hircus |
| `species_level_marker_count` | W3-H06 | 物种级标记基因数 | sample | min=1, median=2, max=2 (n=60) |
| `annotated_species_count` | W3-H07 | 注释物种数 | sample | min=1, median=2, max=2 (n=60) |
| `known_species` | W3-H08 | 是否已知物种 | sample | 示例: True |
| `inferred_mt_genus` | W3-H05 | 推断线粒体属 | sample | 示例: Rattus, Capra |
| `inferred_mt_species_chinese` | — | — | sample | — |
| `notbest_genuslist` | — | — | sample | 示例: Capra, Rattus |
| `notbest_genus` | W3-H10 | 非最优属数量 | sample | min=0, median=0, max=1 (n=60) |
| `source_sample` | — | contig 来源样本 ID | sample | 示例: v100, v101, v102 |
| `global_sample_id` | — | 跨批次全局样本 ID（batch_id__sample_id） | sample | — |
| `extracted_at` | — | 指标抽取 UTC 时间戳 | sample | — |

### 分组比较分析使用的核心指标

用于 `scripts/analysis/run_analysis.py`：

- `n_species_inferred`（W3-H04）：推断线粒体物种
- `n_genus_inferred`（W3-H05）：推断线粒体属

---

## 5. W4 Kraken/Bracken 微生物谱

**目录**：`batches/vazyme_fragment_test/harmonized/workflow4/`

### 输出文件

| 文件 | 粒度 | 行数 |
| --- | --- | --- |
| `microbiome_bracken_sample.tsv` | sample | 60（60 样本） |
| `microbiome_bracken_top15.tsv` | sample×taxon | 895（895 行（每样本 Top15 物种）） |

### 字段说明

#### `microbiome_bracken_sample.tsv`

| 列名 | metric_id | 指标含义 | 粒度 | 本批次数值范围 |
| --- | --- | --- | --- | --- |
| `batch_id` | — | XvirBench 批次 ID | sample | — |
| `sample_id` | — | 生物学样本 ID（v61–v120） | sample | 示例: v100, v101, v102 |
| `kraken_classified_reads` | W4-K02 | Kraken 各分类单元 reads | sample×taxon | min=2.484e+04, median=7.95e+05, max=2.009e+06 (n=60) |
| `kraken_unclassified_reads` | W4-K01 | Kraken 未分类比例 | sample | min=6.49e+05, median=1.736e+07, max=3.264e+07 (n=60) |
| `kraken_unclassified_frac` | W4-K01 | Kraken 未分类比例 | sample | min=0.8213, median=0.9535, max=0.992 (n=60) |
| `bracken_species_taxa` | W4-K08 | Top-N 物种数 | sample | min=11, median=32, max=201 (n=60) |
| `bracken_species_reads_assigned` | W4-K03 | Bracken 估计 reads | sample×taxon | min=2.412e+04, median=7.939e+05, max=2.008e+06 (n=60) |
| `bracken_species_frac_of_classified` | W4-K04 | Bracken 相对丰度 | sample×taxon | min=0.9712, median=0.9985, max=0.9997 (n=60) |
| `bracken_genus_taxa` | W4-K08 | Top-N 物种数 | sample | min=12, median=39, max=135 (n=60) |
| `bracken_genus_reads_assigned` | W4-K03 | Bracken 估计 reads | sample×taxon | min=1.415e+04, median=5.784e+05, max=2.006e+06 (n=60) |
| `bracken_genus_frac_of_classified` | — | — | sample | min=0.093, median=0.9983, max=0.9999 (n=60) |
| `bracken_family_taxa` | W4-K08 | Top-N 物种数 | sample | min=14, median=34.5, max=90 (n=60) |
| `bracken_family_reads_assigned` | — | — | sample | min=1.539e+04, median=7.946e+05, max=2.009e+06 (n=60) |
| `bracken_family_frac_of_classified` | — | — | sample | min=0.3549, median=0.9996, max=0.9999 (n=60) |
| `global_sample_id` | — | 跨批次全局样本 ID（batch_id__sample_id） | sample | — |
| `extracted_at` | — | 指标抽取 UTC 时间戳 | sample | — |

#### `microbiome_bracken_top15.tsv`

| 列名 | metric_id | 指标含义 | 粒度 | 本批次数值范围 |
| --- | --- | --- | --- | --- |
| `batch_id` | — | XvirBench 批次 ID | sample×taxon | — |
| `sample_id` | — | 生物学样本 ID（v61–v120） | sample×taxon | 示例: v100, v101, v102 |
| `rank` | W4-K05 | 分类单元名称与 taxid | sample×taxon | min=1, median=8, max=15 (n=895) |
| `name` | W4-K05 | 分类单元名称与 taxid | sample×taxon | 示例: Coxiella-like endosymbiont, Mivirus wuhanense, Homo sapiens |
| `taxonomy_id` | W4-K05 | 分类单元名称与 taxid | sample×taxon | min=195, median=2.845e+04, max=3.053e+06 (n=895) |
| `new_est_reads` | W4-K03 | Bracken 估计 reads | sample×taxon | min=12, median=1047, max=1.783e+06 (n=895) |
| `fraction_total_reads` | W4-K04 | Bracken 相对丰度 | sample×taxon | min=7e-05, median=0.00227, max=0.9774 (n=895) |
| `global_sample_id` | — | 跨批次全局样本 ID（batch_id__sample_id） | sample×taxon | — |
| `extracted_at` | — | 指标抽取 UTC 时间戳 | sample×taxon | — |

### 分组比较分析使用的核心指标

用于 `scripts/analysis/run_analysis.py`：

- `kraken_unclassified_frac`（W4-K01）：Kraken 未分类比例
- `bracken_species_taxa`（W4-K08）：Top-N 物种数
- `bracken_species_reads_assigned`（W4-K03）：Bracken 估计 reads

---

## 6. W5 病毒 RPM 定量

**目录**：`batches/vazyme_fragment_test/harmonized/workflow5/`

### 输出文件

| 文件 | 粒度 | 行数 |
| --- | --- | --- |
| `virus_quantification_sample.tsv` | sample | 60（60 样本） |
| `virus_quantification_rpm.tsv` | sample×ref | 695（695 行（样本 × 病毒 contig）） |

### 字段说明

#### `virus_quantification_sample.tsv`

| 列名 | metric_id | 指标含义 | 粒度 | 本批次数值范围 |
| --- | --- | --- | --- | --- |
| `batch_id` | — | XvirBench 批次 ID | sample | — |
| `sample_id` | — | 生物学样本 ID（v61–v120） | sample | 示例: v97, v98, v99 |
| `n_viral_contigs_with_reads` | W5-Q09 | 有表达的病毒 contig 数 | sample | min=5, median=11, max=21 (n=60) |
| `total_mapped_reads` | W5-Q02 | mapped reads | sample×ref | min=1.531e+04, median=8.862e+04, max=1.588e+07 (n=60) |
| `max_rpm` | W5-Q10 | 最高 RPM 病毒 | sample | min=489.5, median=5973, max=3.721e+05 (n=60) |
| `median_rpm` | W5-Q08 | RPM | sample×ref | min=4.667, median=30.26, max=1110 (n=60) |
| `mean_coverage_pct` | W5-Q04 | 覆盖度 | sample×ref | min=72.25, median=90.11, max=99.48 (n=60) |
| `clean_reads` | W5-Q01 | clean reads 总数 | sample | min=1.58e+06, median=3.663e+07, max=6.845e+07 (n=60) |
| `mapping_rate_pct` | W5-Q02 | mapped reads | sample×ref | min=0.06389, median=0.636, max=39.65 (n=60) |
| `host_group` | — | 宿主分组（rat / tick / mosquito）；W2/W5/W7 按宿主参考分别计算 | sample | 示例: mosquito, rat, tick |
| `global_sample_id` | — | 跨批次全局样本 ID（batch_id__sample_id） | sample | — |
| `extracted_at` | — | 指标抽取 UTC 时间戳 | sample | — |

#### `virus_quantification_rpm.tsv`

| 列名 | metric_id | 指标含义 | 粒度 | 本批次数值范围 |
| --- | --- | --- | --- | --- |
| `batch_id` | — | XvirBench 批次 ID | sample×ref | — |
| `sample_id` | — | 生物学样本 ID（v61–v120） | sample×ref | 示例: v111, v110, v109 |
| `reference_id` | W5-Q11 | 参考序列 ID | ref | 示例: 110-110-k141_1632, 98-98-k141_8139, 98-98-k141_77004 |
| `start_pos` | — | RPM 比对起始位置 | sample×ref | min=1, median=1, max=1 (n=695) |
| `end_pos` | — | RPM 比对终止位置 | sample×ref | min=1045, median=6161, max=1.904e+04 (n=695) |
| `mapped_reads` | W5-Q02 | mapped reads | sample×ref | min=2, median=970, max=1.49e+07 (n=695) |
| `covbases` | W5-Q03 | 覆盖碱基数 | sample×ref | min=298, median=4448, max=1.904e+04 (n=695) |
| `coverage` | W5-Q04 | 覆盖度 | sample×ref | min=20.05, median=98.33, max=100 (n=695) |
| `mean_depth` | W5-Q05 | 平均深度 | sample×ref | min=0.2378, median=17.29, max=5.715e+04 (n=695) |
| `mean_baseq` | W5-Q06 | 平均碱基质量 | sample×ref | min=33.5, median=37.9, max=39.7 (n=695) |
| `mean_mapq` | W5-Q07 | 平均 MAPQ | sample×ref | min=16, median=39.4, max=44 (n=695) |
| `total_clean_reads` | W5-Q01 | clean reads 总数 | sample | min=1.58e+06, median=3.752e+07, max=6.845e+07 (n=695) |
| `RPM` | W5-Q08 | RPM | sample×ref | min=0.03091, median=32.45, max=3.721e+05 (n=695) |
| `host_group` | — | 宿主分组（rat / tick / mosquito）；W2/W5/W7 按宿主参考分别计算 | sample×ref | 示例: mosquito, rat, tick |
| `global_sample_id` | — | 跨批次全局样本 ID（batch_id__sample_id） | sample×ref | — |
| `extracted_at` | — | 指标抽取 UTC 时间戳 | sample×ref | — |

### 分组比较分析使用的核心指标

用于 `scripts/analysis/run_analysis.py`：

- `mapping_rate_pct`（W5-Q02）：mapped reads
- `median_rpm`（W5-Q08）：RPM
- `n_viral_contigs_with_reads`（W5-Q09）：有表达的病毒 contig 数
- `mean_coverage_pct`（W5-Q04）：覆盖度

---

## 7. W6 病毒注释

本批次 **未运行** W6，无 harmonized 输出。

---

## 8. W7 建库方法学 benchmark

**目录**：`batches/vazyme_fragment_test/harmonized/workflow7/`

### 输出文件

| 文件 | 粒度 | 行数 |
| --- | --- | --- |
| `fragmentation_benchmark.tsv` | sample | 60（60 样本） |
| `fragmentation_method_summary.tsv` | method×host | 8（8 行（method × 宿主分层汇总）） |

### 字段说明

#### `fragmentation_benchmark.tsv`

| 列名 | metric_id | 指标含义 | 粒度 | 本批次数值范围 |
| --- | --- | --- | --- | --- |
| `batch_id` | — | XvirBench 批次 ID | sample | — |
| `sample_id` | — | 生物学样本 ID（v61–v120） | sample | 示例: v97, v98, v99 |
| `method` | W7-F14 | 建库方法分组 | sample | 示例: cDNA_Frag_30C5Min, RNA_Frag_85C6Min, RNA_Frag_94C7Min |
| `total_reads_x` | W7-F01 | STAR 输入 reads 数 | sample | min=7.902e+05, median=1.831e+07, max=3.423e+07 (n=60) |
| `uniquely_mapped_pct` | W7-F02 | 唯一比对率 | sample | min=9.19, median=15.11, max=72.17 (n=60) |
| `multi_mapped_pct` | W7-F03 | 多比对率 | sample | min=3.06, median=6.515, max=23.57 (n=60) |
| `unmapped_pct` | W7-F04 | 过短未比对率 | sample | — |
| `median_5prime_to_3prime_bias` | W7-F05 | 5′→3′ 偏倚中位数 | sample | min=0, median=0, max=0.7555 (n=60) |
| `median_cv_coverage` | W7-F06 | 覆盖 CV 中位数 | sample | min=0.5583, median=1.287, max=1.501 (n=60) |
| `percent_duplication` | W7-F07 | PCR 重复率 | sample | min=0.08987, median=0.3245, max=0.9127 (n=60) |
| `total_reads_y` | W7-F08 | BAM 总 reads（嵌合统计） | sample | min=2.216e+06, median=5.625e+07, max=1.171e+08 (n=60) |
| `chimeric_reads` | W7-F09 | 嵌合体 reads 数 | sample | min=1.465e+05, median=2.985e+06, max=1.147e+07 (n=60) |
| `chimeric_rate_pct` | W7-F10 | 嵌合体比例 | sample | min=3.749, median=5.585, max=13.53 (n=60) |
| `splice_junctions_total` | W7-F11 | 剪接位点总数 | sample | min=1.911e+04, median=6.236e+04, max=1.555e+05 (n=60) |
| `splice_junctions_known` | W7-F12 | 已知剪接位点 | sample | min=2760, median=2.157e+04, max=3.22e+04 (n=60) |
| `splice_junctions_novel` | W7-F13 | 新剪接位点 | sample | min=9447, median=4.349e+04, max=1.233e+05 (n=60) |
| `host_group` | — | 宿主分组（rat / tick / mosquito）；W2/W5/W7 按宿主参考分别计算 | sample | 示例: mosquito, rat, tick |
| `global_sample_id` | — | 跨批次全局样本 ID（batch_id__sample_id） | sample | — |
| `extracted_at` | — | 指标抽取 UTC 时间戳 | sample | — |

#### `fragmentation_method_summary.tsv`

| 列名 | metric_id | 指标含义 | 粒度 | 本批次数值范围 |
| --- | --- | --- | --- | --- |
| `batch_id` | — | XvirBench 批次 ID | method×host | — |
| `method` | W7-F14 | 建库方法分组 | sample | 示例: RNA_Frag_85C6Min, cDNA_Frag_30C5Min, RNA_Frag_94C7Min |
| `sample_id` | — | 生物学样本 ID（v61–v120） | method×host | min=66.5, median=97, max=116 (n=8) |
| `total_reads_x` | W7-F01 | STAR 输入 reads 数 | sample | min=1.508e+07, median=1.749e+07, max=2.6e+07 (n=8) |
| `uniquely_mapped_pct` | W7-F02 | 唯一比对率 | sample | min=12.52, median=15.96, max=71.83 (n=8) |
| `multi_mapped_pct` | W7-F03 | 多比对率 | sample | min=4.702, median=9.526, max=13.82 (n=8) |
| `unmapped_pct` | W7-F04 | 过短未比对率 | sample | — |
| `median_5prime_to_3prime_bias` | W7-F05 | 5′→3′ 偏倚中位数 | sample | min=0, median=0.0001081, max=0.6229 (n=8) |
| `median_cv_coverage` | W7-F06 | 覆盖 CV 中位数 | sample | min=0.5631, median=1.25, max=1.391 (n=8) |
| `percent_duplication` | W7-F07 | PCR 重复率 | sample | min=0.105, median=0.2458, max=0.7919 (n=8) |
| `total_reads_y` | W7-F08 | BAM 总 reads（嵌合统计） | sample | min=3.714e+07, median=6.054e+07, max=7.917e+07 (n=8) |
| `chimeric_reads` | W7-F09 | 嵌合体 reads 数 | sample | min=2.109e+06, median=3.244e+06, max=9.179e+06 (n=8) |
| `chimeric_rate_pct` | W7-F10 | 嵌合体比例 | sample | min=4.143, median=5.574, max=13.43 (n=8) |
| `splice_junctions_total` | W7-F11 | 剪接位点总数 | sample | min=3.095e+04, median=8.701e+04, max=1.409e+05 (n=8) |
| `splice_junctions_known` | W7-F12 | 已知剪接位点 | sample | min=4718, median=2.166e+04, max=3.033e+04 (n=8) |
| `splice_junctions_novel` | W7-F13 | 新剪接位点 | sample | min=2.617e+04, median=6.36e+04, max=1.106e+05 (n=8) |
| `host_group` | — | 宿主分组（rat / tick / mosquito）；W2/W5/W7 按宿主参考分别计算 | method×host | 示例: mosquito, rat, tick |
| `global_sample_id` | — | 跨批次全局样本 ID（batch_id__sample_id） | method×host | — |
| `extracted_at` | — | 指标抽取 UTC 时间戳 | method×host | — |

### 分组比较分析使用的核心指标

用于 `scripts/analysis/run_analysis.py`：

- `uniquely_mapped_pct`（W7-F02）：唯一比对率
- `multi_mapped_pct`（W7-F03）：多比对率
- `median_cv_coverage`（W7-F06）：覆盖 CV 中位数
- `percent_duplication`（W7-F07）：PCR 重复率
- `chimeric_rate_pct`（W7-F10）：嵌合体比例

---

## 9. 附录：尚未抽取的 WORKFLOW_SUMMARY 指标

| Workflow | 未抽取示例 |
| --- | --- |
| W1 | W1-R03 Q20、部分 run 级 seqkit 字段 |
| W2 | W2-V08–V18 HMM/BLAST/迭代详情 |
| W3 | W3-H01–H03 标记基因深度 |
| W4 | W4-K06–K07 跨样本矩阵 |
| W6 | 全部（本批次未运行） |
| W7 | W7-F15–F21 Preseq、gene body |

## 10. 附录：再生 Excel 交付表

```bash
python3 scripts/build_harmonized_excel.py \
  --batch-id vazyme_fragment_test \
  --output docs/vazyme_benchmark_metrics.xlsx
```

输出 47 个 sheet，含 60 样本全量 harmonized 数据及分析汇总表。
