# BioAgent Runtime 修复记录

本分支修复 BioAgent 历史会话恢复和 Open WebUI 后台任务污染问题，并收敛 `.claude` 的持久化目录结构。

## Bug 1：长时间空闲后历史对话恢复失败

### 问题现象

用户长时间离开后重新打开 Open WebUI 历史对话并继续发送消息，会看到：

```text
Response payload is not completed:
<TransferEncodingError: 400, message='Not enough data to satisfy transfer length header.'>
```

### 原因

BioAgent 已经保存了：

```text
Open WebUI chat_id -> Claude session_id
```

但恢复时错误地调用：

```python
client.query(prompt, session_id=claude_session_id)
```

`query()` 的 `session_id` 只用于标识流式输入消息，不会加载历史 transcript。新的 `ClaudeSDKClient` 因此创建了新 session。SDK 返回的新 session ID 与映射中的旧 ID 不一致后，runtime 在已经输出部分 SSE 内容的情况下抛出异常，导致响应没有正常发送 `[DONE]`。

### 具体改动方法

修改 `agent/runtime.py`：

1. 根据 `X-OpenWebUI-Chat-Id` 读取：

   ```text
   .claude/sessions/bioagent/chat-map/<openwebui_chat_id>.json
   ```

2. 从映射中取得 `claude_session_id`，并验证对应 transcript 存在且是合法 JSONL。

3. 创建 SDK client 时通过 options 恢复会话：

   ```python
   ClaudeAgentOptions(resume=claude_session_id)
   ```

4. client 连接后只发送当前新增消息：

   ```python
   await client.query(prompt)
   ```

5. 新对话完成第一轮后，从 `ResultMessage.session_id` 获取真实 Claude session ID，并写入 chat-map。

6. 保留 session ID 一致性检查，防止映射和 transcript 错配。

修改 `agent/adapter.py`：

1. 在 SSE generator 内捕获 `InvalidSessionError` 和 `SessionStateError`。
2. 发生错误时发送结构化 error event。
3. 最后仍发送：

   ```text
   data: [DONE]
   ```

这样 Open WebUI 会显示真实 session 错误，而不是底层 `TransferEncodingError`。

修改测试：

- `agent/tests/test_runtime.py` 使用符合真实 SDK 行为的 FakeClient。
- 覆盖新 session 映射保存、`SessionManager` 重建、`ClaudeAgentOptions.resume` 和恢复后增量消息发送。
- 真实测试已验证 Adapter 重启后仍能恢复相同 Claude session 和之前的上下文。

## Bug 2：Open WebUI 后台任务污染用户主会话

### 问题现象

Open WebUI 生成标题、标签等后台内容时，会把类似下面的结果写入 BioAgent 主对话：

```json
{"title": "Simple Hello Greeting"}
```

后台任务 prompt 也会进入用户主 Claude transcript，破坏后续多轮对话上下文。

### 原因

Open WebUI 的用户消息和标题、标签等后台任务携带相同的：

```text
X-OpenWebUI-Chat-Id
```

虽然 Open WebUI 请求 metadata 中存在 `task` 字段，但此前没有将它转发给 adapter。`SessionManager` 因而无法区分用户主消息和后台任务，将两者写入同一个持久 session。

### 具体改动方法

修改 `open-webui/backend/open_webui/env.py`：

```python
FORWARD_SESSION_INFO_HEADER_TASK = "X-OpenWebUI-Task"
```

修改 `open-webui/backend/open_webui/routers/openai.py`：

1. 读取请求中的 `metadata.task`。
2. 将任务类型转发给 adapter：

   ```text
   X-OpenWebUI-Task: title_generation
   ```

修改 `agent/adapter.py`：

1. `ChatRequest` 接收可选 `metadata`。
2. 同时识别：

   ```text
   X-OpenWebUI-Task
   metadata.task
   ```

3. 没有 task 标记的请求进入持久主会话。
4. 有 task 标记的请求进入临时会话。

修改 `agent/runtime.py`：

1. 新增 `stream_ephemeral_turn()`。
2. 每个后台任务创建独立的临时 `ClaudeSDKClient`。
3. 后台任务不读取 chat-map。
4. 后台任务不创建 chat-map。
5. 请求完成后立即断开临时 client。

修改 `agent/tests/test_adapter.py`：

- 验证普通消息使用持久 session。
- 验证 task 请求使用临时 session。
- 验证 task 请求不会创建 chat-map。
- 验证流式错误仍以合法 SSE 结束。

## 改动 3：收敛 `.claude` 持久化目录

### 目标结构

项目的 `.claude` 只保留以下三类持久数据：

```text
.claude/
├── skills/
│   └── bioinformatics-workflow-gatekeeper/
│       └── SKILL.md
└── sessions/
    ├── bioagent/
    │   └── chat-map/
    └── projects/
```

目录职责：

- `skills/`：保存项目级 Agent Skill。
- `sessions/bioagent/chat-map/`：保存 Open WebUI chat ID 与 Claude session ID 的映射。
- `sessions/projects/`：保存 Claude 主 session 和 subagent transcript。

### 具体做法

修改 `agent/config.py`，将持久状态和 SDK 临时运行状态分开：

```python
CLAUDE_STATE_DIR = PROJECT_ROOT / ".claude" / "sessions"
CLAUDE_RUNTIME_CONFIG_DIR = Path("/tmp/bioagent-claude-runtime")
```

修改 `agent/runtime.py`：

1. `CLAUDE_STATE_DIR` 只保存 chat-map 和 transcript。
2. SDK subprocess 使用 `/tmp/bioagent-claude-runtime` 作为 `CLAUDE_CONFIG_DIR`。
3. Adapter 启动时自动创建符号链接：

   ```text
   /tmp/bioagent-claude-runtime/projects
     -> /data/bioagent/agent/.claude/sessions/projects
   ```

4. Claude SDK 仍可通过该链接创建和恢复 transcript。
5. SDK 自动生成的以下内容只写入 `/tmp`：

   ```text
   backups/
   plans/
   sessions/
   session-env/
   shell-snapshots/
   telemetry/
   .claude.json
   ```

6. 删除 `.claude` 下已有的无关目录和文件。
7. `/tmp` 内容可在服务器重启后丢失；Adapter 下次启动会自动重建运行目录和 `projects` 链接。

### 验证结果

- Agent 和 Adapter 共 22 项测试通过。
- 后台 task 请求完成后没有生成 chat-map。
- Adapter 重启后成功通过原 Claude session ID 恢复上下文。
- 真实 Claude 请求执行后，`.claude` 没有重新生成 `plans`、`telemetry`、`backups` 等目录。
