# W1 批次下机-QC-组装 HTML 报告生成提示词

你是病原监测领域的生物信息学报告整理助手。请基于本地项目目录中的测序、质控、rRNA 去除、样本合并和组装统计文件，为每一个批次分别生成一个自包含 HTML 格式报告，并同步导出标准化样本明细表。

## 输入范围

- 优先读取 `W1_QC_REPORT_GUIDE.md` 中定义的字段口径和评分规则。
- 自动扫描项目目录下与候鸟、天津粪便测试、媒介蚊虫、V350399514、媒介鼠蜱相关的 Excel、CSV、TSV、LOG 或既有统计表。
- 不同批次字段可能不完整；只汇总真实存在的字段，不臆造数据。

## 报告结构

每个批次生成一个独立 HTML，章节顺序固定为：

1. 执行摘要
2. S0 原始数据
3. S1 fastp 质控
4. S2 rRNA 去除
5. S3 样本汇总 / 加测合并
6. S4 组装
7. 样本综合 QC
8. 评分标准
9. 图件
10. 附录

项目抬头只放批次总体评价、样本数、等级分布、低深度样本、需关注样本和阶段完整性。完整摘要只在正文 `1. 执行摘要` 中出现一次，不要在抬头和正文重复。

## 执行摘要模板

摘要应尽量采用下面的句式；如果某字段缺失，则明确写“当前源表未提供……”，不要把缺失阶段判定为失败。

```text
本批次共评估{样本类型} {样本数} 个（{批次ID}）。以样本为单位汇总各 lane 后，单样本原始 reads 中位数为 {median} Mb（范围 {min}-{max} Mb），原始碱基量中位数为 {median} Gb（范围 {min}-{max} Gb），原始 Q30 中位数为 {median}%。
fastp 后样本级 reads 保留率中位数为 {median}%（{min}%-{max}%），fastp 后 Q30 中位数为 {median}%。剔除 reads 的主要来源为「{主要来源}」；若源表未拆分剔除原因，则写明“当前源表未拆分到具体原因”。
rRNA 去除后平均保留率为 {mean}%（中位数 {median}%），样本级 Post-rRNA R1 深度中位数为 {median} Mb（范围 {min}-{max} Mb；本批次与 merge/clean 结果一致）。
de novo 组装 ≥1 kb contig 中位数为 {median} 条（范围 {min}-{max} 条）。
综合评级：优 {n} 个、良 {n} 个、可接受 {n} 个、需关注 {n} 个、不建议下游 {n} 个；批次总体达到批次质控要求/需结合缺失阶段或关注样本复核。低深度样本（Post-rRNA R1 < 5 Mb）：{样本列表或无}。需重点关注：{样本列表或无}。
```

## 统计口径

- reads 统一为 Mb，按 `reads / 1e6` 展示。
- bases 统一为 Gb，按 `bases / 1e9` 展示。
- 比例统一为百分比，保留 2 位小数。
- fastp 保留率使用 fastp 后 reads / raw reads。
- rRNA 保留率优先使用 clean R1 / fastp R1；如果存在 prinseq 中间步骤，应在正文注明具体分母。
- 低深度样本定义为 Post-rRNA R1 < 5 Mb。
- `contigs_ge1kb_n` 表示长度 ≥1 kb 的 contig 条数；`contigs_ge1kb_bp` 表示这些 contig 的总碱基数，二者不能混用。

## 图件要求

每个报告固定包含 4 个图位：

- `fig01_stage_yield`：各阶段 R1 reads / bases。
- `fig02_fastp_qc`：fastp 保留率、重复率及可用过滤指标；如果有剔除原因字段，展示剔除组成。
- `fig03_rrna_qc`：rRNA 保留率与 Post-rRNA 深度，并标出 5 Mb 低深度参考线。
- `fig04_assembly`：组装产出综合图，包括 clean depth vs contigs、contig 条数、平均长度和 ≥1 kb contig 比例。

如果没有有效分组信息，则所有样本按“整体”处理。如果某阶段没有可绘制字段，仍保留对应图位，并在图中注明“当前批次未提供……字段”，不要让报告出现缺失图件。

## 风格与输出

- HTML 应自包含，图表使用 Plotly 或等效方式内嵌，离线可打开。
- 图表使用白底、无衬线字体、简洁坐标轴和 SCI 汇报风格配色。
- 样本明细表应可横向滚动，保留样本名、分组、阶段指标、评分和来源追溯字段。
- 每个批次同步输出标准化 TSV 表，便于后续核对和二次分析。
- 报告末尾必须附带免责声明：本结果仅限科研实验室内部参考，不得作为临床诊断或公共卫生干预的直接决策依据。

## 当前项目推荐命令

```bash
python scripts/generate_batch_qc_reports.py --root /Users/guojd/Desktop/Project/xiada
```

如需指定输出目录：

```bash
python scripts/generate_batch_qc_reports.py \
  --root /Users/guojd/Desktop/Project/xiada \
  --out-dir /Users/guojd/Desktop/Project/xiada/outputs/批次下机与QC组装报告_YYYYMMDD
```
