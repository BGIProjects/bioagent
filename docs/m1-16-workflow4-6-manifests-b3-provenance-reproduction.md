# M1 第十六轮 W4–W6 manifest 与 W2 provenance 复现记录

日期：2026-09-27。范围仅含 Agent 能力契约、工程知识和 W2 只读证据解析；未上传数据、迁移数据库、修改 UI、调用模型、执行 workflow shell 或扫描大型参考库。

## 变更与边界

- W4／W5／W6 新增 3／3／5 个 CapabilityManifest；execution spec／planner 升至 v7，v6 方案启动前须重新编译。
- 新增小型 `engineering-knowledge-v4`；v1–v3 文件保持原样且仍通过哈希验证。
- W2 最终表只提供候选 roster；九项指标改从 coverage、CheckV、NR 三张上游表取值和定位。CLI summary schema 为 v2，只返回四个来源与计数。
- 未接 Assessment、规则、报告、持久化、API 或 UI。W5 病毒 reference 是执行输入；W6 的 CheckV／VIGOR／DRAM-v 数据库不是本轮发布的正式资产。

## 本机验证

在 `agent/` 执行：

```sh
PYTHONPATH=/Users/lfz/miniconda3/envs/open-webui/lib/python3.11/site-packages \
  /Users/lfz/miniconda3/envs/adapter/bin/python -m pytest -q
/Users/lfz/.local/bin/ruff check adapter.py candidate_evidence.py deterministic_planner.py \
  pipeline_spec.py workflow_catalog.py tests/test_adapter.py \
  tests/test_candidate_evidence_parser.py tests/test_deterministic_planner.py \
  tests/test_deterministic_runtime.py tests/test_engineering_knowledge.py \
  tests/test_remote_worker.py tests/test_resource_calibration.py \
  tests/test_workflow_adapters.py tests/test_analysis_runner.py
```

结果为 240 passed、2 skipped，变更檔 Ruff 通过。直接执行全 repo Ruff 另报告 8 个既有问题，位于 `m1_assets.py`、`taxonagent_adapter.py`、`tests/test_m1.py` 与 `tools/watch.py`，本轮未修改。根目录明确指定的 M0／M1 CLI 测试为 4 passed；Backend analysis／plan 回归为 96 tests；五个 analysis 相关 Vitest 文件为 52 tests。

Prettier check 通过。首次沙箱内命令在 Pyodide 准备阶段被本机代理 socket 的 `EPERM` 阻挡，尚未进入 Vite；同一命令在沙箱外完成唯一一次正式 8 GiB build，Vite 用时 59.18 秒。完整输出位于 `/tmp/bioagent-m1-16-frontend-build.log`（430,698 bytes）。

## Cyclone dry-run

先以 `ssh -o ClearAllForwardings=yes Cyclone true` 检查连线，再部署内容定址 worker `93e033860220e860d39dd5840febe8fb32263aad9d71af1f2cd778d2060ab510`。新建以下 run-local 目录，仅调用 Snakemake dry-run：

| Workflow | Run                                       | 输入                                          |          DAG 结果 | 目录大小 |
| -------- | ----------------------------------------- | --------------------------------------------- | ----------------: | -------: |
| W4       | `analysis-m1-w4-manifest-dry-20260927-03` | 既有 W1 `v120` clean reads                    |  7 jobs，return 0 |  240 KiB |
| W5       | `analysis-m1-w5-manifest-dry-20260927-03` | 同一 clean reads＋既有 putative viral contigs |  7 jobs，return 0 |  212 KiB |
| W6       | `analysis-m1-w6-manifest-dry-20260927-03` | 848-byte example FASTA＋94-byte taxonomy      | 12 jobs，return 0 |  668 KiB |

三个输出都含 `This was a dry-run (flag -n)`，没有执行列出的 shell command。输入大小核对后仍为 1,717,631,486、1,808,575,242、79,823、848 与 94 bytes；`/data` 尚余 365 GiB。三个 run 都返回 `RECOVERY_DEPENDENCY_IDENTITY_INCOMPLETE`，因此只支持 `dry_run_validated`，不代表真实工具、参考库或恢复验收。

## W2 只读聚合

在既有完成 run `analysis-20260813-160906-0f9eda85` 上直接运行最终 worker 的 `candidate_evidence.py --summary`，未写回原 run。结果：

- 8 candidates、72 observations、8 missing issues、8 dependency limitations；
- `virus_candidates.csv`：3,269 bytes／8 rows；
- `coverage.csv`：1,175 bytes／11 rows；
- `quality_summary.tsv`：1,319 bytes／11 rows；
- `nr_result.csv`：2,962 bytes／11 rows。

真实 coverage 与最终汇总存在 6 个约 `1e-16` 的序列化差异，因此实现只对 `Profile_cov` 允许 `1e-15` 绝对误差；其他指标仍要求十进制值完全相等，实质 coverage 差异也 fail closed。负向测试另覆盖来源越界、symlink、缺档／缺栏、重复候选、候选缺上游列、非法数值、数值不一致及读取中变化；缺值不转成 0。

## 未完成项

正式参考 release、许可、完整哈希、ReleaseSet、真实 W4–W6 运行、W2–W6 恢复、Assessment、领域规则、报告／API／UI 接入及专家审核仍未完成。README 没有新入口或配置，保持不变；Open WebUI 预期只有回归验证，不产生源码变更。
