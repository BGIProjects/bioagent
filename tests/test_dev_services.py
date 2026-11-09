from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]


@pytest.fixture
def checkout(tmp_path):
    for name in ("agent", "open-webui", "deployment"):
        (tmp_path / name).mkdir()
    for name in ("dev-services.sh", "deployment/load-profile.sh"):
        shutil.copy2(ROOT / name, tmp_path / name)
    (tmp_path / "agent/.env").write_text(
        "BIOAGENT_MANAGE_TAXONAGENT=1\nTAXONAGENT_MCP_URL=http://127.0.0.1:8765/mcp\n"
    )
    (tmp_path / "open-webui/.env").write_text(
        "PORT=8081\nFRONTEND_URL=http://127.0.0.1:15173\nVITE_WEBUI_BASE_URL=http://127.0.0.1:18081\n"
    )
    return tmp_path


def run(checkout, script):
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("BIOAGENT_", "BASH_FUNC_"))
    }
    env.update(SHELL="/bin/bash", HOME=str(checkout))
    return subprocess.run(
        ["bash", "-c", "source ./dev-services.sh\n" + script],
        cwd=checkout,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )


def test_env_ports_and_health_are_independent_of_browser_urls(checkout):
    result = run(
        checkout,
        'printf "%s\\n" "$BACKEND_PORT" "$BACKEND_HEALTH_URL" "$FRONTEND_HEALTH_URL" "$FRONTEND_URL" "$VITE_WEBUI_BASE_URL"',
    )
    assert result.stdout.splitlines() == [
        "8081",
        "http://127.0.0.1:8081/health",
        "http://127.0.0.1:5173/",
        "http://127.0.0.1:15173",
        "http://127.0.0.1:18081",
    ]


def test_service_shell_loads_credentials_and_clears_proxy(checkout):
    (checkout / ".bashrc").write_text(
        "export http_proxy=http://invalid:9\nexport MINIMAX_API_KEY=test-only\nproxy_off() { unset http_proxy; }\ntest() { exit 99; }\n"
    )
    result = run(
        checkout,
        """
command=$(service_command "$ROOT/agent" '[[ -z ${http_proxy:-} && -n ${MINIMAX_API_KEY:-} ]] && printf "service-ready"')
bash -c "$command"
""",
    )
    assert result.stdout == "service-ready"
    assert "test-only" not in result.stdout + result.stderr


def test_tmux_receives_current_ports_instead_of_stale_server_env(checkout):
    result = run(
        checkout,
        """
ensure_port_available() { :; }
session_exists() { return 1; }
wait_health() { :; }
fake_tmux() { printf '%s\\n' "$@"; }
TMUX=fake_tmux
start_service Backend bioagent-backend 8081 command "$ROOT/test.log" "$BACKEND_HEALTH_URL"
""",
    )
    assert "PORT=8081" in result.stdout.splitlines()
    assert "VITE_WEBUI_BASE_URL=http://127.0.0.1:18081" in result.stdout.splitlines()
    assert "MINIMAX_API_KEY" not in result.stdout


def test_start_and_stop_order_include_only_opted_in_taxonagent(checkout):
    result = run(
        checkout,
        """
resolve_tmux() { :; }
resolve_runtime_tools() { CONDA=/bin/true; NODE_BIN=/bin; }
start_service() { printf 'start %s\\n' "$1"; }
stop_service() { printf 'stop %s\\n' "$1"; }
start_all
main stop
""",
    )
    assert result.stdout.splitlines() == [
        f"start {name}" for name in ("TaxonAgent", "Agent", "Backend", "Frontend")
    ] + [f"stop {name}" for name in ("Frontend", "Backend", "Agent", "TaxonAgent")]


def test_external_taxonagent_is_not_started_or_stopped(checkout):
    (checkout / "agent/.env").write_text(
        "TAXONAGENT_MCP_URL=http://external.example/mcp\n"
    )
    result = run(
        checkout,
        """
resolve_tmux() { :; }
resolve_runtime_tools() { CONDA=/bin/true; NODE_BIN=/bin; }
start_service() { printf 'start %s\\n' "$1"; }
stop_service() { printf 'stop %s\\n' "$1"; }
start_all
main stop
""",
    )
    assert "TaxonAgent" not in result.stdout
