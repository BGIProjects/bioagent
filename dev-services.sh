#!/usr/bin/env bash
set -euo pipefail

ROOT=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
set -a
for config_file in "$ROOT/agent/.env" "$ROOT/open-webui/.env"; do
    if [[ -f "$config_file" ]]; then
        # shellcheck disable=SC1090
        source "$config_file"
    fi
done
set +a
# shellcheck disable=SC1091
source "$ROOT/deployment/load-profile.sh"
bioagent_load_profile services
PROFILE_PYTHON=${BIOAGENT_PROFILE_PYTHON:-python3}
CONDA=${BIOAGENT_CONDA_BIN:-${CONDA_EXE:-}}
NODE_BIN=${BIOAGENT_NODE_BIN:-}
TMUX=${TMUX_BIN:-tmux}
AGENT_HOST=${AGENT_HOST:-127.0.0.1}
AGENT_PORT=${AGENT_PORT:-8001}
AGENT_URL=${AGENT_URL:-http://127.0.0.1:${AGENT_PORT}}
BACKEND_HOST=${BACKEND_HOST:-127.0.0.1}
BACKEND_PORT=${PORT:-${BACKEND_PORT:-8080}}
PORT=$BACKEND_PORT
BACKEND_URL=${BACKEND_URL:-http://127.0.0.1:${BACKEND_PORT}}
FRONTEND_HOST=${FRONTEND_HOST:-127.0.0.1}
FRONTEND_PORT=${FRONTEND_PORT:-5173}
FRONTEND_URL=${FRONTEND_URL:-http://127.0.0.1:${FRONTEND_PORT}}
AGENT_HEALTH_URL=http://127.0.0.1:${AGENT_PORT}/v1/models
BACKEND_HEALTH_URL=http://127.0.0.1:${BACKEND_PORT}/health
FRONTEND_HEALTH_URL=http://127.0.0.1:${FRONTEND_PORT}/
SERVICE_SHELL=${BIOAGENT_SERVICE_SHELL:-${SHELL:-/bin/bash}}
case "$SERVICE_SHELL" in
    */bash) SERVICE_SHELL_FLAGS=-ic ;;
    */zsh) SERVICE_SHELL_FLAGS=-lic ;;
    *) echo "服务 shell 仅支持 Bash 或 zsh：$SERVICE_SHELL" >&2; exit 2 ;;
esac
MANAGE_TAXONAGENT=${BIOAGENT_MANAGE_TAXONAGENT:-0}
TAXONAGENT_URL=${TAXONAGENT_MCP_URL:-}
TAXONAGENT_SESSION=bioagent-taxonagent
TAXONAGENT_LOG=/tmp/bioagent-taxonagent.log

AGENT_SESSION=bioagent-agent
BACKEND_SESSION=bioagent-backend
FRONTEND_SESSION=bioagent-frontend
AGENT_LOG=/tmp/bioagent-agent.log
BACKEND_LOG=/tmp/bioagent-backend.log
FRONTEND_LOG=/tmp/bioagent-frontend.log
LOG_WARN_BYTES=$((${BIOAGENT_LOG_WARN_MIB:-100} * 1024 * 1024))

usage() {
    echo "用法: $0 {start|stop|restart|status|drain [原因]|resume [说明]}"
}

admission_command() {
    local action=$1 reason=${2:-}
    if [[ -z "${BIOAGENT_ADMISSION_STATE_FILE:-}" ]]; then
        echo "准入控制需要显式启用 DeploymentProfile。" >&2
        return 2
    fi
    if [[ "$action" == status ]]; then
        "$PROFILE_PYTHON" "$ROOT/deployment_admission.py" \
            --state-file "$BIOAGENT_ADMISSION_STATE_FILE" status
    else
        "$PROFILE_PYTHON" "$ROOT/deployment_admission.py" \
            --state-file "$BIOAGENT_ADMISSION_STATE_FILE" "$action" --reason "$reason"
    fi
}

discover_executable() {
    local name=$1 discovered
    discovered=$(command -v "$name" 2>/dev/null || true)
    if [[ ! -x "$discovered" && -x "$SERVICE_SHELL" ]]; then
        local lookup="type -P '$name'"
        [[ "$SERVICE_SHELL" == */zsh ]] && lookup="whence -p '$name'"
        discovered=$("$SERVICE_SHELL" "$SERVICE_SHELL_FLAGS" "$lookup" 2>/dev/null | tail -n 1)
    fi
    [[ -x "$discovered" ]] || return 1
    printf '%s\n' "$discovered"
}

resolve_tmux() {
    local discovered
    if [[ "$TMUX" == */* ]]; then
        [[ -x "$TMUX" ]] || {
            echo "TMUX_BIN 不可执行：$TMUX" >&2
            return 1
        }
        return
    fi
    discovered=$(discover_executable "$TMUX" || true)
    [[ -n "$discovered" ]] || {
        echo "找不到 tmux；请安装 tmux 或设置 TMUX_BIN。" >&2
        return 1
    }
    TMUX=$discovered
}

resolve_runtime_tools() {
    local discovered
    if [[ -z "$CONDA" ]]; then
        CONDA=$(discover_executable conda || true)
    fi
    [[ -x "$CONDA" ]] || {
        echo "找不到 conda；请初始化 Conda 或设置 BIOAGENT_CONDA_BIN。" >&2
        return 1
    }

    if [[ -n "$NODE_BIN" && -x "$NODE_BIN" && ! -d "$NODE_BIN" ]]; then
        NODE_BIN=$(dirname "$NODE_BIN")
    elif [[ -z "$NODE_BIN" ]]; then
        discovered=$(discover_executable node || true)
        [[ -n "$discovered" ]] && NODE_BIN=$(dirname "$discovered")
    fi
    [[ -x "$NODE_BIN/node" && -x "$NODE_BIN/npm" ]] || {
        echo "找不到 node/npm；请启用 Node 22，或将 BIOAGENT_NODE_BIN 设为 node/npm 所在目录（也可传 node 可执行文件）。" >&2
        return 1
    }

    local dependency
    for dependency in curl lsof openssl ssh; do
        if ! discover_executable "$dependency" >/dev/null; then
            echo "缺少启动依赖：$dependency" >&2
            return 1
        fi
    done
}

session_exists() {
    "$TMUX" has-session -t "$1" 2>/dev/null
}

port_pid() {
    lsof -nP -tiTCP:"$1" -sTCP:LISTEN 2>/dev/null | head -n 1
}

health_url() {
    if [[ "$MANAGE_TAXONAGENT" == 1 && "$1" == "$TAXONAGENT_URL" ]]; then
        [[ -x "$CONDA" ]] || CONDA=$(discover_executable conda || true)
        PYTHONPATH="$ROOT/agent" "$CONDA" run --no-capture-output -n adapter python -c \
            'import asyncio,sys; from taxonagent_adapter import TaxonAgentClient; sys.exit(asyncio.run(TaxonAgentClient(sys.argv[1]).status())["status"] != "ready")' \
            "$1" >/dev/null 2>&1
    else
        curl --noproxy '*' -fsS --max-time 2 "$1" >/dev/null 2>&1
    fi
}

file_size_bytes() {
    local path=$1
    if [[ ! -f "$path" ]]; then
        echo 0
    elif stat -f '%z' "$path" >/dev/null 2>&1; then
        stat -f '%z' "$path"
    else
        stat -c '%s' "$path"
    fi
}

format_bytes() {
    awk -v bytes="$1" 'BEGIN {
        split("B KiB MiB GiB TiB", units, " ")
        unit = 1
        while (bytes >= 1024 && unit < 5) {
            bytes /= 1024
            unit++
        }
        if (unit == 1) {
            printf "%.0f %s", bytes, units[unit]
        } else {
            printf "%.1f %s", bytes, units[unit]
        }
    }'
}

session_owns_pid() {
    local session=$1 current=$2 pane_pid parent count=0
    pane_pid=$("$TMUX" display-message -p -t "$session:0.0" '#{pane_pid}' 2>/dev/null || true)
    [[ -n "$pane_pid" ]] || return 1
    while [[ "$current" =~ ^[0-9]+$ ]] && (( current > 1 )) && (( count < 32 )); do
        [[ "$current" == "$pane_pid" ]] && return 0
        parent=$(ps -o ppid= -p "$current" 2>/dev/null | tr -d ' ')
        [[ -n "$parent" && "$parent" != "$current" ]] || break
        current=$parent
        count=$((count + 1))
    done
    return 1
}

wait_health() {
    local name=$1 url=$2 session=$3 attempts=${4:-90}
    local count=0
    until health_url "$url"; do
        count=$((count + 1))
        if ! session_exists "$session"; then
            echo "$name 启动进程已退出，请查看对应日志。" >&2
            return 1
        fi
        if (( count >= attempts )); then
            echo "$name health 检查超时：$url" >&2
            return 1
        fi
        sleep 1
    done
    echo "$name 已就绪：$url"
}

ensure_port_available() {
    local name=$1 port=$2 session=$3
    local pid
    pid=$(port_pid "$port" || true)
    if [[ -n "$pid" ]] && ! session_exists "$session"; then
        echo "$name 端口 $port 已由非目标进程 PID $pid 占用；未做终止。" >&2
        return 1
    fi
    if [[ -n "$pid" ]] && ! session_owns_pid "$session" "$pid"; then
        echo "$name 端口 $port 由 PID $pid 占用，但不属于 $session；未做终止。" >&2
        return 1
    fi
}

start_service() {
    local name=$1 session=$2 port=$3 command=$4 log=$5 url=$6
    ensure_port_available "$name" "$port" "$session"
    if session_exists "$session"; then
        echo "$name session 已存在。"
    else
        : >"$log"
        local key
        local -a environment=()
        # A pre-existing shared tmux server may carry stale deployment variables.
        # Credentials are read inside the interactive service shell, never argv.
        for key in BIOAGENT_DEPLOYMENT_PROFILE BIOAGENT_PROFILE_PYTHON \
            AGENT_HOST AGENT_PORT BACKEND_HOST PORT FRONTEND_HOST FRONTEND_PORT \
            FRONTEND_URL VITE_WEBUI_PORT VITE_WEBUI_BASE_URL; do
            environment+=(-e "$key=${!key-}")
        done
        "$TMUX" new-session -d -s "$session" "${environment[@]}" "$command >>$(printf '%q' "$log") 2>&1"
    fi
    wait_health "$name" "$url" "$session"
}

service_command() {
    local directory=$1 command=$2 initialized
    initialized="if command -v proxy_off >/dev/null 2>&1; then proxy_off >/dev/null 2>&1; fi; builtin cd $(printf '%q' "$directory") && $command"
    printf 'exec %q %s %q' "$SERVICE_SHELL" "$SERVICE_SHELL_FLAGS" "$initialized"
}

start_all() {
    resolve_tmux
    resolve_runtime_tools
    local agent_cmd backend_cmd frontend_cmd taxonagent_cmd
    if [[ "$MANAGE_TAXONAGENT" == 1 ]]; then
        if [[ "$TAXONAGENT_URL" != http://127.0.0.1:8765/mcp && "$TAXONAGENT_URL" != http://localhost:8765/mcp ]]; then
            echo "管理本机 TaxonAgent 需要将 TAXONAGENT_MCP_URL 设为 http://127.0.0.1:8765/mcp。" >&2
            return 1
        fi
        taxonagent_cmd=$(service_command "$HOME/projects/taxonagent" \
            "[[ -n \${MINIMAX_API_KEY:-} ]] || { echo 'MINIMAX_API_KEY 未配置'; exit 1; }; exec env LLM_BACKEND=minimax MINIMAX_MODEL=MiniMax-M3 $(printf '%q' "$CONDA") run --no-capture-output -n taxonagent python $(printf '%q' "$HOME/projects/taxonagent/mcp/taxonagent_mcp.py")")
        start_service TaxonAgent "$TAXONAGENT_SESSION" 8765 "$taxonagent_cmd" "$TAXONAGENT_LOG" "$TAXONAGENT_URL"
    fi
    agent_cmd=$(service_command "$ROOT/agent" "exec $(printf '%q' "$CONDA") run --no-capture-output -n adapter ./start.sh")
    backend_cmd=$(service_command "$ROOT/open-webui/backend" "exec $(printf '%q' "$CONDA") run --no-capture-output -n open-webui ./dev.sh")
    frontend_cmd=$(service_command "$ROOT/open-webui" "export PATH=$(printf '%q' "$NODE_BIN"):\$PATH; exec npm run dev:fast -- --host $(printf '%q' "$FRONTEND_HOST") --port $(printf '%q' "$FRONTEND_PORT") --strictPort --force")
    start_service Agent "$AGENT_SESSION" "$AGENT_PORT" "$agent_cmd" "$AGENT_LOG" "$AGENT_HEALTH_URL"
    start_service Backend "$BACKEND_SESSION" "$BACKEND_PORT" "$backend_cmd" "$BACKEND_LOG" "$BACKEND_HEALTH_URL"
    start_service Frontend "$FRONTEND_SESSION" "$FRONTEND_PORT" "$frontend_cmd" "$FRONTEND_LOG" "$FRONTEND_HEALTH_URL"
}

stop_service() {
    local name=$1 session=$2
    if ! session_exists "$session"; then
        echo "$name session 未运行。"
        return
    fi
    "$TMUX" send-keys -t "$session" C-c
    local count=0
    while session_exists "$session" && (( count < 10 )); do
        sleep 1
        count=$((count + 1))
    done
    if session_exists "$session"; then
        "$TMUX" kill-session -t "$session"
    fi
    echo "$name 已停止。"
}

status_line() {
    local name=$1 session=$2 url=$3 log=$4
    local session_state=未运行 health_state=不可用 log_bytes
    session_exists "$session" && session_state=运行中
    health_url "$url" && health_state=正常
    log_bytes=$(file_size_bytes "$log")
    printf '%-9s session=%-6s health=%-6s log=%s (%s)\n' \
        "$name" "$session_state" "$health_state" "$log" "$(format_bytes "$log_bytes")"
    if (( log_bytes >= LOG_WARN_BYTES )); then
        echo "警告：$name 日志已达到 $(format_bytes "$log_bytes")；运行中的 session 不会自动截断。"
    fi
}

status_all() {
    local tmp_available
    if [[ "$MANAGE_TAXONAGENT" == 1 ]]; then
        status_line TaxonAgent "$TAXONAGENT_SESSION" "$TAXONAGENT_URL" "$TAXONAGENT_LOG"
    fi
    status_line Agent "$AGENT_SESSION" "$AGENT_HEALTH_URL" "$AGENT_LOG"
    status_line Backend "$BACKEND_SESSION" "$BACKEND_HEALTH_URL" "$BACKEND_LOG"
    status_line Frontend "$FRONTEND_SESSION" "$FRONTEND_HEALTH_URL" "$FRONTEND_LOG"
    tmp_available=$(df -Pk /tmp | awk 'NR == 2 {printf "%.0f", $4 * 1024}')
    echo "/tmp     可用=$(format_bytes "${tmp_available:-0}")（日志仅在创建新 session 或 restart 时截断）"
    if [[ -n "${BIOAGENT_ADMISSION_STATE_FILE:-}" ]]; then
        admission_command status || echo "Admission 状态无效；新分析将 fail closed。"
    else
        echo "Admission 未配置（默认接收新分析）"
    fi
    if ssh -o ClearAllForwardings=yes -o ConnectTimeout=5 "${BIOAGENT_SSH_HOST:-Cyclone}" true >/dev/null 2>&1; then
        echo "Compute   SSH=正常（远端 worker session 不受本脚本管理）"
    else
        echo "Compute   SSH=连接暂时不可用（不推断远端任务失败）"
    fi
}

main() {
    case "${1:-}" in
        start) start_all ;;
        stop)
            resolve_tmux
            stop_service Frontend "$FRONTEND_SESSION"
            stop_service Backend "$BACKEND_SESSION"
            stop_service Agent "$AGENT_SESSION"
            if [[ "$MANAGE_TAXONAGENT" == 1 ]]; then
                stop_service TaxonAgent "$TAXONAGENT_SESSION"
            fi
            ;;
        restart)
            "$0" stop
            "$0" start
            ;;
        status)
            resolve_tmux
            status_all
            ;;
        drain) admission_command drain "${2:-部署维护}" ;;
        resume) admission_command resume "${2:-维护完成}" ;;
        *) usage; return 2 ;;
    esac
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    main "$@"
fi
