# M1 第十三轮：Workflow 1 依赖身份与 B3 契约基础复现

日期：2026-09-26。源码基线：根仓库 `b5d58bf`、Agent `95d1b0c`、Open WebUI `d8f5eaabc`。

## 范围与结论

- 不做上传、真实 FASTQ 计算、真实 Workflow 1 中断恢复、模型调用、数据库／API／UI 变更。
- Workflow 1 五阶段 manifest、execution spec／planner v4、recovery contract v2 已实现；本机测试和 Cyclone 全阶段 DAG dry-run 通过。
- CandidateEvidence v2 仅为 Agent 内部契约；保留 v1 读取，新增 4,889 字节冻结初筛 fixture 和负向案例，不生成 Assessment 或领域结论。
- 结论边界为“程序存在、dry-run 通过、真实恢复未验证”。A3、B1、B3、M1 和 M2 均未完整验收。

## 本机验证

在 `agent/` 执行：

```bash
PYTHONPATH=/Users/lfz/miniconda3/envs/adapter/lib/python3.11/site-packages \
  /Users/lfz/miniconda3/envs/open-webui/bin/python -m pytest -q
/Users/lfz/.local/bin/ruff check <本轮改动的 Python 文件>
```

结果为 Agent `210 passed, 2 skipped, 90 subtests passed`，Ruff 通过。单独使用 `adapter` 环境收集全套测试时缺少既有报告依赖 `pandas`；使用已有 `open-webui` Python 提供报告依赖，并将 `adapter` site-packages 加入 `PYTHONPATH` 后完成全量回归，没有安装新依赖。

在 `open-webui/backend/` 执行方案／执行／恢复相关测试：

```bash
WEBUI_SECRET_KEY=bioagent-test-only-secret BIOAGENT_REMOTE_DATA=false \
  /Users/lfz/miniconda3/bin/conda run -n open-webui python -m pytest -q \
  open_webui/routers/test_analysis.py \
  open_webui/routers/test_analysis_plans_api.py
```

结果为 `69 passed`。在 `open-webui/` 执行五个 analysis 相关 Vitest 文件，结果为 `50 passed`。Prettier 与最终 8 GiB build 也通过；完整 build 输出写入 `/tmp/bioagent-m1-13-frontend-build.log`。首次准备 Pyodide 时被沙箱禁止连接本机代理，尚未进入 Vite build；按同一命令在获准环境重跑后以 `built in 1m 3s` 完成。

## Cyclone dry-run 与依赖身份

通过现有 `RemoteWorkerClient` 部署当前 worker，并为新目录 `analysis-m1-w1-identity-dry-20260926-02` 编译 `contig_filter` 目标。execution spec v4 展开 `read_qc → rrna_filter → sample_merge → assembly → contig_filter`；Snakemake 只执行 `--dry-run`，唯一 phase `upstream` 返回 0。

依赖身份完整，软件集合为 `snakemake`、`fastp`、`bowtie2`、`samtools`、`seqkit`、`megahit`，总身份 SHA-256 为：

```text
6d3f7d3f2646b1a270890d3591ea66eadff769a6cca0bc5e07db9c3779d98ff9
```

rRNA Bowtie2 六文件聚合 SHA-256 为 `84d03f99d5c602fac206b90d260b489ecaf9d0a65876190eab7bdfef0490f610`：

| 后缀         |      字节 | SHA-256                                                            |
| ------------ | --------: | ------------------------------------------------------------------ |
| `.1.bt2`     | 963167055 | `971f525cb9af6974615d844ced9a846ed80c4e788435783c5b4ecd2f2e0e5208` |
| `.2.bt2`     | 535428412 | `a189410ba53439f2505147ad3cc6bfc47ee5bb759708bbb61c9f77e87b4b1d33` |
| `.3.bt2`     |  18122075 | `938d451143ef9d8249668b3ba29dae306828e9770fb3bacb55ec84450b2a48aa` |
| `.4.bt2`     | 535428407 | `fa3f46291aa7402879c5acd37001611b94d7e07c525e32433496c87ca6202934` |
| `.rev.1.bt2` | 963167055 | `4841f5d7d53f5425334bf02b1d1c0ad60b189da3b2720cbe65c143ff974e4b7c` |
| `.rev.2.bt2` | 535428412 | `ffcae81085cb00a1331609da9a91d8f2a11cd9ceacad345d3c9703c5237894ad` |

dry-run 前后输入 stat 保持：R1 为 device `2048`、inode `201459176`、size `126682083`、mtime `1788511511`；R2 为 device `2048`、inode `201459177`、size `172927531`、mtime `1788511513`。没有执行 FASTQ shell command，也没有修改 Workflow 源码。

## 容量、限制与回退

- 新远端 dry-run 目录为 268 KiB，`dry-run.json` 占 24 KiB；Cyclone `/data` 验证时可用 365 GiB。本机 fixture 为 4,889 字节，`/tmp` 可用约 192 GiB。
- 索引完整 SHA-256 只在新 run、dry-run 与人工 resume 计算；状态轮询不计算，也不建立缓存库。
- 本轮未清理或覆盖既有 run；保留用户未追踪的 `reports/`。
- 回退 Agent commit 即可恢复 v3 编译与 recovery contract v1。已产生的 v4 方案／v2 contract 不应由旧代码启动或原地降级；应重新编译新方案。CandidateEvidence v2 尚无持久化消费者，删除 v2 类、fixture 与测试即可回退，v1 不受影响。
