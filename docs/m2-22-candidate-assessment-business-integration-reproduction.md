# M2 第二十二轮：Workflow 2 工程研判业务接入复现记录

## 1. 范围与结论

本轮把既有 Workflow 2 CandidateEvidence v2 与确定性工程 findings 接入授权业务 revision 和指定版本 HTML 报告。没有核准领域规则或知识时，所有 Assessment 继续固定为 `not_generated`，不调用 MiniMax-M3，也不产生分类、支持程度或生物学结论。

本轮不做资料上传、条件接入、新 workflow 计算、本地模型、训练、数据库 migration 或前端修改。B3 与 M2 仍未整体完成。

## 2. Agent 与 Cyclone 只读接口

Agent 新增：

```text
POST /analysis/runs/candidate-assessments
POST /v1/analysis/runs/candidate-assessments
```

请求只含远端 `run_dir` 和 1–5 个明确 candidate ID。worker 要求 run 目录是配置 run root 下的 canonical path，然后读取 run-local state、Workflow 2 四个小型来源与已发布工程 release；不接受输出路径，也不写 state、报告或来源文件。

响应按 candidate ID 排序，包含：

- 四个来源的 run-relative path、SHA-256、bytes 与 rows；
- release resolution、缺失依赖及限制；
- 完整 CandidateEvidence v2 observation／issue；
- 固定 `status=not_generated`、`review_status=pending`、`provider=model=none` 的 Assessment 及工程 findings；
- canonical JSON 的 `packet_sha256`。

Agent 正文限制 60 KiB，为 Backend 64 KiB 数据库限制预留信封空间。五个合成候选的实际完整 JSON 为 47,089 bytes；候选过多、重复、未知或正文超限均拒绝。

## 3. `python -S` 部署边界与修正

首次 Cyclone 验证中 snapshot 正常，但 control worker 直接导入 assessment 契约时返回 `No module named 'pydantic'`。原因是持久 control worker 按设计由 `/home/liufangzhou/.pixi/envs/snakemake/bin/python -S` 启动，而契约模型需要 runner 环境的 site packages。

最终实现保持 control worker 为纯标准库：它以固定参数列表启动同一配置的 runner Python 子进程，不使用 shell，超时 60 秒，只接收单个有界 JSON；子进程完成 Pydantic 解析与 release 校验。自动测试再以 `python -S remote_worker.py rpc` 启动真实 control 入口，确认可桥接到 assessment runtime。没有恢复多个环境、没有使用旧 `/data` 环境，也没有修改 Workflow 源码。

## 4. WebUI 权限、验证与持久化

业务入口：

```text
POST /api/v1/analysis/projects/{project}/chats/{chat}/candidate-assessments
```

只有项目 `can_review` 成员可调用。服务端先确认 run 已登记到同一 chat，并只使用登记的远端 run directory；随后独立验证：

- packet SHA-256 与 64 KiB 上限；
- run ID、明确选择的 candidate 集合和 observation ID 唯一性；
- finding 只能引用包内 evidence ID；
- Assessment 必须保持 `not_generated/pending`，没有 draft，provider／model 为 `none`，错误码为 `DOMAIN_ASSETS_PENDING`。

验证通过后追加 `generated` AssessmentRevision，报告身份固定为 `workflow2_candidate_assessment` / `candidate-assessment-packet-v1`，report SHA-256 使用 packet digest。项目列表显示 `assessment_status=not_generated`；既有指定 revision HTML 报告完整转义并展示该包。普通成员、仅分析成员、未知 run、远端不可用、包体篡改及版本冲突均不写库。

## 5. Cyclone 验证

开始前执行：

```bash
ssh -o ClearAllForwardings=yes -o ConnectTimeout=8 Cyclone true
```

只读检查通过。content-addressed worker 版本：

```text
a45fe40ea991e89198fa0021ebd0e050cd1abd409bd1e2b000c35acb8086ca89
```

在既有完成 run `analysis-m118-priority-full-r2-20260930` 上，snapshot 返回 found；使用故意不存在的 candidate ID 调用新 operation，精确返回 `ASSESSMENT_CANDIDATE_UNKNOWN`，证明部署、runner bridge、state／四来源解析和 release 校验均已实际执行。安全审核拒绝读取整列真实 candidate ID，因此本轮未把远端验证扩大为正向候选内容导出；正向包体由本机真实 parser 契约测试覆盖。该限制不是 workflow 失败。

## 6. 自动验证

Agent 定向与 control bridge：

```bash
/Users/lfz/miniconda3/bin/conda run -n adapter \
  python -m pytest -q \
  tests/test_candidate_assessment.py \
  tests/test_remote_worker.py \
  tests/test_adapter.py
```

Backend 使用测试专用 secret、`BIOAGENT_REMOTE_DATA=false` 与 importlib 模式，按文件隔离运行：

```bash
/Users/lfz/miniconda3/bin/conda run -n open-webui \
  python -m pytest -q --import-mode=importlib \
  open_webui/utils/test_analysis_candidate_assessments.py \
  open_webui/utils/test_analysis_planner.py

/Users/lfz/miniconda3/bin/conda run -n open-webui \
  python -m pytest -q --import-mode=importlib \
  open_webui/routers/test_analysis_projects.py
```

最终 Agent 一般测试为 265 passed、2 skipped，另有 100 subtests passed；报告 runtime 测试为 11 passed，合计 276 passed、2 skipped。Backend 两组相关测试为 9＋17，共 26 passed。变更文件 Ruff、文档 Prettier 与 `git diff --check` 通过。本轮没有前端变更，按项目验证顺序不重复运行 Vitest 或前端 build。

## 7. 容量、限制与回退

开始和结束时本机约 184 GiB 可用，仓库约 2.4 GiB。新增内容只有代码、测试与文档；数据库不新增表，不保存 FASTQ、完整来源表、HTML、日志或模型结果。

回退时可停用新 Agent／Backend endpoint；既有 revision 是追加式小型记录，保留后仍可由旧 A4 历史接口读取。删除 revision 会破坏审核历史，因此不作为代码回退步骤。无核准领域资产时继续交付已验证数值与不足说明，不自动调用云端模型补齐。
