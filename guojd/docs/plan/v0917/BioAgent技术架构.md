# BioAgent 技术架构

**版本**：v0917（2026-09-17）  
**系统**：XvirMind / BioAgent 宏转录组病毒鉴定与专家研判系统  
**配套研究方案**：同目录《宏转录组未知病毒自动鉴定系统研究方案》v0917  
**读者**：实现与评审（比研究方案更细的模块、契约、时序、失败与测试）

本文描述**应当建成**的技术架构，并标注与 2026-09 代码基线的差距。凡写「现状」，均指代码或 demo 存在，不等于生产验收通过。

---

## 1. 架构目标与非目标

### 1.1 目标

1. 用户确认后，分析在注册计算插件上可复现执行。
2. 报告中的数字可从产物复算；引用可回到不可变知识原文。
3. 模型不可用时，结构化路径仍能完成规划、执行与数值报告。
4. 前端与会话 SDK 可替换；替换后领域行为不变。
5. 默认断网；云端调用需管理员策略 + 用户确认。

### 1.2 非目标

* 通用自主 Agent（开放电脑、无限工具环、自我复制 subagent）。
* 临床诊断器械注册与治疗建议。
* 用 LLM 重写 Snakemake 规则图。
* 未校准的融合概率作为官方置信度。
* 把 Open WebUI 或 Claude Agent SDK 做成不可替换产品本体。

### 1.3 设计原则（来自主流 Agent 系统，落地为约束）

| 原则 | 含义 | 落地 |
| --- | --- | --- |
| P1 职责分离 | Planner ≠ Executor ≠ Judge | 编译器 / runner / 校验器分模块，均非「同一个聊天循环」 |
| P2 类型化 IO | 工具输入输出有 schema | Artifact 类型、CapabilityManifest、ConversationAction |
| P3 最小权限 | 模型看不到原始 FASTQ 全路径密钥 | 裁剪证据包；禁止 Bash 跑流水线 |
| P4 失败闭合 | 不确定则降级，不编造 | KNOWLEDGE_INSUFFICIENT、未生成研判、waiting_resources |
| P5 人类把关 | 高成本动作需确认 | 方案启动、专项计算、补算、云端 |
| P6 不可变事实 | 历史输出不被新模型改写 | 报告 revision、ReleaseSet 钉住 |
| P7 评估门禁 | 行为由测试定义 | 负向契约集必须全拦截 |
| P8 可观察 | 每步有身份与原因 | attempt_id、waiting_reason、policy_version |

---

## 2. 逻辑视图

### 2.1 四层业务 + 两个平面

```text
                    ┌──────────── 资产平面 ────────────┐
                    │ 知识包 规则包 参考库 插件 模型包 │
                    └───────────────┬──────────────────┘
                                    │ release_id
┌──────────┐   ┌──────────┐   ┌─────▼────┐   ┌──────────┐
│ 输入层    │──▶│ 方案层    │──▶│ 计算层    │──▶│ 交付层    │
│ 数据/权限 │   │ 编译/确认 │   │ 队列/插件 │   │ 报告/审核 │
└──────────┘   └────┬─────┘   └─────┬────┘   └────▲─────┘
                    │               │              │
                    └───────知识与证据平面─────────┘
                         检索 规则 校验 引用注册
```

### 2.2 部署职责（三服务）

```text
[浏览器]
    │ HTTPS
[业务后端]  鉴权、项目、上传会话、方案登记、报告版本、审核
    │ 内部 API（已鉴权上下文）
[宿主编排]  检索、规则、编译、provider、提交 execution_spec
    │ SSH / 受控 RPC（非模型任意命令）
[计算服务]  队列、tmux、Snakemake、产物、run state
```

BioAgent **不得**直连业务数据库做权限判断；计算服务 **不得**执行模型生成的 shell。

### 2.3 与 v260830 Harness 八层对照

见研究方案 §3.1。实现时不要再创建 `core/pm_agent.py` 去 `query("执行完整鉴定")`。

---

## 3. 运行时：两种会话，一条分析链

系统里有两条并发控制流，必须在接口上拆开。

### 3.1 对话控制流（窄任务）

```text
用户消息
  → 业务后端鉴权 + 项目上下文
  → 宿主构造 ProviderRequest
       task_kind ∈ {intent, param_suggest, qa_cite, evidence_explain}
       tools: 无 或 只读检索（由宿主执行后注入片段）
  → ProviderResult JSON
  → ConversationAction.validate
       允许: respond | clarify | propose_patch
       禁止: start_run | write_report_html | cite_unregistered
  → 若 propose_patch：展示 diff，用户确认后 **重新编译**
```

`ConversationAction` 不得再无条件清空 citations；只能在校验失败时拒绝整包。

### 3.2 分析控制流（确定性）

```text
用户确认方案
  → POST /analysis/runs/start
  → 后端检查项目权限、dataset 指纹、plan revision
  → 编排器取出已编译 execution_spec（不可被请求体里的模型字段覆盖）
  → 计算队列 enqueue(run_id, spec, release_set)
  → worker: materialize inputs → adapter.phase → snakemake
  → 写 telemetry / artifacts
  → 交付：数值报告必出；研判视证据与知识是否齐全
```

### 3.3 智能模式时序

```text
start(auto)
  → screen: 抽样 5% + Kraken（记录 seed、库版本、实际 pairs）
  → publish report.preliminary (immutable)
  → continue confirmed targets   // 不得 skip 剩余
  → publish report.full
```

紧急模式：只跑 preliminary 范围，页眉写明「非完整鉴定」。

---

## 4. 模块目录（应当存在的包）

以下按逻辑包分组。路径以 bioagent 实现中心为准；前端在 open-webui fork。

### 4.1 契约与编译

| 模块 | 职责 | 关键类型 |
| --- | --- | --- |
| `conversation_contract` | 动作枚举、patch schema、引用校验 | ConversationAction, ProposedPatch |
| `pipeline_spec` | 目标、阶段、artifact 类型 | Goal, Stage, ArtifactType |
| `workflow_catalog` | 对用户暴露的生物学阶段，隐藏 rule 名 | Capability id |
| `deterministic_planner` | 依赖闭包、配对、路径、样本一致性 | ExecutionSpec |
| `resource_calibration` | 历史 P50/P90 额度 | ResourceEstimate |

编译规则：

* 输入不足 → 失败，列出缺失 artifact，不猜测。
* 宿主去除未开放 → 不得伪造成 clean reads。
* 未知 capability 版本 → 拒绝，要求重编译。

### 4.2 执行

| 模块 | 职责 |
| --- | --- |
| `workflow_adapters` | W1–W6：复制/symlink 工作流、改 config、phase 目标、解析器 |
| `analysis_runner` | 按 spec 顺序执行 phase，失败即停，写 state |
| `remote_worker` / `remote_client` | SSH、私有 tmux、flock、reconciliation |
| `adaptive_routing` / `adaptive_screening` | 模式、初筛、快报后继续 |
| `queue` | 单一调度者、优先级、waiting_resources、attempt |

Adapter 契约（每个 capability）：

```text
prepare(spec, workdir) -> PreparedJob
run(job) -> PhaseResult          # 调 snakemake，禁止 shell=True 拼接用户字符串
parse(artifacts) -> EvidenceRows
fingerprint() -> adapter_version + smk + container/pixi lock
```

### 4.3 知识、规则、证据

| 模块 | 职责 |
| --- | --- |
| `knowledge.store` | SQLite：Source, Passage, Entity, Relation, KnowledgeRelease |
| `knowledge.retrieve` | FTS5 + 过滤（类群、版本、项目授权） |
| `knowledge.cite` | 注册 citation_id，解析 locator |
| `rules.engine` | 类群特异检查，输出 RuleHit |
| `evidence.parse` | 各 workflow 解析器 → CandidateEvidence |
| `evidence.verify` | 复算、单位、分母、哈希 |
| `report.template` | 转义渲染 HTML/PDF，禁止模型 HTML |

### 4.4 Provider

```text
ProviderRequest:
  task_kind, schema_id, messages_or_context, budget, model_ref
ProviderResult:
  status, structured_payload, model_id, latency_ms, error_code
```

适配器：

* `provider.minimax_claude_sdk`：包装现有开发路径，隔离 session id。
* `provider.local_openai`：vLLM / llama.cpp。
* `provider.deepseek_harness`（可选）：关闭自主 tool loop。

宿主在调用前完成检索；模型侧**不要**再自己 MCP 搜网。

### 4.5 业务后端（WebUI）

* Project / ProjectMember（owner, analyst, reviewer, viewer）
* UploadSession（分块、偏移、摘要、配额）
* Dataset revision + 双重指纹（symlink 与 target）
* Plan revision + 绑定 ReleaseSet
* Run / Attempt / QueueItem
* ReportRevision / ReviewEvent
* 所有列表与下载服务端鉴权

Dashboard 必须读上述聚合，禁止静态示例数组作为交付。

### 4.6 计算后分析子系统

独立包 `XvirBench/benchmark/package`：

* `discover` → `extract`（调用各 `extract_results.py`）→ `tables` / `stats` / `plots_r` → `biology` → `report`
* 与鉴定 Agent 的关系：可读同一 run-dir，不写回 FASTQ，不启动 Snakemake。
* 提示词即规范：`FULL_PIPELINE_ANALYSIS_SYSTEM.md`。

---

## 5. 数据模型（最小字段）

### 5.1 CapabilityManifest

```yaml
capability_id: workflow1.upstream
version: "1.x"
stages: [fastp, rrna_filter, merge, assemble]
artifacts_in: [paired_fastq]
artifacts_out: [clean_reads, contigs]
params_schema: { preset_id: ["fastp_standard", "fastp_loose"] }
resources: { threads: 8, mem_gb_hint: "from_history" }
software: { snakemake: ">=9", seqkit: "required" }
references: [rRNA_index@release]
parser: w1_qc_parser@v
validation: dry_run | real_run | none
```

### 5.2 ReleaseSet

一次运行冻结：`knowledge_release`, `rule_release`, `reference_releases[]`, `plugin_versions[]`, `model_pack?`。

### 5.3 CandidateEvidence

```yaml
candidate_id: string
sample_id: string
run_id: string
attempt_id: string
observations:
  - name: nt_identity_aa
    value: 0.91
    unit: fraction
    query: RdRp
    subject: ...
    coverage_basis: "aligned / query_len"
    source: { file: "...", locator: "line:..", sha256: "..." }
    tool: diamond@...
    reference: nr@release
    missing: false   # 缺测不得写成 0
```

### 5.4 Assessment

```yaml
conclusion_grade: supported | partial | insufficient | conflicting | excluded
taxonomy_suggestion: { rank, name, note: "not ICTV final" }
conflicts: [rule_id]
gaps: [missing_control, low_depth]
citations: [citation_id]
limitations: [string]
model_pack: id?
knowledge_release: id
rule_release: id
```

### 5.5 ConversationAction

```yaml
type: respond | clarify | propose_patch
text: string
citations: [citation_id]   # 必须属于本轮 RetrievalResult
patch: { preset_id?: string, goals?: [...], viral_type?: ... }
```

非法：`type: execute`、未注册 citation、绝对路径、HTML 脚本。

---

## 6. 计算插件：W1–W6 适配要点

### 6.1 物化策略

* 原始 FASTQ：只读引用（绝对路径登记在 dataset，不进模型）。
* 中间产物：run root 内；跨 phase 用 symlink，禁止拷贝整库。
* workflow 源码：按插件版本拷贝或只读挂载，run-local 覆写必须进入快照。

### 6.2 阶段依赖（示意）

```text
W1: fastp → rrna_filter → merge → assemble
W2: 依赖 contigs 或 clean_reads（入口在 spec 中声明）
W3: 依赖 clean_reads / contigs（标记基因）
W4: 依赖 clean_reads
W5: 依赖 W2 代表序列 + clean_reads
W6: 依赖 W2 病毒序列
```

并行（W2∥W3∥W4）由 runner 按资源准入调度，**用户 UI 仍呈线性步骤**，避免暴露 DAG 造成误操作。

### 6.3 低深度与口径

合并 R1 < 5×10⁶ 标记 `low_depth`。RPM、物种数、contig 数不得单独写成生物学差异。Kraken 未分类比例与 Bracken 相对丰度分母必须写明「已分类空间」。

### 6.4 提取器接口（供后处理与证据解析共用思想）

```python
def extract_all(result_dir: Path) -> dict:
    return {"workflow": "...", "version": "...", "tables": {name: [row, ...]}}
```

鉴定路径的 parser 应与提取器字段对齐，避免两套口径。

---

## 7. 知识库技术设计

### 7.1 存储

* 不可变目录：`knowledge/releases/<id>/{manifest.json, corpora/, sqlite}`
* SQLite：FTS5 对 Passage；关系表不替代原文。
* 不做首期图数据库或独立向量服务。

### 7.2 五条资产线

1. 分类知识（ICTV、标志基因、别名）
2. 方法技能卡（W1–W6 陷阱与解释模板）
3. 工具契约只读视图（从 CapabilityManifest 生成）
4. 文献 Passage（许可、DOI、哈希、定位）
5. 参考库**说明**（计算侧索引仍由 B1 管，知识侧只登记用途与版本）

### 7.3 检索 API

```text
retrieve(query, corpora, taxon_hint, release_id, limit)
  -> RetrievalResult{ hits[], status: ok | empty | unavailable }
```

分数仅排序。中文与导入同预处理；gene 名 / taxon id 精确匹配。

### 7.4 安全

资料中的「请忽略以上指令」不得提升工具权限。检索文本与系统规则通道隔离。

---

## 8. 报告与审计

### 8.1 业务交付包

* `delivery.html`：转义后的鉴定/数值报告
* `evidence.json`：CandidateEvidence
* `assessment.json`（可选）
* `citations.jsonl`
* `release_set.json`

图若嵌入：data URI。禁止绝对路径与 traceback JSON。

### 8.2 运行审计包

* execution_spec、队列事件、attempt、tmux/pid 观察、工具版本、命令摘要（无密钥）
* 管理员内部报告可含对话时间线

### 8.3 批次后处理包

`XvirBench/benchmark/runs/<batch>/report.html|pdf` + `tables/` + `figures/` + `r/`。

生物学段落必须出现图号与样本数字；冲突优势类群走 (i)–(iv) 协议。

---

## 9. 安全、权限与多租户

* 权限在后端强制；浏览器隐藏不等于安全。
* 远端文件列表投影为项目逻辑根，防路径穿越。
* 上传：块大小限制、配额、未完成不可进 dataset。
* 模型输入脱敏：无密钥、无完整 FASTQ、无其他项目检索命中。
* `local_only` 默认；MiniMax 仅开发或显式比较。
* 危险数据删除：仅管理员工具，不进模型工具表。

---

## 10. 失败模式与状态机

### 10.1 Run 状态

```text
draft_plan → confirmed → queued → running
    → waiting_resources → queued
    → interrupted (进程消失，保留产物)
    → failed (phase 错，不交付完整鉴定结论)
    → completed_numeric
    → completed_assessed (研判通过校验)
```

preliminary 报告可在 running 时已发布，且此后不可变。

### 10.2 Provider 错误

| 错误 | 行为 |
| --- | --- |
| timeout / 5xx | 明确失败，不重试计算 |
| schema 不符 | 一次修复机会可选；再失败转表单 |
| 未知 citation | 拒绝该 action |
| 云端禁用 | 不得 failover 到公网 |

### 10.3 Worker 错误

* SSH 失联：显示 stale 缓存，远端继续
* 指纹暂不可验：retryable，不标失败
* 参考库清单不符：拒绝启动
* 重复 start：同一 run_id 幂等，不第二套计算

---

## 11. 可观测性与评测

### 11.1 日志与指标

结构化日志字段：`project_id, run_id, attempt_id, capability_id, release_set, actor`。  
指标：队列等待、phase 墙钟、provider 延迟、校验拒绝原因计数。

### 11.2 测试金字塔

1. 契约单测：planner、adapters、conversation_contract、report_evidence  
2. 路由与 worker 模拟：断线、重复恢复、auto 继续  
3. 知识：空检索、冲突、伪造 ID  
4. 前端：分析页配对与确认  
5. 登记的真实 run（写 run root，不改原始 FASTQ）  
6. 模型留出集（影子目录，不写正式报告）

代码修改顺序建议：相关 pytest/vitest → Ruff → Prettier → 必要时一次 frontend build。

---

## 12. 关键时序（详细）

### 12.1 受控改参

```text
用户：「fastp 宽松一点」
  → task_kind=param_suggest
  → 模型返回 preset_id=fastp_loose
  → UI 展示受影响步骤与数值差
  → 用户确认
  → compile(new revision)
  → 旧 plan 只读
```

### 12.2 专项 ICTV 计算（条件接入）

```text
用户对候选确认「按科阈值计算」
  → SpecialistTask(parent_run, candidate_id, input_snapshot)
  → 宿主检查服务健康与预算
  → 调用注册 capability（非模型 Bash）
  → 结果校验后挂到证据图
  → UI 显示「追加专项」，不改主方案 identity
```

无状态查询接口的服务：**禁止**自动重试启动。

### 12.3 专家补算

```text
Reviewer: 需补证（缺片段覆盖）
  → ReviewEvent
  → 系统生成关联候选的 plan 提议（新 steps）
  → 用户/分析员确认
  → 新 run，引用可复用 artifact
  → 新 AssessmentRevision 替代关系指向旧报告
```

---

## 13. 配置与交付

### 13.1 DeploymentProfile

交互地址、编排地址、计算入口、数据根、资产根、Pixi/Snakemake、模型后端、资源额度、`local_only`。不内嵌密钥；模板进 `.env.example`。

### 13.2 现场更新

导入暂存 → 清单哈希 → 兼容检查 → 回归 → 原子切换默认 ReleaseSet。在途任务保持旧组合。

### 13.3 备份

业务库、知识发布、run 清单、报告与审核。定期演练。保留期限项目可配。

---

## 14. 现状对照（实现差距清单）

| 架构组件 | 2026-09 基线 | 到 M1 必须补 |
| --- | --- | --- |
| ConversationAction | 有；曾清空 citations | 校验后保留合法引用 |
| W1–W6 adapter | 源码有 | 真数据逐项验收 + Manifest 发布 |
| auto 路由 | 高置信可结束 pipeline | 快报后继续 |
| 项目权限 | overlay/demo 有；cyclone 未合入 | 合入并替换 Dashboard 假数据 |
| 上传 | overlay 分块 | 生产路径准入与配额 |
| 队列恢复 | overlay | 单一调度者，禁双活 |
| 知识 | demo pack | 审核发布 + 断网检索 |
| 研判 | schema v4 数值 | 候选规则 + 校验说明 |
| Provider | Claude SDK 写死 | 接口抽出 + 一种本地后端 |
| 后处理分析 | XvirBench/benchmark 已可跑示例批次 | 与 run 产物字段对齐 |

---

## 15. 接口一览（最小目标）

前缀以业务后端 `/api/v1/analysis` 为例。

| 方法 | 路径 | 作用 |
| --- | --- | --- |
| CRUD | `/projects`, `/members` | 项目隔离 |
| POST | `/uploads` + chunks | 大文件 |
| POST | `/datasets/preflight` | 配对指纹 |
| POST | `/plans/compile` | 确定性编译 |
| POST | `/runs/start` | 仅接受已编译 spec |
| GET | `/runs/{id}` | 含 waiting_reason, observed_at |
| POST | `/runs/{id}/resume` | 显式恢复 |
| GET | `/reports/{id}` | 指定 revision |
| POST | `/evidence/verify` | 数值与引用 |
| POST | `/reviews` | 审核事件 |
| POST | `/specialists` | 条件专项 |

编排对内：`Provider.complete(request)`；计算对内：`Queue.submit(spec)`。

聊天补全 `/v1/chat/completions` 只返回 ConversationAction，**不得**内嵌 start_run。

---

## 16. 编码红线（给实现者的提示词）

1. 不要给模型 `Bash` 执行 snakemake。
2. 不要让 auto 在初筛后 skip 用户已确认阶段。
3. 不要用模型 HTML 当作交付报告。
4. 不要把缺失写成 0。
5. 不要在知识为空时宣称研判已完成。
6. 不要为了里程碑发布更差的量化模型。
7. 不要把文档勾选当成 cyclone 已上线。
8. 不要引入第二套插件引擎「更通用」而弃用 catalog/adapter。
9. 不要自动外发样本到云。
10. 改报告口径必须先改提示词/生成器再重跑，禁止手改成品字节。

---

## 17. 术语

* **Capability**：注册的计算或专项能力。  
* **Artifact**：类型化产物（如 paired_fastq, contigs）。  
* **ReleaseSet**：一次运行钉住的资产组合。  
* **Preliminary report**：范围受限的不可变快报。  
* **Assessment**：待审核研判，不是诊断。  
* **Provider**：模型供应适配器。  
* **Host**：宿主编排服务。  
* **local_only**：无授权不离境。

---

## 18. 参考文献与依据（设计，非性能承诺）

* 本仓库顶层设计 v1.1、三轨实施清单 v1.1、建设评价 2026-09-10。
* ICTV Code 关于分类标准不可简单统一数值化的条款（用于拒绝「一个阈值打天下」）。
* 行业实践：工具调用 Agent、工作流引擎与 LLM 解耦、RAG 必须引用校验、Human-in-the-loop 审批高副作用工具（Claude Code / OpenAI Agents / 工作流产品如 Snakemake、Temporal 的职责分离思想）。
* 后处理分析规范：`FULL_PIPELINE_ANALYSIS_SYSTEM.md`。

具体论文列表与许可在知识包 Source 表中维护，不在架构文档复制未授权全文。


---

## 19. ConversationAction 与 Provider JSON 示例

### 19.1 合法 respond（带引用）

```json
{
  "type": "respond",
  "text": "根据已发布的 Picornaviridae 条目，P1 蛋白氨基酸差异常用于属级讨论，不能单独定种。",
  "citations": ["cite_ictv_picorna_p1_2024"]
}
```

宿主须确认 `cite_ictv_picorna_p1_2024` 属于本轮 `RetrievalResult.hits`。

### 19.2 合法 propose_patch

```json
{
  "type": "propose_patch",
  "text": "建议改用 fastp 宽松预设，将影响 W1 质控保留率，不改变下游 capability 集合。",
  "patch": {
    "preset_id": "fastp_loose",
    "expected_stages": ["fastp", "rrna_filter", "merge", "assemble"]
  }
}
```

非法字段示例（必须拒绝）：`patch.snakemake_extra`、`patch.skip_stages=["assemble"]`、`patch.shell="rm -rf"`。

### 19.3 ProviderRequest

```json
{
  "task_kind": "evidence_explain",
  "schema_id": "assessment_draft.v1",
  "budget": { "max_tokens": 1200, "timeout_s": 60 },
  "model_ref": "local-qwen-32b-awq",
  "context": {
    "release_set": "rs_20260917",
    "candidates": ["cand_001"],
    "rule_hits": ["HIGH_ID_LOW_COV"],
    "passages": [
      { "citation_id": "cite_...", "locator": "p.12#para3", "text": "……" }
    ]
  }
}
```

上下文只含裁剪后的证据与片段。禁止附带 FASTQ 路径列表以外的文件系统树。

### 19.4 校验伪代码

```
function validate_action(action, retrieval, evidence):
  if action.type not in {respond, clarify, propose_patch}: reject
  for id in action.citations:
    if id not in retrieval.ids: reject("unknown_citation")
  if action.patch:
    if keys(action.patch) - ALLOWED_PATCH: reject
    if action.patch.preset_id not in published_presets: reject
  return accept
```

---

## 20. 队列算法与恢复

### 20.1 排序键

```
priority_key = (
  project.priority,          # 管理员配置，数值小优先
  -wait_boost,               # 等待超过 T 小时后提升（默认 T=24，可配置）
  run.urgency_rank,          # emergency > auto > standard
  enqueued_at                # FIFO
)
```

同一时刻最多 1 个重型分析占用参考库敏感资源（NT/Kraken 全库）。轻量只读检索不走该槽。

### 20.2 准入

在阶段边界检查：CPU 余量、内存、run root 磁盘、是否已有 running job。不足则 `waiting_resources`，释放槽位给其他可跑任务，**保留用户目标**。

### 20.3 恢复检查表

恢复 attempt 前必须全部为真：

1. dataset 指纹（link 与 target）与 plan 绑定一致  
2. execution_spec 字节或规范哈希一致  
3. plugin 版本、Snakemake/Pixi lock 一致  
4. ReleaseSet 参考库清单完整  
5. worker 同一逻辑执行环境（或明确兼容矩阵允许）  
6. 已完成 phase 的 artifact 类型与哈希可验证  

任一项失败：新建 plan/run，只按契约引用可复用产物，禁止「目录里有文件就续跑」。

### 20.4 幂等

`start` 与 `resume` 以 `(run_id, idempotency_key)` 去重。控制面重启不得插入第二个 Snakemake。

---

## 21. 规则引擎（首期规则目录）

规则输出 `RuleHit{id, severity, evidence_refs, message_id}`，必须带上用到的 observation 名。

| rule_id | 触发 | 报告行为 |
| --- | --- | --- |
| HIGH_ID_LOW_COV | 同一性高且 query 覆盖低 | 冲突：不得仅因 identity 写「已知种」 |
| NEAR_THRESHOLD | 指标落入该类群阈值邻域（配置带宽） | 标注接近阈值，交给审核 |
| LOW_DEPTH_INFLATED_RPM | low_depth 且 RPM 为队列最高 | 技术效应，禁止「载量最高」 |
| HOST_CALL_VS_KRAKEN | W3 宿主与 W4 优势种域冲突 | 宿主以标记基因为准，k-mer 作偏差 |
| MISSING_CONTROL | 方案声明有对照但证据缺失 | gap，不得当阴性 |
| INCOMPLETE_SEGMENT | 分节段病毒缺少关键片段 | gap |
| CHECKV_NOT_VIRUS | CheckV 非病毒/污染提示 | 不得升为确证 |
| FAMILY_CONFLICT | 不同工具科级不一致 | 并列展示 |
| UNCLASSIFIED_DOMINANT | Kraken 未分类 ≫ 已分类 | fig/表必须声明组成空间 |
| PRELIMINARY_SCOPE | 报告来自紧急/抽样 | 页眉限制范围 |

类群阈值从知识包读取，不在 Python 里写死 90%。无适用规则 → `gaps += NO_APPLICABLE_RULE`，而不是「通过」。

---

## 22. 各流程证据解析口径

| 流程 | 主产物 | 解析注意 |
| --- | --- | --- |
| W1 | merge 后 reads、contig 统计、fastp JSON、rRNA 保留率 | 比例列 0–1 与 0–100 归一；Q30 口径写明 after_fastp |
| W2 | 假定病毒 contig、CheckV、ANI 簇 | HQ 条数 ≠ 流行率；长度分布单独证据 |
| W3 | 线粒体物种 | 与实验 host 对照；多样本一致才支持设计宿主 |
| W4 | kraken report、bracken 表 | fraction_total_reads 常为已分类空间；top15 ≠ 全库 |
| W5 | RPM 表、mapping rate | 分母 clean reads；与 W1 深度联合 |
| W6 | CheckV、注释表、一致性 | 暗物质比例如实；无功能注释不是失败 |

后处理 `biology.py` 的绑图讨论应复用同一口径，避免鉴定报告写 0.04%、批次报告写成 4%。

---

## 23. 前端信息架构（可替换，但主路径固定）

分析页必有、且尽量不依赖模型：

1. 项目切换  
2. 文件树或上传进度  
3. 配对结果与预检错误  
4. 目标勾选（W1–W4、可选 W6）与模式三选一  
5. 方案卡片：参数、库版本、预计资源  
6. 确认启动  
7. 运行：阶段、等待原因、快报下载  
8. 报告：数值 / 研判 / 审核  
9. 只读知识检索（可选）  

Dashboard：真实计数。地图与「全球疫情」装饰图不作为 M1 范围。

---

## 24. 文件级映射（实现中心）

| 逻辑 | 建议路径 |
| --- | --- |
| 动作契约 | `bioagent/agent/conversation_contract.py` |
| 编译 | `deterministic_planner.py`, `pipeline_spec.py` |
| 目录 | `workflow_catalog.py`, `workflow_adapters.py` |
| 执行 | `analysis_runner.py`, `remote_worker.py` |
| 路由 | `adaptive_routing.py`, `adaptive_screening.py` |
| 证据 | `open-webui/.../utils/report_evidence.py` 及独立 `agent/evidence/` |
| 知识 | 新建 `agent/knowledge/`（勿只写在 SDK skill） |
| Provider | 新建 `agent/provider/` |
| 计算源 | `Workflows/workflowN_*/` |
| 提取 | `Workflows/.../scripts/extract_results.py`, `XvirBench/scripts/extract_io.py` |
| 批次报告 | `XvirBench/benchmark/package/` |
| 知识发布 | `knowledge/releases/`, `publish_knowledge_pack.py` |
| 部署 | `deploy/`, DeploymentProfile |

cyclone `/data/bioagent` 仅为运行态，必须与上述实现中心同步，禁止长期两套逻辑。

---

## 25. M0 Demo 技术步骤（结果回放）

不跑完整 FASTQ，验证研判链路：

1. 选一个有授权的既有 run 包，登记产物哈希。  
2. 跑解析器得到 CandidateEvidence。  
3. 加载 demo 知识包与规则包。  
4. 检索 + 本地模型生成 Assessment 草稿。  
5. 校验器故意注入：改数字、假 citation、删冲突，必须失败。  
6. 渲染 HTML。  
7. 断网重复 4–6。  
8. 关掉模型，确认仍能出数值报告 + 「未生成研判」。  

该 demo 通过 ≠ W1–W6 全真机验收。

---

## 26. 性能与容量规划方法（不写死数字）

阶段 0 实测后写入 profile：

* 单样本 W1 墙钟 vs reads 数  
* Kraken 全库 vs 5% 抽样  
* 共享盘 IOPS 导致的并行衰减  
* 本地模型 tokens/s 与并发 1 的内存  

重型任务默认并发 1 的原因：参考库与慢盘争用。增加并发必须有实测，而不是「机器有 128 核」。

---

## 27. 与主流框架的集成边界

```text
                    ┌─────────────┐
     用户意图        │  宿主 Host  │  领域规则、编译、校验、提交
          │         └──────┬──────┘
          │                │ ProviderRequest
          ▼                ▼
   Open WebUI ─── 仅 UI  ──┼── Claude SDK / vLLM / DeepSeek Harness
   或其他前端              │
                           ▼
                    ExecutionSpec ── SSH Worker ── Snakemake
```

LangGraph / AutoGen 可用于**离线实验**编排四类任务评测，不得接入生产 runner。若未来引入图编排，只能画在 Host 内、工具表仍白名单。

---

## 28. 修订记录

| 版本 | 日期 | 说明 |
| --- | --- | --- |
| v260830 / v0616 | 2026-06 | Harness + Claude SDK 为中心的实验方案 |
| 顶层设计 v1.1 | 2026-09-10 | 私有化、三轨、模型与执行分离 |
| **技术架构 v0917** | **2026-09-17** | 把原则展开为模块、契约、状态机、规则目录与红线 |
