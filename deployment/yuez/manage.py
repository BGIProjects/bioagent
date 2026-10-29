#!/usr/bin/env python3
"""Manage only the account-owned BioAgent yuez deployment."""

import argparse
import json
import os
from pathlib import Path
import secrets
import subprocess
import urllib.request


PROJECT = Path(__file__).resolve().parents[2]
STATE = Path.home() / ".local/share/bioagent-yuez"
UNITS = ["bioagent-yuez-agent.service", "bioagent-yuez-webui.service"]


def systemctl(*args, check=True):
    return subprocess.run(["systemctl", "--user", *args], check=check)


def environment_file(name, values):
    destination = STATE / "config" / (name + ".env")
    if destination.exists():
        return destination
    with destination.open("x", encoding="utf-8") as output:
        os.chmod(destination, 0o600)
        for key, value in values.items():
            output.write(key + "=" + json.dumps(str(value)) + "\n")
    return destination


def install():
    for directory in ["config", "data", "runs", "logs", "cache"]:
        (STATE / directory).mkdir(parents=True, exist_ok=True)
    shared = {
        "BIOAGENT_RUN_ROOT": STATE / "runs",
        "PATH": str(STATE / "runtimes/node/bin") + ":/usr/local/bin:/usr/bin:/bin",
        "PYTHONUNBUFFERED": "1",
    }
    agent_environment = environment_file("agent", {
        **shared,
        "CLAUDE_RUNTIME_CONFIG_DIR": STATE / "claude-runtime",
    })
    webui_environment = environment_file("webui", {
        **shared,
        "DATA_DIR": STATE / "data",
        "FRONTEND_BUILD_DIR": PROJECT / "open-webui/build",
        "WEBUI_SECRET_KEY": secrets.token_urlsafe(48),
        "WEBUI_AUTH": "true",
        "ENABLE_SIGNUP": "true",
        "DEFAULT_USER_ROLE": "user",
        "WEBUI_URL": "http://172.24.195.66:8083",
        "OPENAI_API_BASE_URLS": "http://127.0.0.1:8003/v1;http://172.24.195.65:8000/v1",
        "OPENAI_API_KEYS": "not-required;",
        "ENABLE_FORWARD_USER_INFO_HEADERS": "true",
        "ENABLE_OLLAMA_API": "false",
        "OFFLINE_MODE": "true",
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "HF_HOME": STATE / "cache/huggingface",
        "TIKTOKEN_CACHE_DIR": STATE / "cache/tiktoken",
        "BYPASS_EMBEDDING_AND_RETRIEVAL": "true",
        "RAG_EMBEDDING_MODEL_AUTO_UPDATE": "false",
        "RAG_RERANKING_MODEL_AUTO_UPDATE": "false",
        "WHISPER_MODEL_AUTO_UPDATE": "false",
        "GLOBAL_LOG_LEVEL": "WARNING",
        "SCARF_NO_ANALYTICS": "true",
        "DO_NOT_TRACK": "true",
        "ANONYMIZED_TELEMETRY": "false",
        "CORS_ALLOW_ORIGIN": "http://172.24.195.66:8083;http://127.0.0.1:8083;http://localhost:8083",
    })
    unit_directory = Path.home() / ".config/systemd/user"
    unit_directory.mkdir(parents=True, exist_ok=True)
    configurations = [
        ("agent", PROJECT / "agent", agent_environment,
         [STATE / "envs/agent/bin/python", "-m", "uvicorn", "adapter:app",
          "--host", "127.0.0.1", "--port", "8003"]),
        ("webui", PROJECT / "open-webui/backend", webui_environment,
         [STATE / "envs/webui/bin/python", "-m", "uvicorn", "open_webui.main:app",
          "--host", "0.0.0.0", "--port", "8083"]),
    ]
    for name, working_directory, config, command in configurations:
        unit = "\n".join([
            "[Unit]",
            "Description=BioAgent yuez " + name,
            "After=network.target",
            "", "[Service]", "Type=simple",
            "WorkingDirectory=" + str(working_directory),
            "EnvironmentFile=" + str(config),
            "ExecStart=" + " ".join(map(str, command)),
            "Restart=on-failure", "RestartSec=5", "TimeoutStopSec=30",
            "StandardOutput=append:" + str(STATE / "logs" / (name + ".log")),
            "StandardError=append:" + str(STATE / "logs" / (name + ".log")),
            "", "[Install]", "WantedBy=default.target", "",
        ])
        (unit_directory / ("bioagent-yuez-" + name + ".service")).write_text(unit)
    systemctl("daemon-reload")
    systemctl("enable", *UNITS)
    print("Deployment units installed. Configuration files are private and preserved.")


def status():
    systemctl("status", "--no-pager", "--lines=0", *UNITS, check=False)
    for name, url in [
        ("agent", "http://127.0.0.1:8003/v1/models"),
        ("webui", "http://127.0.0.1:8083/health"),
        ("frontend", "http://127.0.0.1:8083/"),
    ]:
        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                print(name + ": HTTP " + str(response.status))
        except Exception as error:
            print(name + ": " + type(error).__name__)


parser = argparse.ArgumentParser()
parser.add_argument("action", choices=["install", "start", "stop", "restart", "status"])
arguments = parser.parse_args()
if arguments.action == "install":
    install()
elif arguments.action == "status":
    status()
else:
    systemctl(arguments.action, *UNITS)
