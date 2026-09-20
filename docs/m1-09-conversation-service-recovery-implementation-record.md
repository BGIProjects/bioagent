# M1 第九轮：对话服务恢复实施记录

日期：2026-09-21。接续[第八轮受控需求修改](m1-08-controlled-requirements-implementation-record.md)。本轮只恢复 Dashboard／Analysis 对话可用性与公开能力目录读取，不扩展知识库、TaxonAgent、专家语义验收或完整 M1 范围。

## 根因与范围

- Agent 将所有 `X-OpenWebUI-Chat-Id` 都当作持久 UUID；首次或兼容入口缺失该 header、使用 `local:` ID 或传入其他非 UUID 时，在调用模型前返回 `A valid Open WebUI chat ID is required`。
- analysis router 的 project guard 没有豁免已鉴权的只读 `/api/v1/analysis/capabilities`，因此无 project context 的页面初始化被误判为 404；health 和确定性 planner 本身没有失效。
- 运行环境曾安装 `claude-agent-sdk 0.2.152`，并把对外名称 `MiniMax-M3` 直接传给 Claude CLI；第八轮因此出现 `claude-code:unrecognized_model`、两例 unavailable 和一例 timeout。
- tmux 与三个本机服务本身无故障。Codex 沙箱不能可靠访问宿主 tmux socket 与 loopback，沙箱内的 stopped／unreachable 是假阴性；宿主环境复核为准。

本轮没有数据库迁移、前端视觉修改或兼容层，也不修改第八轮失败记录。

## 实作

### Agent

- 新增 `requirements.txt`，固定 `claude-agent-sdk==0.2.103`；实际安装身份为 SDK 0.2.103、Claude Code 2.1.179。health 公开已安装与要求的非敏感 SDK 版本字段，版本不符时 conversation model 明确 unavailable。
- MiniMax 改用中国大陆 `https://api.minimax.cn/anthropic` 端点。SDK 子进程只接收 `ANTHROPIC_AUTH_TOKEN`，并将 `ANTHROPIC_MODEL` 及 Sonnet／Opus／Haiku 默认映射设为 `MiniMax-M3[1m]`，auto compact window 设为 1,000,000；不再传 Claude CLI `--model MiniMax-M3`。公共 provider 身份仍是 `MiniMax-M3`。
- 有效 UUID 沿用既有 SDK session／resume 映射；缺失、`local:` 或其他非 UUID ID 改为依照宿主有限历史执行单次临时 SDK session，不保存 resume 映射。
- timeout、schema、输出上限、显式云端授权、错误码及动作校验契约保持不变。

### Open WebUI

- 已鉴权的只读 capabilities 路由不再要求 project context；登录要求仍由 router dependency 保留。
- 回归测试覆盖 Backend 为首次聊天生成 UUID，并把同一 ID 写入任务、metadata 与下游模型请求；Agent adapter 另覆盖无 ID 的单次回合。

### 文件与运维

- 根 README 只把 Agent 安装入口改为 requirements，并补充必要的 MiniMax 中国大陆端点／模型映射说明；Agent README 与架构文档记录 session 和可选 chat ID 契约。
- `AGENTS.md` 新增长期诊断约束：宿主 tmux／loopback 状态与 Codex 沙箱结果冲突时，必须在沙箱外重新执行服务状态检查后再判断。

## 自动验证

- Agent 全量 pytest：155 passed、2 skipped；相关 provider／runtime／adapter 用例覆盖固定 SDK 配置、UUID resume、无 ID／非 UUID 临时回合、timeout、schema、provider error 与 health 版本检查。
- Backend 相关 unittest：76 passed；覆盖 analysis guard、planner、OpenAI metadata 与首次聊天 ID 链路。
- Frontend 相关 Vitest：43 passed。Agent 与 Backend 相关 Ruff、Markdown Prettier 通过；最终一次 8 GiB heap production build 成功。

## 宿主服务与在线验证

- 固定依赖安装后重启 Agent、Backend、Frontend；宿主 `dev-services.sh status` 显示三个 tmux session、health 与 listener 均正常，Cyclone SSH 正常。
- Agent health 返回 deterministic `ready`、conversation model `ready`，SDK installed／required 均为 0.2.103；Agent capabilities 返回 200。
- 使用短期本机登录 token 验证 Backend capabilities 在无 project context 时返回 200，schema v1、10 个 deliverable 与 1 个 capability；无 token 时返回 401，token 与 secret 未输出。
- 使用合成文本经 Backend OpenAI proxy 完成一次带 UUID 的非流式对话，返回 200、模型为 `BioAgent` 且有正文。首次聊天 UUID 的生成与转发由上述完整链路测试覆盖。

## MiniMax smoke

在显式授权下，以不含 FASTQ、样本内容、私有路径或密钥的冻结合成输入，各调用一次 `qc-only`、`fastp-length-50`、`vague-length`：

| case              | 结果                 | error                  |  latency |
| ----------------- | -------------------- | ---------------------- | -------: |
| `qc-only`         | 未通过 schema        | `MODEL_SCHEMA_INVALID` | 4,653 ms |
| `fastp-length-50` | 未通过 schema        | `MODEL_SCHEMA_INVALID` | 5,025 ms |
| `vague-length`    | 通过，返回 `clarify` | 无                     | 2,328 ms |

三例均完成 provider 往返，不再出现 `MODEL_UNAVAILABLE`、`MODEL_TIMEOUT` 或 `unrecognized_model`，说明本轮的 SDK／端点／模型身份故障已恢复。前两例模型候选未通过既有严格 schema，因此没有 proposal 被登记，也没有自动修复或补跑；这属于后续 C1 输出质量／专家语义评测，不放宽宿主 schema 来掩盖失败。

## Dashboard streaming 后续修复

同日浏览器复核发现 `/analysis` 正常，但 Dashboard streaming 仍返回 `MODEL_UNAVAILABLE`。对应 SDK transcript 显示 MiniMax 已生成自然语言正文，却没有只返回 `StructuredOutput`；Agent 当时让 Dashboard 与 Analysis 共用 `ConversationAction` schema，并把单轮只有文字的终态误分类为 provider unavailable。

- Dashboard 现在使用独立的 message-only 契约和精简 prompt，只产生文字回复，不生成 action trace 或 proposal；涉及数据集、方案、参数和执行变更时引导用户进入 `/analysis`。
- 只有 `chat_meta.source=analysis` 才启用原有严格 `ConversationAction`。MiniMax 的普通 `TextBlock` 可包装为 message 后继续接受调用方 schema 与输出预算校验；synthetic／API error 不会成为回复，Analysis 纯文字仍被 schema 拒绝。
- 没有新增模型调用、修复重试、HTTP 接口、数据库迁移或 Open WebUI 代码。Agent 全量 pytest 为 161 passed、2 skipped；Backend metadata／首次聊天 11 项及 Dashboard Vitest 4 项通过。
- 重启后三个本机服务与 Cyclone SSH 正常。使用合成文本经 authenticated Open WebUI proxy 执行一次 `local:dashboard:` streaming smoke，返回 200、有正文、正常结束且无错误事件；未发送 FASTQ、私有路径或密钥，也未重复 `/analysis` 云端 smoke。

## 未完成事项与回退

- `qc-only` 与 `fastp-length-50` 尚未形成合格结构化 proposal；完整 C1、专家语义审核、本地模型比较和上线门槛仍未完成。
- TaxonAgent、正式知识库及项目授权检索仍关闭；确定性表单、方案编译与执行边界不变。
- 如需回退，先停止本机服务，将 Agent requirements 与 provider 配置恢复到上一版本，再重启三个服务。无数据库状态需要回滚；SDK transcript 与第八／九轮结果保留作审计。

本次后续修复建议提交信息：Agent `fix: accept plain dashboard conversation replies`；根仓库 `docs: record dashboard chat recovery`。Open WebUI 没有代码变更，不需要提交。
