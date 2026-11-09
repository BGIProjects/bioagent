# BioAgent 开发部署

本仓库支持 macOS 本机开发及 Linux 5090 部署；固定的 Workflow 1–6、FASTQ 预检、资源采集和分析产物全部留在 Cyclone。macOS 可直接访问 <http://127.0.0.1:5173>；5090 的浏览器访问使用下文的 SSH 转发，后端端口为 8081。

## 架构

```text
Chrome :5173 → Open WebUI Backend :8080 → BioAgent :8001
                                              │
                                              └─ SSH alias Cyclone
                                                 ├─ remote worker / private queue scheduler
                                                 ├─ /data/user/liufangzhou/datasets
                                                 ├─ /data/user/liufangzhou/runs
                                                 └─ Workflow 1–6
```

BioAgent 使用 `ssh -o ClearAllForwardings=yes`，因此不会启用 SSH config 中已有的转发。连接通过 ControlMaster/ControlPersist 复用。远端 worker 只同步运行所需 Python 模块，按内容哈希发布到：

```text
/data/user/liufangzhou/.bioagent/worker/releases/<sha256>
```

RPC 控制进程、每个 run root 的单一私有 tmux scheduler 与 analysis runner 共用 Cyclone 本机 NVMe 上的 `/home/liufangzhou/.pixi/envs/snakemake/bin/python`；Snakemake 与 SeqKit 分别使用 `/home/liufangzhou/.pixi/bin/snakemake`、`/home/liufangzhou/.pixi/bin/seqkit`。当前验证版本为 Python 3.12.14、Snakemake 9.26.1 与 SeqKit 2.13.0，不需要另建或迁移 adapter 环境，也不会回退 `/data` 上的旧环境。

Workflow 1 的源配置仍可保留原工具路径；worker 复制到 run root 后会只在 run-local `config.yaml` 中把 `software.seqkit` 改为 Pixi 入口，不修改 Cyclone 上的 Workflow 源码。

## Developer Guide

本节是 macOS 和 5090 的部署指南。默认继续使用现有 Cyclone 账号、数据与 Workflow；完成一次依赖安装后，日常操作请直接跳到[启停服务](#启停服务)。

### 1. 准备本机工具

需要 Git、OpenSSH、rsync、tmux、Conda、Node.js 22、npm、OpenSSL、curl 与 lsof。macOS 可先安装 Xcode Command Line Tools 与 Homebrew，再安装命令行依赖；Conda 建议使用 Miniconda，Node 建议由 nvm 管理：

```bash
xcode-select --install
brew install git rsync tmux openssl curl lsof
nvm install 22
nvm use 22
node --version
conda --version
```

`xcode-select --install` 已执行过时会提示工具已经存在。Miniconda 与 nvm 请按各自安装程序初始化 zsh 后再继续。

Linux 可用发行版的包管理器安装同名工具，支持 Bash，无需安装 zsh。5090 的 tmux 位于 `~/bin/tmux`，已加入 PATH。每次进入 5090 后执行 `proxy_off`；启动脚本也会在每个服务的交互式 shell 中执行该函数（如果存在），不需要修改共享的 `.bashrc`。脚本使用 Bash 内建 `[[ ... ]]` 检查，避免与用户定义的同名 `test` 函数冲突。

### 2. 克隆仓库与 submodule

```bash
git clone --recurse-submodules git@github.com:BGIProjects/bioagent.git
cd bioagent
git submodule update --init --recursive
git submodule status --recursive
```

最后一条命令应列出 `agent` 与 `open-webui`，且行首不应出现表示未初始化的 `-`。

### 3. 创建本机环境并安装依赖

以下命令均从仓库根目录执行：

```bash
conda create -n adapter python=3.11 -y
conda run -n adapter python -m pip install -r agent/requirements-lock.txt

conda create -n open-webui python=3.11 -y
conda run -n open-webui python -m pip install -U \
  -r open-webui/backend/requirements.txt

ONNXRUNTIME_NODE_INSTALL_CUDA=skip CYPRESS_INSTALL_BINARY=0 npm --prefix open-webui install
```

启动脚本不会自动 install 或 build。前端完整 build 只用于最终验收，见[验证](#验证)。

### 4. 配置并核对 Cyclone

在 `~/.ssh/config` 中准备 `Cyclone` alias；将主机地址替换为研究院实际地址：

```sshconfig
Host Cyclone
    HostName <Cyclone hostname or IP>
    User liufangzhou
    ServerAliveInterval 30
    ServerAliveCountMax 3
    ControlMaster auto
    ControlPath ~/.ssh/control-%C
    ControlPersist 10m
```

BioAgent 每次都会追加 `ClearAllForwardings=yes`，无需配置 5173/8080/8001 的 SSH port forwarding。先验证连接、私有 tmux、目录和 Workflow 1–6：

```bash
ssh -o ClearAllForwardings=yes Cyclone 'printf "SSH OK\n"'
ssh -o ClearAllForwardings=yes Cyclone \
  '/data/user/liufangzhou/bin/tmux -V'
ssh -o ClearAllForwardings=yes Cyclone '
  set -eu
  test -d /data/user/liufangzhou/datasets
  test -d /data/user/liufangzhou/runs
  for workflow in \
    workflow1_upstream workflow2_virusid_2026viral workflow3_hostid \
    workflow4_kraken_bracken workflow5_virus_quantification \
    workflow6_virus_annotation; do
      test -d "/data/user/guojindan/Projects/Workflows/$workflow"
  done
  printf "Cyclone paths OK\n"
'
```

远端 worker 固定使用 `/data/user/liufangzhou/bin/tmux -L bioagent-worker`，不要改为全局 tmux server。data root 可包含 symlink；准入规则见[数据路径与 symlink](#数据路径与-symlink)。

### 5. 在 Cyclone 准备 Home Pixi 工具

先按 Pixi 官方方式为远端用户安装 Pixi，再在 Cyclone 执行：

```bash
ssh -o ClearAllForwardings=yes Cyclone
pixi global install -c conda-forge -c bioconda snakemake
pixi global install -c bioconda seqkit
pixi global install \
  --environment bioagent-report \
  --channel conda-forge \
  --pinning-strategy exact-version \
  --expose bioagent-report-python=python \
  --expose bioagent-rscript=Rscript \
  --expose bioagent-weasyprint=weasyprint \
  python=3.12 pandas scipy openpyxl weasyprint \
  r-base r-ggplot2 r-dplyr r-tidyr r-readr r-scales \
  r-patchwork r-ggbeeswarm r-stringr
/home/liufangzhou/.pixi/envs/snakemake/bin/python --version
/home/liufangzhou/.pixi/bin/snakemake --version
/home/liufangzhou/.pixi/bin/seqkit version
/home/liufangzhou/.pixi/bin/bioagent-report-python -c 'import pandas, scipy, openpyxl'
/home/liufangzhou/.pixi/bin/bioagent-rscript --version
/home/liufangzhou/.pixi/bin/bioagent-weasyprint --version
exit
```

Snakemake runner 与报告环境彼此隔离；Bowtie2、MEGAHIT、Kraken2 等 Workflow 软件继续使用各 Workflow 当前配置，待对应路径正式支持后再迁移，不要在部署阶段批量安装。

### 6. 创建本机配置

tracked example 是配置的唯一模板，实际 `.env` 会被 Git 忽略：

```bash
cp agent/.env.example agent/.env
cp open-webui/.env.example open-webui/.env
```

需要集中管理部署差异时，可先验证并显式启用不含密钥的 DeploymentProfile；它会在启动时覆盖地址、路径、工具、模型身份与资源额度，其他功能开关仍来自 `.env`：

```bash
python3 deployment_profile.py validate deployment/profiles/cyclone-development.json
BIOAGENT_DEPLOYMENT_PROFILE=deployment/profiles/cyclone-development.json \
  ./dev-services.sh start
```

`deployment/profiles/independent-target.json` 是使用不同地址和目录的目标部署配置样例，须按现场实际路径准备依赖后再使用。两个 profile 都只记录 `MINIMAX_API_KEY` 这个凭证变量名；密钥值仍只由启动环境提供。profile 未显式启用时，现有 `.env` 启动方式不变。

建立运维恢复快照时，使用 profile 中的业务库、资产、run root、容量与保留数量；输出目录可指向已挂载的备份介质。工具使用 SQLite 在线备份，只从 Cyclone 读取已登记 run 的 `state.json` 与 `reports/`，并逐档校验 SHA-256。恢复命令只建立新的 staging 目录，不覆盖正式路径：

```bash
python3 deployment_backup.py create \
  deployment/profiles/cyclone-development.json backup-20261004 \
  --output-root /path/to/backup-media
python3 deployment_backup.py verify /path/to/backup-media/backup-20261004
python3 deployment_backup.py stage-restore \
  /path/to/backup-media/backup-20261004 /path/to/empty-restore-staging
```

工具不会自动删除旧快照。管理员先生成逐份验证的保留计划，核对 `keep`／`delete`、可回收容量与计划 `sha256`，再显式提交完全相同的摘要；期间目录变化、损坏快照、异 profile、未知文件或未完成操作都会拒绝清理：

```bash
python3 deployment_backup.py retention-plan \
  deployment/profiles/cyclone-development.json \
  --output-root /path/to/backup-media
python3 deployment_backup.py prune \
  deployment/profiles/cyclone-development.json \
  --output-root /path/to/backup-media \
  --plan-sha256 <retention-plan 输出的 sha256>
```

保留数量仍是整套 profile 级策略，不是项目级期限；需要外部受控排程定期执行。staging 或保留清理验证通过也不等于独立目标部署或定期恢复演练已经完成。

更新或维护前先显式停止新分析准入；这不会停止已在 Cyclone 运行或排队的任务。确认服务、数据库和在途任务状态后再维护，完成检查后恢复准入：

```bash
BIOAGENT_DEPLOYMENT_PROFILE=deployment/profiles/cyclone-development.json \
  ./dev-services.sh drain '部署维护'
BIOAGENT_DEPLOYMENT_PROFILE=deployment/profiles/cyclone-development.json \
  ./dev-services.sh status
# 执行已核准的维护并验证服务
BIOAGENT_DEPLOYMENT_PROFILE=deployment/profiles/cyclone-development.json \
  ./dev-services.sh resume '维护完成'
```

drain 期间新的 run start／resume 会收到可重试的 `ADMISSION_DRAINING`；方案编译、状态和报告读取保持可用。准入状态损坏时 fail closed，须由管理员修复或执行受控 resume，不能删除文件来绕过。

离线交付前先核对源码锁和目标平台介质。`source` 应成功；当前仓库没有提交数 GiB 的 wheel／uv／npm／Pyodide／系统与计算介质，而且 MiniMax-M3 不是离线模型，因此 `check` 预期返回退出码 3 和明确 blocker，不能当作已完成离线安装：

```bash
python3 deployment_preflight.py source
python3 deployment_preflight.py check
# 介质由目标平台构建并附带 media-manifest.json 后：
python3 deployment_preflight.py verify-media /path/to/offline-media
python3 deployment_preflight.py check --media-root /path/to/offline-media
```

media manifest 必须逐项覆盖 `deployment/offline-install-manifest.json` 的七类介质，并登记目标 platform／architecture、大小和 SHA-256；未知档案、缺件、篡改或 symlink 均拒绝。即使七类确定性运行介质齐全，MiniMax-M3 仍会保留 `MODEL_NOT_OFFLINE_CAPABLE`，不冒充全离线模型交付。

离线资产包先进入独立 store，不能直接覆盖当前 `agent/assets`。package／ReleaseSet 完整验证后，切换与回滚还必须处于 admission draining：

```bash
python3 asset_release_manager.py --store /srv/bioagent/asset-release-store \
  verify-package /media/knowledge-v1 --max-bytes 1073741824
python3 asset_release_manager.py --store /srv/bioagent/asset-release-store \
  import-package /media/knowledge-v1 \
  --max-bytes 1073741824 --min-free-bytes 5368709120
python3 asset_release_manager.py --store /srv/bioagent/asset-release-store \
  import-set /media/release-set-v1.json

./dev-services.sh drain '切换资产版本'
python3 asset_release_manager.py --store /srv/bioagent/asset-release-store \
  --admission-state /path/from/deployment-profile/admission.json \
  activate release-set-v1 --actor operator
python3 asset_release_manager.py --store /srv/bioagent/asset-release-store binding
./dev-services.sh resume '资产切换完成'
```

`status` 会列出 active／previous ReleaseSet、已安装数量与未完成的 `.partial-*`；`rollback --actor operator` 使用同一 draining gate 原子切回 previous。DeploymentProfile 的 `asset_release_store` 会导出为 `BIOAGENT_ASSET_RELEASE_STORE`：新方案冻结 active binding，启动前若 active 已变化则要求重新编译；已开始任务和恢复继续使用 run 中原组合。日常规划只校验小型 state／ReleaseSet／package manifest，不重扫大型 payload；全量内容哈希只在导入、切换和管理员 `status` 时执行。未准备 active ReleaseSet 的显式 profile 会 fail closed；默认未启用 profile 的既有开发入口保持不变。正式包仍须有真实来源、许可、回归及兼容记录。

默认模板已经对应当前 Cyclone。若更换远端账号或存储位置，至少同步修改下列变量：

- SSH 与 worker：`BIOAGENT_SSH_HOST`、`BIOAGENT_REMOTE_PYTHON`、`BIOAGENT_REMOTE_CONTROL_PYTHON`、`BIOAGENT_REMOTE_TMUX`、`BIOAGENT_REMOTE_WORKER_ROOT`
- 数据、产物与队列：`BIOAGENT_DATA_ROOT`、`BIOAGENT_DATA_ALLOWED_ROOTS`、`BIOAGENT_RUN_ROOT`、`BIOAGENT_QUEUE_AGING_HOURS`（默认 `24`，只接受正数）
- 资产版本：`BIOAGENT_ASSET_RELEASE_STORE`（只在已导入并启用 active ReleaseSet 后设置）
- 工具：`BIOAGENT_SNAKEMAKE`、`BIOAGENT_SEQKIT`
- Workflow：`BIOAGENT_WORKFLOW1_SOURCE` 至 `BIOAGENT_WORKFLOW6_SOURCE`
- Open WebUI：`BIOAGENT_DATA_ROOT`、`BIOAGENT_RUN_ROOT` 与需要时的 `PORT`

`TAXONAGENT_MCP_URL` 默认留空。5090 可启用现有 TaxonAgent：在 `agent/.env` 中设置下列值，确认 `taxonagent` Conda 环境和 `~/projects/taxonagent/mcp/taxonagent_mcp.py` 已就绪。

```dotenv
TAXONAGENT_MCP_URL=http://127.0.0.1:8765/mcp
BIOAGENT_MANAGE_TAXONAGENT=1
```

统一启动脚本会使用 `LLM_BACKEND=minimax MINIMAX_MODEL=MiniMax-M3` 启动 TaxonAgent，并继承 shell 中的密钥。手动诊断时可在独立终端执行；不要与已管理的 session 重复启动：

```bash
proxy_off
conda activate taxonagent
LLM_BACKEND=minimax MINIMAX_MODEL=MiniMax-M3 \
  python ~/projects/taxonagent/mcp/taxonagent_mcp.py
```

当前接口为只读 `taxonagent_query(question)`，用于 `/analysis` 分类知识问答；不接入序列分类。只连接外部 TaxonAgent 时保留 `BIOAGENT_MANAGE_TAXONAGENT=0`，脚本不会启停外部服务。

5090 的 `open-webui/.env` 使用以下配置。服务监听端口和本机浏览器转发地址分别设置，健康检查始终访问 5090 的实际监听端口：

```dotenv
PORT=8081
FRONTEND_URL=http://127.0.0.1:15173
VITE_WEBUI_BASE_URL=http://127.0.0.1:18081
AIOHTTP_CLIENT_TIMEOUT=600
```

Backend 启动时由 tracked `open-webui/backend/dev.sh` 自动创建或复用 `open-webui/backend/.webui_secret_key`，不需要也不应在 `.env` 手工设置 WebUI secret。

### 7. 可选启用 MiniMax

默认 `BIOAGENT_MODEL_POLICY=local_only`，未配置本地模型时对话不可用，表单、方案编译和执行仍可使用。当前 M0 开发实例已获显式云端授权，在忽略提交的 `agent/.env` 中设置 `BIOAGENT_MODEL_POLICY=minimax_explicit` 后使用 MiniMax；没有自动云端回退。仅启用确定性功能时可跳过本节。

Agent requirements 固定 `claude-agent-sdk==0.2.103`（内嵌 Claude Code 2.1.179）。provider 使用中国大陆 `https://api.minimax.cn/anthropic` 端点，并在 SDK 子进程内将默认 Claude 模型映射为 `MiniMax-M3[1m]`；对外模型名称仍为 `MiniMax-M3`。

只在交互式 shell 配置（macOS 的 `~/.zshrc` 或 5090 的 `~/.bashrc`）中加入密钥，不要写入仓库、`.env`、命令输出或日志：

```bash
export MINIMAX_API_KEY='<your key>'
```

重新打开对应终端。仅验证变量存在，5090 使用 Bash 版本：

```bash
/bin/zsh -lic '[[ -n "$MINIMAX_API_KEY" ]] && echo "MINIMAX_API_KEY is set"'
/bin/bash -ic '[[ -n "$MINIMAX_API_KEY" ]] && echo "MINIMAX_API_KEY is set"'
```

### 8. 启动服务

`dev-services.sh` 从当前 PATH 或交互式 Bash/zsh 查找 Conda 与 Node，并依可选 TaxonAgent → Agent → Backend → Frontend 启动。也可用 `BIOAGENT_SERVICE_SHELL=/bin/bash` 显式指定服务 shell：

```bash
./dev-services.sh start
./dev-services.sh status
open http://127.0.0.1:5173
```

5090 部署在自己的电脑另外打开一个终端并保持转发命令运行，然后访问 <http://127.0.0.1:15173/analysis>：

```bash
ssh -N -o ExitOnForwardFailure=yes \
  -L 15173:127.0.0.1:5173 \
  -L 18081:127.0.0.1:8081 5090
```

Agent 与 TaxonAgent 无需浏览器端口转发。若本机转发端口被占用，请同时调整 `.env` 中的浏览器地址、CORS Origin 与转发命令。

若工具不在 shell PATH，可显式覆盖；`BIOAGENT_NODE_BIN` 可传 node 可执行文件，也可传同时包含 `node`/`npm` 的目录：

```bash
BIOAGENT_CONDA_BIN=/path/to/conda \
BIOAGENT_NODE_BIN=/path/to/node/bin \
TMUX_BIN=/path/to/tmux \
  ./dev-services.sh start
```

启动入口只使用 tracked `agent/start.sh` 与 `open-webui/backend/dev.sh`；Backend 直接运行轻量 uvicorn，不调用 `start.sh`。Frontend 使用 `npm run dev:fast`，创建新 session 时强制重建 Vite 依赖缓存；重复执行 `start` 不会创建重复 session。首次准备浏览器 Python 功能或构建时，`scripts/prepare-pyodide.js` 会核对本地 Pyodide runtime 与所有依赖包的 SHA256，完整缓存可直接复用；缺包或版本不符时仍需下载。5090 已准备匹配的本地缓存，日常启动无需再次访问 CDN。

若浏览器在 Frontend 重启后显示 `500: Internal Error`，并且前端日志提示 `node_modules/.vite/deps` 中的 chunk 不存在，请先按 `Command+Shift+R` 强制刷新。若仍未恢复，清除 `127.0.0.1:5173` 的站点数据后重新登录；这类错误来自已打开页面保留的旧 Vite 模块地址，不表示 Backend 或 Agent 健康检查失败。

### 9. 迁移后的快速验收

```bash
curl -fsS http://127.0.0.1:8001/v1/models
curl -fsS http://127.0.0.1:8001/v1/analysis/health
# 5090 使用 8081；macOS 默认使用 8080
curl -fsS http://127.0.0.1:8081/health
curl -fsS http://127.0.0.1:5173/ >/dev/null
ssh -o ClearAllForwardings=yes -o ConnectTimeout=5 Cyclone true
./dev-services.sh status
```

然后在 WebUI 中选择 `BJ-2024-615_1.fastq.gz` 与 `BJ-2024-615_2.fastq.gz`，新建 dataset revision 并执行 quick preflight；应保持 `ready`，且智能模式能够生成 Workflow 1 方案。这里只做预检和 DAG dry-run，不执行重型 Workflow。`status` 还会显示三个日志大小、`/tmp` 可用空间和 Cyclone 连接摘要。

## 启停服务

依赖已经安装后，在仓库根目录运行：

```bash
./dev-services.sh start
./dev-services.sh status
./dev-services.sh stop
./dev-services.sh restart
```

`start` 依次启动已启用的 TaxonAgent、Agent、Backend、Frontend 并等待 health；`stop` 逆序终止，只操作自己管理的命名 session。停止这些服务不会终止 Cyclone 上的分析。对非目标进程占用的端口，脚本会拒绝启动而不终止进程。

| 服务     | 本机 tmux           | 地址             | 日志                         |
| -------- | ------------------- | ---------------- | ---------------------------- |
| Agent    | `bioagent-agent`    | `127.0.0.1:8001` | `/tmp/bioagent-agent.log`    |
| Backend  | `bioagent-backend`  | `127.0.0.1:8080` | `/tmp/bioagent-backend.log`  |
| Frontend | `bioagent-frontend` | `127.0.0.1:5173` | `/tmp/bioagent-frontend.log` |

5090 Backend 使用 `127.0.0.1:8081`；可选 TaxonAgent session 为 `bioagent-taxonagent`，客户端地址为 `http://127.0.0.1:8765/mcp`，日志为 `/tmp/bioagent-taxonagent.log`。

日志在同一个 tmux session 内持续追加，仅在创建新 session（包括 `restart`）时截断，不自动 rotation。`status` 会显示每个日志的大小和 `/tmp` 可用空间；单个日志达到 100 MiB 时只告警、不自动删除，因此极长的单次运行仍存在填满磁盘的理论风险。

每个服务使用交互式 Bash 或 login zsh 启动，并在 shell 初始化后执行可用的 `proxy_off`。Agent 和 TaxonAgent 继承 shell 中的 `MINIMAX_API_KEY`，不把密钥放入命令参数或日志。脚本显式传递当前端口和 profile，避免既有 tmux server 的旧环境影响新 session。Backend 使用 tracked 轻量入口 `backend/dev.sh`，首次启动通过 `openssl rand` 创建 `backend/.webui_secret_key`，之后复用；密钥文件权限受 `umask 077` 保护且被 Git 忽略。

本机私有配置只有 `agent/.env`、`open-webui/.env` 与自动生成的 `open-webui/backend/.webui_secret_key`，均不提交 Git。

## 远端任务与恢复

每个 run root 使用 `/data/user/liufangzhou/bin/tmux -L bioagent-worker` 维护唯一的 `bioagent-scheduler-<run-root-hash>`。scheduler 从 run-local state 读取持久队列，按 aging、冻结的项目优先级、紧急路由及入队时间排序；`analysis.lock` 只作为最终互斥。同一时间最多一个分析进入 `running`，其余显示为“排队中”或“等待资源”。

查看远端 session：

```bash
ssh -o ClearAllForwardings=yes Cyclone \
  /data/user/liufangzhou/bin/tmux -L bioagent-worker list-sessions

ssh -o ClearAllForwardings=yes -t Cyclone \
  /data/user/liufangzhou/bin/tmux -L bioagent-worker attach-session -t bioagent-scheduler-<run-root-hash>
```

SSH 暂时失联只会显示缓存状态和「连接暂时不可用」，不会把任务标记为失败。重连后以远端 state、scheduler、PID、boot ID 与 runner 命令为准：queued／waiting 会重新纳管；仍存活的 runner 只监看，不重复启动；已进入 running 但进程消失或主机重启则标记 `interrupted`，保留产物且不自动重跑。资源不足会登记 `waiting_stage`、原因与检查时间并释放准入，auto 已生成的初筛报告和完整流程 checkpoint 会保留。

新建的 Workflow 1 run 使用 recovery contract v2 冻结所选阶段的 workflow 源码闭包、软件和参考索引身份；任务中断后可在 `/analysis` 通过“检查并恢复”重新核对依赖并追加 attempt。已验证的完整 phase 可复用，依赖变化、旧恢复契约或 Workflow 2–6 会拒绝原地恢复；当前尚未完成真实 Workflow 1 中断恢复验收。

Dataset fingerprint 也遵循同样语义：Cyclone 暂时不可用时返回可重试错误并保持当前 dataset 状态；只有远端确认 logical link 或 canonical target 的指纹改变时才标记为 `stale`。历史上已标记 stale 的 revision 不会被自动改写，应重新选择文件建立新 revision。

## 数据路径与 symlink

- Data root：`/data/user/liufangzhou/datasets`
- Run root：`/data/user/liufangzhou/runs`
- 额外允许的 symlink target：`/data/user/guojindan/Projects/flu_tgs_ngs/rawdata/NGS`

文件与目录 symlink 都可使用。UI 和数据集保存 data root 下的 logical path；worker 在 Cyclone 解析 canonical target，并同时记录目标 stat 与路径中每个 symlink 的 lstat/target stat。broken link、循环、不可读目标、目录逃逸和 allowlist 外目标会被拒绝。其他共享资料根需加入 `BIOAGENT_DATA_ALLOWED_ROOTS`。

Workflow 仅在 run root 创建 run-local 文件、link 或 copy，不修改原始 FASTQ 或 symlink target。目前测试对为：

```text
/data/user/liufangzhou/datasets/BJ-2024-615_1.fastq.gz
/data/user/liufangzhou/datasets/BJ-2024-615_2.fastq.gz
```

## 项目分析

管理员在 `/dashboard` 页首的“项目设置”对话框创建项目、登记既有数据路径并设置成员；创建项目不会自动加入，需明确勾选“将自己加入并授予分析权限”或另行加入成员。成员在两页原页首选择项目，通过“进入分析”／“项目看板”保留选择并切换页面，查看共享历史，在自己的会话中分析。审核权限目前只登记；项目优先级在确认执行时由后端重新鉴权并冻结到 queue，新设置只影响之后提交的任务。

继续使用 SQLite；首次升级前先做一致性备份。迁移、权限操作与回退见 [M1 第二轮记录](docs/m1-02-projects-implementation-record.md)。本轮页首整合、浏览器验证与仅前端回退见 [M1 第三轮记录](docs/m1-03-project-ui-implementation-record.md)。无需新增环境变量；沿用 `BIOAGENT_DATA_ROOT`、`BIOAGENT_REMOTE_DATA` 和原有 Cyclone 连接配置。

在 `/analysis` 选取已有数据集后，打开数据集卡片的“样本背景”查看或编辑元信息；窄屏入口位于内容区“数据集与背景”。背景独立版本化，保存不触发计算；新编译方案才冻结当前背景，旧方案／报告不回填。操作、迁移备份与回退见 [M1 第四轮记录](docs/m1-04-dataset-metadata-implementation-record.md)，无需新增配置。

数据集建立者可在“修订配对与角色”检查样本分组并逐项确认技术重复，保存新数据版本后另行生成方案；新版本背景不自动继承。见 [M1 第五轮记录](docs/m1-05-sample-grouping-implementation-record.md)，无需新增配置。

`/analysis` 提供智能、标准、紧急三种模式：智能模式先生成 5% 初筛快报，再继续已确认完整流程；标准模式直接执行完整流程；紧急模式只完成 5% 初筛。没有成对 reads 时智能／紧急会明确降为标准。任务区按状态提供初筛报告、带人工审核清单的诊断意见书、标准交付报告 HTML/PDF 与运行审计报告。交付报告只覆盖 W1–W6，确定性生成并写入 run-local `reports/standard/`；配置入口为 `agent/.env.example` 中三个 `BIOAGENT_REPORT_*` 变量。详见 [M1 第六轮记录](docs/m1-06-adaptive-routing-implementation-record.md)与 [M1 第七轮记录](docs/m1-07-standard-delivery-report-implementation-record.md)。

当前 `/analysis` 的“优先 Demo”区读取 capabilities schema v2 中的版本化本地工具与工作流技能，并提供科学、工具、技能报告入口。报告 API 为 `POST /api/v1/analysis/runs/priority-reports` 与 `GET /api/v1/analysis/runs/artifact-report`；所有产物留在对应 run 的 `reports/standard/`。科学报告的受控推理仅在 `BIOAGENT_MODEL_POLICY=minimax_explicit` 时使用现有 MiniMax 配置；密钥仍只由交互式 shell 提供，不写入仓库或报告。

任务区会显示队列位置、冻结的项目／任务优先级、等待阶段及可读资源原因；继续使用现有轮询，没有新增队列管理页或取消操作。合格的 `interrupted` 任务提供受控人工恢复，详见 [M1 第十二轮记录](docs/m1-12-interrupted-run-recovery-reproduction.md)与[第十三轮记录](docs/m1-13-workflow1-identity-b3-contract-reproduction.md)；队列复现与限制见 [M1 第十一轮记录](docs/m1-11-persistent-queue-reproduction.md)。

`/analysis` 可对已发布的工程能力、artifact 与 fastp 白名单参数显示受控引用卡片；每条回答最多保存 4 个短摘录，随项目会话隔离并可在历史对话重开。工程契约不代表生物学审核；历史复现见 [M1 第十轮记录](docs/m1-10-engineering-citations-reproduction.md)。启用 TaxonAgent 后，分类知识使用独立来源卡片，保留服务未提供的版本和定位信息为空，并标记尚未经人工审核；不使用隔离回放中的待审核语料，也不新增数据库迁移。可用 `What is the classification standard of Coronaviridae?` 在 `/analysis` 验证。

Workflow 2 的只读工程研判入口为 `agent/candidate_assessment.py --state <run>/.bioagent/state.json --summary`。它只输出 evidence／finding／assessment 聚合计数；在领域资产与正式 reference release 未核准时不会生成研判草稿、写回 run 或新增数据库记录。实现边界与 Cyclone 实证见 [M1 第十七轮记录](docs/m1-17-release-contract-m2-assessment-reproduction.md)。

## 验证

M1 第一轮开发检查入口为 `m1-check.py assets|offline|evaluate`，复现命令、固定输入、评测结果与未来专家审核流程见 [M1 实施记录](docs/m1-01-assets-evaluation-implementation-record.md)。该开发工具不新增配置或数据库；模型评测只有传入 `--allow-cloud` 才调用 MiniMax，输出仅写入 run root 下新的 `m1-*` 目录。

M0 的隔离回放入口为根目录 `m0-replay.py`，复现命令、产物位置和未完成项见 [M0 实施记录](docs/m0-implementation-record.md)。回放只读取现有初筛的小型结果文件，输出写入 run root 下新的 `m0-*` 目录，不启动计算或覆盖正式报告。

```bash
# Agent（adapter 环境没有单独安装 pytest 时，可借用 open-webui 的 pytest 包）
PYTHONPATH=/Users/lfz/miniconda3/envs/open-webui/lib/python3.11/site-packages \
  /Users/lfz/miniconda3/envs/adapter/bin/python -m pytest -q

# Backend
BIOAGENT_REMOTE_DATA=false WEBUI_SECRET_KEY=test-only-key PYTHONPATH=. \
  /Users/lfz/miniconda3/envs/open-webui/bin/python -m unittest \
  open_webui.utils.test_analysis_datasets \
  open_webui.routers.test_analysis \
  open_webui.routers.test_analysis_plans_api \
  open_webui.utils.test_analysis_run_delivery \
  open_webui.utils.test_report_evidence

# Frontend
npm run test:frontend -- --run src/lib/utils/analysisRun.test.ts \
  src/lib/utils/systemResources.test.ts src/lib/utils/singleFlight.test.ts \
  src/lib/apis/analysis/index.test.ts
```

最后才执行一次前端 build：

```bash
NODE_OPTIONS=--max-old-space-size=8192 npm run build >/tmp/bioagent-frontend-build.log 2>&1
```
