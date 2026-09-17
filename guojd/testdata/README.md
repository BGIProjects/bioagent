# 第一波测试包

从 BJ-2024-615 各抽 20000 对 reads，不改原始文件。分析页文件树根目录会出现 `testdata/`。

## 单样本（1 对文件）

选择：

- `testdata/reads/single/demoA_R1.fastq.gz`
- `testdata/reads/single/demoA_R2.fastq.gz`

期望：配对成 1 条 record，可直接预检。目标点「第一波 W1–W4+W6」。

## 多样本（多个文件）

同时勾选：

- `testdata/reads/multi/demoA_R1.fastq.gz`
- `testdata/reads/multi/demoA_R2.fastq.gz`
- `testdata/reads/multi/demoB_R1.fastq.gz`
- `testdata/reads/multi/demoB_R2.fastq.gz`

期望：2 条 records，提示确认 sample 分组后再规划。

## Contig（1 个或多个文件）

- 单条：`testdata/contigs/KP641127.fna`（Flavivirus）
- 多条：再加上 `testdata/contigs/KP325401.fna`

非 FASTQ 需在数据集卡片里指定 artifact 为 contigs。右侧「知识/专项」可对 KP641127 做定种 / RVA dry-run。

## 注意

- 不要把产物写回本目录或 wangdaxi 源仓。
- 完整 W1–W4+W6 即使是 2 万对 reads 仍可能很慢；第一波先验收配对、方案、只读知识和 dry-run。
