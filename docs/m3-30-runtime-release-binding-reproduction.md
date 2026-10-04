# 第 30 轮复现：Active ReleaseSet 规划与 run 冻结接线

日期：2026-10-04

## 范围

本轮连接第 28 轮 asset store 与确定性规划／运行状态，只验证小型工程 package。没有正式知识、规则、参考库、capability 或模型包，没有启动 workflow、调用 MiniMax-M3、修改业务数据库、扫描原始 FASTQ 或清理旧资产。

## 身份与运行语义

`active-release-set.json` schema v2 现在原子保存 active／previous ID、ReleaseSet SHA-256、排序 package ID／版本／manifest SHA-256、actor、时间和整体摘要。package 导入成功后目录为 0555、文件为 0444；版本更新必须导入新版本，不能覆盖原目录。

显式 DeploymentProfile schema v4 提供 `operations.asset_release_store`。Agent 规划时：

1. 验证 active state 自身摘要；
2. 验证 ReleaseSet 小文件摘要、passed regression；
3. 验证每个 package manifest 摘要、identity、许可和 passed validation；
4. 把规范化 binding 写入 plan 和 decision trace。

启动重复步骤 1–3；active 变化会使旧未启动方案与 authoritative plan 不一致。local／Cyclone runtime 再重验结构与 binding 摘要后保存进 run state。resume 只验证 persisted binding，不读取 current active；因此新切换不改写进行中或历史任务。大型 payload 的逐档 SHA-256 仍只在 import、activate／rollback 和管理员 `status` 执行。

## 小型切换演练

使用第 28 轮 41-byte 工程 fixture 新建独立 store；所有写入仅位于 `/tmp`：

```bash
python3 asset_release_manager.py --store /tmp/bioagent-round30-store \
  import-package /tmp/bioagent-round28-media/knowledge-v1 \
  --max-bytes 1048576 --min-free-bytes 1073741824
python3 asset_release_manager.py --store /tmp/bioagent-round30-store \
  import-set /tmp/bioagent-round28-media/release-set-v1.json
python3 asset_release_manager.py --store /tmp/bioagent-round30-store \
  import-set /tmp/bioagent-round28-media/release-set-v2.json
python3 deployment_admission.py \
  --state-file /tmp/bioagent-round30-admission.json \
  drain --reason 'Round 30 runtime binding drill'
```

draining 期间依次 activate v1、activate v2、rollback，并在每一步执行：

```bash
python3 asset_release_manager.py --store /tmp/bioagent-round30-store binding
```

实际身份：

| 状态        | ReleaseSet SHA-256                                                 | binding SHA-256                                                    |
| ----------- | ------------------------------------------------------------------ | ------------------------------------------------------------------ |
| active v1   | `c4b2342678f7840193abb0568cb00c3b179b17e745c29bd7f90cc223675df507` | `69939b82503c372fcca8a2978c0524957423f90454a0496cbbbac577931f98bc` |
| active v2   | `ae6b8badab1ba1d5954e3f1c50b2052ad6940279ca7143c643bf3060ce6e9eb6` | `f6ac47622634d65ceef2f3e769822c14f2035c9381c20a0119009cde2e5e98c2` |
| rollback v1 | `c4b2342678f7840193abb0568cb00c3b179b17e745c29bd7f90cc223675df507` | `69939b82503c372fcca8a2978c0524957423f90454a0496cbbbac577931f98bc` |

最终 state 557 bytes、mode 0600；package directory 0555、manifest 0444。store 20 KiB、media 16 KiB，active v1、previous v2、incomplete imports 0。准入已恢复 accepting。

Agent 独立读取命令：

```bash
cd agent
/Users/lfz/miniconda3/bin/conda run -n adapter python -c \
  'import json; from pathlib import Path; from asset_release_binding import load_active_release_binding; print(json.dumps(load_active_release_binding(Path("/tmp/bioagent-round30-store")), sort_keys=True))'
```

结果与 root `binding` 完全相同。

## 自动验证

```bash
/Users/lfz/miniconda3/bin/conda run -n adapter python -m pytest -q \
  tests/test_asset_release_manager.py tests/test_deployment_profile.py \
  tests/test_deployment_backup.py tests/test_deployment_preflight.py \
  tests/test_deployment_admission.py

cd agent
/Users/lfz/miniconda3/bin/conda run -n adapter python -m pytest -q \
  tests/test_asset_release_binding.py tests/test_deterministic_planner.py \
  tests/test_deterministic_runtime.py tests/test_remote_client.py \
  tests/test_remote_worker.py tests/test_adapter.py tests/test_config_profile.py \
  tests/test_admission_control.py
```

根测试 32 passed；Agent 101 passed、26 subtests passed。负向覆盖 state／set／manifest 漂移、symlink、未通过验证或未知许可、无 active、切换后启动旧方案、远端伪造 binding；恢复测试确认不读取 current active。

## 边界与回退

当前两个 profile 只登记目标 store 路径，未初始化正式 active；显式启用 profile 后若 store 未准备，新方案 fail closed，默认未启用 profile 的现有开发流程不变。回退时先 drain，再用 `rollback --actor ...` 切换 previous；已开始和历史 run 保持原 binding。没有实现无引用 package 清理，也没有证明任何 fixture 可供科学分析。
