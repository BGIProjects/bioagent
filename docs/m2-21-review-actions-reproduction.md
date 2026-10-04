# M2 第二十一轮：审核动作闭环复现记录

## 1. 范围与结论

本轮补齐 A4 第三项：纯解释 revision 的报告发布、关联 candidate 的补算方案提议与显式确认、审核修订的待审核训练导出。A4 三项任务至此完成，但没有正向领域 Assessment，也没有启动 C2 训练，因此 M2 共同验收仍未通过。

本轮不处理资料上传或条件接入，不访问 Cyclone，不调用 MiniMax-M3，不运行 Workflow，不修改前端，也不训练或打包模型。

## 2. 解释 revision 与旧报告回看

- `AssessmentRevision` 新增 `revision_kind=generated|explanation`；`explanation` 必须以已有 revision 为 base。
- `GET /api/v1/analysis/projects/{project}/chats/{chat}/assessment/{revision}/report` 返回指定不可变 revision 的自包含 HTML，包含 report kind／version／SHA-256、结构化内容、审核事件和补算提议。
- 报告字符串、JSON、理由及 evidence locator 全部转义；响应使用 attachment 和 `nosniff`。
- 自动测试确认建立 explanation revision 前后 `AnalysisPlan.latest_revision` 保持 1，`AnalysisPlanExecution` 仍只有原来一条；不会因为文字修订创建计算。

## 3. 补算提议与确认

审核人通过：

```text
POST /api/v1/analysis/projects/{project}/chats/{chat}/assessment/{revision}/computation-proposals
```

提交 candidate ID、当前 plan revision、原因与既有 `AnalysisPlanPatch` 白名单字段。服务端复用确定性编译与 preview，保存变更前后、警示及 resulting plan，不接受无变化 patch。

相同 `rcp_<uuid>` 与相同请求幂等返回；同 ID 不同 candidate／patch 返回 409。patch 与 impact 合计超过 64 KiB 时拒绝写库。提议只处于 pending，不启动计算。原 chat 拥有者且具 `can_analyze` 权限时可从项目范围的 accept／reject endpoint 显式决定；accept 再核对 base plan revision，建立新 plan revision 并记录关联 assessment revision 与 candidate，仍需后续独立执行确认。重复确认在编译前返回 409。

## 4. 待审核训练导出

`GET /api/v1/analysis/projects/{project}/assessment-training-export` 只允许 `can_review` 成员访问。导出仅包含至少有一条审核事件的 revision，并固定：

- `status=pending_training_review`
- `training_eligible=false`
- `triggers_training=false`
- 来源项目、chat、run、report identity 和 assessment revision
- 小型 input snapshot、输出修订、完整审核事件与稳定 record SHA-256
- 许可确认、冲突解决、近重复隔离的数据划分及训练目标批准四项后续门槛

导出动作不写数据库、不读取 FASTQ、不调用模型，也不触发训练。

## 5. 数据库迁移与容量

Alembic revision `b3c4d5e6f7a8` 基于 `a2b3c4d5e6f7`：为既有研判版本增加 `revision_kind`，旧行默认 `generated`；新增 `analysis_review_computation_proposal` 保存小型 patch、impact 与决定身份。升级／回退自动测试确认旧 revision 保留且新表可移除。

开始与结束时本机可用空间约 184 GiB，仓库约 2.4 GiB。本轮不产生大型报告副本、计算资料或模型产物；HTML 和训练候选均按请求即时生成，数据库仍只线性保存小型 metadata。

## 6. 验证

定向测试：

```bash
BIOAGENT_REMOTE_DATA=false \
WEBUI_SECRET_KEY=<test-only-value> \
  /Users/lfz/miniconda3/bin/conda run -n open-webui \
  python -m pytest -q open_webui/routers/test_analysis_projects.py
```

结果为 16 passed。相关 Backend routers、datasets、grouping、planner、delivery、evidence 与 chat 权限测试继续以 `BIOAGENT_REMOTE_DATA=false`、pytest importlib 模式按文件隔离运行，共 185 passed。

```bash
/Users/lfz/.local/bin/ruff check <本轮变更 Python 文件>
PATH=/Users/lfz/.nvm/versions/node/v22.23.2/bin:$PATH \
  npx prettier --check ../docs/bioagent-implementation-roadmap.md \
  ../docs/bioagent-implementation-history.md \
  ../docs/m2-21-review-actions-reproduction.md
```

Ruff、Prettier、Alembic head、迁移升级／回退与 `git diff --check` 通过。本轮没有前端变更，按验证约束不重复运行前端 build。

## 7. 限制与回退

补算提议只开放既有计划白名单字段，不允许 shell、任意 workflow 或立即执行。待审核训练导出不证明来源许可、语义正确、数据划分或训练目标已批准，不能直接送入训练。回退应用后历史 A4 表保持；downgrade migration 会删除补算提议表和 revision 类型字段，执行前应先导出业务记录。
