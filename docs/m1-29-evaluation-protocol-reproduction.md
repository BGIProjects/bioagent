# 第 29 轮复现：四任务评测 protocol 与诚实 split

日期：2026-10-04

## 范围

本轮冻结四任务评测的案例身份、用途、近重复 group、split、指标和发布阻断。没有调用 MiniMax-M3、训练本地模型、建立专家标签、修改业务数据库或上传资料；现有 fixture 只评估 JSON schema 与宿主工程边界。

## 冻结协议

协议位于 `agent/benchmarks/evaluation_protocol_v1.json`，由 `agent/evaluation_protocol.py` 严格读取。当前身份为：

```text
protocol:      bioagent-four-task-evaluation-v1
protocol sha:  ae38892de8049c4c0f5e3519af4bbf19c202640773486e6440b953bcb5cdc4a8
suite:         m1-development-v1
suite sha:     668559eb0372db4316ef50a7fd46aa909895d2064e03359e1c3affcfcd11b2a3
group:         bj-2024-615-screening-and-m0-assets
development:   16
training:      0
validation:    0
final_test:    0
```

16 个案例共用一个候选、证据快照和 M0 资产，不能跨 split。development 允许 prompt iteration；其他 split 禁止。协议完整覆盖且只接受以下指标：

- schema pass rate；
- legal action／citation／finding boundary pass rate；
- provider error rate；
- provider 总延迟 p50／p95／max；
- 引用语义适用性；
- 冲突遗漏与幻觉事实率；
- 专家修订时间及字段成本。

前三类自动指标按实际模式输出。无 provider 的 fixture 不产生 provider error 或虚构 latency；语义与人工成本保持 `not_reviewed`／`not_measured`。当前 gate 固定 blocked，并明确列出缺本地模型基线、专家语义审核和三个空 split。

## 离线复现

开始前按项目约束执行只读 SSH 连通检查：

```bash
ssh -o ClearAllForwardings=yes -o BatchMode=yes -o ConnectTimeout=10 Cyclone \
  'python3 -c "import os; print(os.path.isdir(\"/data/user/liufangzhou/runs\"))"'
```

在仓库根运行 offline fixture；不加 `--allow-cloud`，所以不会调用 MiniMax-M3：

```bash
/Users/lfz/miniconda3/bin/conda run -n adapter python m1-check.py offline \
  --ssh-host Cyclone \
  --run-root /data/user/liufangzhou/runs \
  --bundle /data/user/liufangzhou/runs/m0-baseline-20260912/bundle.json \
  --bundle-sha256 43a2e26300d2cdd0e801669bc6d2ed9df1ce6d9380d0507702565bde2593da9e \
  --output /data/user/liufangzhou/runs/m1-offline-protocol-20261004
```

实际输出：

```text
mode:                    offline_validator_fixtures
schema passed:           16/16
engineering passed:      16/16
negative injections:     16/16 rejected
provider error/latency:  not_applicable
expert metrics:          pending
release gate:            blocked
files/bytes:             19 / 655097
results sha256:           97c6cd21fca62b22e3e38136125db3b32bd35096bc3f4e2a7a2897ba942eba32
protocol sha256:          ae38892de8049c4c0f5e3519af4bbf19c202640773486e6440b953bcb5cdc4a8
```

输出目录包含冻结的 `cases.json`、`evaluation-protocol.json`、bundle、逐案例记录及汇总。远端 `/data` 结束时可用 379,682,508,800 bytes；没有读取或写入原始 FASTQ。

## 自动验证

```bash
cd agent
/Users/lfz/miniconda3/bin/conda run -n adapter python -m pytest -q \
  tests/test_m1.py tests/test_provider.py tests/test_evidence_replay.py \
  tests/test_controlled_requirements_evaluation.py

/Users/lfz/.local/bin/ruff check \
  evaluation_protocol.py m1_evaluation.py tests/test_m1.py ../m1-check.py
```

结果为 34 passed、5 subtests passed，Ruff 通过。负向测试覆盖 suite SHA 漂移、case partition、同源 group 跨 split、metric set 与 gate 状态；严格读取器另外拒绝 prompt policy、字段及摘要不一致。

## 容量与边界

本机可用空间约 185 GiB，仓库约 2.4 GiB，`agent/benchmarks` 约 32 KiB；没有新增 SQLite 表、模型权重或资料副本。现有 16 例均为未审核 development fixture，不能用来估算生物学正确率、设置上线门槛或比较模型收益。只有取得来源与训练许可、专家审核并按候选／同源群建立独立非开发资料后，才能解除对应 blocker。
