# BioAgent 实施历史：第 1–24 轮

> 覆盖日期：2026-09-12 至 2026-10-04；从实施路线图 v1.17 拆分，持续记录 M0–M3 工程切片。
> 本文保存各轮范围、证据、限制与复现记录，不表示 M0／M1／M2／M3 已通过整体验收。当前任务状态与后续计划见[实施路线图](bioagent-implementation-roadmap.md)。

<a id="m1-round-1"></a>

## 第 1 轮：轻量资产准备与开发评测（2026-09-12，用户确认）

本轮只推进 **B1 工程准备、B2 离线检索验证、C1 开发评测基础**，不以完成完整 M1 为目标。用户确认专家实际审核与审核工具留到 M2 网页实现；本轮不建立离线审核交接系统。知识、规则、评测案例与模型输出均保持待审核，不发布可信领域结论。

- 本机新增知识／评测资产控制在 100 MiB 内；沿用小 JSON 包与 SQLite 内存索引，不新增业务数据库、向量库或本地模型。
- 大型参考库留在 Cyclone；仅检查登记路径、小文件哈希和有限索引元信息，不扫描全库、不复制索引、不重跑 FASTQ。当前观察不能补证历史版本，缺少完整身份时明确“不具备发布条件”。
- B1 的生产执行绑定、正式参考库发布与真实计算验收，B2 的审核发布／项目鉴权／正式引用持久化，以及 A1–A3 留待后续。当前 CLI 不改变生产可选能力或准入。
- C1 固定四类各四个开发案例，用相同契约与预算执行一轮显式授权的 MiniMax-M3 评测，每例最多调用一次，保留失败，不自动修复或补跑。没有专家真值、本地模型基线、训练／验证／最终测试集，也不据此设置上线门槛。
- M2 专家网页的预期操作步骤记录在 [M1 实施记录](m1-01-assets-evaluation-implementation-record.md#未来专家审核操作待-m2-网页实现)，不是当前可用功能。

| 任务   | 本轮实际状态                                                                                                                    | 完整验收仍缺少                                                                             |
| ------ | ------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| B1     | 隔离资产检查 CLI、catalog／适配器／解析器源码哈希、run-local SeqKit 身份、真实远端依赖观察和异常测试通过                        | 完整 workflow 源码闭包、参考库版本／许可／完整哈希与兼容组合、编译／执行绑定、真实运行验收 |
| B2     | 复用小包与 SQLite；中英文、类群、快照、冲突共存、待审核排除、空检索及来源损坏回归通过                                           | 专家审核、正式发布、项目鉴权、业务引用持久化                                               |
| C1     | 16 个冻结开发案例、单轮评测 CLI、逐例输出／错误／耗时与工程校验；真实 MiniMax schema 14/16、工程校验 8/16，通过率不代表语义正确 | 专家语义审核、修订积累、隔离的数据划分、本地模型比较与上线门槛                             |
| M0／M1 | **均未全部完成**；真实 M0 数值回放的 74 条原证据和 7 个候选指标复算通过                                                         | M0 原有本地后端／离线生成／领域审核缺口，以及本表和 A1–A3 未完成项                         |

以上区分代码、自动测试、真实结果回放和真实模型评测，不将模拟异常或历史初筛回放计为新增 FASTQ 分析验收。命令、产物、容量、实际模型失败和复现步骤见 [M1 实施记录](m1-01-assets-evaluation-implementation-record.md)。

<a id="m1-round-2"></a>

## 第 2 轮：项目、成员权限与数据授权（2026-09-13，用户确认）

本轮只实施 **A1 的最小项目、成员权限、数据授权与必要页面**。继续使用 SQLite，不新增参考库、模型、云端评测或重型计算。上传、队列、专家审核动作、正式知识发布及引用持久化继续延期；审核开关只登记，优先级尚不影响调度。Dashboard 保留布局和品牌，将静态地图、统计与告警标为“演示数据”，真实项目列表独立展示，研判／审核显示“未接入”。

| 项目       | 本轮实际完成与证据                                                                                                               | 限制                                               |
| ---------- | -------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------- |
| 项目与归属 | Project／ProjectMember、Chat／dataset 权威 project_id、管理表单；管理员未入项目不能读取内容，成员默认查看，分析／审核独立        | 不提供审核动作或独立管理系统                       |
| 授权检查   | 分析、共享历史、文件、方案、执行、状态、报告及通用聊天／生成／导出／任务控制接入检查；封闭分享、克隆、文件夹绕过，项目会话只归档 | 既有权限测试和工程验证通过，不代表正式生产安全审计 |
| 数据范围   | 保存 logical／canonical 边界和根指纹；仅展示获准入口，创建／修订／执行重新授权；替换拒绝、暂时不可验返回 retryable 503           | 不扩容数据；原有远端 worker 不随成员撤权中止       |
| 历史迁移   | 隔离副本先升级，正式库一致性备份后迁移；1 个历史项目、1 名原用户、3 个 dataset、2 条文件授权；方案和执行路径保持                 | 未授权异常归属不开放；回退需配对旧代码与迁移前备份 |
| 页面与测试 | 项目选择、只读历史、项目共享数据入口、分页列表；隔离多用户测试、切换迟到回应测试及前端构建                                       | 未进行人工多浏览器验收；研判／审核统计仍未接入     |

本机真实 GET 验证中项目、历史会话、方案、3 个 dataset 共 8 项返回 200，未获准路径返回 403；已有双端文件的 quick preflight 返回 ready，仅检查前 1,000 对记录，未启动分析 workflow。迁移前 864,256 字节，迁移后 888,832 字节，一致性备份 864,256 字节。具体测试数量、命令、产物与回退步骤见[第二轮记录](m1-02-projects-implementation-record.md)；[第一轮记录](m1-01-assets-evaluation-implementation-record.md)保留原日期、模型结果、哈希及未来专家操作约定。

A1 按本轮最小工程范围交付；A2／A3、B1／B2／C1 的原缺口及 M0 本地模型／领域审核缺口继续保留，**M0／M1 整体未完成**。

## 第 3 轮：项目入口与页面体验（2026-09-13，用户确认）

本轮只收尾 A1 项目入口与页面体验。Dashboard 原页首统一选择项目、进入分析及管理员项目设置；Analysis 使用同一原页首呈现项目权限和返回看板入口，移除重复顶栏。新增控件采用局部深色圆角样式，桌面使用自动页首与剩余内容高度，窄屏自然滚动。

- 已完成：复用 Modal 的项目／路径／成员表单，关闭丢弃草稿并返回焦点，失败保留输入，保存后重读列表与权限；不改变后台授权。
- 已完成：显式无权项目不回退到其他项目，跨页保留 `project`，项目切换清除 `chat` 并重建内容，列表／分页／设置通过请求序号隔离迟到响应。他人会话只读提示放在会话标题旁。
- 验证：项目权限 Python 11 项、Vitest 36 项通过；Chrome 152／Cypress 13.17.0 的 18 项浏览器用例覆盖四种尺寸、125% 等效视口／DPR、底部可达、空状态、快速切换、分页、设置草稿及刷新。真实环境仅 GET 项目、历史和 dataset 列表，均为 200；修改情境均使用 API 桩。
- 本轮不新增 API、数据库表或迁移，不备份业务库，不引入模型或参考资料，不调用云端模型或提交计算。A2／A3、专家审核、正式发布及原 B1／B2／C1 缺口继续延期，**M0／M1 整体未完成**。

构建、截图、容量、命令及限制见[第三轮记录](m1-03-project-ui-implementation-record.md)。前两轮历史与专家审核约定保持原样；本轮浏览器桩验证不替代真实多用户端到端授权验收。

## 第 4 轮：数据集元信息与背景版本（2026-09-13，用户确认）

本轮只推进 **A2 元信息与背景版本追溯**：按 dataset ID／资料 revision 保存使用者背景，与计算输入分离。样本名称、批次备注、宿主背景、样本类型、表型、对照及数据集备注均为可选纯文字，不参与分类、模型指令或参数编译。

- 已完成：独立背景版本表及 GET／PUT／分页历史接口；项目成员可读，有分析权者可改；64 KiB 请求限制、字段／样本校验、并发 409、相同内容不重复追加。新数据版本不自动继承背景。
- 已完成：新方案冻结背景快照，去重比较背景版本但不改变计算 hash；下载报告按实际执行对应的方案 revision 显示转义背景。旧方案缺失快照仍为未记录，不读取最新背景回填。
- 已完成：数据集卡片内可收合表单与历史，取消丢弃草稿、失败保留输入、重新载入解决冲突，迟到回应隔离；窄屏复用卡片并保持输入框可达。他人会话保持只读。
- 验证：Python 主回归 36 项、报告／回放 7 项、Vitest 38 项及 Cypress 23 项通过；隔离升级与本机迁移均比对 53 张旧表的原字段数据不变。真实环境只读项目、数据集、背景与历史，均为 200。实际格式、构建及归档证据见[第四轮记录](m1-04-dataset-metadata-implementation-record.md)。
- 延期：上传、计算分组／技术重复确认、fastp 审核预设、完整资产绑定、A3、专家审核及前几轮缺口；指定本机 NGS 文件留待未来上传验收，本轮没有传输或分析。**完整 A2、M0／M1 均不勾选验收**。

第四轮随后补修背景表单裁切：桌面卡片增加最高占文件区 60% 的独立滚动区与局部细滚动条，窄屏维持自然滚动。Vitest 34 项及 Cypress 27 项通过，新增原生滚轮验证，纠正此前仅靠 `scrollIntoView()` 无法证明使用者可滚动的验收缺口。构建与新归档见[第四轮补修记录](m1-04-dataset-metadata-implementation-record.md#第四轮补修背景表单滚动2026-09-13)，不涉及 API 或数据库变更。

## 第 5 轮：样本分组与技术重复确认（2026-09-13，用户确认）

本轮只补 **A2 样本分组与技术重复确认**，沿用 run_id → sample_id，不处理病例／对照分组。仍由数据集建立者在具有项目分析权时修订，他人会话只读。

- 已完成：按样本预览修改前后 run／配对文件，逐个确认多 run 样本；字段变更清除确认、取消丢弃、失败保留及切换隔离。修订表单复用第四轮滚动区，移除重复高度限制。
- 已完成：PATCH 精确确认清单、两条正规化路径的 run 唯一性检查；确认摘要／哈希／操作者／时间存入既有 revision checks，预检保留。无需新表或迁移。
- 已完成：编译与执行检查确切数据版本；未确认历史多 run 数据须保存确认后重新编译。旧方案、报告、已启动执行不改写；新数据 revision 背景不继承。
- 验证：Python 90 项、adapter 映射 1 项、Vitest 36 项及 Cypress 34 项通过。只用小型合成资料、隔离数据库及 API 桩，无真实 FASTQ 计算；格式、构建、产物容量和限制见[第五轮记录](m1-05-sample-grouping-implementation-record.md)。
- 本机只读：健康、项目及数据集列表 200；详情因数据授权暂不可验证返回 retryable 503（本机 Agent 8001 无监听），未列为远端验证成功。Ruff／Prettier 与一次 8 GiB build 通过；归档约 1.71 MiB，无业务迁移或真实修订。
- 延期：上传、fastp 预设、完整资产绑定、A3、专家审核及前几轮缺口。**完整 A2、M0／M1 不勾选验收**。

## 第 6 轮：三种模式与阶段报告（2026-09-13，用户确认）

本轮只推进 **A3 前三项**，不扩展上传、持久化优先级队列、`waiting_resources`、恢复操作或大型知识库。execution spec 保持 v2，planner 与 routing policy 升至 v2；没有新增数据库表、迁移、模型或环境变量。

- 已完成：`auto` 对高／低信号均先原子发布不可变初筛快报，再检查完整流程资源并继续已确认 DAG；A／B 只表达初筛判断。完整资源不足时 execution 为 `blocked`，快报仍可下载。
- 已完成：`emergency` 只做 5% 初筛并结束，`standard` 不初筛并直接执行完整流程；auto／emergency 没有成对 reads 时统一降为 standard。新方案用 `routing_policy_version=2` 与 `completion_behavior` 表达语义，旧 policy 启动时返回 `PLAN_ROUTING_OBSOLETE`。
- 已完成：state v3 使用轻量 `reports` 登记 preliminary／final；初筛写入 `.bioagent/preliminary-telemetry.json`，固定生成时间、证据路径和 SHA-256，完整流程不得覆盖。旧 state 的单一 `report` 读取时按 `report_kind` 映射。
- 已完成：`/analysis` tab 直接建立对 `routingMode` 的响应式依赖；连续切换以请求序号隔离迟到回应，历史对话恢复已保存模式。任务区按状态分别展示“下载初筛报告”和“下载诊断意见书”。
- 验证：Agent 68 项（2 skip）、Backend 66 项、相关 Vitest 34 项及新增 Cypress 2 项通过；Cyclone 只完成 health、两条 logical source 解析、1,000 对 reads quick preflight 与 Workflow 1 单一 fastp DAG dry-run。未执行初筛、workflow shell command、完整分析或模型调用。
- 容量与限制：远端新 dry-run 目录 13 文件、224,759 bytes；资源历史 SQLite 仅只读核对且无迁移。持久化队列、重新排队／恢复、多样本真实运行、完整 A3 与前几轮缺口继续延期，**完整 M0／M1 仍不勾选验收**。

接口、测试命令、容量、限制与回退见[第六轮记录](m1-06-adaptive-routing-implementation-record.md)。

## 第 7 轮：标准交付报告（2026-09-17，用户确认）

本轮新增 W1–W6 标准交付报告，不合并现有诊断意见书：后者保留证据索引、结果边界及人工审核清单；用户不关心的一般文件清单移至改名后的“运行审计报告”。

- 已完成：run-local 提取、样本主表、低深度标记、分组非参数统计、R/ggplot2 图、自包含 HTML、同源 A4 横向 PDF、manifest 与 state `standard_delivery` 登记；只覆盖 W1–W6，使用确定性模板。
- 已完成：Agent／WebUI 经鉴权与 SHA-256 校验下载 HTML/PDF；状态接口公开可用格式，UI 分别显示交付报告、诊断意见书及运行审计报告。
- 已完成：方案冻结的样本背景传入远端 state；报告失败不改写计算结果，CLI 可独立 report-only 重建。
- 已完成：Cyclone 以既有 W1+W2 run 验证，W3–W6 正确跳过；报告未出现绝对路径、一般文件清单或 checklist，诊断意见书 checklist 回归保留。

实际命令、产物、测试结果、限制与回退见[第七轮记录](m1-07-standard-delivery-report-implementation-record.md)。

## 第 8 轮：受控需求与能力契约（2026-09-18，用户确认）

本轮只推进 **A2 受控需求／参数、B1 最小 CapabilityManifest 与 C1 受控改参评测切片**，不宣称完整 A2、B1 或 C1 完成。没有新增数据库表或迁移；复用方案 JSON、proposal 与 revision。

- 已完成：Workflow 1 发布 `read_qc`、`rrna_filter`、`sample_merge`、`assembly`、`contig_filter` 五个交付终点；确定性编译最小依赖闭包，排除必要步骤时返回依赖冲突，已有 contigs 时可以跳过 assembly。
- 已完成：fastp manifest v1 发布六个白名单参数与 `workflow_default`；execution spec／planner 升至 v3，冻结规范化参数、manifest v1、adapter v1 与方案哈希。远端 worker 排队前复验；旧能力契约必须重编。
- 已完成：proposal 在登记前确定性预编译，合法提案展示目标、排除、参数 before／after、影响和重编步骤；冲突提案不保存。`/analysis` 使用“更改需求”，公开能力目录来自 `GET /api/v1/analysis/capabilities`。
- 已完成：五个固定受控需求开发案例与离线宿主验证。经显式授权运行三例真实 MiniMax smoke，但 SDK 报 `MiniMax-M3` 未识别；两例 `MODEL_UNAVAILABLE`、一例 `MODEL_TIMEOUT`，均未生成越权提案，不记为通过。
- Cyclone：`read_qc`、`rrna_filter` 及带 `length_required=50` 的 DAG dry-run 均通过；实际 fastp run 最终完成，仅选择 fastp，输入指纹复核不变，遥测登记 fastp 1.3.2。前两次 run 分别暴露 YAML 作用域误替换和 wrapper 布尔字面量问题，修复后保留失败记录。

完整实现、验证、限制和回退见[第八轮记录](m1-08-controlled-requirements-implementation-record.md)。上传、标准／宽松审核预设、其他工具参数、完整 ReleaseSet／参考库身份、专家语义审核和本地模型比较仍延期，**完整 A2、B1、C1、M0／M1 均不勾选验收**。

## 第 9 轮：对话服务恢复（2026-09-21，用户确认）

本轮只恢复 Dashboard／Analysis 对话与 capabilities 读取，不扩展知识、执行或数据库范围。

- 已完成：Agent 固定 `claude-agent-sdk==0.2.103`／Claude Code 2.1.179，使用 MiniMax 中国大陆端点与 `MiniMax-M3[1m]` SDK 映射；health 校验并公开非敏感 SDK 版本。有效 UUID 保留 resume，缺失或非 UUID ID 使用单次临时 session。
- 已完成：authenticated capabilities 不再被 project guard 误拦；首次聊天 UUID 到下游模型 metadata 的链路有回归测试。宿主三服务、health、Backend capabilities 与一次带 UUID 的代理对话均验证正常。
- 实际 smoke：三例均不再出现 unavailable、timeout 或 unrecognized model；`vague-length` 通过，`qc-only` 与 `fastp-length-50` 被严格 schema 拒绝为 `MODEL_SCHEMA_INVALID`，未登记 proposal、未自动补跑。
- Dashboard 后续修复：一般聊天改用 message-only 契约，并安全接收通过该 schema 的 MiniMax 自然文字；只有 `source=analysis` 使用 action／proposal 契约。authenticated streaming smoke 返回正文且无错误，Analysis 严格边界保持不变。
- 诊断约束：Codex 沙箱可能无法访问宿主 tmux socket／loopback；冲突时必须在沙箱外复核服务状态。TaxonAgent、正式知识库、专家语义审核、本地模型和完整 C1 继续延期。

根因、配置、测试、实际耗时、限制与回退见[第九轮记录](m1-09-conversation-service-recovery-implementation-record.md)。第八轮失败记录保留，**完整 C1、M0／M1 仍不勾选验收**。

## 第 10 轮：工程知识引用闭环（2026-09-23，用户确认）

本轮只推进 **B2 小型工程知识引用闭环**，并重跑 C1 四类开发 smoke；不扩展分类学／领域知识，不新增数据库表、migration、向量库、环境变量或 Dashboard 检索。

- 已完成：发布 8,283 bytes 的 `engineering-knowledge-v1` 与 release registry，由 capability catalog 身份和文件 SHA-256 双重校验；只包含能力、交付目标、artifact、fastp 白名单参数及版本，使用内存 SQLite FTS5。
- 已完成：`/analysis` 对工程问题最多检索 4 段、每段 512 字；模型只能在 `respond` 引用本轮 snapshot ID。缺失、重复、伪造、跨 snapshot 或被篡改引用在输出前拒绝；ICTV 与 12 段 `pending` M0 资料仍不上线。
- 已完成：引用以 `analysis_knowledge_citations@v1` 随既有项目会话保存，不建独立表；Backend 与前端都执行大小／来源校验，历史对话在桌面及窄屏显示来源、版本、定位、snapshot 和“非生物学审核”提示。
- 验证：Agent 全量 168 passed、2 skipped；相关 Backend 107 项、Vitest 53 项、Chrome/Cypress 19 项通过。MiniMax 16 例真实 smoke 为 schema 12/16、工程校验 7/16；引用问答 4/4，通过以外的输出均被既有边界拒绝，不自动修复或补跑。
- 容量：tracked 工程 release 共 8,283 bytes；远端评测 8 文件、544,310 bytes。业务 SQLite 只增加每条回答至多 4 个受限短摘录，没有另建知识数据库。

命令、结果、哈希、限制与回退见[第十轮复现记录](m1-10-engineering-citations-reproduction.md)。正式领域知识、专家语义审核、claim 级领域引用、向量召回和完整 B2／C1／M0／M1 继续延期。

## 第 11 轮：持久队列（2026-09-25，用户确认）

本轮只完成 **A3 的持久排队切片**，不做数据上传、M2、模型／知识资产扩充或新的 FASTQ 计算。没有新增业务数据表、migration 或独立 queue database；队列事实继续保存在 Cyclone run root 的既有 state。

- 已完成：每个 run root 使用唯一的私有 tmux scheduler；`analysis.lock` 只保留最终互斥，不再由多个 per-run supervisor 竞争决定顺序。旧 queued state 缺少 queue metadata 时按 normal 和既有 `queued_at` 纳管。
- 已完成：queue policy v1 冻结权威 `project_id`／`project_priority`、路由级别与入队时间；排序依次为超过 aging 阈值的最老任务、项目 `high → normal → low`、同级 emergency、入队时间及 run ID。`BIOAGENT_QUEUE_AGING_HOURS` 默认 24，只接受正数，运行中任务不抢占。
- 已完成：准入资源不足转为 `waiting_resources`，登记阶段、原因和检查时间并继续检查其他任务。auto 初筛完成后若完整流程等待资源，会保留初筛报告及 full-analysis checkpoint，恢复时不重跑初筛。
- 已完成：重复 start 幂等；scheduler／控制连接／WebUI 恢复时重新纳管 queued／waiting。已启动 runner 以 PID、boot ID 和命令行核对，存活时只监看；确认消失时转 `interrupted`，不自动重跑。
- 已完成：执行前重新核对项目分析权限与 dataset／chat 的权威项目关系，优先级只从项目记录冻结。status 公开具名 queue 字段，资源摘要统计 waiting，`/analysis` 显示简体中文状态、位置、冻结优先级、等待阶段与可读原因。
- 验证：Agent 全套 178 passed、2 skipped；相关 Backend 165 项、Vitest 43 项、Cypress 3 项通过。Cyclone 隔离 diagnostic-only run 验证 `high+emergency → high → low`、资源等待恢复及 scheduler 中止后接管；4 个任务均只启动一次，主诊断目录共 72 KiB，未读写 FASTQ、调用模型或生信工具。

产物级一致性检查、attempt 历史与人工 resume 继续延期，因此不宣称 A3 或 M1 完整完成；上传、完整 ReleaseSet、正式领域知识、专家语义评测和本地模型也仍未完成。本轮命令、诊断状态和回退见[第十一轮复现记录](m1-11-persistent-queue-reproduction.md)。

## 第 12 轮：受控中断恢复（2026-09-25，用户确认）

本轮只收敛 **A3 的受控中断恢复切片**，不做数据上传，也不开始 M2。没有新增数据库表、migration、queue／attempt database 或配置项；attempt 事实与恢复契约保存在 Cyclone run-local state，业务库只追加既有 AnalysisEvent。

- 已完成：state v3 additive `recovery_contract` 与 `attempts`；新 run 从 attempt 1 开始，冻结方案／execution spec、能力契约、dataset 双重指纹、worker release、run-local workflow 及已登记工具／参考资产身份。每次 attempt 的小型控制产物位于 `.bioagent/attempts/<序号>/`，大型结果不复制。
- 已完成：Agent resume 只接受 `interrupted`、具备恢复契约且 runner 已消失的同一 run；在 run-local lock 内重验上下文、输入、worker、依赖及完成 phase 的 SHA-256 checkpoint，再原子追加 attempt 并以原项目优先级、当前入队时间重新排队。重复请求幂等；旧 state、身份不完整、任何变化或缺失均拒绝，暂时不可验证映射为 retryable 503 并保持中断状态。
- 已完成：恢复跳过已验证的完整 phase；中断 phase 使用 `--rerun-incomplete` 并强制重跑受控 rules。已发布 preliminary report 不改写；未发布初筛只允许在原 run 内重建。本轮只有 diagnostic 与 Workflow 1 `read_qc` 能形成完整依赖身份，其他真实 workflow 明确不可恢复。
- 已完成：Backend 新增 plan revision resume 入口，重验 owner、当前项目分析权、chat／dataset／project、最新 revision 和待处理 proposal，复用原 execution row 并追加 requested／accepted／rejected 事件。status 只公开精简 recovery 字段；运行审计报告列出 attempt 历史，不公开 PID 或实体依赖路径。
- 已完成：`/analysis` 仅向可写成员的合格 `interrupted` 任务显示“检查并恢复”，复用确认组件，显示次数、处理中状态和简体中文阻挡原因；成功后立即刷新排队状态。唯读、旧 state 或依赖不合格时没有可操作入口。
- 验证边界：Agent 195 passed、2 skipped；Backend 171 项、Vitest 45 项、Cypress 5 项通过。Cyclone 补跑 32 KiB diagnostic-only run：精确终止专用 runner／scheduler 后由 reconciliation 标记 `interrupted`，人工恢复为 attempt 2 并完成，attempt 1 保留。首次连接超时发生在建 run 前，也已如实记录；diagnostic 成功不视为真实 workflow 恢复验收。命令与状态见[第十二轮复现记录](m1-12-interrupted-run-recovery-reproduction.md)。

**受控恢复切片已完成；A3／M1 仍未完成。** 尚缺 Workflow 2–6 及 Workflow 1 非 `read_qc` 阶段的完整工具／参考库身份、auto 初筛两种发布边界与真实多样本恢复、主机重启实演和真实 workflow 验收。B1、B2、C1 及 M0 的既有缺口不变。

## 第 13 轮：Workflow 1 依赖身份与 B3 契约基础（2026-09-26，用户确认）

本轮不做数据上传，先完成 Workflow 1 的能力与依赖身份切片；本机测试、六文件索引哈希和 Cyclone 全阶段 DAG dry-run 通过后，才开始 M2/B3 的纯内部契约基础。没有新增数据库表、migration、向量库、环境变量、后端 API、审核页面或模型调用，也没有复制 FASTQ、参考库或大型结果。

- **程序存在：**Workflow 1 五个阶段进入同一 capability catalog，manifest 登记软件、参考资产、parser、资源和实际验证状态；execution spec／planner 升至 v4 并冻结全部所选阶段 manifest。旧 v3 方案仍可读取，但启动必须重新编译。
- **受控恢复：**新 Workflow 1 run 使用 recovery contract v2，按所选阶段最小化冻结 Snakemake、fastp、Bowtie2 wrapper 与两个 align binary、samtools、SeqKit、MEGAHIT 入口与现有 core binary、六个 rRNA Bowtie2 索引及排除结果／cache 后的 workflow 源码闭包。缺失依赖拒绝建立可恢复契约，暂时不可读返回 retryable unavailable；resume 时内容变化返回 dependency changed 并保持 `interrupted`。旧 contract 不补写，Workflow 2–6 仍拒绝恢复。
- **dry-run 通过：**当前 worker 部署后，`contig_filter` 目标展开五阶段并在 Cyclone 返回 0；依赖身份完整，六个索引逐文件 SHA-256 与聚合 SHA-256 均已记录。只产生 268 KiB 新 dry-run 目录，没有执行 FASTQ shell command，输入 stat 未变。
- **真实恢复未验证：**没有制造真实 Workflow 1 中断，也没有运行完整 FASTQ 计算；因此只证明程序、自动测试、身份计算和 DAG dry-run，不宣称 A3／B1 或 M1 完成。
- **B3 契约基础：**保留 CandidateEvidence v1 读取，新增内部 CandidateEvidence v2，表达 run／attempt、初筛或全量范围、候选类型、单位／population、缺失与零值、artifact 定位与 SHA-256、工具／参考身份、受限派生操作、输入 evidence IDs、来源分组及冲突／缺失／限制。使用 M0 冻结初筛数值新增不足 5 KiB 的小型 fixture 与负向案例；不生成 Assessment，不接报告、UI、持久化或领域结论。
- **验证：**Agent 210 passed、2 skipped（另有 90 subtests）；相关 Backend 69 项与 Vitest 50 项通过。Ruff、Prettier 与一次 8 GiB 前端 build 结果见[第十三轮复现记录](m1-13-workflow1-identity-b3-contract-reproduction.md)。

**M1/M2 均不勾选完整验收。** B1 仍缺 Workflow 3–6 manifest、Workflow 2 不可变参考 release、许可和正式兼容组合；A3 仍缺真实 Workflow 1 中断恢复、auto 发布边界与主机重启实演；B3 仍缺 Workflow 2 原始多表 provenance、规则、知识、Assessment、专家冻结集及业务接入。

## 第 14 轮：Workflow 2 能力契约与候选解析（2026-09-26，用户确认）

本轮不做数据上传、FASTQ 重算、模型调用、专家审核、UI、后端 API 或数据库变更。先把 Workflow 2 五阶段登记为正式 capability contract，再以既有完成 run 对内部 CandidateEvidence v2 parser 做唯读聚合验证；候选列没有传回本机或写入新文件。

- **M1/B1：**Workflow 2 的序列准备、HMM 候选搜索、候选提取、证据工具链和结果汇总均登记 manifest v1，包含软件、参考资产、资源、parser 和验证状态。execution spec／planner 升至 v5，新方案冻结所选 W1／W2 manifests；v4 方案保留读取但启动前必须重新编译。
- **DAG dry-run：**首次 dry-run 发现 adapter 把 source workflow 不产生的 `taxonomy.tsv` 列为 target，Snakemake 以 `MissingRuleException` 返回 1；修正完成边界后在新目录展开 21 个 jobs 并返回 0，没有执行显示的 shell command。五个 W2 manifest 因此标记 `dry_run_validated`，不是实际运行或参考库发布验证。
- **工程知识：**保留不可变 `engineering-knowledge-v1`，新增并启用 v2；只说明 W2 工程能力、依赖和验证边界，不把 NT、NR、CheckV、病毒宿主库或 HMM 视为已核准领域资产。
- **M2/B3：**新增只读 W2 候选解析器，从完成 phase 定位 `virus_candidates.csv`，支持现行与历史样本结构；输出 `virus_contig` CandidateEvidence v2 的长度、HMM coverage、CheckV、NR 和基因计数等观测，并保存相对路径、行列、SHA-256、来源分组、分母和未知身份限制。缺值不当作 0；重复候选、样本无法对应、schema／数值／路径／读取变化均 fail closed。
- **真实聚合验证：**既有 W1＋W2 run 的 8 行候选全部解析为 8 个候选、72 项 observation；登记 8 个缺值 issue 和 8 个历史依赖身份 limitation。来源表为 3,269 bytes，SHA-256 `43b4c12f36838261c896ce481d8166314dcfa495a93faad7d1029f9e508e8551`。CLI 只提供 aggregate summary，不输出候选内容。
- **自动验证：**Agent 226 passed、2 skipped（另有 90 subtests）；根目录 4 项、Backend 69 项及 Vitest 52 项通过，Ruff 通过。Prettier 与最终 build 见[第十四轮复现记录](m1-14-workflow2-manifest-b3-parser-reproduction.md)。

**M1/M2 仍未完成。** B1 尚缺 Workflow 3–6 manifests、Workflow 2 不可变参考 release／许可／完整哈希和正式兼容组合；A3 尚缺真实 Workflow 1 中断恢复与主机重启实演；B3 尚缺原始 W2 多表 provenance 链、领域规则、知识引用、Assessment、专家冻结集、持久化及业务接入。Workflow 2 仍不可受控恢复。

## 第 15 轮：Workflow 3 能力契约（2026-09-26，用户确认）

本轮只推进 **M1/B1 的 Workflow 3 宿主识别能力契约**，不做数据上传、真实 workflow 计算、M2、模型调用、数据库变更或大型参考库扫描。没有新增环境变量、后端 API、UI 或 migration。

- **M1/B1：**Workflow 3 的宿主标记比对、覆盖度、BLAST、证据整合和结果汇总均登记 manifest v1，包含输入／输出 artifact、Bowtie2／Samtools／BLASTn／Python 与固定文本工具、EukaMarker 索引／taxonomy、parser、资源和限制。execution spec／planner 升至 v6；v5 方案保留读取，但启动前必须重新编译。
- **工程知识：**保留可校验的 v1／v2 文件，新增并启用 4,518 bytes 的 `engineering-knowledge-v3`；只发布 W3 工程契约和验证边界，不把 EukaMarker 索引、taxonomy 或汇总脚本视为具备许可及完整哈希的正式 release。
- **DAG dry-run：**复用既有 run 的 `v120` clean reads 与 contig，只在新隔离目录展开 `host_mapping → host_coverage → host_blast → host_integrate → host_summary` 共 5 个 jobs。Snakemake 返回 0 并明确为 dry-run，没有生成结果文件；目录为 300 KiB，输入 stat 未变。
- **恢复边界：**W3 dependency identity 未扩充，dry-run 明确返回 `RECOVERY_DEPENDENCY_IDENTITY_INCOMPLETE`；因此 W3 不可受控恢复，也未完成真实运行或正式 ReleaseSet 验收。
- **自动验证：**Agent 229 passed、2 skipped（另有 93 subtests）；根目录 4 项、Backend 69 项及 Vitest 50 项通过。Ruff、Prettier 与唯一一次 8 GiB 前端 build 结果见[第十五轮复现记录](m1-15-workflow3-manifest-reproduction.md)。

**M1/M2 仍未完成。** B1 尚缺 Workflow 4–6 manifests、W1–W3 正式参考 release／许可／完整哈希、兼容组合及真实运行验收；A3 仍缺真实 Workflow 1 中断恢复、W2–W6 恢复身份与主机重启实演。B2／C1、M0 及既有 M2/B3 缺口不变，本轮没有继续推进 M2。

## 第 16 轮：Workflow 4–6 能力契约与 W2 多表追溯（2026-09-27，用户确认）

本轮不做数据上传、数据库迁移、UI、模型调用、真实生信计算或大型参考库扫描；不复制 FASTQ、workflow 或参考库到本机。先收尾 W4–W6 的 M1 capability contract，再把 W2 候选证据由最终汇总表扩展为四个小型来源的只读追溯。

- **M1/B1：**W4 的 Kraken2、Bracken 与汇总，W5 的 Bowtie2／Samtools 比对、coverage 筛选与 RPM 汇总，以及 W6 的 CheckV、策略分流、结构注释、DRAM-v 功能注释与交付汇总共新增 11 个 manifest。W5 病毒 reference 保持为执行输入，不伪装成发布资产；W6 的工具与数据库身份仍如实保留未完成状态。每个 W1–W6 公开 stage 现在恰有一个 manifest，并有完整性测试约束。
- **版本与工程知识：**execution spec／planner 升至 v7；v6 方案仍可查看但启动前必须重新编译。保留可校验的工程知识 v1–v3，新增并启用 `engineering-knowledge-v4`，只描述 W1–W6 工程契约与验证限制，不作为领域资料或正式参考 release。
- **Cyclone dry-run：**最终内容定址 worker `93e033860220e860d39dd5840febe8fb32263aad9d71af1f2cd778d2060ab510` 在三个新 run 目录分别展开 W4 7、W5 7、W6 12 个 jobs，均返回 0 并明确为 `-n` dry-run。三个目录为 240／212／668 KiB，输入大小保持 1,717,631,486、1,808,575,242、79,823、848 与 94 bytes，`/data` 尚余 365 GiB。三者 recovery identity 都仍为 `RECOVERY_DEPENDENCY_IDENTITY_INCOMPLETE`；W6 `strict_tools=false` 及 dry-run 不代表 CheckV／VIGOR／DRAM-v 真实验收。
- **M2/B3：**最终 `virus_candidates.csv` 只决定候选集合；`Profile_cov`、五项 CheckV 指标与 `qlen`／`nr_pident`／`approval_rate` 分别回溯 coverage、CheckV 和 NR 来源。每项 observation 使用对应来源的 run-relative path、行列、SHA-256、工具和 unknown reference identity。候选缺列、重复 ID、schema／数值错误、路径越界、symlink、实质数值不一致与读取中变化均 fail closed；只对 `Profile_cov` 允许 `1e-15` 的浮点序列化绝对误差，缺值仍保持缺值。
- **真实只读聚合：**既有完成 run 仍得到 8 个候选、72 项 observation、8 个 missing 与 8 个 dependency limitation；四个来源合计 8,725 bytes，CLI summary schema v2 仅输出 `sources[]` 与聚合计数，不输出候选 ID 或内容，也不写回原 run。
- **验证：**Agent 全量 240 passed、2 skipped；变更檔 Ruff 通过。全 repo Ruff 仍有 8 个既有、与本轮无关的问题。根 CLI、Backend、Vitest、Prettier 与唯一一次 8 GiB 前端 build 的实际结果见[第十六轮复现记录](m1-16-workflow4-6-manifests-b3-provenance-reproduction.md)。

**M1/M2 仍未完成。** W1–W6 正式参考 release、许可、完整哈希、ReleaseSet、真实运行与 W2–W6 受控恢复仍缺；B3 尚未接 Assessment、领域规则、正式知识引用、报告、持久化、API、UI 或专家冻结集。M0、B2、C1 及既有 A 轨缺口不变。

## 第 17 轮：依赖契约与确定性工程研判（2026-09-27，用户确认）

本轮不做数据上传、数据库迁移、UI、模型调用、新 workflow 计算或大型参考库扫描。增加小型可校验 ReleaseSet／依赖身份解析，并将既有 Workflow 2 CandidateEvidence v2 映射为不含正向生物结论的确定性工程 findings。

- **M1 契约切片：**发布 `candidate-evidence-v2` capability 与 `b3-engineering-integrity-rules-v1`，逐档校验 release 及实现 SHA-256。resolution 从 execution spec、capability contract 与 recovery contract 区分 complete／incomplete／unavailable；旧 state、版本不符、缺依赖与暂时不可读均 fail closed。W2 的 NR／NT 来源 checksum 可登记为 observation，但不证明已安装数据库内容完整，不提升 reference release 或恢复资格；execution spec 仍为 v7。
- **M2/B3 工程 findings：**固定检查缺失、冲突、依赖身份、同来源相关性和领域资产缺口。finding 只能引用已有 evidence ID，缺值不按零处理、冲突不删除、同 source group 不重复计票。没有核准领域规则与知识时，所有候选均保持 `Assessment(status=not_generated, review_status=pending)`，provider／model 为 `none`，没有 draft、claim、分类或支持程度。
- **唯读入口：**`candidate_assessment.py --state <run>/.bioagent/state.json --summary` 只输出来源哈希和候选／观测／finding／assessment 聚合计数；不接受输出路径、不写回 run、不输出候选 ID 或序列。本轮未接报告、API、UI 或业务持久化。
- **Cyclone 实证：**既有 run `analysis-20260813-160906-0f9eda85` 保持 8 candidates、72 observations、8 missing 与 8 dependency limitations；新增映射得到 8 个 not-generated Assessment、0 个 draft。四来源 size／mtime 未变且 SHA-256 重核通过，远端写入为 0。NR／NT 分别只读取 164／92 个小型 `.md5` 来源清单，不递归读取已安装数据库。
- **验证与容量：**Agent 248 passed、2 skipped，新增与 W2 parser 定向测试 27 passed；根 CLI 4 passed、Backend 96 tests、Vitest 50 passed。新增 assets 为 3,118 bytes，全部 Agent 新程式、资产与测试约 32 KiB；没有扩充 SQLite。Ruff、Prettier 与唯一一次前端 build 详见[第十七轮复现记录](m1-17-release-contract-m2-assessment-reproduction.md)。

**M1/M2 仍未完成。** 本轮工程 release 不是正式领域或 reference ReleaseSet。W1–W6 正式 reference release／许可／完整内容哈希、真实运行与 W2–W6 受控恢复仍缺；B3 仍缺核准领域规则与知识、可审核正向 Assessment、报告／API／UI／持久化及专家冻结集。M0、B2、C1 及既有 A 轨缺口不变。

## 第 18 轮：优先三项 Demo（2026-09-30，用户确认）

本轮优先级调整为三个可运行 Demo：端到端科学报告、`fastp@1.3.2` 本地工具条目，以及 `bioagent-w1-read-qc@1.0.0` 原样／受控修改。只使用 `BJ-2024-615` 成对 FASTQ；不新增第二个工具、通用市场、多样本推论、本地模型、正式专家审核或 W3–W6 重算，也没有数据库 migration。

- **程序已完成：**capabilities／execution spec 升至 v2／v8，冻结工具契约与 skill invocation；未知工具、版本不符、未登记 skill、原始 CLI 和非白名单参数均 fail closed。worker 建立远端 state 前实测 fastp 版本，终态保存输入／输出哈希、参数、指标与错误码。
- **报告已完成：**新增九笔方法／类群／阈值本地文献 release；MiniMax-M3 只接收匿名 ID 并只能排列既定 claim，确定性 renderer 插入事实与 locator。未知 ID、越界字段、缺文献、路径越界及结果不匹配均拒绝或降级；单样本报告不做群组推论，H/N 最佳命中不写成已确认亚型。
- **业务入口已完成：**Agent／Backend 提供受控报告生成和 SHA-256 校验下载，snapshot 回传工具与 artifact report；`/analysis` 只新增一个极简“优先 Demo”区块。没有通用管理后台，技能修改继续走既有“更改需求”。
- **真实运行：**首次完整 run 的 W1 成功，但暴露 W2 helper 无法从 PATH 找到 config 中 `hmmsearch` 的问题；未把该失败当作验收。修正只作用于 runner 的 phase PATH，不修改 Workflow 源码。`analysis-m118-priority-full-r2-20260930` 随后以 2:38:54 完成 W1→W2；同一持久 scheduler 再以 40 秒完成 `analysis-m118-priority-qc80-20260930`。两者 fastp 输出 artifact digest 不同，compiled spec 除 `length_required`、override 与派生 digest 外一致。
- **报告实证：**完整 run 的 93 个 facts、九笔文献、MiniMax-M3 受限 reasoning plan、HTML／PDF 与工具报告均完成；修改版技能报告完成。相同 frozen 结果第二次生成命中 cache，facts JSON 与 HTML 逐字节一致。最终 artifact digest、引用与数值见复现记录。
- **验证：**Agent 264 passed、2 skipped，Backend 80 passed，Vitest 65 passed；变更文件 Ruff、Prettier、skill quick validation 与 diff whitespace 均通过。沙箱内 build 在编译前的 Pyodide 下载阶段被本机代理权限阻断；沙箱外的一次完整 8 GiB 前端 build 通过。真实工具版本、未知／错版拒绝、受控 skill 修改、报告越界防护、缺文献降级与路径限制均有自动测试覆盖。

实际 run、digest、容量与复现命令见[第十八轮复现记录](m1-18-priority-demos-reproduction.md)。三项完成只代表本轮指定 Demo；不提升 M1／M2／M3 共同里程碑，也不补齐正式 reference release、许可、专家审核、本地模型或 W2–W6 受控恢复。

## 第 19 轮：标准交付报告版型与完整分析对齐（2026-10-02，用户确认）

本轮诊断确认第十八轮两个标准交付报告尚未完整满足参考版型：旧版缺少完整导航、五类状态标签、数据驱动叙述、专用图表与科研限制页尾，PDF 表格还存在逐字直排；完整 run 另因空值被字符串化而误收 `sample_id=nan`。本轮只重建报告，不重跑 FASTQ、W1 或 W2，不修改数据库、Backend、UI、README、`AGENTS.md` 或 `.gitignore`。

- **模板与资料契约：**标准模板升级为 `bioagent-standard-delivery-v2`，保留 `standard_delivery` schema v1 与既有下载 API。sample ID 先正则化并拒绝空值、非有限数及 `NaN` 类文本；W1–W6 以具名指标组装 sample-level master table，不再无差别摊平数值。完整 run 因而恢复为唯一的 `BJ-2024-615`。
- **统计与叙述：**描述统计统一输出 n、missing、mean、SD、median、Q25、Q75、min、max；只有至少两个水平且至少两组 `n≥2` 才生成 Kruskal–Wallis、Mann–Whitney、BH 与效应量。单样本只作描述性解读，缺失流程明确跳过，不虚构分组推论或组装结果。
- **版型与图表：**实现 kicker、五个状态标签、锚点目录、警示区、编号 W1–W6 章节、结构化表、方法摘要、受限 R 附录与科研限制页尾；随 worker 部署确定性 R 主题和 W1–W6 专用图。单样本降级为点图／柱图；表格采用横向布局，避免逐字直排。
- **安全发布：**report-only 先在 `reports/standard/` 内暂存，成功后只替换报告拥有的目录与文件，保留 `scientific/`、`tool-demo/`、`skill-demo/`。manifest 登记 `template_version`，不收录自身或优先 Demo 目录；正式运行不依赖 XvirMind／XvirBench。
- **真实重建：**content-addressed worker `182a5ad8b43d68d3976084daac4664c1e127b8e07189de7ca02c39238287e6a4` 对 `analysis-m118-priority-full-r2-20260930` 与 `analysis-m118-priority-qc80-20260930` 各执行一次最终 report-only。前者为一个样本、W1/W2 extracted、W3–W6 skipped；后者为一个样本且只有实际可用的 W1 read-QC。两份 PDF 均由 WeasyPrint 69.0 产生，为 12／8 页 A4 landscape。
- **不变性与验证：**两个 run 的 Workflow 目录指纹、原始 FASTQ stat 和三类优先 Demo artifact SHA-256 均与重建前一致。20 个 PDF 页面全部转 PNG 检查，无逐字直排、裁切、重叠、黑块或不可读表格。Agent 230 passed、2 skipped，Backend 51 passed，Vitest 65 passed；变更文件 Ruff 通过，Agent 全目录 Ruff 仍只有 8 个与本轮无关的既有诊断。

新版完整产物、SHA-256、容量、复现命令和验证边界见[第十九轮复现记录](m1-19-standard-delivery-layout-alignment-reproduction.md)。本轮完成标准交付报告版型与已有 W1–W6 提取能力的对齐；没有新增 W7，也不把缺失 workflow、单样本资料或未核准领域资产解释成已完成的生物学验收。

## 第 20 轮：不可变研判版本与追加式审核事件（2026-10-04）

本轮先实现不依赖领域专家、模型训练或远端重算的 M2/A4 审核基础；不做资料上传、条件接入、正向生物学研判、报告正文入库、补算提议或训练。本轮新增数据库 migration，因此将容量上限与不可变语义放在 API 边界，而不是保存大型报告或证据文件。

- **不可变研判版本：**新增 `AnalysisAssessmentRevision`，绑定项目、分析、已登记 run、报告类型／版本／SHA-256、短摘要与不超过 64 KiB 的结构化内容；使用 `base_revision` 乐观并发控制，新版本显式记录 `supersedes_id`，旧版本不覆盖。
- **追加式审核事件：**新增 `AnalysisReviewEvent`，保存审核人、认可／需补证／需修订、理由、证据定位和时间。事件只追加；同一版本可保留多个意见，新研判版本不会删除旧事件。
- **权限和来源边界：**只有 `can_review` 成员可建立研判版本或提交审核；普通项目成员只读，管理员身份本身不获得内容权限。研判只能绑定同一分析已登记的 run，跨项目、跨分析与未知 run 均拒绝。
- **三状态分离：**项目列表分别显示计算、研判与审核状态；计算完成不再暗示研判或审核完成。最新研判版本没有审核事件时显示待审核，旧版本的意见仍可从历史 API 读取。
- **数据库体积：**不保存 HTML、PDF、FASTQ、完整日志或大型 evidence blob；报告继续留在 run root，仅保存身份和小型结构化修订。单一研判内容硬限制 64 KiB、证据定位最多 50 项。
- **验证：**Backend 相关测试按文件隔离运行共 180 passed（其中本轮定向 14 passed）；Vitest 全量 66 passed；变更 Python Ruff、前端／文档 Prettier 及唯一一次完整前端 build（1 分 9 秒）通过。容量与复现命令见[第二十轮复现记录](m2-20-assessment-review-foundation-reproduction.md)。

**A4 尚未完成。** 前两项任务已完整实现并在 roadmap 勾选；仍缺纯解释修订后的报告发布、关联候选的补算提议及显式确认、审核训练资料导出。B3 仍只有确定性工程 findings 和 `not_generated` Assessment，本轮没有把审核基础误记为正向领域研判。

## 第 21 轮：解释修订、补算确认与待审核训练导出（2026-10-04）

本轮完成 M2/A4 剩余任务，不扩展到 B3 正向生物学研判或 C2 训练。继续不做资料上传与条件接入；没有访问 Cyclone、调用 MiniMax-M3、运行 Workflow 或启动任何训练。

- **指定版本报告：**每个研判 revision 可单独下载确定性、自包含 HTML，显示固定 report identity、结构化内容、审核事件和补算提议；所有内容经过 HTML 转义，旧 revision 可独立回看。
- **纯解释修订：**新增 `revision_kind=explanation`，必须基于已有研判版本。建立解释 revision 只追加小型业务记录和新报告视图，不创建 plan revision、execution 或远端任务；原报告身份与旧研判保持不变。
- **候选补算提议：**审核人可针对既有 assessment revision 与 candidate 建立白名单 plan patch；服务端用确定性编译器生成并冻结 impact preview。相同 proposal ID 与相同内容幂等返回，内容冲突拒绝。只有具分析权限的原 chat 拥有者可显式确认，确认只建立新 plan revision，不自动执行；过期 plan revision 与重复确认均拒绝。
- **待审核训练导出：**项目审核人可导出带稳定 record SHA-256 的候选 JSON；只包含小型输入快照、输出修订、审核事件和来源 identity，固定 `training_eligible=false`、`triggers_training=false`，并列出许可、冲突、数据划分和训练目标批准四项后续门槛。
- **数据库与迁移：**Alembic `b3c4d5e6f7a8` 为研判版本增加类型字段，并新增小型补算提议表；patch 与 impact 合计硬限制 64 KiB，不保存 HTML、PDF、FASTQ、日志或模型数据。既有 revision 升级为 `generated`，downgrade 验证可回退。
- **验证：**Backend 相关测试以隔离进程运行共 185 passed，其中项目／审核定向 16 passed；Ruff、Prettier、Alembic 单一 head、迁移升级／回退和 diff whitespace 均通过。本轮未修改前端，不重复执行 build。命令、容量和限制见[第二十一轮复现记录](m2-21-review-actions-reproduction.md)。

**A4 三项任务已完成。** M2 仍未完成，因为 B3 缺核准领域规则、正式知识、正向 Assessment 与回归集，C2 也因无本地模型、无审核训练集和不在本机训练而保持未开始；待审核导出不等于可训练数据或训练批准。

## 第 22 轮：Workflow 2 工程研判业务接入（2026-10-04）

本轮推进 M2/B3 在“无核准领域资产”条件下可独立完成的业务切片，不做资料上传、条件接入、正向生物学分类、知识引用、模型调用、训练或新 workflow 计算。A4 既有 revision、审核和 HTML 报告保持为唯一业务持久化机制，没有新增数据库表或 migration。

- **有限候选包：**Agent 新增每次 1–5 个候选的确定性包，完整保留 CandidateEvidence v2、`not_generated` Assessment、冲突／缺失／相关证据 findings、四来源 identity 与 release resolution。候选按 ID 排序，包体生成 SHA-256；正文超过 60 KiB 拒绝。五个合成候选的实际序列化结果为 47,089 bytes。
- **远端只读边界：**run 目录须同时通过 lexical 与 canonical run-root 检查，state、四个来源与 release 实现继续逐档校验。Cyclone control worker 的 `python -S` 不加载 Pydantic；本轮使用既有 runner Python 的 60 秒隔离子进程解析，未迁移环境或恢复旧 `/data` 环境。控制进程只接收有界 JSON，不写 run。
- **授权业务入口：**`can_review` 成员可对同一项目／chat 已登记 run 调用 candidate-assessments import。Backend 独立重验包体 SHA-256、run/candidate identity、观测唯一性、finding evidence 引用以及固定 `not_generated/pending/provider=none/model=none`，再追加不可变 revision；普通成员和仅分析成员均拒绝。
- **报告与状态：**导入 revision 使用 `workflow2_candidate_assessment` / `candidate-assessment-packet-v1` 身份，可从既有指定 revision 报告下载；项目列表显示 `assessment_status=not_generated`，不再把工程不足状态显示为 draft。报告只呈现转义后的受控 JSON，不生成生物学结论。
- **Cyclone 实证：**只读 SSH 检查通过，content-addressed worker `a45fe40ea991e89198fa0021ebd0e050cd1abd409bd1e2b000c35acb8086ca89` 在既有完成 run 上返回 `snapshot=found`，并对故意不存在的候选精确 fail closed 为 `ASSESSMENT_CANDIDATE_UNKNOWN`。安全审核未允许导出整列候选 ID，因此没有把该检查扩展成远端正向包体读取；本机真实契约测试覆盖正向包体、持久化、权限和报告。
- **验证与容量：**Agent 合计 276 passed、2 skipped（另有 100 subtests），Backend 相关 26 passed；Ruff、Prettier 与 diff whitespace 通过。本机仍约 184 GiB 可用、仓库约 2.4 GiB；不保存 FASTQ、来源表、HTML 或模型内容副本。数据库每条 revision 仍限制 64 KiB，Agent 额外预留约 4 KiB 信封空间。

自动测试、静态检查、复现命令与回退边界见[第二十二轮复现记录](m2-22-candidate-assessment-business-integration-reproduction.md)。本轮完成路线图 1.7 的三个工程切片；B3 七项整项仍不勾选，因为核准领域规则／知识、正向 Assessment、领域引用与专家冻结回归集仍缺。M2、M3 不提升。

## 第 23 轮：DeploymentProfile 配置边界（2026-10-04）

本轮先完成不依赖离线介质、独立目标机器或本地模型的 M3/A5 配置任务；不做资料上传、条件接入、服务启动、数据库迁移、远端计算、模型调用、依赖安装或备份恢复。默认 `.env` 工作流保持不变，只有显式指定 profile 才覆盖受治理的部署字段。

- **严格无密钥契约：**新增 DeploymentProfile schema v1，精确限制顶层和嵌套字段、绝对路径、唯一服务端口、模型 HTTPS `/anthropic` 端点、Workflow 1–6 集合和正数资源额度。profile 只允许登记 `MINIMAX_API_KEY` 变量名，不能保存密钥值；shell loader 逐行校验变量名并使用 `printf -v`，不执行 profile 内容。
- **开发与目标配置：**Cyclone profile 固化现有三项本机服务、远端数据／run／worker、Home Pixi 工具、Workflow 1–6 和 MiniMax-M3。独立目标 profile 改用 `bioagent-compute`、15173／18080／18001 及 `/opt`／`/srv` 路径，仍遵守用户确认的 MiniMax-M3 替代策略；它只是一份待部署模板，不声称目标路径已存在。
- **实际启动接线：**`dev-services.sh` 读取服务地址、端口、SSH 主机和日志阈值；Agent／Backend 在各自 `.env` 之后重新加载组件 profile，确保集中值优先。Agent 的对外模型 ID、provider 模型和端点由环境配置；未设置 `BIOAGENT_DEPLOYMENT_PROFILE` 时所有既有默认值不变。
- **验证与容量：**两份 profile 均通过 CLI 校验和安全导出；根测试 9 passed，Agent 配置／provider／adapter 定向 37 passed（另 7 subtests），四个 shell 入口通过 `bash -n`，Ruff、Prettier 与 diff whitespace 通过。本轮无前端源码变更，不重复 build。本机仍约 184 GiB 可用、仓库约 2.4 GiB，没有新增数据库或大型文件。

本轮只勾选 A5 第一项。离线安装包、完整依赖锁定、独立环境鉴权／任务运行、断网验证、备份恢复、在途更新和 B4／C3 联合回滚仍缺，因此 A5 与 M3 不提升。命令、字段映射和回退方式见[第二十三轮复现记录](m3-23-deployment-profile-reproduction.md)。

## 第 24 轮：内容校验恢复快照（2026-10-04）

本轮实现 A5 备份／恢复中可在现有开发实例安全验证的基础，不做资料上传、条件接入、服务停止、数据库迁移、模型调用、workflow 计算或正式路径覆盖。来源侧只读；恢复始终进入新 staging 目录，不能由工具直接替换业务库、Agent assets 或 Cyclone run。

- **Profile v2：**新增业务 SQLite 路径、备份根、保留数量与备份容量上限；Backend 显式启用 profile 时也由它取得 `DATABASE_URL`。两套 profile 的默认上限均为 20 GiB、保留数量为 7，但工具刻意不自动删除旧快照。
- **原子快照：**SQLite 使用 online backup 得到单文件一致性副本；Agent 小型版本化 assets 拒绝 symlink 后复制；从业务库冻结的注册 run 集合经固定 `ClearAllForwardings=yes` rsync 只读取 `.bioagent/state.json` 与 `reports/`。目标先写同根 `.partial-*`，完整验证成功才改名。
- **完整性与关系：**manifest 精确列出每个普通文件的 size／SHA-256，并以 sidecar 保护 manifest。校验覆盖 SQLite quick check、核心表、十类孤儿关系、持久化工程引用结构、注册 run state JSON、意外文件和总额度；stage restore 只接受不存在的目标并再次执行相同校验。
- **真实只读演练：**按规定先做 Cyclone SSH 连通检查。当前开发库、92 KiB Agent assets 及一个已登记 run 的状态／报告形成 16 files、1,228,177 bytes 的快照；恢复到另一 `/tmp` staging 后摘要、2 projects、2 members、1 run 和 10 项关系检查完全一致。当前库的 assessment／citation 计数为 0，不伪造正向数据。
- **自动验证与容量：**根 Profile／backup 测试共 13 passed；fixture 另覆盖一个合法工程引用、内容篡改、孤儿成员、无效引用、已存在恢复目录及安全 rsync 参数。Ruff、Prettier、shell 语法与 diff whitespace 通过。本机仍约 185 GiB 可用，仓库约 2.4 GiB；演练快照和恢复目录各约 1.2 MiB，未写入仓库或远端。

A5 第三项仍未完整完成：尚无按项目保留策略的自动／定期执行，也没有在独立恢复机器重建服务、核对登录鉴权与浏览器查询历史报告。第一项保持完成；第二、第四项及 B4／C3 不提升。命令、失败边界与 staging 清单见[第二十四轮复现记录](m3-24-recovery-snapshot-reproduction.md)。
