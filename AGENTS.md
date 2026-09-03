# BioAgent 本机开发说明

## 路径与服务

- Open WebUI 前后端：`/data2/lfz/projects/bioagent/open-webui`
- BioAgent：`/data2/lfz/projects/bioagent/agent`
- Workflow 1 源码：`/data2/lfz/projects/workflows/workflow1_upstream`
- 测试 FASTQ：`/data2/lfz/datasets/BGI/NGS/BJ-2024-615_{1,2}.fastq.gz`
- Analysis runs：`/data2/lfz/checkpoints/BGI`
- 端口：Frontend `5173`、Backend `8080`、Agent `8001`
- tmux：`bioagent-frontend`、`bioagent-backend`、`bioagent-agent`
- 日志：`/tmp/bioagent-frontend.log`、`/tmp/bioagent-backend.log`、`/tmp/bioagent-agent.log`

## 工具与环境

- Node/npm：`/data2/lfz/tools/nvm/versions/node/v22.23.2/bin`
- Conda：`/data2/lfz/tools/miniconda3/bin/conda`
- Agent conda 环境：`adapter`
- Backend conda 环境：`open-webui`
- Ruff：`/data/lfz/bin/ruff`
- Workflow 1 的 Snakemake、fastp、Bowtie2、MEGAHIT、SeqKit：`/data2/lfz/tools/pixi/bin`
- Workflow 1 的 samtools：`/data2/lfz/tools/samtools/bin/samtools`
- Workflow 1 的 Bowtie2 rRNA 索引前缀：`/data2/lfz/databases/BGI/zhongda_rRNAdb/zhongda_rRNAdb`
- `MINIMAX_API_KEY` 由交互式 shell 环境提供；不得打印、复制到文档或提交 Git。
- 本机 CUDA 10 不受锁定版 `onnxruntime-node` 的 GPU 包支持；安装前端依赖使用 `ONNXRUNTIME_NODE_INSTALL_CUDA=skip npm ci`，保留内置 CPU 运行时。

## 当前本机状态

- TaxonAgent/5090 不可用，本机设置 `TAXONAGENT_MCP_URL=''`。
- 仅启用 Workflow 1 对应的 `contig_filter`；Workflow 2–6 暂不启用。
- Workflow 1 已迁移完成；除非用户明确要求，不要安装或升级现有生信软件。
- `BIOAGENT_DATA_ROOT=/data2/lfz/datasets/BGI/NGS`
- `BIOAGENT_RUN_ROOT=/data2/lfz/checkpoints/BGI`
- 本机忽略提交的配置为 `agent/.env`、`open-webui/.env` 和 `open-webui/backend/dev-custom.sh`；WebUI secret 由后者首次启动时生成，不要提交或输出。

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
