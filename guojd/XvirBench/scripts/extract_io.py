"""Shared helpers for workflow extract_results.py scripts."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import pandas as pd
except ImportError:
    pd = None  # type: type


def xvirbench_scripts_dir() -> Path:
    return Path(os.environ.get("XVIRBENCH_ROOT", "/data/user/guojindan/Projects/XvirBench")) / "scripts"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def base_payload(workflow: str, version: str, result_dir: Path, **extra) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "workflow": workflow,
        "version": version,
        "result_dir": str(result_dir.resolve()),
        "extracted_at": utc_now_iso(),
        "tables": {},
    }
    payload.update(extra)
    return payload


def write_json(payload: Dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


def write_xlsx(payload: Dict[str, Any], path: Path, sheet_keys: List[tuple]) -> None:
    if pd is None:
        raise RuntimeError("导出 Excel 需要 pandas 与 openpyxl: pip install pandas openpyxl")
    path.parent.mkdir(parents=True, exist_ok=True)
    meta = {k: v for k, v in payload.items() if k != "tables"}
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        pd.DataFrame([meta]).to_excel(writer, sheet_name="meta", index=False)
        for sheet, key in sheet_keys:
            rows = payload.get("tables", {}).get(key, [])
            pd.DataFrame(rows if rows else []).to_excel(writer, sheet_name=sheet, index=False)


def df_records(df: Optional["pd.DataFrame"]) -> List[Dict[str, Any]]:
    if df is None or df.empty:
        return []
    out = df.where(df.notna(), None).to_dict(orient="records")
    return out


def read_csv_safe(path: Path, **kwargs) -> Optional["pd.DataFrame"]:
    if pd is None or not path.is_file():
        return None
    try:
        return pd.read_csv(path, **kwargs)
    except Exception:
        return None


def read_tsv_safe(path: Path, **kwargs) -> Optional["pd.DataFrame"]:
    return read_csv_safe(path, sep="\t", **kwargs)


def read_excel_safe(path: Path, **kwargs) -> Optional["pd.DataFrame"]:
    if pd is None or not path.is_file():
        return None
    try:
        return pd.read_excel(path, **kwargs)
    except Exception:
        return None
