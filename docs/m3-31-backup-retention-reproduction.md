# 第 31 轮复现：已验证快照的保留计划与显式清理

日期：2026-10-04

## 范围

本轮为既有恢复快照增加 profile 级保留计划与管理员显式清理。没有自动排程、项目级不同期限、正式备份根删除或独立恢复主机验收。当前业务库和 Cyclone run 只读；所有演练写入 `/tmp/bioagent-round31-backups`。

## 契约与失败边界

- `retention-plan` 先对每份快照运行既有完整校验，再核对 profile ID、带时区创建时间、目录类型及实际 bytes；按创建时间和名称确定性排序。
- 输出体的规范化 JSON 形成 SHA-256。`prune` 使用 0600 `.retention.lock`，在锁内重新生成计划；管理员摘要不一致时不删除任何目录。
- 只允许安全命名的同 profile 快照。损坏内容、异 profile、symlink、未知文件、`.partial-*` 或 `.prune-*` 一律 fail closed。
- 待删除目录先在同一备份根原子改名为摘要绑定的 `.prune-*`，再精确删除；不接收 glob，不触碰计划外快照或来源数据。

## 自动验证

```bash
/Users/lfz/miniconda3/bin/conda run -n adapter python -m pytest -q \
  tests/test_asset_release_manager.py tests/test_deployment_profile.py \
  tests/test_deployment_backup.py tests/test_deployment_preflight.py \
  tests/test_deployment_admission.py
/Users/lfz/.local/bin/ruff check \
  deployment_backup.py tests/test_deployment_backup.py
```

预期为 35 passed。回归覆盖保留顺序、错误／过期摘要不删除、精确回收 bytes、未知与未完成目录、内容篡改及异 profile 拒绝。

## 当前实例只读演练

先按约束完成 Cyclone SSH 只读连通检查。临时 profile 复制当前开发配置，只把 `profile_id` 改为 `round31-retention-drill`、备份根改为 `/tmp/bioagent-round31-backups`、保留数量改为 2；没有密钥。然后执行：

```bash
python3 deployment_backup.py create \
  /tmp/bioagent-round31-profile.json round31-1
python3 deployment_backup.py create \
  /tmp/bioagent-round31-profile.json round31-2
python3 deployment_backup.py create \
  /tmp/bioagent-round31-profile.json round31-3
python3 deployment_backup.py retention-plan \
  /tmp/bioagent-round31-profile.json
python3 deployment_backup.py prune \
  /tmp/bioagent-round31-profile.json \
  --plan-sha256 10c255d9d82159383e69338dca1bef7c7a1ca9d4327da48053954f4a5448e5d8
```

计划保留 `round31-3`、`round31-2`，删除 `round31-1`；总量 3,693,741 bytes，可回收 1,231,247 bytes。提交后 `deleted_bytes` 与计划一致，第二次计划的 `delete` 为空。两份剩余快照分别再次验证为 16 files、1,228,177 payload bytes、2 projects、2 members、1 run、10 relationship checks；目录实际约 2.5 MiB。

## 容量、限制与回退

演练时本机卷约 460 GiB、已用 249 GiB、可用 185 GiB，仓库约 2.4 GiB。被清理的 `/tmp` 演练副本不恢复，但正式数据库、Agent assets 和 Cyclone run 未修改；两份较新快照仍可 stage restore。

此机制不创建 cron／heartbeat，也不把一个 profile 的固定份数解释成按项目保留政策。A5 第三项还需要受控定期演练，以及在独立恢复环境核对服务重建、用户权限、引用／运行关联和旧报告浏览器访问。
