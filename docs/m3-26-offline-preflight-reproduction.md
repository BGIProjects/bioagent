# 第 26 轮复现：离线依赖 BOM 与介质 preflight

日期：2026-10-04

## 范围

本轮冻结 Agent 依赖，并建立 Backend／Frontend 既有 lock 与目标平台离线介质的验证入口。没有下载或封装 wheel、uv cache、npm cache、Pyodide、系统工具、计算环境或模型；没有在独立目标安装、初始化数据库或断网运行。

## 源码锁检查

```bash
python3 deployment_preflight.py source

/Users/lfz/miniconda3/bin/conda run -n adapter python -m pip check
/Users/lfz/miniconda3/bin/conda run -n adapter \
  python -m pytest -q \
  tests/test_deployment_preflight.py \
  tests/test_deployment_profile.py \
  tests/test_deployment_admission.py \
  tests/test_deployment_backup.py

/Users/lfz/.local/bin/ruff check \
  deployment_preflight.py tests/test_deployment_preflight.py
```

`source` 实际结果：

- Agent pip-freeze：48 packages，1,050 bytes；
- Backend uv lock：356 packages、2,358 artifact hashes，726,658 bytes；
- Frontend npm lock v3：1,274 packages、1,274 artifact identities，547,768 bytes；
- 三档合计 1,275,476 bytes，均输出内容 SHA-256。

根部署测试合计 22 passed；Agent 环境 `pip check` 为 `No broken requirements found`。相关 Agent config／provider／adapter／admission 回归另为 40 passed、7 subtests passed。

## 当前 readiness

```bash
python3 deployment_preflight.py check
```

预期退出码为 3，而不是成功：缺少 `source`、`agent-wheelhouse`、`backend-uv-cache`、`frontend-npm-cache`、`frontend-pyodide-cache`、`system-runtime`、`compute-runtime` 七类目标介质；另固定返回 `MODEL_NOT_OFFLINE_CAPABLE`。这是预期的真实限制，不是测试失败。

有目标平台介质后执行：

```bash
python3 deployment_preflight.py verify-media /path/to/offline-media
python3 deployment_preflight.py check --media-root /path/to/offline-media
```

测试中的合成七组件介质可通过 deterministic readiness；随后仍因 MiniMax-M3 外部服务保持 full offline false。未知组件、缺组件、重复组件、摘要／大小变化、额外文件、symlink 和不带时区的 manifest 均拒绝。

## 容量与限制

本机约 185 GiB 可用、仓库约 2.4 GiB。当前 `open-webui/node_modules` 约 1.2 GiB，adapter Conda env 约 414 MiB，Open WebUI Conda env 约 2.7 GiB；本轮不复制这些开发环境，避免制造不适用于目标 OS／architecture 的数 GiB 假离线包。

完成 A5 第二项仍需用户指定实际目标平台与离线介质策略，再生成并核对所有 payload，完成安装、迁移、管理员／项目初始化和健康故障演练。用户确认继续使用 MiniMax-M3，因此全离线模型生成明确不可完成；确定性分析路径可在介质齐备后单独验收。
