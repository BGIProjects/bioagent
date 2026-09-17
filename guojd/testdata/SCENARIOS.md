# 分析页小批量 testdata

目录：`testdata/scenarios/`。在 5174 分析页右侧「文件列表」打开 `testdata` → `scenarios`。

| 情形 | 目录 | 怎么用 |
|---|---|---|
| 单样本双端 | `S1_single_pe` | 勾选 demoA_R1/R2，目标选第一波或 W1+W2 |
| 多样本双端 | `S2_multi_sample` | 勾选 demoA + demoB 两对，测分组 |
| contig 定种/RVA | `S3_hepacivirus_contigs` | 选 KP641127.fna；右侧「知识/专项」定种 → RVA（科 Flaviviridae） |
| 模拟病毒 reads（界面） | `S4_hepacivirus_reads` | 200 对来自 KP641127，只打通界面 |
| 组装 + W2/W3/W5 | `S5_hepacivirus_w2w3w5` | hepaA/hepaB 各 2500×150bp PE；hepaA 另含 400 对 ND1 宿主 spike。目标：质控与组装、病毒识别、宿主识别、病毒定量。W7 不进默认报告。 |

S1–S4 每份 reads 都是 **200 对**，用来打通界面、方案、报告和专项。S5 用来真正跑通 W2（至少 1 条病毒序列）、W3、W5。

定种走 wangdaxi `virus_taxonomy`（MCP :8766）。RNA 注释增量走 wangdaxi RVA（MCP :8767）。流程注释仍是 W6。默认结构化报告覆盖 W1–W6，不含 W7。
