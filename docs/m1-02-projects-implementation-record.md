# M1 第二轮：最小项目与权限

日期：2026-09-13。依据：[实施路线图第 1.5 节](bioagent-implementation-roadmap.md#15-m1-第二轮范围与实际状态2026-09-13用户确认)。前一轮为[第一轮：轻量资产准备与开发评测](m1-01-assets-evaluation-implementation-record.md)，其中日期、结果、哈希和[未来专家审核操作（待 M2 网页实现）](m1-01-assets-evaluation-implementation-record.md#未来专家审核操作待-m2-网页实现)保持原记录。

## 范围与入口

本轮交付 A1 的最小项目、成员权限、数据范围与必要页面。继续使用 SQLite，没有新增参考库、模型、云端评测或 FASTQ 分析运行。**M0／M1 整体仍未完成**。上传、队列、审核动作、正式知识发布与引用持久化留待后续。

- 管理员进入 `/dashboard` →“项目设置”→“新建项目”，填写名称、优先级及授权文件／目录的 logical path。仅登记已有路径，不移动文件。优先级默认普通，目前不影响任务排序。
- 创建时不自动加入项目；需要分析时明确勾选“将自己加入并授予分析权限”，或在成员表单另行加入。管理员未加入项目时只能管理设置，不能读取项目分析内容。
- 成员默认可查看；“可分析”和“可审核”独立，默认关闭。审核开关仅登记，不会出现审核动作。移除成员后，新读取／修改／确认执行被拒绝，已启动的远端计算继续运行。
- 成员在 `/analysis` 选择项目，查看项目历史；他人会话只读。有分析权限者可选项目已有 dataset，在自己的新会话重新编译和确认执行。项目分析不能通用分享、克隆或加入共享文件夹，不支持硬删除，可归档。
- 文件树根只展示项目授权入口。授权同时保存 logical path、canonical 范围及根指纹；链接替换拒绝，新建／修订 dataset 和执行均重新检查，远端暂不可验证返回 retryable 503。管理员撤销路径后该路径的新访问／执行被拒绝。
- Dashboard 保留展示布局及品牌，真实项目和分页分析列表接入 API；静态地图、统计和告警标明“演示数据”。研判／审核显示“未接入”，不拿计算完成充当审核完成。

接口集中在 `/api/v1/analysis/projects`：列表／详情、管理员 POST／PATCH、`/{id}/members`、成员 PUT／DELETE、`/{id}/chats?page=1` 及 `/{id}/datasets?page=1`。列表每页 50 条。新建分析、dataset 与 benchmark 须指定项目，既有对象按数据库归属鉴权；不能用聊天 metadata 重新绑定项目。无需新增环境变量，继续使用原 `.env.example` 配置。

## 迁移、备份与回退

环境：macOS、Node 22.23.2；后端 Python 3.11（Conda `open-webui`），已有 Agent 使用 `adapter`。本轮只修改根仓库和 `open-webui`，Agent 接口复用现有数据解析及预检入口。

新增 Alembic 版本 `8091a2b3c4d5`，前一版本为 `7f8091a2b3c4`。按原用户迁移 analysis／benchmark 会话与 dataset 到独立“历史分析”项目，仅原用户获得查看和分析权限；未知／已删除用户对应项目没有成员。授权仅从历史 dataset 的既有文件引用提取，没有授予整个 data root。历史会话的通用分享与文件夹关联清除，原方案 revision、执行登记、报告及 run 路径保留。

实际先通过 SQLite `Connection.backup()` 将业务库复制到 `/tmp/bioagent-a1-legacy.db`，在副本上升级并逐行比较旧表。确认方案 1 条、方案版本 1 条、执行 1 条、dataset 版本 5 条、事件 15 条及原会话内容不变。随后创建正式一致性备份并升级业务库；开始前本机三项服务已停止，未终止任何远端 worker。升级后启动现有本机服务做只读验证。

| 文件                                                      |  字节数 | 用途                   |
| --------------------------------------------------------- | ------: | ---------------------- |
| 迁移前 `open-webui/backend/data/webui.db`                 | 864,256 | 844 KiB                |
| `open-webui/backend/data/m1-projects-pre-8091a2b3c4d5.db` | 864,256 | 一致性备份，Git 忽略   |
| 迁移后业务库／隔离副本                                    | 888,832 | 868 KiB，仅增加 24 KiB |

备份 SHA-256：`627dabe8bf0fd1bf52f03c66a25513a51f1fa6ae56d7bdde8cfbeac858961956`。迁移形成 1 个项目、1 名原用户成员、3 个 dataset 归属和 2 条既有文件授权，没有复制数据文件入库。

复现迁移时先停止本机服务（`./dev-services.sh stop`，不停止远端 worker），用 SQLite `backup()` 创建新命名备份与隔离副本；不要覆盖上面的原始备份。对副本执行：

```bash
cd open-webui/backend
BIOAGENT_REMOTE_DATA=false DATA_DIR=/tmp/bioagent-a1-isolated \
  DATABASE_URL=sqlite:////tmp/bioagent-a1-legacy.db \
  WEBUI_SECRET_KEY=test-only-key PYTHONPATH=. \
  /Users/lfz/miniconda3/envs/open-webui/bin/python -c 'import open_webui.config'
```

确认 `PRAGMA integrity_check` 为 `ok`、`alembic_version` 正确及历史记录不变后，再升级正式库。正式启动入口 `./dev-services.sh start` 会使用原配置和 secret；隔离验证用的 test-only-key 不写入正式配置。

回退须先停止本机服务，另外备份当前库，再恢复**迁移前数据库与匹配的旧代码**。本轮前 `open-webui` 基线为 `325b4aeb9e142115a9563c9890615b8417216eae`，Agent 基线为 `61a99bb7c0f35a14d517ce50e6f25580406a47da`（未修改）。恢复应使用 SQLite backup API，不能在服务运行时直接覆盖数据库文件；保留现有 `.env` 与 secret。**恢复旧备份会失去迁移后新增的业务数据**，须先另行保存；不使用新代码自动重新升级旧备份，不通过反向迁移恢复已清除的分享关联。

## 验证与复现

从 `open-webui/backend` 运行（始终指定隔离数据库，避免测试导入触发正式库迁移）：

```bash
BIOAGENT_REMOTE_DATA=false DATA_DIR=/tmp/bioagent-a1-tests \
  DATABASE_URL=sqlite:////tmp/bioagent-a1-tests.db \
  WEBUI_SECRET_KEY=test-only-key PYTHONPATH=. \
  /Users/lfz/miniconda3/envs/open-webui/bin/python -m unittest \
  open_webui.routers.test_analysis_projects \
  open_webui.routers.test_analysis \
  open_webui.routers.test_analysis_plans_api \
  open_webui.routers.test_analysis_datasets_api \
  open_webui.routers.test_analysis_benchmark \
  open_webui.routers.test_openai_analysis_metadata \
  open_webui.models.test_chats \
  open_webui.utils.test_analysis_datasets \
  open_webui.utils.test_analysis_run_delivery \
  open_webui.utils.test_report_evidence \
  open_webui.test_chat_completion_tasks
```

Python **112 项通过**，其中项目专项 11 项。测试使用内存 SQLite 与明确的合成异常：多用户双项目、管理员未入项目、独立授权、撤权、跨项目 ID、伪造 metadata、通用分享／克隆／文件夹、导出过滤、symlink 目标替换／逃逸、retryable 503、历史迁移、他人方案执行拒绝与重复预约防重。旧报告与方案相关测试保持通过。没有将模拟异常当作真实远端故障演练。

从 `open-webui` 运行：

```bash
npm run test:frontend -- --run src/lib/apis/analysis/index.test.ts \
  src/lib/utils/bioagentChat.test.ts src/lib/utils/analysisRun.test.ts
```

Vitest **34 项通过**，含项目参数、无项目空列表、reset／destroy 后迟到历史回应不能覆盖新会话或全局 chat ID。页面通过编译验证；未进行人工多浏览器验收。

随后检查本轮 Python 文件。新文件 Ruff 检查通过；对修改的既有文件按 `HEAD` 逐文件比较 Ruff 的代码与诊断信息，无新增诊断，既有 35 项复杂度／风格诊断保留，未宣称整个上游仓库 lint 清零。日志见下列产物。

```bash
# 在 open-webui；本轮修改的 ts/svelte，以及根 README、路线图与两轮记录
./node_modules/.bin/prettier --check <本轮修改的文件>
NODE_OPTIONS=--max-old-space-size=8192 npm run build >/tmp/bioagent-a1-build.log 2>&1
```

前端构建通过，唯一一次进入 Vite 的编译约 1 分钟，8 GiB Node 上限。首次 `npm run build` 在 Pyodide 准备阶段因沙箱网络限制失败，尚未进入 Vite；保留该失败日志，开放所需网络后完成准备与构建。未修改 Pyodide 资产或增加构建配置；不运行 `npm run check`。

真实环境使用原用户短期令牌（仅保留在验证进程内）读取项目、项目历史、文件入口、会话、最新方案及 3 个 dataset：8 项均返回 200；未获准路径返回 403。经授权的既有文件 quick preflight（`full=false`）返回 ready，检查 1,000 对记录、解压读取 737,594 字节；`compressed_bytes=299609614` 是原文件大小统计，**不表示本轮读取了整个文件**。没有创建新项目、dataset、方案、proposal 或计算执行，没有云端调用。

复现真实验证可使用浏览器中原用户登录后的项目入口，读取历史及已授权 dataset；管理员另用隔离账号／项目检查查看和分析开关。预检复用现有 Agent `/v1/analysis/datasets/preflight`，只提交获准 dataset 的原 sources／artifacts，`full=false`，不得确认执行；令牌和 secret 不保存到记录或日志。

## 产物与剩余限制

本机临时验证日志使用 `/tmp/bioagent-a1-*`；业务备份留在 Git 忽略的 `backend/data`，不上传数据库。完整验证日志、结果摘要与 SHA-256 清单保存于 `Cyclone:/data/user/liufangzhou/runs/m1-projects-20260913-1152/`，19 个文件共 455,187 字节；`final-manifest.json` 的 SHA-256 为 `2f6f5c6a402f8104d3a99a7588c870c591dd9a97dda9b73a130ff7cdb32e9e50`，逐文件哈希在清单内。数据库不包含在此目录。项目专项补测管理员分享 ID 回退后再次通过 11 项；共享 benchmark 的事件记录改按已授权会话创建者读取，相关 7 项回归通过。归档前盘点，本机 `/tmp/bioagent-a1-*` 验证文件及隔离库合计 2,859,420 字节（包含日志暂存副本，不含前端构建缓存）。知识／评测资产新增为 0；数据库增量仅 24 KiB，不增加大型内容。

此轮 A1 是最小工程交付。授权成员本身对已读内容的另行复制无法撤回；已发出的计算不中止。正式知识与引用隔离、审核动作、报告审核版本、上传、队列、领域验收及生产安全审计均不在本轮内。需要专家后，严格按[第一轮中标明“待 M2 网页实现”的操作约定](m1-01-assets-evaluation-implementation-record.md#未来专家审核操作待-m2-网页实现)实施账号授权、逐项审核、意见裁决、版本追加、补算确认与资产发布；本轮成员的审核开关不会提供这些尚未实现的页面或命令。
