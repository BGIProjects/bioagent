# M1 第十二轮受控中断恢复复现记录

日期：2026-09-25–26。基线为根仓库 `51b469a`、Agent `386bb64`、Open WebUI `f4533d0df`。本轮只验证 A3 的受控中断恢复切片，不上传数据、不执行 FASTQ、不调用模型，也不开始 M2。

## 范围与实现

- 新 run 在 state v3 中追加 `recovery_contract` 与 `attempts`。方案、能力契约、dataset 双重指纹、worker、workflow、工具及已登记参考资产身份在首次执行前冻结；旧 state 不补写契约，不能原地恢复。
- attempt 的日志、telemetry、manifest 与 phase checkpoint 位于 `.bioagent/attempts/<序号>/`。计算结果继续共用原 run root，不复制 FASTQ 或大型结果。
- resume 只接受 `interrupted`。它在 run-local lock 内检查 runner、冻结上下文、输入、依赖和已完成 phase 的 SHA-256；通过后沿用原 project／priority，以新的入队时间追加一次 `manual_resume` attempt。重复请求不增加 attempt。
- 完整 checkpoint phase 会跳过；中断 phase 使用 Snakemake `--rerun-incomplete` 并强制重跑受控 rules。已发布 preliminary report 保持不可变。
- 当前依赖身份闭包只允许 diagnostic 与 Workflow 1 `read_qc`；其他 workflow 返回 `RECOVERY_DEPENDENCY_IDENTITY_INCOMPLETE`，不能借此宣称完整 A3。
- WebUI Backend 复用既有 execution row，重验 owner、项目分析权、对象关系、最新 revision 与 pending proposal，并追加既有 AnalysisEvent。浏览器只收到精简 recovery 状态，不收到 PID 或远端实体路径。

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

结果：Agent 195 passed、2 skipped；Backend 171 项；Vitest 45 项；Cypress 5 项，覆盖窄屏 `interrupted → 确认 → queued` 及唯读成员无恢复入口。新增回归包括方案／输入／worker／依赖／checkpoint 变化、暂时无法验证的 retryable 503、存活 runner、重复请求、完成 phase 跳过、中断 phase 强制重跑、未发布 screening 清理、已发布 preliminary 保留、项目关系及撤权。Agent 与 Backend 改动文件的 Ruff 通过，前端与文档 Prettier check 通过。

最终前端编译命令：

```bash
cd open-webui
NODE_OPTIONS=--max-old-space-size=8192 \
  npm run build > /tmp/bioagent-frontend-build-m1-12.log 2>&1
tail -60 /tmp/bioagent-frontend-build-m1-12.log
```

首次在沙箱内执行时，Pyodide 准备阶段因既有本机代理连接被禁止而停止，尚未进入 Vite；按环境要求在宿主重跑后 `✓ built in 1m`，静态站点写入 `build`。

## Cyclone 诊断与容量

使用当前 `RemoteWorkerClient` 建立一个 30 秒 diagnostic-only run，待专用 runner 启动后精确终止该 run 的 runner／scheduler PID，由新 scheduler reconciliation 标记 `interrupted`，再调用 resume 并检查 attempt 1 保留、attempt 2 完成。

首次执行时，SSH 建立 control master 阶段连接 `Cyclone` 超时；`./dev-services.sh status` 同样报告“SSH 连接暂时不可用”。该失败发生在 worker 部署与 `diagnostic_launch` 之前，没有建立 run 或终止 PID。用户恢复连接后先以中间 release 成功补验 `analysis-recovery-diagnostic-fa7ff7bbbd`；补齐 retryable 503 与未发布 screening 清理后 worker hash 改变，因此再以最终 release 重跑。以下为最终结果：

```text
run_id:             analysis-recovery-diagnostic-08bcd3df50
run_dir:            /data/user/liufangzhou/runs/analysis-recovery-diagnostic-08bcd3df50
worker_version:      9c5705ca7d24ded4d40cf841b996640094f518b5e60a6c4b8c150f66a1ad40ef
running -> [runner + scheduler 精确终止] -> interrupted
resume RPC:         queued
attempt 1:          initial / interrupted
attempt 2:          manual_resume / completed
final status:       completed
```

最终 recovery 摘要为 `attempt_count=2`、`current_attempt=2`、`blocker_code=null`；完成态的 `available=false` 符合只允许恢复 `interrupted` 的契约。诊断没有读取 FASTQ、workflow、参考库或调用模型，不能替代真实 workflow 恢复验收。

两个成功 diagnostic run 各为 32 KiB，合计 64 KiB，只包含 state、supervisor 与小型 attempt 控制产物。最终状态检查中三个本机服务均健康、Cyclone SSH 正常，`/tmp` 可用 191.7 GiB，三个服务日志合计约 20 KiB。没有数据库 schema 或 migration；实际业务增量设计上仅为少量 AnalysisEvent JSON。本轮没有复制 FASTQ、计算结果或参考库。

## 限制与回退

- Workflow 2–6、Workflow 1 非 `read_qc`、真实多样本以及 auto preliminary 发布前／后的远端恢复尚未验收。暂时无法验证身份时应返回 retryable 503 并保持 `interrupted`；身份变化或不完整则拒绝恢复并要求新建 plan／run。
- `failed` 与 `blocked` 不进入 resume。项目优先级沿用初次冻结值；resume 只更新入队时间，不读取后续优先级设置。
- 回退时先停止新 resume 请求并处理已入队／运行 attempt，再回退 WebUI 与 Agent。既有 state v3 的 additive 字段可保留审计；旧代码不会据此自动恢复。不得删除共享结果来回退，也不得恢复多个 per-run supervisor。

建议提交信息：

- 根仓库：`docs(m1): record controlled interrupted-run recovery`
- Agent：`feat: add controlled interrupted-run recovery`
- Open WebUI：`feat(analysis): resume interrupted runs`
