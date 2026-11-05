#!/usr/bin/env python3
"""Install the dependencies of the checked-out BioAgent submodules."""

from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import subprocess
from urllib.parse import unquote, urljoin
from urllib.request import urlopen


PROJECT = Path(__file__).resolve().parents[2]
STATE = Path.home() / ".local/share/bioagent-yuez"
UV = STATE / "bin/uv"
environment = os.environ.copy()
environment.update(
    PATH=str(STATE / "runtimes/node/bin") + ":" + environment.get("PATH", ""),
    UV_CACHE_DIR=str(STATE / "cache/uv"),
    UV_PYTHON_INSTALL_DIR=str(STATE / "runtimes/python"),
    UV_HTTP_TIMEOUT="180",
    CYPRESS_INSTALL_BINARY="0",
    PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD="1",
    npm_config_cache=str(STATE / "cache/npm"),
    npm_config_registry="https://registry.npmmirror.com",
)


class TorchWheelLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.matches = []

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        href = dict(attrs).get("href", "")
        filename = unquote(href.split("#", 1)[0])
        if "torch-2.9.1+cpu-cp311-cp311-manylinux_2_28_x86_64.whl" in filename:
            self.matches.append(href)


with urlopen("https://download.pytorch.org/whl/cpu/torch/", timeout=60) as response:
    torch_links = TorchWheelLinks()
    torch_links.feed(response.read().decode("utf-8"))
if len(torch_links.matches) != 1 or "#sha256=" not in torch_links.matches[0]:
    raise RuntimeError("Could not identify the pinned CPU-only PyTorch wheel and hash")
torch_wheel_url = urljoin("https://download.pytorch.org/whl/cpu/torch/", torch_links.matches[0])


def install(name, commands, working_directory):
    log_path = STATE / "logs" / ("install-" + name + ".log")
    with log_path.open("a") as log:
        for command in commands:
            command = list(map(str, command))
            log.write("RUN " + " ".join(command) + "\n")
            log.flush()
            result = subprocess.run(
                command, cwd=working_directory, env=environment, stdout=log,
                stderr=subprocess.STDOUT,
            )
            if result.returncode:
                return {"component": name, "success": False, "exit_code": result.returncode}
    return {"component": name, "success": True}


agent_python = STATE / "envs/agent/bin/python"
webui_python = STATE / "envs/webui/bin/python"
jobs = [
    (
        "agent",
        [[UV, "pip", "install", "--python", agent_python,
          "claude-agent-sdk==0.2.97", "fastapi==0.136.3", "uvicorn[standard]==0.41.0",
          "pydantic==2.13.4", "httpx==0.28.1", "PyYAML>=6.0,<7"]],
        PROJECT / "agent",
    ),
    (
        "webui",
        [
            [UV, "pip", "install", "--python", webui_python, torch_wheel_url],
            [UV, "pip", "install", "--python", webui_python, "-r",
             PROJECT / "open-webui/backend/requirements.txt"],
        ],
        PROJECT / "open-webui/backend",
    ),
    (
        "frontend",
        [[STATE / "runtimes/node/bin/npm", "ci", "--no-audit", "--no-fund"]],
        PROJECT / "open-webui",
    ),
]

with ThreadPoolExecutor(max_workers=3) as executor:
    futures = [executor.submit(install, *job) for job in jobs]
    results = [future.result() for future in futures]

(STATE / "dependency-install.json").write_text(json.dumps(results, indent=2) + "\n")
for result in results:
    print(json.dumps(result), flush=True)
raise SystemExit(0 if all(result["success"] for result in results) else 1)
