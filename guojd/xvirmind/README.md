# XvirMind v1.1 方案代码（DeepSeek Harness 前端 + 专项 MCP）

本目录是按 2026-09-10/11 顶层设计落地的**可运行骨架**，与 cyclone `/data/bioagent`、liufangzhou bioagent 并行，不覆盖旧运行态。

## 架构

```
浏览器  :3080  DeepSeek Harness 风格 Web（会话 / Trajectory / 插件面板）
   │
宿主 Host :3080/api   主 Agent：意图路由、确认、引用校验
   ├── taxonomy MCP  :8766   /data/user/wangdaxi/Projects/virus_taxonomy
   └── annotation MCP :8767  /data/user/wangdaxi/rna_virus_annotation
```

- 前端可替换：当前是 DSH 架构适配页（host + 浏览器，工具为插件）。本机 Node 为 v10，官方 `npx @deepseek-ai/dsh web` 无法启动，故先提供兼容宿主。
- 查询类 MCP（KB / 科级规则 / 科列表）默认可调用。
- 计算类 MCP（`taxonomy_classify` / `annotation_annotate`）默认 dry-run；需界面确认 **且** `XVIRMIND_ALLOW_COMPUTE=1` 才尝试真实脚本。

## 启动

```bash
cd /data/user/guojindan/Projects/XvirMind/xvirmind
bash scripts/start.sh
```

测试端口：

| 服务 | 地址 |
| --- | --- |
| Web / 主 Agent | http://127.0.0.1:3080/ |
| Host API 健康检查 | http://127.0.0.1:3080/api/health |
| Taxonomy MCP | http://127.0.0.1:8766/health |
| Annotation MCP | http://127.0.0.1:8767/health |

停止：`bash scripts/stop.sh`

## 自测

```bash
cd /data/user/guojindan/Projects/XvirMind/xvirmind
PYTHONPATH=. python3 -m pytest tests/test_mcp_contract.py -q
```

示例查询（启动后）：

```bash
curl -s http://127.0.0.1:3080/api/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"查询 Coronaviridae 的 ICTV 分类标准"}'
```
