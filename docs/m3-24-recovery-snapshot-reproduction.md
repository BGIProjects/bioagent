# 第 24 轮复现：内容校验恢复快照

日期：2026-10-04

## 范围

本轮建立 A5 的小型恢复快照基础：业务 SQLite、Agent 版本化 assets、已登记 run 的 state／reports 使用同一 manifest；恢复只进入新 staging 目录。没有覆盖正式数据、停止服务、执行 workflow、复制 FASTQ／参考库／完整 workflow 输出、自动清理旧备份，或宣称独立目标灾备通过。

## 契约与安全边界

- DeploymentProfile schema v2 新增 `operations.business_db`、`operations.backup_root`、`operations.backup_retention_count` 与 `resources.backup_max_gib`。profile 仍不保存密钥。
- SQLite 使用 online backup，而不是复制可能仍有 WAL 的数据库文件。恢复副本以 immutable read-only 模式检查，避免为已冻结 WAL-mode 文件创建 sidecar。
- run ID 只来自已冻结业务库，限安全字符；SSH host alias 也收紧为安全 token。rsync 固定 `ClearAllForwardings=yes`、`--protect-args`、`--safe-links` 与 include list，只读 `.bioagent/state.json` 和 `reports/***`。
- assets 与最终快照拒绝 symlink／非普通文件；单档和清单逐项核对，实际总量不得超过 profile 上限。失败的 `.partial-*` 自动清理，不产生可误用的完成目录。
- `stage-restore` 要求目标不存在，复制后再全量验证才原子改名。它不会把 staging 安装为正式服务。

## 自动复现

```bash
/Users/lfz/miniconda3/bin/conda run -n adapter \
  python -m pytest -q \
  tests/test_deployment_profile.py tests/test_deployment_backup.py

/Users/lfz/.local/bin/ruff check \
  deployment_profile.py deployment_backup.py \
  tests/test_deployment_profile.py tests/test_deployment_backup.py

bash -n dev-services.sh deployment/load-profile.sh \
  agent/start.sh open-webui/backend/dev.sh
git diff --check
```

预期为 13 passed，Ruff、shell 和 whitespace 检查通过。fixture 的业务库包含一个合法工程引用，并分别验证档案篡改、孤儿 project member、无效引用、已存在恢复目标和固定 rsync 安全参数。

## 当前实例只读演练

先按远端操作约束确认 SSH，再建立、验证和恢复到 `/tmp`：

```bash
ssh -o ClearAllForwardings=yes -o ConnectTimeout=5 Cyclone true

python3 deployment_backup.py create \
  deployment/profiles/cyclone-development.json round24-drill \
  --output-root /tmp/bioagent-round24-backup
python3 deployment_backup.py verify \
  /tmp/bioagent-round24-backup/round24-drill
python3 deployment_backup.py stage-restore \
  /tmp/bioagent-round24-backup/round24-drill \
  /tmp/bioagent-round24-restore
python3 deployment_backup.py verify /tmp/bioagent-round24-restore
```

三次验证一致：16 个受管普通文件、1,228,177 bytes、2 个项目、2 个成员、1 个已登记 run、10 类关系检查、0 assessment、0 持久化工程引用。后两个 0 是当前库真实状态；不以 fixture 的引用替代正式业务数据。快照和 staging 各约 1.2 MiB，Cyclone 仅被读取。

## 容量、限制与回退

演练后本机卷约 460 GiB，总使用约 249 GiB，可用约 185 GiB；仓库约 2.4 GiB。快照不包含 FASTQ、大型参考库、workflow 中间结果、模型权重或日志全文；这些应由 B4／C3 交付和既有 run 保留策略分别治理。

恢复工具尚未实现定时排程、项目级不同保留期、管理员确认清理、独立主机服务重建或浏览器鉴权验收，因此路线图 A5 第三项保持未勾选。回退只需弃用 staging；正式数据库、assets 和远端 run 从未被修改。
