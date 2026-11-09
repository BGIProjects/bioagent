# M1 第六轮：智能模式续跑与路由控件复现记录

## 范围与基线

本轮基线为根仓库 `24019dc`、Agent `13956ba`、Open WebUI `fdea57fcb`。只实现 A3 前三项及 `/analysis` routing tab 修复；不实现上传、持久化优先级队列、`waiting_resources`、重新排队、恢复操作或大型知识库，不新增数据库表、迁移、模型或环境变量。

## 模式矩阵

| 请求模式  | 有成对 reads 时                                   | 无成对 reads 时       | 可用报告                                      |
| --------- | ------------------------------------------------- | --------------------- | --------------------------------------------- |
| auto      | 5% 初筛 → preliminary → 资源检查 → 已确认完整 DAG | standard／`full_only` | 执行中 preliminary；成功后 preliminary＋final |
| emergency | 5% 初筛 → preliminary → 结束                      | standard／`full_only` | preliminary                                   |
| standard  | 不初筛，直接执行已确认完整 DAG                    | 不变                  | 成功后 final                                  |

auto 的 A／B 只记录高／低信号，不决定 pipeline 是否结束。完整资源不足时状态为 `blocked`，preliminary 保留；队列等待和恢复不在本轮范围。

新方案保留 execution spec v2，使用 planner v2、`routing_policy_version=2` 和 `completion_behavior=screen_then_full|screen_only|full_only`。旧方案仍可读，启动时以 `PLAN_ROUTING_OBSOLETE` 要求重新生成。

## 报告与 WebUI

初筛完成后原子写入 run-local `.bioagent/preliminary-telemetry.json`；首次生成时间、证据 JSON 路径与文件 SHA-256 固定，完整分析只写 final telemetry，不覆盖快报。state v3 的 `reports` 只登记路径和小型元信息，不把报告正文或大文件写入 SQLite。历史单一 `report` 依 `report_kind` 映射为 preliminary 或 final。

状态接口返回 `reports`；报告下载必须传 `kind=preliminary|final`，两类均沿用项目／会话鉴权及远端证据复算。Agent snapshot 以 `report_kind` 选择对应 telemetry。

tab 始终送出 auto 的根因是 Svelte 反应式语句只调用函数，未直接读取 `routingMode`。现在 `desiredRouting` 直接由 `routingMode` 构建；连续切换仍用请求序号拒绝迟到回应，旧模式方案不能启动。历史对话优先恢复已保存模式。

## 复现命令与结果

```bash
cd agent
PYTHONPATH=. /Users/lfz/miniconda3/envs/adapter/bin/python -m unittest \
  tests.test_adaptive_routing tests.test_deterministic_planner \
  tests.test_workflow_adapters tests.test_analysis_runner tests.test_remote_worker

cd ../open-webui
BIOAGENT_REMOTE_DATA=false DATA_DIR="$test_root/data" \
  DATABASE_URL="sqlite:///$test_root/test.db" WEBUI_SECRET_KEY=test-only-key \
  PYTHONPATH=backend /Users/lfz/miniconda3/envs/open-webui/bin/python -m unittest \
  open_webui.routers.test_analysis open_webui.routers.test_analysis_plans_api \
  open_webui.utils.test_analysis_run_delivery open_webui.utils.test_replay_report \
  open_webui.utils.test_report_evidence

npm run test:frontend -- --run \
  src/lib/utils/analysisRun.test.ts src/lib/apis/analysis/index.test.ts

env -u ELECTRON_RUN_AS_NODE npx cypress run --browser electron \
  --config-file cypress.project-ui.config.cjs \
  --spec cypress/e2e/analysis-routing.cy.js
```

结果：Agent 68 项通过、2 项 skip；Backend 66 项通过；Vitest 34 项通过；Cypress 2 项通过。Cypress 实际点击智能、标准、紧急三个 tab，断言三次 `POST /plans` 的 mode 为 `auto → standard → emergency`，并覆盖 standard 慢回应及两类报告按钮。所有浏览器 API 都是合成拦截，没有模型或计算请求。

随后运行相关 Ruff、Prettier check，最后仅运行一次：

```bash
NODE_OPTIONS=--max-old-space-size=8192 npm run build \
  >/tmp/bioagent-m1-routing-build.log 2>&1
```

## Cyclone dry-run 与容量

使用 data root 内两个 logical path：

```text
/data/user/liufangzhou/datasets/BJ-2024-615_1.fastq.gz
/data/user/liufangzhou/datasets/BJ-2024-615_2.fastq.gz
```

worker health 的 control Python 为 `/home/liufangzhou/.pixi/envs/snakemake/bin/python`。来源解析后大小分别为 126,682,083 与 172,927,531 bytes；quick preflight 仅读取 1,000 对 records、737,594 uncompressed bytes，结果 `ready`。

新目录 `Cyclone:/data/user/liufangzhou/runs/analysis-m1-routing-dry-run-20260913-1943/` 的 Workflow 1 fastp DAG dry-run 返回 0，只建立 DAG，没有执行显示的 shell command。目录共 13 个文件、224,759 bytes。未执行 5% 初筛、完整 workflow 或云端模型。

远端资源历史库 `/data/user/liufangzhou/runs/.bioagent/resource-history.sqlite3` 只读核对为 32,768 bytes，SHA-256 `af03daccd9b6625733b7a41c829fc747f0e2a60dab5d50d6e8fa5411fc258ca5`；本轮没有 schema 或业务数据库迁移。最终前端 build 日志为 430,305 bytes，`build/` 为 299,172 KiB、5,635 个文件；未生成 Cypress 截图或视频。

## 限制与回退

本轮真实远端验证只到 source resolve、quick preflight 和单规则 DAG dry-run，不代表快速初筛、完整 Workflow 1–6、多样本、生物学结果或 A3 全量验收。资源不足仍直接 `blocked`；`waiting_resources`、持久排序、重新排队和恢复留待后续。

回退时先停止新准入并核对在途任务，再分别回退 Agent 与 Open WebUI 代码；根仓库仅回退文档。没有数据库迁移或配置需要回退。新 state 的 `reports` 与 preliminary 文件应保留以供新代码读取；旧代码不认识该列表时不会展示阶段报告，因此不要在仍需下载快报时单独回退 WebUI／Agent 契约。
