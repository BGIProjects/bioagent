from __future__ import annotations

import os
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = ROOT / "config" / "defaults.yaml"


def load() -> dict:
    data = yaml.safe_load(DEFAULTS.read_text(encoding="utf-8")) if DEFAULTS.exists() else {}
    host = data.setdefault("host", {})
    mcp = data.setdefault("mcp", {})
    paths = data.setdefault("paths", {})
    policy = data.setdefault("policy", {})
    host["bind"] = os.environ.get("XVIRMIND_HOST", host.get("bind", "127.0.0.1"))
    host["port"] = int(os.environ.get("XVIRMIND_WEB_PORT", host.get("port", 3080)))
    mcp["taxonomy_port"] = int(os.environ.get("XVIRMIND_TAXONOMY_PORT", mcp.get("taxonomy_port", 8766)))
    mcp["annotation_port"] = int(os.environ.get("XVIRMIND_ANNOTATION_PORT", mcp.get("annotation_port", 8767)))
    if os.environ.get("XVIRMIND_TAXONOMY_ROOT"):
        paths["taxonomy_root"] = os.environ["XVIRMIND_TAXONOMY_ROOT"]
    if os.environ.get("XVIRMIND_ANNOTATION_ROOT"):
        paths["annotation_root"] = os.environ["XVIRMIND_ANNOTATION_ROOT"]
    if os.environ.get("XVIRMIND_RUN_ROOT"):
        paths["run_root"] = os.environ["XVIRMIND_RUN_ROOT"]
    policy["allow_compute"] = os.environ.get("XVIRMIND_ALLOW_COMPUTE", "0") in {"1", "true", "TRUE"}
    policy["local_only"] = os.environ.get("XVIRMIND_LOCAL_ONLY", "1") not in {"0", "false", "FALSE"}
    return data
