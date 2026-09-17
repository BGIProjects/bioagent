from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any


class JsonStore:
    """Process-local JSON documents with atomic replace."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, name: str) -> Path:
        return self.root / name

    def load(self, name: str, default: Any) -> Any:
        path = self.path(name)
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return default

    def save(self, name: str, value: Any) -> None:
        path = self.path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(value, ensure_ascii=False, indent=2, default=str)
        fd, tmp = tempfile.mkstemp(prefix=path.name, dir=str(path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def now(self) -> int:
        return int(time.time())
