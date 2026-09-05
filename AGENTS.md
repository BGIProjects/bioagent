# BioAgent 本机开发说明

## 路径与服务

- Open WebUI 前后端：`/Users/lfz/Documents/Project/bioagent/open-webui`
- BioAgent：`/Users/lfz/Documents/Project/bioagent/agent`
- Workflow 1 源码：`Cyclone:/data/user/guojindan/Projects/Workflows/workflow1_upstream`
- 测试 FASTQ：`Cyclone:/data/user/guojindan/Projects/flu_tgs_ngs/rawdata/NGS/BJ-2024-615_{1,2}.fastq.gz`
- Analysis runs：`Cyclone:/data/user/liufangzhou/runs`
- 端口：Frontend `5173`、Backend `8080`、Agent `8001`
- tmux：`bioagent-frontend`、`bioagent-backend`、`bioagent-agent`
- 日志：`/tmp/bioagent-frontend.log`、`/tmp/bioagent-backend.log`、`/tmp/bioagent-agent.log`

## 工具与环境

- Node/npm：`/Users/lfz/.nvm/versions/node/v22.23.2/bin`
- Conda：`/Users/lfz/miniconda3/bin/conda`
- Agent conda 环境：`adapter`
- Backend conda 环境：`open-webui`
- Ruff：`/Users/lfz/.local/bin/ruff`
- `MINIMAX_API_KEY` 由交互式 shell 环境提供；不得打印、复制到文档或提交 Git。

## 当前本机状态

- TaxonAgent/5090 不可用，本机设置 `TAXONAGENT_MCP_URL=''`。
- 启用 Workflow 1–6，在 `Cyclone` 完成计算。
- `BIOAGENT_SSH_HOST=Cyclone`，SSH 调用固定使用 `ClearAllForwardings=yes`。
- `BIOAGENT_DATA_ROOT=/data/user/liufangzhou/datasets`，额外 symlink allowlist 为 `/data/user/guojindan/Projects/flu_tgs_ngs/rawdata/NGS`。
- `BIOAGENT_RUN_ROOT=/data/user/liufangzhou/runs`。
- Cyclone control worker、tmux supervisor 与 runner 共用 `/home/liufangzhou/.pixi/envs/snakemake/bin/python`，Snakemake 与 SeqKit 分别使用 `/home/liufangzhou/.pixi/bin/snakemake`、`/home/liufangzhou/.pixi/bin/seqkit`；不回退 `/data` 上的旧环境。
- 远端 Python、Snakemake 与 SeqKit 位于 Cyclone 本机 NVMe；命令行工具使用 `pixi global install -c bioconda <tool>` 管理，无需迁移或维护第二套 adapter 环境。私有 tmux 仍使用 `/data/user/liufangzhou/bin/tmux -L bioagent-worker`。
- Workflow 1 只在 run-local 副本覆写 `software.seqkit` 为 Home Pixi 入口，不修改 Cyclone 上的 Workflow 源码。
- 本机忽略提交的配置为 `agent/.env`、`open-webui/.env` 和 `open-webui/backend/.webui_secret_key`；WebUI secret 由 tracked `open-webui/backend/dev.sh` 首次启动时生成，不要提交或输出。
- tracked `.env.example` 是唯一配置模板；Backend 由 tracked `open-webui/backend/dev.sh` 直接启动轻量 uvicorn，不调用重型 `start.sh`。
- 根目录 `dev-services.sh` 统一执行 `start|stop|restart|status`；停止本机服务不得终止远端 worker session。
- SSH 断线不得推断 Workflow 失败；重连后以远端 state、tmux、PID 与 boot ID reconciliation。
- data root 内可使用 allowlisted 文件或目录 symlink；保存 logical path，执行前解析 canonical target 并验证 link/target 双重指纹。
- 远端 fingerprint 暂时无法验证时保持 dataset 原状态并返回 retryable 503；只有确认不一致才标记 `stale`。
- 本机服务日志仅在创建新 tmux session（包括 `restart`）时截断，不自动 rotation；`status` 会显示大小、`/tmp` 可用空间并在 100 MiB 告警。

## 验证顺序

- 修改后先运行相关 Python/Vitest 测试和 Ruff，再运行 Prettier check。
- 最后只运行一次前端 build，避免 build → check → build。
- `npm run check` 会产生 9k+ 既有类型错误，不作为验收命令；使用 `npm run build` 验证可编译。
- Build 使用 `NODE_OPTIONS=--max-old-space-size=8192`，完整输出写入 `/tmp`，只读取日志结尾。

## 实作偏好

- UI 文案使用简体中文。
- 保持极简设计，优先删除无用代码，不保留无明确需求的兼容层。
- 允许破坏式更新；避免过度防御、重复抽象和无必要文件。
- 不修改或搬动原始 FASTQ；测试输出只能写入 run root。
