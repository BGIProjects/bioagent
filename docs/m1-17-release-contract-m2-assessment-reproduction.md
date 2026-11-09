# M1 第十七轮 release 契约与 M2 确定性研判复现记录

日期：2026-09-27。本轮只增加小型 release／依赖身份解析与 Workflow 2 确定性工程 findings；未上传数据、迁移数据库、修改 UI、调用模型、执行 Snakemake 或扫描大型参考库。

## 变更与边界

- `candidate-evidence-v2` capability release 和 `b3-engineering-integrity-rules-v1` 逐档校验 SHA-256；新增资产共 3,118 bytes，整个新增 Agent 程式、资产与测试约 32 KiB。
- release resolution 从 execution spec、capability contract 与 recovery dependency identity 区分 `complete`、`incomplete`、`unavailable`。旧 run、manifest 版本不符、缺少软件／reference／parser／workflow 身份均 fail closed；`RECOVERY_CHECK_UNAVAILABLE` 保持可重试。
- NT／NR 的既有来源压缩包 checksum 只可登记为 observation，不证明已安装 BLAST 数据库内容完整，也不提升 Workflow 2–6 的恢复资格。没有新增 reference release 或 execution spec 版本。
- 五条规则仅检查缺失、冲突、依赖身份、来源相关性与领域资产缺口。所有结果保持 `Assessment(status="not_generated", review_status="pending")`，provider／model 为 `none`，不生成 claim、分类或支持程度。
- `candidate_assessment.py --state <run>/.bioagent/state.json --summary` 只输出聚合资料，不接受输出路径、不写回 run，也不输出候选 ID 或序列。本轮没有 API、报告、持久化或专家页面。

## 本机验证

在 `agent/` 执行：

```sh
PYTHONPATH=/Users/lfz/miniconda3/envs/open-webui/lib/python3.11/site-packages \
  /Users/lfz/miniconda3/envs/adapter/bin/python -m pytest -q
/Users/lfz/.local/bin/ruff check candidate_assessment.py evidence_contract.py \
  remote_client.py tests/test_candidate_assessment.py
```

结果为 248 passed、2 skipped；变更档 Ruff 通过。新增与既有 W2 parser 的定向测试为 27 passed。根目录 M0／M1 CLI 回归为 4 passed；Backend analysis／plan 回归为 96 tests；五个 analysis 相关 Vitest 文件为 50 passed。

release 负向测试覆盖档案篡改、重复／缺少 release、manifest 版本不符、缺少依赖、旧 state、暂时不可读、非法 finding evidence ID 与 checksum observation 不得提升身份。CLI 回归确认 summary 不含候选 ID、逐项 observations 或 draft。

Prettier check 通过。全 Agent Ruff 仍报告 8 个既有问题，位置与第十六轮相同：`m1_assets.py`、`taxonagent_adapter.py`、`tests/test_m1.py` 与 `tools/watch.py`；本轮变更档没有新增问题。首次沙箱内 build 在 Pyodide 准备阶段被本机代理 socket 的 `EPERM` 阻挡，尚未进入 Vite；随后在沙箱外完成唯一一次正式 8 GiB build，client／SSR 分别用时 54.98 秒／1 分 6 秒。完整输出为 `/tmp/bioagent-m1-17-frontend-build.log`（430,151 bytes）。

## Cyclone 唯读实证

先执行 `ssh -o ClearAllForwardings=yes Cyclone` 连通性检查。为遵守“Cyclone 仅唯读验证”，本轮没有发布新 worker；验证程序经 SSH stdin 进入内存，复用已部署且 `candidate_evidence.py` 哈希相同的 worker parser。既有 run `analysis-20260813-160906-0f9eda85` 得到：

- 8 candidates、72 observations、8 missing issues、8 dependency limitations；
- 8 个 `not_generated` Assessment、0 个 draft；
- `EVIDENCE_MISSING`、`DEPENDENCY_IDENTITY_INCOMPLETE`、`CORRELATED_EVIDENCE` 与 `DOMAIN_ASSETS_PENDING` 各 8 项；
- 四个来源大小依次为 3,269、1,175、1,319、2,962 bytes，解析前后 size／mtime 未变且 SHA-256 再核对通过；远端写入为 0。

来源 SHA-256 分别为：

| Artifact               | SHA-256                                                            |
| ---------------------- | ------------------------------------------------------------------ |
| `virus_candidates.csv` | `43b4c12f36838261c896ce481d8166314dcfa495a93faad7d1029f9e508e8551` |
| `coverage.csv`         | `6236581543610056a6cc974ef3c488b0bd1a1374bb528ae48c82babcc84c0a67` |
| `quality_summary.tsv`  | `1d37b83e7723249a85c5c92ed8e74ec85ac7498f9c814e66869e30b9ef031fd1` |
| `nr_result.csv`        | `85011722f644bf7f0fd1caf4cbc0ea075303aa102d045c8c1de317aeb2d98b16` |

只读取 NR 目录 164 个、7,871 bytes 的 `.md5` 小档，聚合 SHA-256 为 `4abe6e868efe9388f2336675d3b18ea1a17ef96c4b82a1a9c9c6f45d9e70ffa1`；NT 目录为 92 个、4,784 bytes，聚合 SHA-256 为 `b5394360709a08824e9cbf57537fa37235e0301044b574457c876534574fcb45`。两者均明确标记 `source_archive_checksums_only`，没有递归读取已安装数据库内容。

## 未完成项

M1／M2 仍未完成。W1–W6 正式 reference release、许可、完整内容哈希、ReleaseSet 与真实运行验收仍缺；W2–W6 不可受控恢复，W1 真实中断恢复也未实演。B3 尚缺核准领域规则与知识、正向 Assessment、报告／API／UI／持久化、专家冻结集和审核。M0 本地模型、B2 与 C1 的既有缺口不变。

本轮未新增环境变量或数据库；`AGENTS.md`、Open WebUI 源码与 README 均未修改。回退只需移除 Agent 新模块／小型资产与对应 README 入口，不影响历史 run、现有报告或业务库。
