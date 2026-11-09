# 第 23 轮复现：DeploymentProfile 配置边界

日期：2026-10-04

## 范围

本轮只实现 A5 第一项：以无密钥 DeploymentProfile 集中描述服务、路径、工具、模型与资源额度，并让现有启动入口在显式启用时实际读取。没有启动服务、访问 Cyclone、执行 workflow、迁移数据库、安装离线依赖、训练模型或验证独立目标环境。

## 产物与边界

- `deployment_profile.py`：stdlib-only 严格校验器及确定性环境导出器；拒绝未知字段、相对路径、重复端口、非 443 `/anthropic` 模型端点、非正数额度与非 `MINIMAX_API_KEY` 凭证变量名。
- `deployment/profiles/cyclone-development.json`：当前开发实例的地址、目录、Workflow 1–6、Home Pixi 工具、MiniMax-M3 与额度。
- `deployment/profiles/independent-target.json`：使用不同主机、端口和 `/opt`／`/srv` 路径的独立目标模板。路径尚未在目标机建立，不是安装通过证明。
- `deployment/load-profile.sh`：输出先写临时文件，逐行校验变量名后以 `printf -v` 导入，不使用 `eval`。JSON 不包含凭证值；`MINIMAX_API_KEY` 仍来自启动环境。
- 根启动器先载入服务字段；Agent 与 Backend 在 `.env` 之后载入各自字段，使显式 profile 成为部署字段的最终值。未设置 profile 时保持现有行为。

## 复现命令

```bash
python3 deployment_profile.py validate deployment/profiles/cyclone-development.json
python3 deployment_profile.py validate deployment/profiles/independent-target.json
python3 deployment_profile.py env deployment/profiles/cyclone-development.json services

/Users/lfz/miniconda3/bin/conda run -n adapter \
  python -m pytest -q tests/test_deployment_profile.py

cd agent
/Users/lfz/miniconda3/bin/conda run -n adapter \
  python -m pytest -q \
  tests/test_config_profile.py tests/test_provider.py tests/test_adapter.py
cd ..

bash -n dev-services.sh deployment/load-profile.sh \
  agent/start.sh open-webui/backend/dev.sh
/Users/lfz/.local/bin/ruff check \
  deployment_profile.py tests/test_deployment_profile.py
/Users/lfz/.local/bin/ruff check \
  agent/config.py agent/tests/test_config_profile.py
PATH=/Users/lfz/.nvm/versions/node/v22.23.2/bin:$PATH \
  npm --prefix open-webui exec prettier -- --check \
  ../README.md ../docs/bioagent-implementation-roadmap.md \
  ../docs/bioagent-implementation-history.md \
  ../docs/m3-23-deployment-profile-reproduction.md
git diff --check
```

预期结果：两份 profile 输出各自 ID 与 SHA-256；根测试 9 passed，Agent 定向测试 37 passed、7 subtests passed；shell、Ruff、Prettier 和 whitespace 检查均成功。本轮没有前端源码变更，因此按项目约束不重复执行 build。

## 容量与数据库

本轮结束前本机卷约 460 GiB，总使用约 249 GiB，可用约 184 GiB；仓库约 2.4 GiB。新增内容为小型 Python／shell／JSON／文档和测试，没有新增 migration、SQLite 内容、模型权重、参考库、FASTQ 或 run 输出。

## 限制与回退

独立目标 profile 只证明 schema 与启动参数映射，不证明目标路径、依赖、鉴权、断网运行或真实分析已经验收。MiniMax-M3 仍需要现场允许的服务连通性和启动环境中的密钥，因此不满足本地模型或全离线生成要求。

回退时停止以 `BIOAGENT_DEPLOYMENT_PROFILE` 启动的新 session，取消该环境变量后重新执行 `./dev-services.sh restart`，即可恢复原 `.env`／默认值路径；profile 不改写 `.env`、数据库、run 或远端 worker。
