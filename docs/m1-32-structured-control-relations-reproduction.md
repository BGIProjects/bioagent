# 第 32 轮复现：同一数据版本的结构化对照关系

日期：2026-10-04

## 范围

本轮在现有样本背景版本中增加结构化对照引用。没有实现用户明确暂缓的上传，没有改变数据集文件、计算方案 hash 或业务库 schema，也没有启动 workflow 或调用模型。

## 契约

- 每个 sample 的 `control_sample_ids` 为 0–32 个同 dataset revision sample ID。
- 后端拒绝自指、重复、其他版本／未知 sample 和额外字段；保存前排序。请求继续受 64 KiB 上限保护。
- 旧背景 JSON 在 UI 编辑时补空列表，无需迁移。当前与历史背景均显示关系。
- execution 使用已冻结的 metadata snapshot；报告 HTML 转义对照 ID，关系只作使用者背景，不成为计算证据或审核结论。

## 自动复现

```bash
cd open-webui/backend
WEBUI_SECRET_KEY=unit-test-only-secret-key-not-for-production \
  /Users/lfz/miniconda3/bin/conda run -n open-webui \
  python -m pytest -q \
  open_webui/routers/test_analysis_metadata.py \
  open_webui/routers/test_analysis_projects.py \
  open_webui/routers/test_analysis_plans_api.py

cd ..
./node_modules/.bin/vitest run \
  src/lib/apis/analysis/index.test.ts \
  src/lib/components/analysis/AnalysisPage.contract.test.ts \
  src/lib/components/analysis/ProjectPanel.contract.test.ts \
  src/lib/components/analysis/DatasetBackground.contract.test.ts
/Users/lfz/.local/bin/ruff check \
  backend/open_webui/models/analysis_metadata.py \
  backend/open_webui/utils/analysis_metadata.py \
  backend/open_webui/routers/test_analysis_metadata.py
NODE_OPTIONS=--max-old-space-size=8192 npm run build >/tmp/bioagent-round32-build.log 2>&1
tail -40 /tmp/bioagent-round32-build.log
```

Backend 三个相关文件预期 61 passed；前端四个文件预期 24 passed。build 只运行一次。新增回归覆盖合法关系的保存与报告、自指、重复及未知 sample 拒绝；既有回归继续验证权限、并发版本、分页历史、execution 冻结和计算 hash 不变。两个 plan 执行成功路径显式 mock admission，避免单元测试依赖实际 Agent 服务。

## 容量与回退

字段保存在既有小型 JSON revision 中，不建关系表或重复业务数据库；单请求硬限 64 KiB，每个样本关系硬限 32。build 后本机卷约 184 GiB 可用。回退前端和契约代码可停止新写入，旧读取／报告路径不会使用该字段；若回退后还要编辑已含关系的历史背景，须先以当前版本追加移除关系的修订，不能宣称旧写入端无损兼容。没有改动当前正式数据库。
