# M1 第十五轮：Workflow 3 Capability Manifest 复现

日期：2026-09-26。源码基线：根仓库 `5c462f0`、Agent `12f9113`、Open WebUI `6cece2ff3`。

## 范围与结论

- 不做数据上传、真实 workflow 计算、M2、模型调用、数据库、API 或 UI 变更。
- Workflow 3 五阶段 manifest 与 execution spec／planner v6 已实现；v5 方案仍可读取，但启动前必须重新编译。
- W3 全阶段 DAG dry-run 通过，五个 manifest 标记为 `dry_run_validated`；EukaMarker 参考资产未登记为正式 release，W3 仍不可恢复。
- 新增 `engineering-knowledge-v3`，保留 v1／v2 可校验文件；README、`AGENTS.md` 与 Open WebUI 源码没有修改，M1／M2 均未完整验收。

## 本机验证

在 `agent/` 执行：

```bash
PYTHONPATH=/Users/lfz/miniconda3/envs/adapter/lib/python3.11/site-packages \
  /Users/lfz/miniconda3/envs/open-webui/bin/python -m pytest -q
/Users/lfz/.local/bin/ruff check <本轮改动的 Python 文件>
```

结果为 Agent `229 passed, 2 skipped, 93 subtests passed`，Ruff 通过。根目录 M0／M1 CLI 回归 `4 passed`；Backend analysis／plan API `69 passed`；五个 analysis 相关 Vitest 文件 `50 passed`。

新增 `engineering-knowledge-v3` 为 4,518 bytes，SHA-256 为 `5b044f6096f591933069a9e0838e9888ae1588fa8ce26b101d6dc142cbffea18`；当前三个不可变工程知识文件与 registry 合计 17,577 bytes。测试逐个核对 v1／v2／v3 文件哈希，并验证 catalog 身份或 manifest version 被篡改时 fail closed。

Prettier check 通过。首次沙箱内 build 在 Pyodide 准备阶段被本机代理 socket 的 `EPERM` 阻挡，尚未进入 Vite；相同命令在沙箱外完成唯一一次正式 build，Vite 用时 1 分 8 秒。完整输出写入 `/tmp/bioagent-m1-15-frontend-build.log`（430,697 bytes）。

## Cyclone DAG dry-run

通过现有 `RemoteWorkerClient` 部署 content-addressed worker `6b1ab59ebb0ffeca82f63b63c164d674e7ded58fb0b02b64baad327fc6f2946e`，在新目录 `analysis-m1-w3-manifest-dry-20260926-01` 编译 `host_summary`。execution spec v6 冻结以下五个 manifest：

```text
workflow3.host_mapping.bowtie2
workflow3.host_coverage.samtools
workflow3.host_blast.blastn
workflow3.host_integrate.posix
workflow3.host_summary.python
```

输入引用既有 run `analysis-20260813-160906-0f9eda85` 的 `v120` clean reads 与过滤 contig。Snakemake 展开 `host_mapping → host_coverage → host_blast → host_integrate → host_summary` 共 5 个 jobs，明确输出 `This was a dry-run (flag -n)` 并返回 0；结果目录没有生成文件。

dry-run 后输入 stat 为：

| 输入   | device |     inode |      bytes |      mtime |
| ------ | -----: | --------: | ---------: | ---------: |
| R1     |   2048 | 192219354 | 1717631486 | 1786609410 |
| R2     |   2048 | 192219367 | 1808575242 | 1786609410 |
| contig |   2048 | 192291871 |   43017951 | 1786610685 |

新 dry-run 目录为 300 KiB，`dry-run.json` 为 13,134 bytes；验证时 Cyclone `/data` 可用约 365 GiB。没有复制 FASTQ、扫描大型参考库、执行 workflow shell 或修改源 workflow。

## 限制与回退

- manifest 记录 EukaMarker Bowtie2／BLAST 数据库与两个 taxonomy 依赖，但没有补写其来源、许可、版本或完整哈希，因此不能作为正式 ReleaseSet。
- dependency identity 明确返回 `RECOVERY_DEPENDENCY_IDENTITY_INCOMPLETE`；W3 中断任务不能原地恢复，真实运行与恢复验收均未执行。
- 回退 Agent commit 即恢复 execution spec／planner v5 与只含 W1–W2 的 manifest catalog；已保存的 v6 方案须重新编译。将工程知识 active release 切回 v2 即可撤回 W3 工程引用，不需要数据库回滚。
