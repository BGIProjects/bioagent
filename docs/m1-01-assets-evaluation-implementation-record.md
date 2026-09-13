# M1 第一轮：轻量资产准备与开发评测

日期：2026-09-12。依据：[实施路线图第 1.3 节](bioagent-implementation-roadmap.md#13-m1-本轮范围调整2026-09-12用户确认)及本轮用户确认。

实施顺序：本篇为第一轮历史记录；后续见[第二轮：最小项目与权限](m1-02-projects-implementation-record.md)。以下保留第一轮日期、结果及审核约定。

## 完成与限制

本轮交付 `m1-check.py assets|offline|evaluate`，推进 B1 的隔离资产检查、B2 的小包检索回归、C1 的四类开发评测。未新增业务 API、数据库或模型，也未改变线上编译、执行准入、可选能力、对话引用清空逻辑和正式报告。**M0、M1 均未全部完成。**

- B1 复用现有 catalog／adapter／CapabilityManifest，记录本机执行与解析代码哈希、远端配置与 Snakefile、小型软件文件哈希、run-local SeqKit 入口及依赖元信息。源码检查未覆盖全部 include／脚本闭包，不作为完整插件发布身份。
- 远端只读 M0 已登记路径：单文件哈希上限 2 MiB、总读取预算 16 MiB；参考目录／索引前缀最多记录 64 个条目并标记截断，不递归、不计算参考索引哈希。当前观察、M0 盘点与历史 run 身份分别保存。
- B2 仍使用约 16 KiB 的 M0 JSON 包及 SQLite 内存索引。中英文、类群过滤、跨快照拒绝、冲突共存、待审核排除、知识不足和检索不可用均有测试；冲突测试是人工构造，不能当作生物学案例。
- C1 固定四类各 4 个开发案例；证据说明复用真实初筛，其中缺失／比例越界两例为显式人工变异。案例、输入包及知识／规则哈希随输出保存；全部 `pending`，没有专家标签、训练集或最终留出集。
- 专家审核、审核工具与发布操作推迟到 M2；A1–A3、B1 正式执行绑定、B2 正式引用持久化、C1 专家语义验收和本地模型比较均未完成。

## 实际验证

资产检查结果为“不具备发布条件”：17 个参考依赖无完整发布身份，6 个 workflow 未形成完整源码与真实执行验证记录，知识／规则仍待审核且许可未确认。Workflow 4 的 `bracken_est` 仍缺失。当前配置哈希与 M0 盘点一致；这不证明参考库未变或其历史身份。小文件实际读取并哈希 4,968,400 字节，没有读取大型索引内容。

离线逻辑验证的 16 个合成输出全部通过，16 个注入错误全部拒绝；云端禁用返回 `CLOUD_DISABLED`。这里的“离线”指检索、规则、输出校验和数值回放不依赖模型网络；CLI 仍通过 SSH 存取 Cyclone 产物，本轮未重新执行操作系统级断网演练。真实 M0 包中 74 条原数值证据、7 个候选指标复算通过，生成独立数值报告，没有重跑 FASTQ。

### 一轮真实 MiniMax-M3 评测

每例最多调用一次，顺序执行；超时 180 秒、上下文上限 24,000 字符、输出上限 8,192 tokens。没有自动修复或补跑，失败保留在 `results.json`。结构通过不代表动作正确、引用语义充分或生物学判断正确。

SDK 为 `claude-agent-sdk 0.2.152`，模型请求为 `MiniMax-M3`，远端权重／版本身份仍未知。

| 任务       | schema 通过 | 工程校验通过 | 四例总延迟 |
| ---------- | ----------- | ------------ | ---------- |
| 意图／追问 | 4/4         | 3/4          | 28,507 ms  |
| 受控改参   | 4/4         | 1/4          | 48,554 ms  |
| 引用问答   | 4/4         | 4/4          | 26,464 ms  |
| 证据说明   | 2/4         | 0/4          | 50,043 ms  |

合计 schema 14/16、工程校验 8/16，provider 总延迟 153,568 ms。失败包括：只要求解释质控限制时额外追问；明确的目标变更请求仍返回追问；生成未注册的 `virus_identification` 目标；说明文字出现未绑定数字或引用缺失观测；另两例返回 `MODEL_SCHEMA_INVALID`。没有把这些输出登记为方案或正式报告。

评测上下文提供现有目标 ID 与类型白名单，尚无经专家审核的方法说明；这是当前提示和宿主契约下的开发基线，不是模型通用能力结论。两例 schema 失败沿用既有 provider 的错误契约，其原始非法载荷未返回，记录为 `output: null`；其余实际结构化输出均保存，不将空输出补造为成功草稿。

只统计 schema、预期动作／白名单改参、本次引用身份及证据／规则完整性的工程检查。语义准确率为“未审核”，人工修订成本及首响应延迟为“未测量”；总延迟由现有 provider 记录。不据这 16 个开发案例设定上线门槛。

### 自动测试

- Agent：相关 M1、证据回放、provider、动作契约、规划及适配器测试 **53 passed，2 skipped**；跳过项为本机缺少源 workflow 和 Snakemake 的已有集成测试，不算验证通过。
- 根仓库：M0／M1 CLI 隔离、目录拒绝、不可覆盖、无云端授权及产物哈希测试 **4 passed**。
- Backend：报告证据与交付回归 **9 tests，OK**。
- Ruff 与变更 Markdown／JSON 的 Prettier check；未修改前端应用，不运行前端 build 或 `npm run check`。

测试运行方式（各命令的工作目录见注释）：

```bash
# agent 目录
PYTHONPATH=/Users/lfz/miniconda3/envs/open-webui/lib/python3.11/site-packages \
  /Users/lfz/miniconda3/envs/adapter/bin/python -m pytest -q \
  tests/test_m1.py tests/test_evidence_replay.py tests/test_provider.py \
  tests/test_conversation_contract.py tests/test_deterministic_planner.py \
  tests/test_workflow_adapters.py

# 根目录
PYTHONPATH=/Users/lfz/miniconda3/envs/open-webui/lib/python3.11/site-packages \
  /Users/lfz/miniconda3/envs/adapter/bin/python -m pytest -q \
  tests/test_m0_replay.py tests/test_m1_check.py

# open-webui/backend 目录
BIOAGENT_REMOTE_DATA=false WEBUI_SECRET_KEY=test-only-key PYTHONPATH=. \
  /Users/lfz/miniconda3/envs/open-webui/bin/python -m unittest \
  open_webui.utils.test_report_evidence open_webui.utils.test_analysis_run_delivery
```

## 产物与复现

完整产物保存在 `Cyclone:/data/user/liufangzhou/runs/`，不进入 Git：

| 目录                  | 内容                                 | 实际文件字节合计 |
| --------------------- | ------------------------------------ | ---------------- |
| `m1-assets-20260912`  | 当前资产观察、基线、缺项与代码身份   | 569,584          |
| `m1-offline-20260912` | 离线工程校验、负向测试及真实数值报告 | 630,882          |
| `m1-minimax-20260912` | 一轮模型的全部输出、错误及宿主校验   | 521,875          |

各目录的 `files.json` 登记其余文件 SHA-256，`provenance.json` 记录代码身份、授权与未完成状态；`results.json` 为检查结果或逐例请求／检索／模型输出／校验。资产记录与 M0 数值报告中的路径仅供维护者核对；模型请求通过 `safe_context` 去除路径与私有字段。

本轮三个远端目录共 1,722,341 字节（约 1.64 MiB）。本机新增冻结案例 7,146 字节（约 7 KiB），沿用的知识／规则包约 16 KiB；CLI 临时工作目录退出即清理，远低于新增资产 100 MiB 上限。`files.json` 的 `payload_bytes` 不包含清单自身，表中为包含清单的实际文件大小合计。

`results.json` 的 SHA-256：

```text
assets:  230bfddb2fc6536fd6c5512957cea63f2a1d48b01ff8b901d3370faed38f0a9b
offline: 5181b1c0bc43623708b6c71be19ab8981498a18d8893aa7050fdb79ac8d71d6e
model:   43e014689c89d4d1c6bf1edadf456bd43f20b03e62fe687e9f51e8c9976e5921
```

从根目录，在已有 adapter／backend 环境下执行；沿用 M0 依赖，不安装模型或额外数据库。密钥由现有交互 shell 提供，不写入命令、文件或输出。以下使用新时间后缀避免覆盖本轮记录：

```bash
export PYTHONPATH=/Users/lfz/miniconda3/envs/open-webui/lib/python3.11/site-packages
M1_PYTHON=/Users/lfz/miniconda3/envs/adapter/bin/python
M1_RUN_ROOT=/data/user/liufangzhou/runs
M1_STAMP=$(date +%Y%m%d-%H%M%S)

m1_check() {
  "$M1_PYTHON" m1-check.py "$@" \
    --ssh-host Cyclone --run-root "$M1_RUN_ROOT" \
    --bundle "$M1_RUN_ROOT/m0-baseline-20260912/bundle.json" \
    --bundle-sha256 43a2e26300d2cdd0e801669bc6d2ed9df1ce6d9380d0507702565bde2593da9e
}

m1_check assets --output "$M1_RUN_ROOT/m1-assets-$M1_STAMP"
m1_check offline --output "$M1_RUN_ROOT/m1-offline-$M1_STAMP"

# 此命令显式授权本次 16 例云端评测；不自动重试。
m1_check evaluate --allow-cloud --output "$M1_RUN_ROOT/m1-minimax-$M1_STAMP"
```

不传 `--allow-cloud` 的 `evaluate` 只记录 16 个 `CLOUD_DISABLED`，不代表真实模型评测。`assets` 成功完成检查时退出码为 0，但必须读取其 `not_release_ready` 状态，不能把 CLI 成功误作发布批准。`evaluate` 完成并保存结果时也返回 0，个别模型失败通过逐例记录和汇总呈现；输入、传输或离线校验失败返回 1。

本轮实际使用以上相同参数，输出后缀固定为 `20260912`。模型响应和时间不可保证逐字复现；案例、输入、预算与代码哈希可核对。移除开发 CLI 即可停用本轮入口，没有数据库迁移或生产服务切换；历史产物保留，不自动清理。

## 未来专家审核操作（待 M2 网页实现）

**以下为后续操作约定，当前没有这些网页或审核入口。现在无需专家审核，也不必填写离线文件。** M2 落地时须以已实现权限、版本与发布能力更新此说明，再向专家开放。

1. **管理员准备。**创建专家账号，仅授予指定项目审核权限；分配冻结的报告、样本／候选、知识与规则版本。知识资产的审核权限另行明确，不因能看项目就自动获得全局发布权限。
2. **专家核对材料。**进入待审核列表，打开指定报告版本，核对样本身份、初筛／全量范围、指标单位和分母，查看证据定位、引用原文、冲突与缺失项；不能把引用定位通过视为语义正确。
3. **逐项提交意见。**对报告提交“认可／需补证／要求修订”，填写理由、适用范围和支持材料；对有问题的知识片段与规则单独提交审核意见，记录审核人、时间和所审版本。
4. **处理修订或补算。**纯文字解释修订追加新报告版本并保留原输出。新增计算形成关联候选的新方案，显示参数、数据及资源影响，由有分析权限的用户确认后才执行。
5. **解决不同意见。**各专家意见并列保留，由指定审核负责人明确裁决；不得通过最后一次写入覆盖此前意见。专家复核新版本与变更理由，历史报告和被替代关系仍可查询。
6. **维护者发布与导出。**知识／规则通过审核后，由维护者完成来源许可核查与回归，再发布新资产版本；旧报告继续绑定旧版本。仅将已审核且来源允许训练的修订另行导出，剔除未解决冲突；训练实验与模型上线分别批准，不自动训练或切换线上模型。
