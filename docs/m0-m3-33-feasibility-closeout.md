# 第 33 轮复现：M0–M3 当前可实施范围收口

日期：2026-10-04

## 只读核对

```bash
system_profiler SPHardwareDataType | rg 'Chip|Total Number of Cores|Memory'
system_profiler SPDisplaysDataType | rg 'Chipset Model|VRAM|Metal'
stat -f '%N %z bytes' open-webui/backend/data/webui.db
du -sk agent/assets open-webui/backend/data .
df -h . /tmp
python3 deployment_preflight.py check
test ! -e .local/asset-release-store
rg -n '^- \[ \]' docs/bioagent-implementation-roadmap.md
git status --short
git -C agent status --short
git -C open-webui status --short
```

硬件为 16 GB Apple M3（8 cores、Metal），没有 NVIDIA GPU；TaxonAgent／5090 按当前开发约束不可用。业务库 1,138,688 bytes，Agent assets 92 KiB，Backend data 4 MiB，仓库约 2.42 GiB，本机卷约 184 GiB 可用。

preflight 的源码 locks 为 ready；命令按设计以退出码 3 报告 source、Agent wheelhouse、Backend uv cache、Frontend npm cache、Pyodide cache、system runtime、compute runtime 七类离线介质缺失，并固定返回 `MODEL_NOT_OFFLINE_CAPABLE`。当前开发 profile 的 `.local/asset-release-store` 不存在，不能把第 28／30 轮 `/tmp` fixture 当正式发布。

## 继续实施所需的最小外部输入

| 范围         | 至少需要                                                                          | 解锁的主要任务                           |
| ------------ | --------------------------------------------------------------------------------- | ---------------------------------------- |
| 用户范围     | 重新授权上传，或重新纳入条件接入                                                  | A2 上传；第 7 节                         |
| 领域审核     | 专家批准的类群资料、规则、正常支持案例、引用语义、修订记录、独立 split 与指标门槛 | S0／D0／B0／B2／B3／C1                   |
| 正式计算资产 | W2–W6 参考库来源／许可／版本／完整哈希、兼容组合与合法真实数据目标                | B1、A2 正式 ReleaseSet、W2–W6 实跑与恢复 |
| 本地模型     | 获许可的模型／tokenizer、可用推理硬件与负责人决定；训练另需审核数据和受控训练环境 | C0、C1 本地比较、C2、C3、D0 离线生成     |
| 私有化介质   | 七类目标平台离线介质、正式 B4／C3 package 与一套不同地址／目录的独立节点          | A5、B4、C3、M3                           |

MiniMax-M3 已覆盖当前明确授权的 provider 工程验证，但它需要网络服务，不能替代路线图中“本地模型实际参与”“断网运行”或模型包现场验收。

## 停止条件与恢复方式

第 1–32 轮已经完成当前环境可验证的工程切片；所有未勾选主项都至少依赖上表一项。继续制造合成正式包、空安装器或未接入的抽象不会满足验收，因此停止扩展。

任一外部输入到位时，从对应未勾选任务继续：先登记来源、许可、身份与验收负责人，再使用已有 strict protocol、ReleaseSet、admission、snapshot／retention 和 run binding 底座验证。无需回滚或重做现有提交。

本轮只有文档变化；不重复上一轮已通过的 61 项 Backend、24 项前端测试与生产 build。验收为 Prettier、`git diff --check` 及三个工作区 clean（提交前仅本轮文档预期 dirty）。
