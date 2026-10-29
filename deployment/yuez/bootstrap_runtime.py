#!/usr/bin/env python3
"""Install account-owned runtimes without changing the system installation."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import tarfile
import urllib.request
import zipfile


ROOT = Path.home() / ".local/share/bioagent-yuez"


def fetch(url):
    with urllib.request.urlopen(url, timeout=90) as response:
        return response.read()


def download(url, target, expected):
    if target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest() == expected:
        return
    print("DOWNLOAD", target.name, flush=True)
    temporary = target.with_suffix(target.suffix + ".part")
    digest = hashlib.sha256()
    with urllib.request.urlopen(url, timeout=90) as response, temporary.open("wb") as output:
        while True:
            block = response.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
            output.write(block)
    if digest.hexdigest() != expected:
        temporary.unlink()
        raise RuntimeError("Download checksum mismatch: " + target.name)
    temporary.replace(target)
    print("VERIFIED", target.name, flush=True)


def run(*args):
    print("RUN", *map(str, args), flush=True)
    subprocess.run(list(map(str, args)), env=environment, check=True)


for directory in ["bin", "downloads", "runtimes", "envs", "logs", "data", "runs", "cache"]:
    (ROOT / directory).mkdir(parents=True, exist_ok=True)

environment = os.environ.copy()
environment.update(
    UV_CACHE_DIR=str(ROOT / "cache/uv"),
    UV_PYTHON_INSTALL_DIR=str(ROOT / "runtimes/python"),
    UV_PYTHON_PREFERENCE="only-managed",
)

metadata = json.loads(fetch("https://pypi.org/pypi/uv/0.13.6/json"))
wheel = next(
    item for item in metadata["urls"]
    if "manylinux_2_17_x86_64" in item["filename"] and item["filename"].endswith(".whl")
)
wheel_path = ROOT / "downloads" / wheel["filename"]
download(wheel["url"], wheel_path, wheel["digests"]["sha256"])
uv = ROOT / "bin/uv"
with zipfile.ZipFile(wheel_path) as archive:
    executable = next(name for name in archive.namelist() if name.endswith("/uv"))
    uv.write_bytes(archive.read(executable))
uv.chmod(0o755)

checksums = fetch("https://nodejs.org/dist/v22.23.4/SHASUMS256.txt").decode()
checksum, filename = next(
    line.split() for line in checksums.splitlines() if line.endswith("-linux-x64.tar.xz")
)
node_archive = ROOT / "downloads" / filename
download("https://registry.npmmirror.com/-/binary/node/v22.23.4/" + filename,
         node_archive, checksum)
node_directory = ROOT / "runtimes" / filename[:-len(".tar.xz")]
if not (node_directory / "bin/node").is_file():
    with tarfile.open(node_archive) as archive:
        for member in archive.getmembers():
            relative = Path(member.name)
            if relative.is_absolute() or ".." in relative.parts:
                raise RuntimeError("Unexpected archive path")
        archive.extractall(ROOT / "runtimes")
node_link = ROOT / "runtimes/node"
if not node_link.exists():
    node_link.symlink_to(node_directory, target_is_directory=True)
environment["PATH"] = str(node_link / "bin") + ":" + environment.get("PATH", "")

run(uv, "--version")
run(node_link / "bin/node", "--version")
run(node_link / "bin/npm", "--version")
run(uv, "python", "install", "3.11")
for name in ["agent", "webui"]:
    destination = ROOT / "envs" / name
    if not (destination / "bin/python").is_file():
        run(uv, "venv", "--python", "3.11", destination)
    run(destination / "bin/python", "--version")

manifest = {
    "state_directory": str(ROOT),
    "uv_version": metadata["info"]["version"],
    "node_archive": filename,
    "node_sha256": checksum,
    "python": "3.11",
}
(ROOT / "runtime-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
print("BOOTSTRAP_COMPLETE", flush=True)
