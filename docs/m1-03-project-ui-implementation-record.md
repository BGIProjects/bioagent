# M1 第三轮：项目入口与页面体验收尾

日期：2026-09-13。接续[第一轮：轻量资产准备与开发评测](m1-01-assets-evaluation-implementation-record.md)和[第二轮：最小项目与权限](m1-02-projects-implementation-record.md)。专家审核操作仍按第一轮记录的“待 M2 网页实现”约定执行。本轮仅收尾 A1 体验，**M0／M1 整体未完成**。

## 入口与行为

- `/dashboard` 原页首统一放置项目选择、“进入分析”和管理员“项目设置”。项目区仅保留真实历史、计算状态和分页；保留品牌、展示布局与演示数据标示。管理员未加入项目时仍可设置，不能进入分析。
- 设置复用现有 Modal，支持关闭按钮、Esc、遮罩关闭与焦点返回。关闭丢弃草稿；新建草稿不切换背景项目；保存期间禁止重复提交，失败保留输入，成功重读项目、权限与历史。审核开关仍只登记，优先级不参与排序。
- `/analysis` 将原页首移到路由层，移除额外顶栏，项目权限与会话标题旁的只读提示分开。唯一“项目看板”入口保留 `project`。加载、错误、无项目均保留页首；显式不可访问项目不静默回退；切换项目清除 `chat`，按项目 ID 重建内容。
- 仅新增控件采用 8px 圆角、36px 最小高度、青色边框和深色背景；保留原生选择框。桌面用自动页首加剩余内容高度，移除重复视口扣减，手机沿用单栏自然滚动。长名称截断后可通过控件 title 查看。

## 复现与验证

环境：macOS，Node 22.23.2，Conda `open-webui` Python 3.11，现有 Cypress 13.17.0／Chrome 152。未下载浏览器、启动 Docker 或修改服务配置。测试前端临时监听 `127.0.0.1:5175`，不替换原 5173 服务。

在根目录运行隔离权限回归（不要省略隔离数据库参数）：

```bash
BIOAGENT_REMOTE_DATA=false DATA_DIR=/tmp/bioagent-m1-ui-python \
  DATABASE_URL=sqlite:////tmp/bioagent-m1-ui-python.db WEBUI_SECRET_KEY=test-only-key \
  PYTHONPATH=open-webui/backend /Users/lfz/miniconda3/envs/open-webui/bin/python \
  -m unittest open_webui.routers.test_analysis_projects \
  > /tmp/bioagent-m1-ui-python.log 2>&1
```

在 `open-webui` 中设置 Node PATH，依序运行：

```bash
export PATH=/Users/lfz/.nvm/versions/node/v22.23.2/bin:$PATH
./node_modules/.bin/vitest run src/lib/utils/projectNavigation.test.ts \
  src/lib/utils/bioagentChat.test.ts src/lib/utils/analysisRun.test.ts \
  src/lib/apis/analysis/index.test.ts > /tmp/bioagent-m1-ui-vitest.log 2>&1
# 单独终端启动；浏览器验证结束后停止该测试前端。
npm run dev:fast -- --host 127.0.0.1 --port 5175 > /tmp/bioagent-m1-ui-vite.log 2>&1
# 另一个终端运行；本机继承的 ELECTRON_RUN_AS_NODE 会妨碍 Cypress 启动。
env -u ELECTRON_RUN_AS_NODE ./node_modules/.bin/cypress run \
  --config-file cypress.project-ui.config.cjs --browser chrome \
  > /tmp/bioagent-m1-ui-cypress.log 2>&1
```

Python **11 项通过**；Vitest **36 项通过**；Cypress **18 项通过**。浏览器尺寸为 1440×900、1280×720、1024×768、390×844，另以 1152×720 CSS 视口与 DPR 1.25 模拟 1440×900 的 **125% 等效布局**，并非手动浏览器缩放菜单验收。覆盖底部输入框可达、无水平溢出、长名称、单一入口、跨页参数、显式无权／无项目、他人只读、快速项目切换、分页迟到响应、设置失败重试、草稿丢弃、焦点返回及窄屏对话框滚动。

浏览器全部采用合成用户与 API 桩，写入不会到达业务后端，模型生成／执行请求直接使测试失败。真实环境另外只读检查：项目列表 200（2 项），所选项目历史 200（1 项）、dataset 列表 200（3 项）；没有读取 FASTQ 内容。真实多用户设置修改未执行，权限依赖既有后端与隔离 Python 回归。

本轮无 Python 改动，Ruff **不适用**。对本轮变更的 Svelte／TS／CSS／Cypress 文件和三份 Markdown 执行 Prettier check；完整命令与结果保存在 `prettier.log`。最后仅执行一次：

```bash
NODE_OPTIONS=--max-old-space-size=8192 npm run build > /tmp/bioagent-m1-ui-build.log 2>&1
```

构建 **成功（退出码 0）**，完整日志保留既有 Svelte／无用 CSS／可访问性及打包体积提示；未运行 `npm run check`，未将既有全量诊断作为本轮修复范围。

## 产物、容量与回退

本地日志为 `/tmp/bioagent-m1-ui-{python,vitest,cypress,build,prettier}.log`，只读结果为 `/tmp/bioagent-m1-ui-readonly.json`；截图在 `/tmp/bioagent-m1-ui/screenshots/project-ui.cy.js/`，含两页桌面、Analysis 手机页首与底部、设置对话框及 125% 等效布局，共 6 张 PNG。截图均为合成数据。

持久目录：`Cyclone:/data/user/liufangzhou/runs/m1-project-ui-20260913-1532/`。共 **15 个文件、4,056,660 字节（约 3.87 MiB）**，包括 `SHA256SUMS`、10 个前端源码／测试文件的 `source-files.sha256`、测试／构建日志、只读结果和截图。`SHA256SUMS` 的 SHA-256 为 `bc9797cb022d89f8909830cc23bfdcca314207fc80c51ecacf37c16380c55465`；远端逐项校验通过。本地归档暂存在 `/tmp/bioagent-m1-ui-20260913-1532/`。

隔离测试库为 831,488 字节；本轮新增前端／测试文件共 20,057 字节。既有构建目录覆盖更新，实际占用从 290,224 KiB 到 299,104 KiB，`.svelte-kit` 从 313,252 KiB 到 319,444 KiB；既有 Pyodide 缓存从 63,280 KiB 到 63,340 KiB，总增量约 14.8 MiB。验证产物没有复制完整构建目录或数据库。

业务库只读观察为 **897,024 字节（876 KiB）**，本轮不迁移、备份或恢复业务库；没有新增业务内容入库。隔离测试库及构建缓存与业务库分开。没有新增模型、参考库或大型知识资产。

回退只恢复本轮前端变更之前的 `open-webui` 版本（基线 `2b5e44d19`），重新构建并启动前端；不恢复旧数据库、不终止远端 worker。根仓库基线为 `b6cbc0e`。本轮不自动创建 commit，`agent` 与 `AGENTS.md` 无变更。
