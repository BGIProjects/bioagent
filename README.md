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
  ▼
BioAgent Adapter（FastAPI，127.0.0.1:8001）
  │  OpenAI 协议与 Claude Agent SDK 协议转换
  ▼
Claude Agent SDK Runtime
  ├── 项目级 Skills、Claude Code 内置工具、本地 session transcript
  ├── ICTV 查询 → MCP Streamable HTTP → TaxonAgent MCP Server（5090:8765）
  └── MiniMax Anthropic-compatible API

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

#### BioAgent Adapter 与 Runtime

- 源码位于 `/data/bioagent/agent`。
- adapter 暴露 `/v1/models` 和 `/v1/chat/completions`，只负责协议转换。
- runtime 负责 Claude SDK 配置、session 创建与恢复、Skill 和工具加载。
- runtime 在 ICTV 分类问题中通过 MCP 调用 5090 上的 TaxonAgent。
- runtime 不访问 Open WebUI 数据库，不保存额外 chat/session 映射。

#### TaxonAgent MCP Server

- 运行于 5090，监听 `0.0.0.0:8765`，MCP endpoint 为 `/mcp`。
- 暴露 `ictv_family_info(family_name)`，用于查询 ICTV 分类规则、划界标准、marker gene 与 genome type。
- Server 源码位于 5090 的独立 `~/projects/taxonagent` 项目，不属于本 repo 的 `agent/` submodule。
- BioAgent 使用内网地址 `http://172.24.202.246:8765/mcp` 访问该服务。

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

TaxonAgent MCP Server 位于 5090，当前需在 `taxonagent` conda 环境中手动启动，不由 cyclone 的用户级 systemd 管理。

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

- 现在只负责 FastAPI 路由、OpenAI-compatible 数据结构和 SSE 流式输出。
- 从请求头读取 `X-OpenWebUI-Chat-Id`，把消息和 chat ID 交给 `SessionManager`。
- 同时支持流式与非流式 completion。
- 移除 Skill 文件读取、阶段切换、prompt 拼接和工具权限业务逻辑。
- 删除 `/plan`、`/execute` 命令和 plan/execute 两种运行模式。

### 2.2 Runtime 与 SessionManager

新增文件：`/data/bioagent/agent/runtime.py`

- 新增 `SessionManager`，负责 SDK options、session 创建、恢复和结果校验。
- 不持有长期运行的 `ClaudeSDKClient`；每个 HTTP 请求使用独立 `query()` subprocess。
- 不访问 `webui.db`，不维护额外数据库映射。
- 校验 chat ID 必须是规范 UUID。
- 校验 transcript 是合法 JSONL，损坏时明确拒绝恢复。
- 校验 SDK 返回 session ID 与 Open WebUI chat ID 一致。

删除文件：`/data/bioagent/agent/phases.py`

### 2.3 多轮对话与 Session 持久化

涉及文件：`runtime.py`、`.gitignore`

```text
Open WebUI chat_id
  ├── transcript 不存在：ClaudeAgentOptions(session_id=chat_id)
  │                        首次发送当前 Open WebUI 历史进行引导
  └── transcript 已存在：ClaudeAgentOptions(resume=chat_id)
                           只发送最新用户消息
```

Transcript 位置：

```text
/data/bioagent/agent/.claude/sessions/projects/-data-bioagent-agent/<chat_id>.jsonl
```

- `.claude/sessions/` 已加入 `.gitignore`。
- `local:` 和 `channel:` 类型 chat ID 使用临时单次会话。

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
- 当前没有 `X-OpenWebUI-Task` 逻辑。此前增加的后台 task Header 和临时会话隔离已经回退，runtime 不对标题、标签等后台请求做专门分类。

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

新增文件：`/data/bioagent/agent/tests/test_runtime.py`

当前 6 个测试覆盖：

- 新 chat 使用 `session_id=chat_id`。
- 已有 transcript 使用 `resume=chat_id`。
- 恢复后只发送最新用户消息。
- 缺失或非法 chat ID 被拒绝。
- 损坏 transcript 被拒绝。
- `local:` chat 使用临时会话。
- SDK 加载全部 Skills 和 Claude Code 工具 preset。

所有测试均已通过。真实两轮调用也已验证第一轮创建 transcript、第二轮恢复并保留上下文。

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

### 2. TaxonAgent MCP Server Setup

In your **first terminal**, connect to 5090 and start the MCP server:

```bash
ssh 5090
conda activate taxonagent
python ~/projects/taxonagent/mcp/taxonagent_mcp.py
```

The server listens on `0.0.0.0:8765` and exposes the Streamable HTTP endpoint at `/mcp`. BioAgent connects to it over the internal network, so browser SSH port forwarding for port 8765 is not required.

### 3. Agent Setup

In your **second terminal**:

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
cp -RPp start.sh start-custom.sh
# set the port and BioAgent run root in start-custom.sh
bash start-custom.sh
```

### 4. Frontend Setup

In your **third terminal**:

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

### 5. Backend Setup

In your **fourth terminal**:

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
# set the correct ports, BioAgent run root,
# and WebUI secret key in dev-custom.sh
bash dev-custom.sh
```

### 6. Connect to CycloneSeq Server

```bash
ssh -N \
  -L 5173:127.0.0.1:5173 \
  -L 8080:127.0.0.1:8080 \
  cyclone  # <name>@172.24.195.66
```

Only the browser-facing frontend and backend ports are forwarded. The BioAgent runtime reaches TaxonAgent MCP directly over the internal network.

The backend starts at http://localhost:8080. API docs are available at http://localhost:8080/docs.

Refresh the frontend at http://localhost:5173 and you should see the full application.

## 3. 张月账号当前开发与测试部署

本节补充当前 `/home/zhangyue/projects/bioagent` 的部署方式。前文的旧版 `/data/bioagent` 部署说明继续保留，二者属于不同部署，不要混用路径、端口或 systemd 服务。

### 3.1 当前工作目录

- 项目根目录：`/home/zhangyue/projects/bioagent`
- Agent：`/home/zhangyue/projects/bioagent/agent`
- Open WebUI：`/home/zhangyue/projects/bioagent/open-webui`
- Agent 服务：`127.0.0.1:8003`
- WebUI：`http://172.24.195.66:8083`
- 分析运行数据：`/home/zhangyue/.local/share/bioagent-yuez/runs`

### 3.2 当前请求链路

```text
浏览器 → WebUI:8083 → BioAgent:8003 → DGX Qwen:172.24.195.65:8000/v1
```

分析页面使用 BioAgent；BioAgent 通过 DGX 上的 `qwen3.8-27b` 进行语义规划。当前部署由 `deployment/yuez/` 中的脚本管理。

### 3.3 当前服务检查

```bash
systemctl --user status bioagent-yuez-agent.service bioagent-yuez-webui.service
curl http://127.0.0.1:8003/health
curl http://127.0.0.1:8083/health
curl http://172.24.195.65:8000/v1/models
```
