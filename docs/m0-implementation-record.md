# M0 实施记录：MiniMax 过渡版

日期：2026-09-12。依据：[实施路线图](bioagent-implementation-roadmap.md)及本轮用户确认。

## 完成范围

本轮完成开发回放的工程链路：既有初筛结果 → 原始产物复算 → 小知识包检索 → 确定性规则 → MiniMax 说明草稿 → 引用／数值校验 → 现有 HTML 模板。没有重新执行 FASTQ，没有改写原始结果、正式报告或执行状态。

| 节点 | 本次完成                                                                              | 尚未完成                                                       |
| ---- | ------------------------------------------------------------------------------------- | -------------------------------------------------------------- |
| S0   | Workflow 1–6 配置依赖盘点、catalog 能力导出、真实结果冻结、最小公共契约和开发验证样例 | 参考库历史版本／许可／完整性确认；本地模型资源与生物学真值基线 |
| A0   | 隔离 CLI、原始来源复算、独立输出与失败记录                                            | 不扩展多人业务入口                                             |
| B0   | 12 个片段、来源／实体／关系、SQLite FTS5、工程规则、引用校验和待审核报告              | 专家审核、类群特异生物学规则和正式知识发布                     |
| C0   | 四类任务的统一 provider 契约、MiniMax SDK 适配、有限上下文、错误与云端策略            | 本地后端、权重身份和未微调本地基线                             |
| D0   | 真实结果的 MiniMax 草稿回放；禁止网络时的检索、数值报告与降级                         | 本地模型实际生成、完整离线生成、正常支持案例的专家审核         |

**M0 未全部完成。** 当前产物是开发草稿，不能算生物学准确率评测或完整 Workflow 1–6 验证。所有资料与规则保持待审核，引用定位正确不代表引用语义充分。

## 案例与产物

选定来源为 Cyclone 的 `analysis-20260905-003912-6e535218`，样本 `BJ-2024-615-f98f3838`，候选是 Kraken 报告中的 taxon `2955291`。这是抽样初筛信号，原有 `known_virus_high_confidence` 仅还原历史工程路由，不提升为确定分类。

冻结包为 261,276 字节，只包含 state、telemetry、routing、初筛日志、Kraken 小表、fastp JSON 及依赖盘点；不包含 FASTQ 或参考索引。首次读取核查文件稳定性，保存 SHA-256；后续回放必须提供整个包的冻结哈希：

```text
43a2e26300d2cdd0e801669bc6d2ed9df1ce6d9380d0507702565bde2593da9e
```

已有 74 条 schema v4 数值证据通过原校验；新增 7 个候选级指标：

| 指标                       | 实际值              | 口径／来源                               |
| -------------------------- | ------------------- | ---------------------------------------- |
| 抽样总对数                 | 138224              | fastp before_filtering.total_reads / 2   |
| 过滤后分类总对数           | 125242              | Kraken root 与 unclassified 分支计数之和 |
| 病毒分支对数               | 33248               | Kraken taxid 10239，第二列               |
| 候选分支对数               | 33247               | Kraken taxid 2955291，第二列             |
| 候选占抽样总对数比例       | 0.2405298645676583  | 33247 / 138224                           |
| 候选占病毒分支比例         | 0.9999699230028873  | 33247 / 33248                            |
| 候选占过滤后分类总对数比例 | 0.26546206544130563 | 33247 / 125242                           |

配对计数依据运行日志中的实际 `--paired` 命令与输入样本定位；不把全样本、抽样和过滤后的分母混用。新指标保留原文件定位、哈希、公式和同源分组；未知 attempt 和历史工具／参考版本保持 unknown。

所有保留产物位于 `Cyclone:/data/user/liufangzhou/runs/`：

- `m0-baseline-20260912/bundle.json`：不可变结果包及当前配置依赖观察。
- `m0-minimax-20260912-final/`：最终代码、资料与模板下的 MiniMax 回放；本次模型将引用／证据 ID 数组输出成错误类型，返回 `MODEL_SCHEMA_INVALID`，保留数值报告。
- `m0-offline-20260912-final/`：最终代码下的断网数值报告与降级记录。
- `m0-minimax-20260912/`、`m0-minimax-20260912-budget8192/`：调试期间保留的降级结果。
- `m0-minimax-20260912-structured/`、`m0-offline-20260912/`：首次成功生成和首次断网验证，保留其原始资产哈希。

每个回放目录包含 `report.html`、`evidence.json`、`citations.json`、`assessment.json`、`provider-trace.json`、`baseline.json`、知识／规则／release JSON 和 `validation.json`。最终记录还包含运行所用 Python 源码哈希；provider trace 记录请求预算、模型配置、SDK 版本、耗时、结果与统一错误，不保存密钥或模型内部推理。

真实模型验证共进行四次受控调用，没有应用内自动修复：最初两次暴露输出预算和 SDK 单轮结果适配问题；第三次成功生成三条草稿并保留全部五条规则发现，耗时 14,893 ms；最终留存调用在 13,438 ms 后因 schema 类型错误被拒绝。成功生成与结构失败都保留，不将单次成功解释为模型稳定性或语义准确率达标。最终调用使用 claude-agent-sdk 0.2.152。

## 知识包、规则与参考库限制

`agent/assets/m0` 约 16 KiB，SQLite 关系表和 FTS5 索引由冻结 JSON 在内存重建，不维护第二份二进制数据库。资料包括固定 agent commit 的方法／工具片段，以及 [Kraken 官方手册](https://github.com/DerrickWood/kraken2/blob/master/docs/MANUAL.markdown)和 [fastp 官方说明](https://github.com/OpenGene/fastp)的少量署名摘录。外部资料固定了摘录内容、抓取日期和哈希，未确认的上游 commit／分发许可保持 unknown。

- 默认检索排除待审核片段。`--include-unreviewed` 仅允许开发回放使用；结果始终标记待审核，模型不能自行修改审核状态。
- 中文查询与索引使用相同双字词项，英文工具名及 taxon ID 保留精确词项。来源损坏、定位错误或跨快照引用被拒绝；空知识与检索不可用分别返回状态。
- 工程规则保留初筛范围、同源证据相关性、参考库未知、缺失对照、待审核、知识不足和数值冲突。没有把工程阈值包装成生物学判读规则。
- 模型只返回本次 evidence／citation ID，数值必须使用证据占位符，报告由宿主填值并转义。冲突和限制由宿主独立渲染，不能被模型省略。
- 当前只能验证结构、引用定位和数值绑定；自由文字的生物学适用性仍需审核。首次草稿中出现过将分类器与宿主路由职责混述的文字，这类语义问题不算自动验收通过。

只读盘点覆盖六个已注册 workflow 的配置：36 个软件条目、17 个参考依赖条目。Workflow 4 的 `bracken_est` 配置路径缺失，其余条目仅确认文件、目录或索引前缀存在；不代表这些能力已运行验证。BOLD 未发现明确注册依赖，未进行全盘搜索。Workflow 5 的参考序列来自输入 artifact，本轮未把示例 reference_fasta 当作已发布参考库。

资源观察：本机为 Apple M3、16 GB 内存；Cyclone 为 x86_64、约 124 GiB 内存，盘点时可用约 108 GiB，`/data` 可用约 440 GiB。本次按用户决定不安装模型、不开展 GPU／训练性能评测，也不依赖 5090。

初筛实际使用的 Kraken 库记录了 16 个顶层文件的大小和修改时间；未扫描大型索引哈希，也不能由当前目录证明历史库身份。NT、NR、CheckV、rRNA、宿主与专用库均保留其当前观察和 unknown 项，不搬库、不重建索引。run-local SeqKit 覆写与原 Workflow 配置分开记录。

## 复现

从根仓库执行。需要 adapter 环境的 SDK／Pydantic／jsonschema 与报告模块所需的 typer。当前机器可借用既有 backend 依赖，无需新增模型或大包：

```bash
export PYTHONPATH=/Users/lfz/miniconda3/envs/open-webui/lib/python3.11/site-packages
M0_PYTHON=/Users/lfz/miniconda3/envs/adapter/bin/python
M0_RUN_ROOT=/data/user/liufangzhou/runs
```

重新冻结会读取原 run；输出必须使用尚不存在的 `m0-*` 名称：

```bash
"$M0_PYTHON" m0-replay.py freeze \
  --ssh-host Cyclone --run-root "$M0_RUN_ROOT" \
  --source-run "$M0_RUN_ROOT/analysis-20260905-003912-6e535218" \
  --output "$M0_RUN_ROOT/m0-baseline-new"
```

使用已冻结包进行经授权的云端回放。密钥只从当前交互 shell 环境继承；`--allow-cloud` 是本次显式授权，不存在自动回退。预算为 180 秒、8192 输出 tokens，单轮生成：

```bash
"$M0_PYTHON" m0-replay.py run \
  --ssh-host Cyclone --run-root "$M0_RUN_ROOT" \
  --bundle "$M0_RUN_ROOT/m0-baseline-20260912/bundle.json" \
  --bundle-sha256 43a2e26300d2cdd0e801669bc6d2ed9df1ce6d9380d0507702565bde2593da9e \
  --output "$M0_RUN_ROOT/m0-replay-new" \
  --allow-cloud --include-unreviewed
```

不传 `--allow-cloud` 时不会调用 SDK／模型；不传 `--include-unreviewed` 时，当前知识包返回不足，模型不被调用。两种情况仍输出已验证数值。错误来源、错误哈希或越界路径会失败并尽量保存独立的 `validation.json`；远端不可达或输出目录非法时写 stderr，不修改原 run 的状态。

完整断网复现需要把小型冻结包预先放入离线机器自己的 run root，省略 `--ssh-host`，并使用新的本地 `m0-*` 输出目录。在 macOS 上，实际验证采用：

```bash
sandbox-exec -p '(version 1) (allow default) (deny network*)' \
  "$M0_PYTHON" m0-replay.py run \
  --run-root /private/tmp/bioagent-m0-offline/runs \
  --bundle /private/tmp/bioagent-m0-offline/runs/m0-baseline/bundle.json \
  --bundle-sha256 43a2e26300d2cdd0e801669bc6d2ed9df1ce6d9380d0507702565bde2593da9e \
  --output /private/tmp/bioagent-m0-offline/runs/m0-offline-new \
  --include-unreviewed
```

隔离进程连接 `127.0.0.1:5173` 被操作系统以 PermissionError 拒绝；离线输出为 `numeric_only / CLOUD_DISABLED`，模型调用数为零。验证报告另行传回 Cyclone 留存。这证明检索与确定性路径离线可用，不证明本地模型生成。

## 检查与回退

- Agent 全套测试：122 passed，2 skipped。跳过项依赖本机不存在的 Workflow 源目录与 Snakemake，不能计作远端真实计算验证。
- Backend：12 项报告／证据／交付测试通过。
- 根 CLI：3 项文件边界及资产完整性测试通过。
- Ruff 与变更 Markdown／JSON 的 Prettier check；没有前端应用修改，未运行前端 build。
- 三类工程样例分别是观测回放、明确派生的数值冲突和知识／证据不足。派生测试使用 synthetic 标识，模型部分用可控 stub 验证边界；不计生物学性能，未授权训练，也未建立训练／最终留出集。

已有输入、快照和报告不覆盖；修订时创建新输出目录。停止回放入口或设为 `local_only` 即可退出云端开发路径，确定性分析仍可使用。旧 Claude transcript 保留，不作为新 provider 的业务上下文来源。本次未启动或重启本机服务、远端 worker 或生信任务，未执行 Git commit。
