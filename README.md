# BioAgent 项目架构与改动记录

本文档描述 cyclone 上 `/data/bioagent` 项目的整体架构、目录组织、服务关系，以及当前版本已经完成的主要改动。

## 1. 项目整体架构

### 1.1 请求链路

```text
本机浏览器
  │  SSH 端口转发，访问 http://127.0.0.1:5173
  ▼
Open WebUI Frontend（SvelteKit/Vite，127.0.0.1:5173）
  ▼
Open WebUI Backend（FastAPI，127.0.0.1:8080）
  │  OpenAI-compatible HTTP + X-OpenWebUI-Chat-Id
  │  后台任务额外携带 X-OpenWebUI-Task
  ▼
BioAgent Adapter（FastAPI，127.0.0.1:8001）
  │  OpenAI 协议与 Claude Agent SDK 协议转换
  ▼
Claude Agent SDK Runtime
  │  项目级 Skills、Claude Code 内置工具、本地 session transcript
  ▼
MiniMax Anthropic-compatible API

固定工作流执行路径：Claude Agent SDK -> Bash -> Snakemake -> workflow1-workflow6
```

### 1.2 组件职责

#### Open WebUI Frontend

- 提供登录、Dashboard、聊天、历史会话和用户交互界面。
- 前端源码位于 `/data/bioagent/open-webui/src`。
- 使用 Vite 开发模式运行，修改源码后支持热更新。

#### Open WebUI Backend

- 负责用户、权限、聊天记录和 OpenAI-compatible 模型连接。
- 数据保存在 `/data/bioagent/data/open-webui`。
- 通过 `X-OpenWebUI-Chat-Id` 将当前 chat UUID 转发给 adapter。
- 标题、标签等后台任务同时通过 `X-OpenWebUI-Task` 标记，避免进入用户主会话。

#### BioAgent Adapter 与 Runtime

- 源码位于 `/data/bioagent/agent`。
- adapter 暴露 `/v1/models` 和 `/v1/chat/completions`，只负责协议转换。
- runtime 负责 Claude SDK 配置、session 创建与恢复、Skill 和工具加载。
- runtime 不访问 Open WebUI 数据库。
- runtime 在本地维护 `Open WebUI chat_id -> Claude session_id` 映射，并使用 Claude transcript 恢复多轮会话。

#### Snakemake Workflows

- 固定分析逻辑位于 `/data/user/guojindan/Projects/Workflows`。
- Agent 负责需求识别、workflow 推荐、两次确认、run 目录准备和结果解释。
- Snakemake 负责 DAG、规则调度和真实分析执行。
- 每次分析使用 `/data/runs/<run_id>` 独立运行目录，不修改源 workflow。

### 1.3 目录结构

```text
/data/bioagent/
├── agent/
│   ├── adapter.py
│   ├── runtime.py
│   ├── config.py
│   ├── tests/
│   └── .claude/
│       ├── skills/
│       └── sessions/
│           ├── bioagent/chat-map/
│           └── projects/
├── open-webui/
├── conda/
│   ├── envs/adapter/
│   ├── envs/open-webui/
│   └── pkgs/
├── env/open-webui.env
├── systemd-user/
├── cache/
└── data/open-webui/
```

### 1.4 服务与端口

| 服务 | systemd unit | 地址 | 工作目录 |
| --- | --- | --- | --- |
| BioAgent adapter | `bioagent-adapter.service` | `127.0.0.1:8001` | `/data/bioagent/agent` |
| Open WebUI backend | `open-webui-backend.service` | `127.0.0.1:8080` | `/data/bioagent/open-webui/backend` |
| Open WebUI frontend | `open-webui-frontend.service` | `127.0.0.1:5173` | `/data/bioagent/open-webui` |

```bash
systemctl --user status bioagent-adapter open-webui-backend open-webui-frontend
systemctl --user restart bioagent-adapter open-webui-backend open-webui-frontend

ssh -N \
  -L 5173:127.0.0.1:5173 \
  -L 8080:127.0.0.1:8080 \
  cyclone
```

## 2. 本次改动

### 2.1 Adapter 职责收敛

修改文件：`/data/bioagent/agent/adapter.py`

- 负责 FastAPI 路由、OpenAI-compatible 数据结构和 SSE 流式输出。
- 从请求头读取 `X-OpenWebUI-Chat-Id`，把消息和 chat ID 交给 `SessionManager`。
- 识别 `X-OpenWebUI-Task` 或 `metadata.task`，将 Open WebUI 后台任务交给临时 session。
- 同时支持流式与非流式 completion。
- 移除 Skill 文件读取、阶段切换、prompt 拼接和工具权限业务逻辑。

### 2.2 Runtime 与 SessionManager

新增文件：`/data/bioagent/agent/runtime.py`

- 新增 `SessionManager`，负责 SDK options、session 创建、恢复和结果校验。
- 为每个 Open WebUI 主对话维护一个长生命周期 `ClaudeSDKClient`，空闲超时后断开。
- 不访问 `webui.db`，使用本地 JSON 文件维护 Open WebUI chat ID 与 Claude session ID 的映射。
- 校验 chat ID 必须是规范 UUID。
- 校验 transcript 是合法 JSONL，损坏时明确拒绝恢复。
- 校验 SDK 返回 session ID 与映射中的 Claude session ID 一致。

删除文件：`/data/bioagent/agent/phases.py`

### 2.3 多轮对话与 Session 持久化

涉及文件：`runtime.py`、`.gitignore`

```text
Open WebUI chat_id
  │
  ├── chat-map 不存在
  │     └── 创建新 Claude session
  │         首次发送当前 Open WebUI 历史
  │         保存 ResultMessage.session_id
  │
  └── chat-map 已存在
        └── ClaudeAgentOptions(resume=claude_session_id)
            connect() 时加载 transcript
            后续只发送最新用户消息
```

映射与 transcript 位置：

```text
/data/bioagent/agent/.claude/sessions/bioagent/chat-map/<openwebui_chat_id>.json
/data/bioagent/agent/.claude/sessions/projects/-data-bioagent-agent/<claude_session_id>.jsonl
```

- `.claude/sessions/` 已加入 `.gitignore`。
- SDK 的 `query(..., session_id=...)` 只标识流式输入消息，不能恢复历史；恢复必须在 `connect()` 前配置 `ClaudeAgentOptions.resume`。
- 标题、标签等 Open WebUI 后台任务使用临时单次会话，不创建 chat-map。

### 2.4 集中配置

新增文件：`/data/bioagent/agent/config.py`

- 模型、API 地址、API 密钥、项目路径、额外目录和系统提示词集中定义于该文件。
- runtime 不从 shell 环境读取这些配置。
- `ClaudeAgentOptions.env` 只负责把 Python 常量传给 SDK subprocess。
- `bioagent-adapter.service` 已移除对 `/data/bioagent/env/adapter.env` 的依赖。

注意：`config.py` 当前包含密钥，不应在未清理密钥时公开源码或日志。

### 2.5 Skill 与工具权限

涉及文件：`runtime.py`、`.claude/skills/bioinformatics-workflow-gatekeeper/SKILL.md`

- 使用 `setting_sources=["project"]` 和 `skills="all"` 加载项目级 Skills。
- 不再由 adapter 手工读取 Skill 并拼接系统提示词。
- 使用 Claude Code 工具 preset，Agent 在所有对话阶段都拥有全部内置工具权限。
- 使用 `permission_mode="bypassPermissions"`，工具调用不经过 adapter 人工审批。

### 2.6 Snakemake Workflow Gatekeeper Skill

新增文件：

```text
/data/bioagent/agent/.claude/skills/bioinformatics-workflow-gatekeeper/SKILL.md
```

- 支持识别 workflow1-workflow6，不推荐 workflow7。
- 第一次确认前不得创建 run 目录或执行 dry-run。
- 第一次确认后才能复制 workflow、准备配置并执行 dry-run。
- dry-run 后必须总结执行计划并进行第二次确认。
- 第二次确认后才能通过 Bash 启动真实 Snakemake 执行。
- 不使用 MCP custom tool，不修改源 workflow。
- workflow1 已完成最小 dry-run，成功生成 `fastp -> bowtie2 -> merge -> megahit -> rename_filter -> all` DAG。

### 2.7 Open WebUI Chat ID Header

涉及位置：

```text
/data/bioagent/env/open-webui.env
/data/bioagent/open-webui/backend/open_webui/routers/openai.py
/data/bioagent/agent/adapter.py
```

当前启用：

```text
ENABLE_FORWARD_USER_INFO_HEADERS=True
```

- Open WebUI 通过 `X-OpenWebUI-Chat-Id` 转发当前 chat UUID。
- adapter 使用该 UUID 创建或恢复 Claude session。
- 未修改 Open WebUI 数据库结构，没有增加 `claude_session_id` 列。
- Open WebUI 将 `metadata.task` 转发为 `X-OpenWebUI-Task`。
- adapter 对标题、标签等后台任务使用临时 Claude client，任务结束后立即断开，不读取或写入主会话映射。

### 2.8 Dashboard 页面

涉及文件：

```text
/data/bioagent/open-webui/src/routes/(app)/dashboard/+page.svelte
/data/bioagent/open-webui/src/routes/auth/+page.svelte
```

- 新增 `/dashboard` 路由，并作为没有明确 redirect 时的登录后默认页面。
- 顶部统计项为 `Samples tracked`、`Reads Analyzed`、`High-risk findings`、`Species Identified`。
- 主区域预留 `Geospatial Virus Spread` 地图。
- 右侧预留 `AI Assistant`。
- 删除 `Recent Analysis Projects` 和 `Dashboard Data Plan`。
- 桌面端跟随左侧 Sidebar 缩宽并向右让位。
- 统计、地图和 AI Assistant 目前仍为静态占位。

### 2.9 Chat System Status 面板

涉及文件：

```text
/data/bioagent/open-webui/src/lib/components/chat/Chat.svelte
/data/bioagent/open-webui/src/lib/components/chat/SystemStatusPanel.svelte
```

- 聊天界面增加右侧 `System Status` 面板。
- 桌面端通过右侧窄栏图标展开或关闭。
- 收起后聊天区域自动扩展；移动端隐藏面板和 toggle。
- Open WebUI 原生 Controls 打开时不同时显示 System Status。
- 当前任务、CPU、内存和存储数据仍为静态占位。

### 2.10 systemd 源码部署

涉及目录：`/data/bioagent/systemd-user/`、`~/.config/systemd/user/`

- adapter、Open WebUI backend 和 frontend 均由用户级 systemd 管理。
- unit 使用绝对 conda 环境路径，不依赖交互式 `conda activate`。
- 源码、环境、缓存、数据库和运行数据均位于 `/data/bioagent`。

### 2.11 测试

涉及文件：

```text
/data/bioagent/agent/tests/test_runtime.py
/data/bioagent/agent/tests/test_adapter.py
```

当前测试覆盖：

- 新 chat 创建并保存 Claude session 映射。
- 已有 transcript 通过 `ClaudeAgentOptions.resume` 恢复。
- `SessionManager` 重建后仍能恢复相同 Claude session。
- 恢复后只发送最新用户消息。
- 缺失或非法 chat ID 被拒绝。
- 损坏 transcript 被拒绝。
- Open WebUI 后台任务使用临时会话且不创建 chat-map。
- 流式失败返回结构化 error 和 `[DONE]`，不会再产生不完整 chunked response。
- SDK 临时运行目录的 `projects` 正确链接到持久 transcript 目录。
- SDK 加载全部 Skills 和 Claude Code 工具 preset。

22 项测试均已通过。真实跨进程调用也已验证第一轮创建 transcript、Adapter 重启后通过原 Claude session ID 恢复并保留上下文。

### 2.12 2026-07-09 Session 修复

#### Bug 1：空闲后历史对话无法恢复

现象：

```text
Response payload is not completed:
<TransferEncodingError: 400, message='Not enough data to satisfy transfer length header.'>
```

原因：

- runtime 虽然保存了 `chat_id -> claude_session_id` 映射，但错误地调用 `client.query(prompt, session_id=...)`。
- 新 `ClaudeSDKClient` 没有通过 `ClaudeAgentOptions.resume` 恢复 transcript，因此创建了新的 Claude session。
- SDK 返回的新 session ID 与旧映射不一致，runtime 在已经发送部分 SSE 文本后抛错，导致响应没有 `[DONE]`。

代码改动：

- `runtime.py` 在创建 client 时加载 chat-map，并设置 `ClaudeAgentOptions(resume=claude_session_id)`。
- 同一个已连接 client 的后续消息只调用 `client.query(prompt)`。
- `adapter.py` 捕获流式 session 异常，发送结构化 error event 和 `[DONE]`，避免底层传输错误掩盖真实原因。
- `tests/test_runtime.py` 使用符合真实 SDK 语义的 FakeClient，并覆盖跨 `SessionManager` 重建恢复。

#### Bug 2：Open WebUI 后台任务污染主对话

原因：

- Open WebUI 标题、标签等后台任务与用户消息携带相同 `X-OpenWebUI-Chat-Id`。
- `metadata.task` 没有转发给 adapter，后台任务因此进入主 Claude session，产生 title/tag prompt 污染。

代码改动：

- `open-webui/backend/open_webui/env.py` 增加 `X-OpenWebUI-Task` Header 配置。
- `open-webui/backend/open_webui/routers/openai.py` 将 `metadata.task` 转发给 adapter。
- `adapter.py` 同时兼容 Header 与请求体中的 `metadata.task`。
- `runtime.py` 为后台任务创建一次性 client，不创建 chat-map，完成后立即断开。
- `tests/test_adapter.py` 覆盖主会话、临时任务和流式异常收尾。

### 2.13 `.claude` 持久化目录约束

`.claude` 只保留以下三类持久数据：

```text
.claude/
├── skills/
└── sessions/
    ├── bioagent/chat-map/
    └── projects/
```

- `skills/` 保存项目级 Skill。
- `sessions/bioagent/chat-map/` 保存 Open WebUI chat ID 与 Claude session ID 映射。
- `sessions/projects/` 保存 Claude transcript 和 subagent transcript。
- SDK 的 `CLAUDE_CONFIG_DIR` 调整为 `/tmp/bioagent-claude-runtime`。
- `/tmp/bioagent-claude-runtime/projects` 是指向持久 `sessions/projects/` 的符号链接。
- `plans`、`telemetry`、`backups`、`session-env`、`shell-snapshots` 等 SDK 临时内容只生成在 `/tmp`，不会写入项目 `.claude`。
- Adapter 启动时会自动创建运行目录和 `projects` 链接，服务器重启后无需手动恢复。

## 3. 当前状态与限制

- Dashboard 的统计、地图和 AI Assistant 尚未连接真实数据。
- System Status 尚未连接服务器资源 API。
- workflow2-workflow6 尚未逐个进行真实数据端到端验证。
- Snakemake 两次确认是 Skill 行为规则，不是底层强制权限闸门。
- runtime 当前按单个 uvicorn worker 设计，同一 chat 不应并发写入。
- Open WebUI backend 最近一次重启受到 cyclone `/data` 系统级磁盘 I/O 阻塞影响；这不是 Python 语法或 Header 回退错误。

## 4. Developer Guide

This guide is nearly identical to the [Open WebUI official document](https://docs.openwebui.com/getting-started/advanced-topics/development), with slight changes.

### 1. Clone the Repository

```bash
git clone --recurse-submodules git@github.com:BGIProjects/bioagent.git
cd bioagent
```

### 2. Agent Setup

In your **first terminal**:

```bash
cd agent
```

Create and activate a virtual environment:

```bash
conda create --name adapter python=3.11
conda activate adapter
```

Install dependencies and start the server:

```bash
pip install claude-agent-sdk fastapi uvicorn
AGENT_PORT=8001 bash start.sh
```

### 3. Frontend Setup

In your **second terminal**:

```bash
cd open-webui
cp -RPp .env.example .env
# change OPENAI_API_BASE_URL if needed
# if the backend port is not 8080,
# uncomment VITE_WEBUI_PORT and set the correct port in .env
npm install
NODE_OPTIONS=--max-old-space-size=8192 npm run build
npm run dev -- --port 5173
# you can use dev:fast afterwards
```

`npm run build` compiles the frontend, catches build-time errors early, and prepares several static resources. `npm run dev` then starts the dev server at http://localhost:5173. It will show a waiting screen until the backend is running.

> [!TIP]  
> If `npm install` falls with compatibility warnings, run `npm install --force`.

### 4. Backend Setup

In your **third terminal**:

```bash
cd open-webui/backend
```

Create and activate a virtual environment (Conda or venv):

```bash
# Option A: Conda
conda create --name open-webui python=3.11
conda activate open-webui

# Option B: venv
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

Install dependencies and start the server:

```bash
pip install -r requirements.txt -U
cp -RPp dev.sh dev-custom.sh
# set the correct ports in dev-custom.sh
bash dev-custom.sh
```

### 5. Connect to CycloneSeq Server

```bash
ssh -N \
  -L 5173:127.0.0.1:5173 \
  -L 8080:127.0.0.1:8080 \
  cyclone  # <name>@172.24.195.66
```

The backend starts at http://localhost:8080. API docs are available at http://localhost:8080/docs.

Refresh the frontend at http://localhost:5173 and you should see the full application.
