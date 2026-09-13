# M1 第四轮：数据集元信息与背景版本追溯

日期：2026-09-13。接续[第一轮资产与评测](m1-01-assets-evaluation-implementation-record.md)、[第二轮项目权限](m1-02-projects-implementation-record.md)与[第三轮页面体验](m1-03-project-ui-implementation-record.md)。本轮仅推进 A2 背景记录，**A2、M0／M1 整体仍未完成**；专家操作约定仍见第一轮“待 M2 网页实现”。

## 操作与版本语义

在 `/analysis` 选择项目及已有数据集，桌面打开“文件列表”中的数据集卡片，窄屏打开内容区“数据集与背景”，展开“样本背景”。有分析权者可编辑自己的会话中选取的共享数据集背景；查看成员及他人会话只读，但可展开历史。

字段为样本名称、测序批次备注、宿主背景、样本类型、表型、对照备注及数据集备注，按已有 sample_id 填写。没有 sample_id 时仅提供数据集备注。短字段最多 200 字，长备注及修改理由最多 1,000 字，请求最多 64 KiB；未知字段及不属于当前数据版本的样本被拒绝。字段不参与计算或模型上下文，不改 sample_id／run_id、文件和分组。

保存须填写理由，首次记录从背景版本 0 追加为 1；内容相同不新增版本。并发冲突返回 409，保留输入并提示重新载入；重新载入和取消会丢弃草稿。切换项目／数据集销毁旧表单并隔离迟到响应。新资料 revision 的背景从未记录开始，不自动继承。

接口（均沿用项目与数据路径授权）：

- `GET /api/v1/analysis/datasets/{id}/metadata?revision=N`：当前背景，未记录为 version 0。
- `PUT` 同一路径：完整 `{base_version, content: {note, samples: {sample_id: {name, batch, host, sample_type, phenotype, control}}}, reason}`；成功追加背景，冲突 409，非法输入 422，超限 413；路径暂不可验沿用 retryable 503。
- `GET .../metadata/history?revision=N&page=P`：每页 20 项，版本降序；返回 `items`／`has_more`，含修改人 ID、理由与时间。

背景保存不触发预检、proposal、重新编译或执行，也不使原方案失效。新方案从数据库读取并冻结快照；背景改变可形成新的方案版本，但计算 input_hash 和 Agent 执行契约不变。下载报告按 execution 对应的方案版本读取快照，将背景作为经转义的使用者记录呈现，与证据分开；旧方案没有快照就显示未记录，不回填最新内容，不改远端报告文件。

## 迁移、容量与回退

环境：macOS、Node 22.23.2、Conda `open-webui` Python 3.11、现有 Cypress 13.17.0／Chrome 152。新增 Alembic `91a2b3c4d5e6`，前版 `8091a2b3c4d5`；新增背景版本表与方案版本表可空 JSON 快照列，不批量补写历史。

先以 SQLite `Connection.backup()` 将业务库复制到 `/tmp/bioagent-m1-metadata-isolated.db`，运行迁移，再对 53 张旧表逐一比较原字段的全部行数据，结果一致；完整性检查 `ok`。随后仅短暂停止 `bioagent-backend`，新建一致性备份、迁移业务库并恢复原 `backend/dev.sh`，健康检查 200。Frontend、Agent 与远端 worker 未停止。

| 观察项                 |    字节数 | 说明                                         |
| ---------------------- | --------: | -------------------------------------------- |
| 迁移前一致性备份       |   921,600 | 900 KiB                                      |
| 迁移后逻辑库／隔离副本 |   937,984 | 916 KiB，增加 16 KiB                         |
| 只读观察时主文件       |   897,024 | WAL 模式，不能单独视为库总大小               |
| 同次观察 WAL           | 2,158,912 | 可变运行日志；不额外 checkpoint 或复制入归档 |

业务库中的背景表仍为 0 行，2 条旧方案快照保持 NULL。备份文件为 `open-webui/backend/data/m1-metadata-pre-91a2b3c4d5e6.db`（Git 忽略），SHA-256：`c48c7c27fca491cc395e34185846889578ce04b3b99b7195900ab75b8832231d`。后台仍使用 SQLite，不引入大型内容。

复现升级：先对自己的新命名隔离副本运行下面命令，避免覆盖本次记录；比较旧表原字段和完整性后，再短暂停止后端、创建新一致性备份并升级正式库。这里的临时密钥仅供隔离导入配置使用，不替换正式 secret：

```bash
BIOAGENT_REMOTE_DATA=false DATA_DIR=/tmp/bioagent-m1-metadata-isolated \
  DATABASE_URL=sqlite:////tmp/bioagent-m1-metadata-isolated.db \
  WEBUI_SECRET_KEY=test-only-key PYTHONPATH=open-webui/backend \
  /Users/lfz/miniconda3/envs/open-webui/bin/python -c 'import open_webui.config'
```

回退须配对第四轮前的 `open-webui` 版本 `739c6c589` 与本次迁移前备份。停止后端，先保留当前库，再用 SQLite backup API 从备份恢复；确保没有遗留旧 WAL／SHM 被新主文件使用，恢复旧代码后重新构建并通过原入口启动。不要把备份直接覆盖到运行中的数据库。**恢复旧备份会失去迁移后新增业务数据**。根仓库基线 `0a255d3`；不回退远端 run，不终止 worker。

## 验证与复现

根目录执行（全部写入隔离库）：

```bash
BIOAGENT_REMOTE_DATA=false DATA_DIR=/tmp/bioagent-m1-metadata-tests \
  DATABASE_URL=sqlite:////tmp/bioagent-m1-metadata-tests.db WEBUI_SECRET_KEY=test-only-key \
  PYTHONPATH=open-webui/backend /Users/lfz/miniconda3/envs/open-webui/bin/python -m unittest \
  open_webui.routers.test_analysis_metadata open_webui.routers.test_analysis_plans_api \
  open_webui.routers.test_analysis_datasets_api open_webui.utils.test_report_evidence \
  > /tmp/bioagent-m1-metadata-python.log 2>&1
```

主回归 **36 项通过**（包含继承的项目权限回归），同样隔离环境另运行 `open_webui.utils.test_analysis_run_delivery open_webui.utils.test_replay_report`，**7 项通过**。覆盖版本追加／去重、真实 SQLite 并发冲突、历史分页、非法字段和样本、64 KiB 限制、角色与撤权、retryable 503、数据版本不变、无方案／执行副作用、方案快照及去重、按执行版本取背景、转义与旧背景不回填。报告测试为离线固定证据／回放，不是新增真实计算。

在 `open-webui` 目录执行：

```bash
export PATH=/Users/lfz/.nvm/versions/node/v22.23.2/bin:$PATH
./node_modules/.bin/vitest run src/lib/apis/analysis/index.test.ts \
  src/lib/utils/analysisRun.test.ts src/lib/utils/bioagentChat.test.ts \
  src/lib/utils/projectNavigation.test.ts > /tmp/bioagent-m1-metadata-vitest.log 2>&1
# 单独终端启动临时前端；验证后停止，仅供本轮使用。
npm run dev:fast -- --host 127.0.0.1 --port 5175 > /tmp/bioagent-m1-metadata-vite.log 2>&1
# 另一终端使用已安装的 Chrome，不下载浏览器。
env -u ELECTRON_RUN_AS_NODE ./node_modules/.bin/cypress run \
  --config-file cypress.project-ui.config.cjs \
  --config 'specPattern=cypress/e2e/*.cy.js,screenshotsFolder=/tmp/bioagent-m1-metadata-screenshots' \
  --browser chrome > /tmp/bioagent-m1-metadata-cypress.log 2>&1
```

Vitest **38 项通过**。Cypress **23 项通过**（5 项背景测试＋18 项项目 UI 回归），覆盖编辑／取消、多样本、失败与冲突、保存禁用、历史只读、切换隔离和窄屏底部可达；已有回归尺寸为 1440×900、1280×720、1024×768、390×844，125% 使用第三轮相同的等效视口／DPR 方法。本轮背景截图为桌面 1440×900、手机 390×844。写操作使用 API 桩；模型或计算请求使测试失败。没有 Docker、模型评测、FASTQ 传输或计算。

真实环境仅 GET 项目、数据集列表、背景和背景历史，4 项均返回 200；背景为 version 0、历史为空。认证令牌仅在进程内使用，未保存或打印。没有进行真实多人编辑或新增真实方案／报告，绑定逻辑由隔离测试验证。

本轮 Python 文件 Ruff 检查通过；Svelte／TS／Cypress 与三份 Markdown 执行 Prettier check。最后仅运行一次前端构建：

```bash
NODE_OPTIONS=--max-old-space-size=8192 npm run build > /tmp/bioagent-m1-metadata-build.log 2>&1
```

构建 **成功，退出码 0**。完整日志保留既有 Svelte／CSS／可访问性及 bundle 体积提示；未执行 `npm run check`。构建使用既有 Pyodide 缓存。Cypress 默认下载曾触发 Vite 重载，已将下载目录移至 `/tmp/bioagent-cypress-downloads` 后重跑通过，最终日志为修正后的结果。

## 产物与限制

持久产物：`Cyclone:/data/user/liufangzhou/runs/m1-dataset-metadata-20260913-1625/`，本地暂存 `/tmp/bioagent-m1-metadata-20260913-1625/`。共 **17 个文件、1,408,057 字节（约 1.34 MiB）**，包括两张合成截图、测试／构建／迁移日志、真实只读结果、数据库比对脚本、16 个源码／测试文件的哈希及总清单。`SHA256SUMS` 的 SHA-256：`33a5581a436f87d705ee87e61ad5c65ea995102e33235ed5d2b6d0f7013e3bae`；远端逐项校验通过。

隔离测试库 843,776 字节、迁移验证副本 937,984 字节，均只在 `/tmp`；连同归档和截图暂存，本轮验证资料低于 10 MiB。既有 `build` 占用保持 299,104 KiB，`.svelte-kit` 从 314,088 KiB 到 319,668 KiB，Pyodide 缓存保持 63,340 KiB；构建缓存不计入验证产物限制，也不上传。

前述 `/tmp/bioagent-m1-metadata-*` 为本轮小型临时文件，业务备份不上传。README 只补入口，没有新环境变量；`AGENTS.md`、agent 和原始数据均无变更。上传、计算分组、审核预设、资产发布、队列与专家审核留待后续。本机 `/Users/lfz/Documents/Project/NGS` 的 FASTQ 保留作未来上传验收资料。

未自动提交。建议根仓库 `docs(m1): record dataset metadata and background versioning`；open-webui `feat(analysis): version dataset metadata and freeze plan context`；agent 无需提交。
