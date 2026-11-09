# 第 25 轮复现：更新前准入 drain／resume

日期：2026-10-04

## 范围

本轮只实现部署维护前的新计算准入闸门。它阻止新的 analysis run start 和 resume，不影响方案编译、状态、证据或报告读取，也不向 Cyclone scheduler／runner 发送停止信号。没有实际停止服务、更新资产／模型、运行 workflow 或执行回滚。

## 状态与调用边界

- DeploymentProfile schema v3 的 `operations.admission_state_file` 是 Agent、Backend client、根运维脚本共用的唯一状态来源。
- 缺档表示默认 accepting；这是未启用 profile 的向后兼容行为。档案一旦存在，schema、字段、摘要、大小、regular-file 与 symlink 检查任一失败都返回 invalid 并拒绝新计算。
- Backend 先查 gate 再登记 execution；Agent 在 planner start／resume 前复查。排空返回 HTTP 503、`ADMISSION_DRAINING`、`retryable=true`，不会建立远端 run。
- `dev-services.sh drain|resume` 不建立 tmux、不停止本机服务、不碰远端 worker；`status` 在启用 profile 时显示同一状态。

## 自动复现

```bash
/Users/lfz/miniconda3/bin/conda run -n adapter \
  python -m pytest -q \
  tests/test_deployment_profile.py \
  tests/test_deployment_admission.py \
  tests/test_deployment_backup.py

cd agent
/Users/lfz/miniconda3/bin/conda run -n adapter \
  python -m pytest -q \
  tests/test_admission_control.py tests/test_adapter.py \
  tests/test_config_profile.py tests/test_provider.py
cd ../open-webui/backend
BIOAGENT_REMOTE_DATA=false \
WEBUI_SECRET_KEY=bioagent-test-only-secret-not-for-production \
/Users/lfz/miniconda3/bin/conda run -n open-webui \
  python -m pytest -q --import-mode=importlib \
  open_webui/utils/test_analysis_planner.py \
  open_webui/routers/test_analysis_projects.py
```

结果依次为 17 passed；40 passed、7 subtests passed；25 passed。测试覆盖默认接受、原子 drain／resume、0600、篡改、symlink、超限、直接 Agent 拒绝、Backend 结构化错误及未调用 planner。

## 本机无服务演练

```bash
BIOAGENT_ADMISSION_STATE_FILE=/tmp/bioagent-round25-admission.json \
  ./dev-services.sh drain 'Round 25 演练'
python3 deployment_admission.py \
  --state-file /tmp/bioagent-round25-admission.json status
BIOAGENT_ADMISSION_STATE_FILE=/tmp/bioagent-round25-admission.json \
  ./dev-services.sh resume '演练完成'
python3 deployment_admission.py \
  --state-file /tmp/bioagent-round25-admission.json status
```

状态依次为 draining、draining、accepting、accepting；最终状态档权限 0600、大小 218 bytes。本演练刻意使用 `/tmp`，没有改变当前服务启动环境、真实 `.env`、数据库或 Cyclone。

## 限制与回退

本轮没有 B4／C3 可发布包，不能验证资产／模型兼容切换、在途任务跨版本观察或联合回滚，所以 A5 第四项仍未勾选。若 gate 程式需回退，必须先以当前受控 CLI 写回 accepting 并核对摘要，再回退服务代码；不能以删除损坏状态档绕过 fail-closed 语义。
