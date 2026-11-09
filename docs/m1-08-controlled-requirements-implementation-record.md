# M1 第八轮：通用受控需求修改实施记录

日期：2026-09-18。接续[第七轮标准交付报告](m1-07-standard-delivery-report-implementation-record.md)。本轮只交付 A2 受控需求／参数、B1 最小 manifest 与 C1 受控改参评测切片；完整 A2、B1、C1、M0／M1 仍未完成。

## 范围与契约

- Workflow 1 新增 `read_qc`、`rrna_filter`、`sample_merge`、`assembly` 五个公开交付终点，连同既有 `contig_filter` 形成五段最小前缀；原六个分析目标继续保留。raw reads 上保留下游目标同时排除 assembly 会返回 `PATCH_DEPENDENCY_CONFLICT`，提供现成 contigs 时则无需 assembly。
- 最小 `CapabilityManifest` v1 登记公开阶段依赖、输入／输出 artifact、验证状态、影响和 adapter 版本。首个能力 `workflow1.read_qc.fastp` 只发布 `length_required`、`qualified_quality_phred`、`unqualified_percent_limit`、`n_base_limit`、`average_qual`、`detect_adapter_for_pe`；拒绝未知字段、越界值、路径、输出和原始 CLI。
- `AnalysisPlanOptions` 与 `ProposedPatch` 新增 `excluded_stages`、`capability_parameters`。proposal 保存前以原 dataset revision 确定性预编译；失败不保存，成功返回目标、参数、步骤、影响和警告 diff。接受仍以 base revision 原子创建新方案，pending proposal 继续阻止启动。
- planner 与 execution spec 升至 v3。spec 冻结规范化参数、manifest v1、adapter v1；后端方案 hash 纳入 execution spec 与 planner 版本。旧能力契约可查看，但执行返回 `PLAN_VERSION_OBSOLETE`。远端 worker 在写 state／排队前再次规范化 spec 与步骤。
- Workflow 1 仅在 override 存在时，于 run-local 副本生成固定 Python wrapper。wrapper 删除被本能力托管参数的长／短旧形式，再追加 manifest 渲染参数；配置只改 run-local `software.fastp`。模型、API 与 wrapper 均不接受命令字符串。
- WebUI 新增 `GET /api/v1/analysis/capabilities`，主目标卡仍只显示六个主要目标，中间交付终点通过“更改需求”对话提出。按钮填入“我想更改需求：”并聚焦；方案卡和 proposal 卡使用能力目录中文标签显示交付、排除、参数差异、警告与重编步骤。

本轮没有数据库迁移，也没有修改 `AGENTS.md`。公开接口复用已有 plan／proposal JSON 列；能力目录不含路径或命令。

## 自动验证

- Agent 相关回归 106 项通过、2 项因本机缺少真实 workflow source 跳过。覆盖五个 W1 终点、最小依赖闭包、排除冲突、已有 contigs、参数规范化／越界／未知字段／不适用、run-local wrapper、远端 worker 复验与五个固定评测案例。
- Backend 方案／planner client 回归 22 项通过。覆盖提案预编译、参数 diff、冲突不保存、revision／pending 约束、能力目录代理、结构化错误码与旧能力契约禁止启动。
- Frontend 相关 Vitest 41 项通过。覆盖“更改需求”文案、草稿与聚焦契约、公开目录请求、参数错误文案、提案接受／拒绝、参数 diff／警告和窄屏布局契约。
- Ruff 与 Prettier 对本轮文件通过；最终一次 8 GiB Node heap 前端 production build 成功。

## MiniMax smoke

在已授权的 `minimax_explicit` 策略下，使用合成上下文顺序运行 `qc-only`、`fastp-length-50`、`vague-length`，每例最多一次调用；未发送 FASTQ、样本内容或私有路径，也未输出密钥。

结果均未通过：前两例分别在 176,188 ms、173,772 ms 返回 `MODEL_UNAVAILABLE`，第三例在 182,772 ms 返回 `MODEL_TIMEOUT`。SDK 同时报 `claude-code:unrecognized_model`，model 为 `MiniMax-M3`。没有结构化输出或 proposal 被登记；离线宿主夹具五例均通过。该结果说明确定性契约已具备，但当前外部 provider 配置不可作为可用模型基线。

## Cyclone 验证

切换前本机 Agent／Backend／Frontend 均未运行；Cyclone 资源接口确认 `running=0`、`queued=0`。当前 content-addressed worker 发布后执行：

- `analysis-cr-dry-qc-20260918-01`：`read_qc` DAG dry-run 通过。
- `analysis-cr-dry-rrna-20260918-01`：`rrna_filter` DAG dry-run 通过。
- `analysis-cr-dry-fastp50-20260918-02`：带 manifest override 的 DAG dry-run 通过。
- `analysis-cr-fastp50-20260918-03`：实际 run 完成，唯一规则为 fastp，冻结值为 `length_required=50`，manifest v1、adapter v1。输入双重指纹完成后复核一致；标准交付报告状态为 ready。
- 遥测登记 fastp 1.3.2，处理前 5,536,168 reads、处理后 4,285,442 reads，`too_short_reads=60,968`；这里只作为工程实跑证据，不作生物学结论。

前两个实际尝试保留在 run root：`analysis-cr-fastp50-20260918-01` 暴露配置替换错误地命中 `resource.fastp`／`params.fastp`，`-02` 暴露 JSON `true` 不是 Python 字面量。分别改为限定 `software` section 和使用 Python `repr` 后，`-03` 完成。失败记录未删除，原始 FASTQ 未写入；run-local wrapper、配置和产物均位于对应 run 目录。

## 限制与回退

- 只有 fastp 六个字段和精确 override 已发布；`workflow_default` 不展开源 workflow 内部默认数字。用户只说“长一点”时仍必须询问具体 bp。标准／宽松审核预设、adapter 序列、线程、输出、split／merge／dedup 均未开放。
- manifest 尚未覆盖 W2–W6、参考库 release、解析器身份、资源 schema 和完整兼容 ReleaseSet；因此 B1 只完成最小切片。
- 实际计算只验证 W1 的 fastp 终点；`rrna_filter` 只做 DAG dry-run。真实模型 smoke 失败，专家语义审核、本地模型比较和上线门槛仍缺失。
- 回退前先停止新任务准入并确认无 queued／running。Open WebUI 回退会隐藏新入口；Agent 回退到旧 spec 后不得启动 v3 方案。已完成和失败 run 全部保留，旧方案仍可读；无需回滚数据库。

建议提交信息：根仓库 `docs: record controlled analysis requirement support`；Agent `feat: compile controlled workflow requirements`；Open WebUI `feat: support controlled analysis plan changes`。
