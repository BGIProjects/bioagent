# guojd 参考快照（2026-09-17）

本目录是 Cyclone 上 `/data/user/guojindan/Projects/XvirMind` 的**最新源码参考**，挂在 `BGIProjects/bioagent` 的 `guojd` 分支，方便对照，不替代仓库根目录的 `agent` / `open-webui` submodule。

## 包含

| 路径 | 说明 |
| --- | --- |
| `xvirmind/` | 本机 XvirMind host / MCP / 知识页（不含 `runs/`、`temp/`） |
| `deploy/openwebui_firstwave/` | Open WebUI 第一/二波 overlay，用于合入 `/data/bioagent` |
| `docs/` | 进展报告与 `plan/v260830` 顶层设计、roadmap |
| `knowledge/` | 知识库 demo 与 `20260911-demo` release |
| `testdata/` | 小规模演示 FASTQ / contig |
| `XvirBench/` | Benchmark 源码与全流程分析体系文档（不含 `batches/` 测序数据） |

## 明确未上传

- `XvirBench/batches/`（约 467G 原始数据）
- `XvirBench/benchmark/runs/` 提取结果
- `runtime/`、`XvirMind_old/`、他人目录软链
- `docs/paper/` 第三方 PDF
- `.env` 密钥文件

合入 cyclone 时请看 `deploy/openwebui_firstwave/README.md`。
