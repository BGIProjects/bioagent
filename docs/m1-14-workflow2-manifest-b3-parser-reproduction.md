# M1 第十四轮：Workflow 2 Manifest 与 B3 候选解析复现

日期：2026-09-26。源码基线：根仓库 `2b206b7`、Agent `03d7ce7`、Open WebUI `6cece2ff3`。

## 范围与结论

- 不做上传、FASTQ 重算、模型调用、专家审核、数据库、API 或 UI 变更。
- Workflow 2 五阶段 manifest 与 execution spec／planner v5 已实现；当前 adapter 的全 DAG dry-run 通过，但工具／参考库身份不完整，仍不可恢复或作为正式 release。
- 内部 parser 从完成的 W2 phase 读取最终候选表并返回 CandidateEvidence v2；CLI 只输出聚合统计，不保存或显示候选内容。
- README、`AGENTS.md` 与 Open WebUI 源码没有修改；M1、M2 均未完整验收。

## 本机验证

在 `agent/` 执行：

```bash
PYTHONPATH=/Users/lfz/miniconda3/envs/adapter/lib/python3.11/site-packages \
  /Users/lfz/miniconda3/envs/open-webui/bin/python -m pytest -q
/Users/lfz/.local/bin/ruff check <本轮改动的 Python 文件>
```

结果为 Agent `226 passed, 2 skipped, 90 subtests passed`，Ruff 通过。根目录 M0／M1 CLI 回归 `4 passed`；Backend analysis／plan API `69 passed`；五个 analysis 相关 Vitest 文件 `52 passed`。新增负向测试覆盖缺栏、重复候选、样本错配、非法及越界数值、run-root 越界和读取中变化。

新增 JSON／Markdown 的 Prettier check 通过。前端以 `NODE_OPTIONS=--max-old-space-size=8192 npm run build` 完成唯一一次正式 build，Vite 用时 1 分 2 秒，日志为 `/tmp/bioagent-m1-14-frontend-build.log`（430,151 bytes）。首次沙箱内尝试在 Pyodide 准备阶段被本机代理 socket 的 `EPERM` 阻挡，未进入 Vite；相同命令改在沙箱外执行后成功。

工程知识保留 `engineering-knowledge-v1` 原文件及 SHA-256 `400699873d502bd9c95f044fe9a9cd061af3e7d6b92eae155833427f7d9e5920`，新增 v2 共 3,654 bytes，SHA-256 `a349760812ebcf0d2c26225e92625a926b702a20d0be6640d1f5989e952fee6a`。

## Cyclone 验证

以既有 contig artifact 编译 `virus_summary`。第一次目录 `analysis-m1-w2-manifest-dry-20260926-01` 因 source workflow 不产生 `taxonomy.tsv` 而返回 1；修正 adapter 完成边界后，新目录 `analysis-m1-w2-manifest-dry-20260926-02` 展开 21 个 jobs 并返回 0。Snakemake 明确标记为 dry-run，没有执行列出的 shell command；两个目录分别约 296 KiB、324 KiB。输入 contig stat 为 device `2048`、inode `192433619`、size `43017951`、mtime `1786610686`，验证后未改写。

对既有 run `analysis-20260813-160906-0f9eda85` 执行：

```bash
cd <BIOAGENT_REMOTE_WORKER_ROOT>/releases/<worker-sha256>
/home/liufangzhou/.pixi/envs/snakemake/bin/python candidate_evidence.py \
  --state /data/user/liufangzhou/runs/analysis-20260813-160906-0f9eda85/.bioagent/state.json \
  --summary
```

最终 worker release 为 `3c20a4e9f15df01f9977b30d20c1d3a03cb9db36814452db56df7f442b080d8d`。聚合结果为 8 个候选、72 项 observation、8 个 missing issue 和 8 个 dependency-identity limitation。来源表 3,269 bytes、8 行，SHA-256 `43b4c12f36838261c896ce481d8166314dcfa495a93faad7d1029f9e508e8551`；未输出候选 ID 或列内容，也未写入原 run。Cyclone `/data` 验证时可用约 365 GiB。

## 限制与回退

- parser 当前只把最终候选表作为 provenance 来源；原始 coverage、CheckV、NT／NR、VHDB 等多表链尚未连接。历史 run 没有冻结工具与参考 release，所有候选保留 limitation。
- Workflow 2 的 summary bundle 仍声明供后续注释使用的 taxonomy 角色，但 source workflow 没有独立 `taxonomy.tsv`；本轮只移除虚假的 Snakemake 完成 target，不宣称 W2→W6 taxonomy 交接已验证。
- 回退 Agent commit 即恢复 execution spec／planner v4 和只含 W1 的运行时 manifest。已保存的 v5 方案须重新编译；删除 v2 parser／release 不影响 v1 证据读取或历史引用。两个 dry-run 目录保留为失败与成功证据，不自动清理。
