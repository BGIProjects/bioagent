# 第 27 轮复现：真实 Workflow 1 中断恢复

日期：2026-10-04

## 范围

本轮使用既有授权的 `BJ-2024-615_{1,2}.fastq.gz`，建立只含 Workflow 1 `read_qc` 的 standard run，验证真实 phase 中断后的同契约人工恢复。没有资料上传、模型调用、业务数据库写入、原始 FASTQ 修改或其他 run 中止。

## 连通与准入

开始前使用固定 SSH 选项做只读检查，并确认持久队列没有 queued／waiting／running 工作：

```bash
ssh -o ClearAllForwardings=yes -o BatchMode=yes -o ConnectTimeout=10 Cyclone \
  'python3 -c "import os; print(os.path.isdir(\"/data/user/liufangzhou/runs\"))"'
```

Agent `RemoteWorkerClient.resolve_sources` 重新解析 data-root logical path 与 allowlisted canonical target。两份输入预检和结束时的 stat 保持：

| read |       bytes |     inode |            mtime_ns |
| ---- | ----------: | --------: | ------------------: |
| R1   | 126,682,083 | 191113385 | 1775226330806003230 |
| R2   | 172,927,531 | 191113386 | 1775226370594836388 |

## 中断与恢复

run 为 `analysis-m127-w1-recovery-20261004`。通过公开的确定性 planner 编译 `goals=["read_qc"]`、standard routing，以同一 planner start／resume；临时演练 harness 不进入仓库。只有在 snapshot 同时满足 `execution=running`、runner PID alive、`upstream=running` 后才执行中断。

中断动作在 Cyclone 再次读取 state／supervisor，并逐一验证：

- supervisor 中的 runner／scheduler PID 未变化；
- runner cmdline 的 `--state` 精确指向本 run；
- runner 是独立 process group，避免遗留其 Snakemake／fastp 子进程；
- scheduler cmdline 的 `--run-root` 精确等于 `/data/user/liufangzhou/runs`。

验证全部通过后先停止 scheduler，再停止该 runner process group。随后 snapshot 建立同一 run-root 的单一 scheduler，由 reconciliation 将状态从 running 变为 interrupted；系统没有自动重算。人工 resume 重新核对输入、方案、worker、workflow 与工具身份后追加 attempt 2。

实际结果：

```text
worker:      a45fe40ea991e89198fa0021ebd0e050cd1abd409bd1e2b000c35acb8086ca89
attempt 1:   initial / interrupted
attempt 2:   manual_resume / completed
phase:       upstream / completed / returncode 0
dependency:  daabfcdcdf223ffbbdc1775c61545f42991bf6c0bc25e349a5a84b15a88a2633
checkpoint:  6 files / 274179641 bytes / b91d7ee890951367ba007023ce8bde79cb2774da4dbff3093d94486f890b5d17
final:       completed / returncode 0
```

最终标准 HTML 为 91,989 bytes、SHA-256 `8957923f8d6a93c74d7acad6f886a1fa3656d5198015dbc26412cc5ad6d1364e`；PDF 为 540,867 bytes、SHA-256 `375472a89a09613a6f44fef7045a52a46fc4c44950c6312b341994b34d4c9b25`。final report ready；runner PID 不再存活，scheduler session 已退出，活动队列为空。

## 自动验证与容量

```bash
cd agent
/Users/lfz/miniconda3/bin/conda run -n adapter \
  python -m pytest -q \
  tests/test_remote_worker.py tests/test_analysis_runner.py \
  tests/test_deterministic_planner.py tests/test_deterministic_runtime.py \
  tests/test_adapter.py tests/test_workflow_adapters.py
```

结果为 129 passed、2 skipped、59 subtests passed。现有负向用例覆盖输入／方案／worker／依赖／已完成 checkpoint 变化、身份暂不可验证、runner 仍存活、重复 resume 与旧 state。

run 占 275,151,448 bytes，只位于 run root。结束时 Cyclone `/data` 可用 379,683,209,216 bytes，Home NVMe 可用 44,845,973,504 bytes；本机约 185 GiB 可用。没有清理输入、其他 run 或旧 attempt。

## 边界

本轮只完成当前具备完整恢复身份的 Workflow 1。Workflow 2–6 尚未完成 B1 的参考资产 release、许可、依赖完整身份及真实 run 验证，因此继续 fail closed，不因 W1 演练而开放。主机真实重启也未执行；boot ID 变化的 reconciliation 由自动测试覆盖。M1 仍受 A2、B1、B2 与 C1 未完成项阻断。
