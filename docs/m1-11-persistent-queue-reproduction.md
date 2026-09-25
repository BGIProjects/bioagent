# M1 第十一轮持久队列复现记录

日期：2026-09-25。基线为根仓库 `2ac50b8`、Agent `6060316`、Open WebUI `72bd8d086`。本轮只验证 A3 持久队列，不上传数据、不运行 FASTQ、不调用模型，也不启动 M2。

## 范围与状态

- 每个 run root 只有一个 `bioagent-scheduler-<run-root-hash>`；队列 metadata 保存在各 run 的 `.bioagent/state.json`，未新增业务表或 queue database。
- queue policy v1 冻结项目及路由优先级；默认 aging 为 24 小时。资源不足为 `waiting_resources`，恢复后重新准入。
- scheduler 重启会接管 queued／waiting，并监看 PID、boot ID 与命令匹配的既有 runner；runner 消失仍为 `interrupted`，不会自动重跑。
- auto 初筛后的完整流程等待会保留 preliminary report 与 full-analysis checkpoint；本轮未执行真实 auto workflow。

## 本机验证

```bash
cd agent
PYTHONPATH=/Users/lfz/miniconda3/envs/open-webui/lib/python3.11/site-packages \
  /Users/lfz/miniconda3/envs/adapter/bin/python -m pytest -q

cd ../open-webui/backend
BIOAGENT_REMOTE_DATA=false WEBUI_SECRET_KEY=test-only-key PYTHONPATH=. \
  /Users/lfz/miniconda3/envs/open-webui/bin/python -m unittest \
  open_webui.routers.test_analysis_metadata \
  open_webui.routers.test_analysis_plans_api \
  open_webui.routers.test_analysis_grouping \
  open_webui.routers.test_analysis \
  open_webui.routers.test_analysis_projects \
  open_webui.routers.test_analysis_datasets_api \
  open_webui.routers.test_analysis_benchmark \
  open_webui.routers.test_openai_analysis_metadata \
  open_webui.utils.test_analysis_run_delivery \
  open_webui.utils.test_analysis_grouping \
  open_webui.utils.test_analysis_datasets \
  open_webui.utils.test_analysis_planner

cd ..
npm run test:frontend -- --run \
  src/lib/apis/analysis/index.test.ts \
  src/lib/utils/analysisRun.test.ts \
  src/lib/components/analysis/AnalysisPage.contract.test.ts

env -u ELECTRON_RUN_AS_NODE npx cypress run \
  --config-file cypress.project-ui.config.cjs \
  --config specPattern=cypress/e2e/analysis-routing.cy.js,baseUrl=http://127.0.0.1:5173
```

结果：Agent 178 passed、2 skipped；Backend 165 项；Vitest 43 项；Cypress 3 项。Cypress 需要单次清除宿主的 `ELECTRON_RUN_AS_NODE=1`，否则 Electron 会被当成 Node 启动。

本轮改动 Python 文件的 Ruff、前端与文档的 Prettier check 均通过。最后一次有效 build 使用：

```bash
cd open-webui
NODE_OPTIONS=--max-old-space-size=8192 \
  npm run build > /tmp/bioagent-frontend-build-m1-11.log 2>&1
tail -40 /tmp/bioagent-frontend-build-m1-11.log
```

build 于 57.09 秒完成。沙箱内首次准备 Pyodide 时被宿主代理权限阻断，随后按环境要求在宿主重跑；这次失败发生在 Vite build 前，不是源码编译错误。

## Cyclone 隔离诊断

诊断目录：`/data/user/liufangzhou/runs/m1-11-diagnostic-20260925T030716Z`。通过当前 `RemoteWorkerClient` 提交四个 1–2 秒 diagnostic-only job；首个 low job 只模拟一次准入阻断，其后提交 high 与 high+emergency。另一个 job 进入等待后，精确中止隔离 session `bioagent-scheduler-82766f4f8cbf`，再由 snapshot 启动同一 run-root scheduler。

观察到的转移与结果：

```text
analysis-diag-low:       queued -> waiting_resources -> running -> completed
completion order:       analysis-diag-emergency -> analysis-diag-high -> analysis-diag-low
analysis-diag-restart:   queued -> waiting_resources -> [scheduler stopped] -> running -> completed
diagnostic starts:       low=1, high=1, emergency=1, restart=1
```

等待状态保存 `DIAGNOSTIC_RESOURCE_WAIT`、检查时间、冻结优先级和队列位置。补齐后另在 `/data/user/liufangzhou/runs/m1-11-stage-diagnostic-20260925T031135Z` 以一个 1 秒任务确认 `waiting_stage=full_analysis`；真实任务的 screening／full-analysis 资源路径另有 Agent 单元测试。

主诊断目录为 72 KiB，补修确认目录为 24 KiB，合计 96 KiB。诊断只写 state、supervisor 与空／极小日志；未访问原始 FASTQ、Workflow、参考库或模型。本机现有 SQLite 未新增 schema，本轮不会因队列明显增长。

## 限制与回退

- 本轮没有 attempt 历史、产物级一致性检查或人工 resume；`interrupted` 仍需后续显式恢复设计。
- 没有抢占运行中任务；aging 只改变尚未准入任务的顺序。项目优先级在确认执行时冻结，之后的项目设置只影响新任务。
- 回退时先停止新准入并处理在途 runner，再停止对应 run-root scheduler，最后回退 Agent 与 WebUI 代码；不可同时恢复多个 per-run supervisor 与新 scheduler。既有 state 和诊断目录可保留审计，删除隔离诊断目录不影响业务 run。

建议提交信息：

- 根仓库：`docs(m1): record persistent queue scheduling`
- Agent：`feat: add durable analysis queue scheduler`
- Open WebUI：`feat(analysis): expose durable queue status`
