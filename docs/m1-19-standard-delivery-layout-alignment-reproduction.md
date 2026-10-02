# M1 第十九轮：标准交付报告版型对齐复现记录

## 1. 范围与结论

本轮以参考报告目录 `reports/pxy_V350399508/` 为只读版型参考，修复第十八轮两个 run 的标准交付报告。HTML 是结构与内容主契约；PDF 必须由同一 HTML 经 WeasyPrint 产生，并逐页作视觉检查。只执行 report-only，不重跑或改写 FASTQ、Workflow 1、Workflow 2，也不改变既有下载 API、数据库、Backend 或 UI。

诊断结论为旧报告**未完整满足**参考版型：缺少完整导航、五个状态标签、数据驱动叙述、专用 W1–W6 图表和科研限制页尾；PDF 表格存在逐字直排。full-r2 还把缺失 sample ID 字符串化成 `nan`，误计为第二个样本。修复后两个报告满足本轮定义的版型与分析契约，且不复制参考批次的样本名、结论或硬编码。

## 2. 身份与输入

- 模板：`bioagent-standard-delivery-v2`；`standard_delivery` schema 继续为 v1。
- Agent worker release：`182a5ad8b43d68d3976084daac4664c1e127b8e07189de7ca02c39238287e6a4`。
- 完整 run：`analysis-m118-priority-full-r2-20260930`。
- 修改版 W1 run：`analysis-m118-priority-qc80-20260930`。
- 参考 HTML SHA-256：`455199b9a17cec929326104643f26702281574e353bd1d8ae7d5f6873d249fc0`。
- 参考 PDF SHA-256：`6044abba99ac400154d35aba28943b35d11585bf00070f513f6a197393ff0a94`。

正式 runtime 只使用 worker release 内的 `standard_report.py`、提取 helper、R 主题与绘图脚本；XvirMind／XvirBench 只作本轮只读参考，不是运行依赖。

## 3. 重建命令

开始前先验证 SSH 与容量：

```bash
ssh -o ClearAllForwardings=yes Cyclone true
df -Pk . /tmp
ssh -o ClearAllForwardings=yes Cyclone 'df -Pk /data /home/liufangzhou'
```

部署上述 content-addressed worker 后，以固定报告 Python 对两个 state 各执行一次最终 report-only：

```bash
ssh -o ClearAllForwardings=yes Cyclone \
  '/home/liufangzhou/.pixi/bin/bioagent-report-python /data/user/liufangzhou/.bioagent/worker/releases/182a5ad8b43d68d3976084daac4664c1e127b8e07189de7ca02c39238287e6a4/standard_report.py --state /data/user/liufangzhou/runs/analysis-m118-priority-full-r2-20260930/.bioagent/state.json'

ssh -o ClearAllForwardings=yes Cyclone \
  '/home/liufangzhou/.pixi/bin/bioagent-report-python /data/user/liufangzhou/.bioagent/worker/releases/182a5ad8b43d68d3976084daac4664c1e127b8e07189de7ca02c39238287e6a4/standard_report.py --state /data/user/liufangzhou/runs/analysis-m118-priority-qc80-20260930/.bioagent/state.json'
```

命令总 wall time（含 SSH）分别约 10.6 秒与 8.4 秒。报告先在各 run 的 `reports/standard/` 内暂存，成功后只替换标准报告拥有的 `extracted/`、`tables/`、`figures/`、`r/`、`report.html`、`report.pdf` 与 `manifest.json`。

## 4. 产物与 SHA-256

原始下载文件保持不变；新版完整目录复制到：

- `reports/20260930-analysis-m118-priority/full-r2/repaired/`
- `reports/20260930-analysis-m118-priority/qc80/repaired/`

| 产物             | 旧版 SHA-256                                                       | 修复版 SHA-256                                                     |
| ---------------- | ------------------------------------------------------------------ | ------------------------------------------------------------------ |
| full-r2 HTML     | `0b8a5d5520108ba3339a9a5b59ede8a241e468dd04e6a31de0be07ce49d3abce` | `b5e27b5f1a090eea8cbb783fbe3d074f9f31280e5feaa207e28fca214e033432` |
| full-r2 PDF      | `266c99dbd6b99f7987fc5b003666ce24badd5f65dacfbad3d2f2481fc0c92be6` | `2bde90ae09867bd6b7f528478ce00c09610e8ac44de959bef91664459bde2070` |
| full-r2 manifest | —                                                                  | `099cc6aafe730625f09a6e2b27a512a70da25d5762830f388b7315c97b6a01e9` |
| qc80 HTML        | `4994438b7e5923ee16265f47df42c4b4bdaa2aaa890812a5c71fa5449f949065` | `dd4b4ba1d2134861c2835d2c26dfa1cb1e1e7d861c69f8ae4d80b1c2ca5d707b` |
| qc80 PDF         | `7275f28cab5326c175af90f9df8125e609766a7c4577a39e4bbe69ca81a9e32e` | `5ab35a448f0aa2cc7e80d183fa98f7d907225662a2785fd2a1115451ea0bff9b` |
| qc80 manifest    | —                                                                  | `9dcda6ffc6b829d5446d857cca78b2b46a11d091f7e1531a6fc1b65bdd8e9dbc` |

full-r2 目录共 38 个文件，manifest 登记除自身外的 37 项；qc80 共 20 个文件，manifest 登记 19 项。逐项 byte size 与 SHA-256 复核通过，manifest 不包含 `scientific/`、`tool-demo/` 或 `skill-demo/`。

## 5. 内容与视觉验收

- 两份 HTML 均有 kicker、恰好五个状态标签、锚点导航、警示区、编号 W1–W6 章节、图说、结构化表、方法摘要、受限 R 附录及科研限制页尾。
- HTML 不含 `/data/user/`、`/home/liufangzhou/` 或参考批次 `pxy_V350399508`。
- full-r2 master table 只有 `BJ-2024-615` 一个样本；W1/W2 为 extracted，W3–W6 为 skipped。W2 实际汇总 1 个候选、1 个 low-quality CheckV 结果、37.97 completeness 与 1 个 cluster；共生成 8 张图。
- qc80 master table 只有一个样本且只显示实际可用的 W1 read-QC 指标；不虚构合并、组装或群组推论，共生成 2 张图。
- PDF producer 为 WeasyPrint 69.0。full-r2 为 12 页、qc80 为 8 页，页面均为 A4 landscape（841.89 × 595.276 pt）。20 页全部以 `pdftoppm -png -r 120` 渲染并检查；无逐字直排、裁切、重叠、黑块、不可读表格或缺失标题／图说。

## 6. 不变性

重建前后下列内容不变：

- full-r2 W1 目录指纹：`7b32ec00ce6cf724d7e5065fc4115772e7cb3621e50acbe337df7ff353939650`。
- full-r2 W2 目录指纹：`06ce5ab4e3a03bca5b5c8fdf6e6c0ec34c3aaa7f77dca40f3741463f6835682b`。
- qc80 W1 目录指纹：`bc15959308b7246d88fef85282036f3710ac9df468951c8a856f2afa572ab270`。
- 输入 R1 stat：`126682083|1775226330|191113385`；R2 stat：`172927531|1775226370|191113386`。
- full-r2 的 scientific 七项与 tool-demo 两项、qc80 的 tool-demo／skill-demo 四项 SHA-256 均与重建前逐项一致；report-only 没有删除或重写这些目录。

## 7. 自动验证与容量

验证顺序及结果：

- Agent 完整 Python：230 passed、2 skipped。
- Backend delivery-report 相关 Python：51 passed。
- Vitest：9 files、65 passed。
- 变更文件 Ruff：通过。Agent 全目录 Ruff 仍报告 8 个与本轮文件无关的既有诊断，未越界修改。
- Prettier：本轮文档检查通过。
- 前端：沙箱内尝试在 Vite 编译前的 Pyodide metadata 下载阶段被本机代理 socket 权限拒绝；随后在沙箱外仅执行一次完整 `NODE_OPTIONS=--max-old-space-size=8192 npm run build`，55.53 秒通过。

容量在开始、每次 report-only 前后及结束时检查。开始时本机可用约 182.5 GiB；结束时 Cyclone `/data` 可用约 358.3 GiB，Home NVMe 可用约 42.4 GiB，均高于 20／50／20 GiB 门槛。报告只回传小型证据与交付产物，没有复制 FASTQ 或大型中间结果。

## 8. 限制与回退

本轮对齐的是 W1–W6 已有结果的资料处理、叙述、图表与版型能力，不增加 W7，也不将缺失 workflow 或单样本资料扩写成未观测的结果。若需回退，可重新部署上一版 Agent worker 并对相同 state 执行 report-only；Workflow 输出与优先 Demo 目录不受影响。
