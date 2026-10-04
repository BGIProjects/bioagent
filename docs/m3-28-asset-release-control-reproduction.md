# 第 28 轮复现：离线资产 ReleaseSet 控制面

日期：2026-10-04

## 范围

本轮新增独立的 package／ReleaseSet store 控制面，验证离线介质进入正式资产路径前的完整性、兼容性、容量与原子切换。没有修改当前 `agent/assets`、runtime 读取或数据库；演练 package 是 41-byte 工程 fixture，不是领域知识、参考库或模型交付包。

## 契约与命令

package manifest schema v1 固定包含：

- `asset_type`：knowledge／rules／reference／capability／model；
- `asset_id`、`version`、`source`、`license`；
- 排序且唯一的精确 `requires`；
- 排序且唯一的 payload path／size／SHA-256；
- pending／passed／failed 验证状态和 record。

ReleaseSet 固定 package manifest SHA-256、带时区创建时间和集合回归记录。实际入口：

```bash
python3 asset_release_manager.py --store /tmp/bioagent-round28-store \
  verify-package /tmp/bioagent-round28-media/knowledge-v1 \
  --max-bytes 1048576

python3 asset_release_manager.py --store /tmp/bioagent-round28-store \
  import-package /tmp/bioagent-round28-media/knowledge-v1 \
  --max-bytes 1048576 --min-free-bytes 1073741824

python3 asset_release_manager.py --store /tmp/bioagent-round28-store \
  import-set /tmp/bioagent-round28-media/release-set-v1.json
```

导入不执行公网下载或 archive 解压；来源必须是已展开的普通目录。payload 先复制到 store 内 `.partial-*`，复验后原子 rename。导入后的同一 package 版本不可覆盖；相同 manifest 重试为幂等。

切换与回滚必须经过第 25 轮 admission gate：

```bash
python3 deployment_admission.py \
  --state-file /tmp/bioagent-round28-admission.json \
  drain --reason 'Round 28 asset drill'

python3 asset_release_manager.py --store /tmp/bioagent-round28-store \
  --admission-state /tmp/bioagent-round28-admission.json \
  activate round28-engineering-v2 --actor round28-drill

python3 asset_release_manager.py --store /tmp/bioagent-round28-store \
  --admission-state /tmp/bioagent-round28-admission.json \
  rollback --actor round28-drill

python3 deployment_admission.py \
  --state-file /tmp/bioagent-round28-admission.json \
  resume --reason 'Round 28 asset drill complete'
```

实际结果为 v1 → v2 → rollback v1，最终 active `round28-engineering-v1`、previous `round28-engineering-v2`。两个 ReleaseSet digest 为 `c4b2342678f7840193abb0568cb00c3b179b17e745c29bd7f90cc223675df507` 与 `ae6b8badab1ba1d5954e3f1c50b2052ad6940279ca7143c643bf3060ce6e9eb6`；active state mode 0600，incomplete imports 为 0。admission 最终恢复 accepting。

## 自动验证与容量

```bash
/Users/lfz/miniconda3/bin/conda run -n adapter \
  python -m pytest -q tests/test_asset_release_manager.py
/Users/lfz/.local/bin/ruff check \
  asset_release_manager.py tests/test_asset_release_manager.py
```

新增测试为 10 passed。负向路径覆盖 payload 篡改、额外档、symlink／路径组件、缺依赖、manifest digest 不符、package／ReleaseSet 未通过验证、未知许可、空间门槛、immutable collision、state 篡改／symlink 与非 draining 切换。

演练 media 为 16 KiB、store 为 20 KiB，本机约 185 GiB 可用。package 内容不进入 SQLite；实际大型资产必须由操作员依据介质和目标 filesystem 明确给出 `max_bytes` 与 `min_free_bytes`，工具不会自动清理 previous 或历史 package。

## 边界

本轮 active pointer 只属于新 store；当前 Agent 仍从 tracked assets 和 run-local 冻结契约读取，不会自动采用该 pointer。完成 B4 仍需正式知识／规则／参考库／插件／模型 package、真实许可和回归记录、运行时按新任务冻结组合、历史 run 保留旧组合、独立目标离线导入、大型介质故障演练及受引用保留策略。MiniMax-M3 没有本地模型 package。
