# M1 第五轮：样本分组与技术重复确认

日期：2026-09-13。前序为[第一轮资产与评测](m1-01-assets-evaluation-implementation-record.md)、[第二轮项目权限](m1-02-projects-implementation-record.md)、[第三轮页面入口](m1-03-project-ui-implementation-record.md)及[第四轮背景版本与滚动修复](m1-04-dataset-metadata-implementation-record.md)。本轮只补 A2 技术重复确认，完整 A2、M0／M1 仍未完成。

## 操作与版本语义

在 `/analysis` 自己的会话中选择自己建立的数据集，点击“修订配对与角色”。已就绪数据现在也可修订；仍需项目分析权限，他人会话只读，其他建立者的数据不能修订。

编辑 `run_id → sample_id`，检查修改前／后样本及配对路径。共用 sample_id 的多个 run 必须逐样本勾选“确认这些 run 属于同一样本的技术重复”；修改身份或配对会清除确认。它不是病例／对照分组，背景中的名称、表型及对照备注不参与计算。

保存会生成新 dataset revision，沿用预检；不会自动生成方案或启动 Workflow。新数据 revision 的背景为未记录，不自动继承。取消丢弃草稿；失败保留输入，409 时重新选择数据集载入最新版本后修改。切换会清空草稿并隔离迟到响应。

PATCH `/api/v1/analysis/datasets/{id}` 在原 `base_revision`、`artifacts` 外增加 `confirmed_groups: [{artifact_id, sample_id}]`，无技术重复时为空数组。后端要求精确清单，拒绝缺漏、重复、多余项；两条 artifact 正规化路径均拒绝同一 artifact 内重复 run_id。确认保存在既有 revision 的 `checks.grouping_confirmation`，包含完整 artifacts 哈希、分组摘要、确认清单、操作者与时间；全量预检保留该字段。模型摘要排除这段含路径的审核记录。

新编译和新执行读取确切数据版本并验证确认。历史多 run 版本缺少确认时返回 409，须保存新版本并重新生成方案；单 run 历史不受此项限制。旧方案、报告和已启动计算不改写。没有新增数据库表、迁移或 Agent 执行字段。

## 复现与验证

基线：根仓库 `cd3e8fd`、open-webui `056e73e24`、agent `61a99bb`。环境沿用 Node 22.23.2、已有 Chrome 152、Cypress 13.17.0 与本机 Conda；不下载浏览器。所有修改测试使用隔离 SQLite、合成小文件或 API 桩；没有真实业务写入、FASTQ 上传或计算。

根目录执行：

```bash
BIOAGENT_REMOTE_DATA=false DATA_DIR=/tmp/bioagent-m1-grouping-tests \
  DATABASE_URL=sqlite:////tmp/bioagent-m1-grouping-tests.db WEBUI_SECRET_KEY=test-only-key \
  PYTHONPATH=open-webui/backend /Users/lfz/miniconda3/envs/open-webui/bin/python -m unittest \
  open_webui.utils.test_analysis_grouping open_webui.routers.test_analysis_grouping \
  open_webui.utils.test_analysis_datasets open_webui.routers.test_analysis_metadata \
  open_webui.routers.test_analysis_plans_api open_webui.routers.test_analysis_datasets_api \
  open_webui.utils.test_report_evidence open_webui.utils.test_analysis_run_delivery \
  open_webui.utils.test_replay_report > /tmp/bioagent-m1-grouping-python.log 2>&1
PYTHONPATH=agent /Users/lfz/miniconda3/envs/adapter/bin/python -m unittest \
  tests.test_workflow_adapters.PipelinePreparationTests.test_technical_replicates_keep_run_identity_and_share_sample \
  > /tmp/bioagent-m1-grouping-adapter.log 2>&1
```

Python **90 项通过**（含继承的项目权限回归，非 90 项新增测试），Agent adapter **1 项通过**。覆盖精确清单、run 唯一性、合并／拆分、旧版本准入、预检保留、准确版本编译、旧报告回放、修订冲突及权限撤销；远端暂不可用使用模拟异常验证 retryable 503。Adapter 仅生成并核对 samples.txt 的两 run／一样本映射，不执行 Workflow。

在 open-webui 目录执行：

```bash
export PATH=/Users/lfz/.nvm/versions/node/v22.23.2/bin:$PATH
./node_modules/.bin/vitest run src/lib/utils/analysisGrouping.test.ts \
  src/lib/apis/analysis/index.test.ts src/lib/utils/analysisRun.test.ts \
  src/lib/utils/projectNavigation.test.ts > /tmp/bioagent-m1-grouping-vitest.log 2>&1
# 临时前端，验证结束停止；不替换正常 5173 服务。
npm run dev:fast -- --host 127.0.0.1 --port 5175 > /tmp/bioagent-m1-grouping-vite.log 2>&1
# 另一终端分别执行，specPattern 必须覆盖配置默认的 project-ui。
env -u ELECTRON_RUN_AS_NODE ./node_modules/.bin/cypress run \
  --config-file cypress.project-ui.config.cjs --browser chrome \
  --config 'specPattern=cypress/e2e/dataset-metadata.cy.js,screenshotsFolder=/tmp/bioagent-m1-grouping-screenshots' \
  > /tmp/bioagent-m1-grouping-metadata-cypress.log 2>&1
env -u ELECTRON_RUN_AS_NODE ./node_modules/.bin/cypress run \
  --config-file cypress.project-ui.config.cjs --browser chrome \
  --config screenshotsFolder=/tmp/bioagent-m1-grouping-screenshots \
  > /tmp/bioagent-m1-grouping-cypress.log 2>&1
```

Vitest **36 项通过**；Cypress **34 项通过**（背景／分组 16、项目 UI 18）。覆盖 1440×900、1280×720、1024×768、390×844，另保留原有等效 125% 项目 UI 测试。桌面通过 Chrome CDP 原生 mouseWheel 验证 scrollTop 变化、确认项及保存可见；截图人工检查了文件树与对话输入框仍可达。

实际浏览器验证修正两处问题：旧表单嵌套动态绑定触发 `role is not defined`，改为明确更新 record；旧 editor 自带高度限制形成第二层滚动，移除后统一复用第四轮滚动容器。未忽略浏览器异常或使用强制点击掩盖裁切。

Ruff、Prettier check 均通过。最后一次前端构建使用 `NODE_OPTIONS=--max-old-space-size=8192 npm run build`，退出码 0；完整日志 `/tmp/bioagent-m1-grouping-build.log`。未运行 `npm run check`。构建仍有既有 Svelte／依赖警告，本轮没有增加全局按钮或菜单框架。

## 产物、落地与回退

验证产物已写入新的 `Cyclone:/data/user/liufangzhou/runs/m1-sample-grouping-20260913-1810/`，不覆盖旧记录。本地归档 `/tmp/bioagent-m1-sample-grouping-20260913-1810/`：13 文件、1,795,678 bytes（约 1.71 MiB），远端含目录占用 1,799,774 bytes。`manifest.sha256` 自身 SHA-256 为 `9c3e90616a51367322057ef8c132a7b6ae62df7f24e1806ff01c8fb248e2a35c`，远端逐文件校验全部通过；`source-files.sha256` 记录本轮前后端及 adapter 测试源码身份。

保留两张小型截图 `grouping-confirmation-wheel.png`、`grouping-saved-desktop.png`，日志为 `python.log`、`adapter.log`、`vitest.log`、`cypress.log`、`metadata-cypress.log`、`ruff.log`、`prettier.log`、`build.log`、`readonly.log`。其余本地截图约 3.43 MiB，测试 SQLite 为 843,776 bytes；归档、临时日志、截图和测试库总量仍低于 10 MiB，不含原有构建缓存。

本机验证时没有既存的 tmux backend session，已用原 `backend/dev.sh` 在 `bioagent-backend` 启动更新后的后端；没有停止远端 worker。临时 5175 前端验证结束已停止。真实 GET `/health`、项目列表与项目数据集列表返回 200；数据集详情返回 `PROJECT_DATA_UNAVAILABLE`、retryable 503，当时本机 8001 无监听。**真实远端数据授权未验证成功**；这与隔离测试的模拟 503 分开记录，未绕过授权或启动额外计算来获得成功结果。后端启动沿用既有 embedding 缓存，无新增模型配置或模型评测。

本轮不备份、不迁移业务库；测试库为 `/tmp/bioagent-m1-grouping-tests.db`，不能用它替换业务库。正式库读取时逻辑大小 954,368 bytes（932 KiB），Alembic 仍为 `91a2b3c4d5e6`；本轮只读检查前后均为 4 个 dataset、6 个数据 revision、4 个方案 revision、0 条背景记录。真实业务库没有新增分组记录，未来每次确认仅在 revision 中保存小型 JSON。

回退使用上述本轮前代码版本，不恢复数据库；已有 revision 与确认 JSON 可保留，但旧代码没有新增的技术重复准入检查，因此回退后不能继续宣称所有新合并均经确认。上传、fastp 审核预设、完整资产绑定、队列、病例／对照分组及专家审核继续延期。
