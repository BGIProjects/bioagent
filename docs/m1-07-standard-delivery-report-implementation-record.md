# M1 第七轮：W1–W6 标准交付报告实施记录

## 范围与决策

本轮基线为根仓库 `cab0cba`、Agent `3570ad4`、Open WebUI `309046113`。提供的标准与本机只读参考 `reports/report.html`（SHA-256 `455199b9a17cec929326104643f26702281574e353bd1d8ae7d5f6873d249fc0`）用于约束 W1–W6 指标提取、统计、R 绘图和报告结构；W7 不在范围内，参考 HTML 不提交。

参考报告不含 checklist，而现有诊断意见书固定包含人工审核清单、证据索引与结果边界，因此两者保持独立。用户界面提供交付报告 HTML/PDF、诊断意见书和运行审计报告；所有用户报告删除一般文件 inventory，完整路径、manifest、生成错误与 hash 留在运行审计报告。

## 实现

- Agent 随 content-addressed worker 部署 `standard_report.py` 与自包含 `scripts/extract_io.py`；报告进程强制把 `XVIRBENCH_ROOT` 指向该 release，不在运行时读取 XvirMind/XvirBench。各流程完成后从 state phase registry 定位 run-local W1–W6 提取器与结果。
- 新方案将冻结的 `metadata_snapshot` 传入远端 state。分组须至少两个非空水平且至少两个水平 `n≥2`；统计包含总体／分组描述、Kruskal–Wallis、Mann–Whitney、BH、ε²、rank-biserial 及剔除低深度样本后的敏感性结果。
- 合并 R1 少于 5,000,000 reads 标为低深度。图由独立 Pixi 环境中的 R/ggplot2 生成，无数据即跳过；HTML 内嵌 PNG，PDF 由同一 HTML 生成。
- run-local `reports/standard/` 保存提取 JSON/TSV、coverage、样本主表、统计表、PNG/PDF 图、R 脚本、HTML、PDF 与 manifest。state `standard_delivery` schema v1 只登记相对路径、大小、媒体类型与 SHA-256。
- 报告生成失败只把 `standard_delivery.status` 设为 `failed`，不改变计算成功状态。`standard_report.py --state <run>/.bioagent/state.json` 是 report-only 重建入口。
- remote worker 只读取 state 登记且位于 run root、大小与 SHA-256 均匹配的产物；Agent 和 Open WebUI 分别提供 `/analysis/runs/delivery-report` 与 `/api/v1/analysis/runs/delivery-report`。
- `internal_report_available`／`/runs/internal-report` 被 `audit_report_available`／`/runs/audit-report` 取代；无旧名称兼容层。

## Cyclone 验证与产物

使用既有完成 run `/data/user/liufangzhou/runs/analysis-20260813-160906-0f9eda85` 执行 report-only。W1、W2 成功提取，W3–W6 标记 `missing_workflow`；计算结果未重跑或修改。

- `report.html`：320,797 bytes；SHA-256 `830336c360fef7dd44c95ad2dcefdaa1f9b331b20b28f275e9e23dd320ba3a4e`。
- `report.pdf`：731,752 bytes；SHA-256 `6c63053af56a926989e4477ef430ae3e3103f8070e1df2b80ae4a15177123b40`。
- 实际产生 7 张内嵌图；检查确认 HTML 无 `/data/user/` 绝对路径、一般文件清单或人工审核 checklist，章节包含 W1–W6、跨流程、结构化统计、方法摘要与 R 脚本。验证所用 worker release 为 `ea3147d8eecd31ef3d56906afa39d148204b9d726daab0ad65f52078944eb1aa`，其中内建提取 helper 已存在。
- manifest 登记的 34 个文件均通过 byte 数与 SHA-256 复核。
- 工具链实测为 SciPy 1.18.1、R 4.5.3、WeasyPrint 69.0；所需 R 包均可加载。

## 验证状态

- Agent：remote worker、runner、deterministic runtime 与标准报告共 49 项通过；其中 7 项标准报告测试覆盖 W1–W6 提取契约、缺失流程、低深度／缺失值、分组门槛、统计与效应量、BH、W6 图表契约、绝对路径隐藏及空数据 R 脚本。
- Backend：analysis router、plan API、run delivery 与 replay report 共 62 项通过；覆盖格式状态、artifact hash／路径拒绝、诊断 checklist 与审计报告改名。
- Frontend：Vitest 11 项、Cypress 2 项通过；Ruff 与 Prettier 通过相关文件。`NODE_OPTIONS=--max-old-space-size=8192 npm run build` 成功，Vite production build 用时 56.36 秒。

## 限制与回退

真实 Cyclone smoke test 只覆盖 W1+W2 与 W3–W6 缺失分支；W3–W6 的全量真实生物学结果仍需后续完成 run 验证。某标准图所需字段不存在时按规则跳过，不绘制空图；报告结论为确定性科研解释，不构成临床诊断。

回退时先停止新任务准入，再分别回退 Open WebUI 与 Agent。已生成的 `reports/standard/` 可保留；旧代码不会展示 `standard_delivery`。本轮没有数据库迁移，根仓库只需回退文档和配置说明。
