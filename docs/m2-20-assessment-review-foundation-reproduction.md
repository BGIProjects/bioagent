# M2 第二十轮：研判与审核版本基础复现记录

## 1. 范围与结论

本轮实现 M2/A4 前两项：不可变 `AssessmentRevision`、追加式 `ReviewEvent`、审核权限和计算／研判／审核三状态分离。它是后续正向 Assessment、解释修订、补算确认和训练资料导出的业务底座，不代表 A4、B3、C2 或 M2 已完成。

本轮不访问 Cyclone、不运行 Workflow、不调用 MiniMax-M3、不训练本地模型，也不处理资料上传或条件接入。

## 2. 数据与权限契约

- `analysis_assessment_revision` 只保存项目、chat、已登记 run、递增 revision、被替代版本、报告类型／版本／SHA-256、短摘要和小型结构化内容。
- `analysis_review_event` 只追加审核决定、审核人、理由、证据定位与时间，不更新或删除历史意见。
- 建立研判版本采用 `base_revision` 乐观并发；并发或过期写入返回 409。
- 只有项目 `can_review` 成员可写；普通成员可读取项目内历史，管理员不会自动获得内容权限。
- run 必须由同一 chat 的 `AnalysisPlanExecution` 登记；未知或跨分析 run 返回 409，跨项目 chat 返回 404。
- 单一 `content` 的 UTF-8 JSON 上限为 65,536 bytes；摘要上限 4,000 字符；证据定位最多 50 项、每项最多 500 字符。不把 HTML、PDF、FASTQ、完整日志或大型证据写入业务数据库。

## 3. API 与界面复现

在具有 `can_review` 权限且已有登记 run 的项目中：

1. `POST /api/v1/analysis/projects/{project_id}/chats/{chat_id}/assessment` 建立新研判版本；请求必须携带当前 `base_revision`。
2. `POST /api/v1/analysis/projects/{project_id}/chats/{chat_id}/assessment/{revision}/reviews` 追加 `accepted`、`needs_evidence` 或 `revision_required` 审核事件。
3. `GET /api/v1/analysis/projects/{project_id}/chats/{chat_id}/assessment` 返回全部研判版本及各版本的完整追加事件历史。
4. 项目分析列表分别显示计算状态、研判版本与最新审核状态；没有研判时保持空白，不以计算完成代替研判或审核完成。

自动测试覆盖无审核权限、未知 run、跨项目访问、64 KiB 上限、过期 revision、版本替代、旧事件保留和三状态展示。

## 4. 迁移与回退

Alembic revision 为 `a2b3c4d5e6f7`，down revision 为 `91a2b3c4d5e6`。升级只新增两张表和查询索引，不改写历史 chat、plan、run 或报告。回退会删除本轮两张新表，因此生产环境回退前必须先导出审核记录；应用代码回退不会改变远端计算或 run root。

## 5. 验证命令与结果

```bash
WEBUI_SECRET_KEY=<test-only-value> \
  /Users/lfz/miniconda3/bin/conda run -n open-webui \
  python -m pytest -q open_webui/routers/test_analysis_projects.py

PATH=/Users/lfz/.nvm/versions/node/v22.23.2/bin:$PATH \
  npm run test:frontend -- --run \
  src/lib/components/analysis/ProjectPanel.contract.test.ts

/Users/lfz/.local/bin/ruff check \
  backend/open_webui/models/analysis_reviews.py \
  backend/open_webui/models/analysis_projects.py \
  backend/open_webui/routers/analysis_projects.py \
  backend/open_webui/routers/test_analysis_projects.py \
  backend/open_webui/migrations/versions/a2b3c4d5e6f7_add_analysis_reviews.py

PATH=/Users/lfz/.nvm/versions/node/v22.23.2/bin:$PATH \
  npx prettier --check \
  src/lib/components/analysis/ProjectPanel.svelte \
  src/lib/components/analysis/ProjectPanel.contract.test.ts
```

结果：Backend 14 passed；Vitest 1 passed；Ruff 与 Prettier 通过。

相关 Backend 测试还以 `BIOAGENT_REMOTE_DATA=false` 和 pytest importlib 隔离方式按文件运行，覆盖 routers、datasets、grouping、planner、delivery、evidence 及 chat 权限，共 180 passed。必须按文件隔离是因为两个目录存在同名 `test_analysis_grouping.py`，且部分测试依赖导入时固定的 remote/local 模式；直接合并收集会产生测试状态污染。Frontend 全量为 10 files、66 passed。Alembic head 为 `a2b3c4d5e6f7`。

最后只执行一次完整 8 GiB 前端编译。沙箱内预备步骤因不能连接本机代理而在 Vite 编译前退出；沙箱外重新执行同一命令后于 1 分 9 秒完成，末尾为 `Wrote site to "build"` 和 `done`：

```bash
NODE_OPTIONS=--max-old-space-size=8192 \
  PATH=/Users/lfz/.nvm/versions/node/v22.23.2/bin:$PATH \
  npm run build >/tmp/bioagent-frontend-build-m2-20.log 2>&1
```

## 6. 容量与限制

开始时本机可用约 187 GiB，结束时约 184 GiB；仓库仍约 2.4 GiB，Open WebUI 含本轮 build 约 2.0 GiB。本轮不创建大型资料或复制远端结果。新增表按小型 metadata 设计，数据库增长与审核版本／事件数量线性相关，单条内容受上述硬限制。

本轮没有正向领域 Assessment、专家结论、纯解释报告再发布、补算流程或训练资料导出；因此 A4 和 M2 均保持未完成。
