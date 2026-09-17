"""Number formatting, path compaction, and drop JSON-like columns for reports."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional

import numpy as np
import pandas as pd

JSON_COL_HINTS = (
    "json",
    "traceback",
    "payload",
    "table_rows_json",
    "stdout",
    "stderr",
)

PATH_COL_HINTS = (
    "out_dir",
    "result_dir",
    "extractor",
    "fallback",
    "path",
    "fq1",
    "fq2",
)

INT_COL_HINTS = (
    "n_",
    "_n",
    "reads",
    "bases",
    "contigs",
    "taxa",
    "count",
    "n_runs",
    "n_tables",
    "k",
    "n_group",
    "n_missing",
)
PCT_COL_HINTS = ("pct", "percent", "q30", "retention")
P_COL_HINTS = ("p_value", "p_adj", "pval")
FRAC_COL_HINTS = ("frac", "effect", "rate", "retention", "duplication")


def drop_json_columns(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    keep = [
        c
        for c in df.columns
        if not any(h in str(c).lower() for h in JSON_COL_HINTS)
    ]
    return df.loc[:, keep]


def _looks_like_path(val: object) -> bool:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return False
    s = str(val).strip()
    return s.startswith("/") or s.startswith("file://")


def detect_path_columns(df: pd.DataFrame) -> list[str]:
    cols = []
    if df is None or df.empty:
        return cols
    for c in df.columns:
        cl = str(c).lower()
        if any(h in cl for h in PATH_COL_HINTS):
            cols.append(c)
            continue
        s = df[c].dropna().astype(str)
        if s.empty:
            continue
        hit = s.map(_looks_like_path).mean()
        if hit >= 0.5:
            cols.append(c)
    return cols


def common_prefix(paths: Iterable[str]) -> str:
    vals = [str(p) for p in paths if p and str(p).startswith("/")]
    if len(vals) < 2:
        return str(Path(vals[0]).parent) + "/" if vals else ""
    try:
        pref = str(Path(*Path(vals[0]).parts[: len(Path(vals[0]).parts)]))
        cp = str(Path(vals[0]))
        for v in vals[1:]:
            a, b = Path(cp).parts, Path(v).parts
            i = 0
            while i < min(len(a), len(b)) and a[i] == b[i]:
                i += 1
            cp = str(Path(*a[:i])) if i else ""
            if not cp:
                return ""
        return cp.rstrip("/") + "/"
    except Exception:
        return ""


def relativize_paths(df: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    """Replace absolute paths with tails; return common prefix for a table note."""
    if df is None or df.empty:
        return df, ""
    out = df.copy()
    path_cols = detect_path_columns(out)
    collected: list[str] = []
    for c in path_cols:
        collected.extend(str(v) for v in out[c].dropna().tolist() if _looks_like_path(v))
    prefix = common_prefix(collected)
    if not prefix:
        # still strip to basename if single absolute paths
        for c in path_cols:
            out[c] = out[c].map(
                lambda v: Path(str(v)).name if _looks_like_path(v) else v
            )
        return out, ""
    for c in path_cols:
        def _rel(v, pref=prefix):
            if not _looks_like_path(v):
                return v
            s = str(v)
            if s.startswith(pref):
                return s[len(pref):] or "."
            return Path(s).name
        out[c] = out[c].map(_rel)
    return out, prefix


def format_number(val: object, col: str = "") -> str:
    if val is None or (isinstance(val, float) and not np.isfinite(val)) or pd.isna(val):
        return "NA"
    if isinstance(val, bool) or (isinstance(val, np.bool_)):
        return "TRUE" if val else "FALSE"
    if isinstance(val, str):
        return val
    cl = col.lower()
    try:
        fv = float(val)
    except (TypeError, ValueError):
        return str(val)

    if any(h in cl for h in P_COL_HINTS):
        if fv < 0.0001:
            return f"{fv:.2e}"
        return f"{fv:.4f}"

    is_int_col = any(h in cl for h in INT_COL_HINTS) or cl in {"n", "k"}
    if is_int_col and abs(fv - round(fv)) < 1e-6:
        return f"{int(round(fv)):,}"

    if any(h in cl for h in PCT_COL_HINTS) and "frac" not in cl:
        # stored 0-1 or 0-100
        x = fv * 100 if 0 <= fv <= 1.5 else fv
        return f"{x:.2f}"

    if any(h in cl for h in FRAC_COL_HINTS) and "pct" not in cl:
        return f"{fv:.4f}"

    if abs(fv - round(fv)) < 1e-9 and abs(fv) >= 1:
        return f"{int(round(fv)):,}"
    if abs(fv) < 1:
        return f"{fv:.4f}"
    if abs(fv) >= 1000:
        return f"{fv:,.2f}"
    return f"{fv:.2f}"


def format_dataframe(df: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    """Drop JSON cols, compact paths, stringify numbers for report tables."""
    if df is None or df.empty:
        return df if df is not None else pd.DataFrame(), ""
    out = drop_json_columns(df)
    out, prefix = relativize_paths(out)
    show = pd.DataFrame(index=out.index)
    for c in out.columns:
        show[c] = [format_number(v, str(c)) if _is_numeric_cell(v) else ("" if pd.isna(v) else str(v)) for v in out[c]]
    return show, prefix


def _is_numeric_cell(v: object) -> bool:
    if isinstance(v, bool) or isinstance(v, np.bool_):
        return False
    return isinstance(v, (int, float, np.integer, np.floating)) and not pd.isna(v)


def shorten_user_text(text: str, known_roots: Optional[list[str]] = None) -> str:
    """Strip absolute prefixes from free-text sentences."""
    if not text:
        return text
    s = text
    roots = known_roots or []
    for r in sorted(roots, key=len, reverse=True):
        if r and r in s:
            s = s.replace(r, "")
    # generic /data/user/... collapse: keep last 3 parts if a unix path appears
    import re
    def _clip(m):
        path = m.group(0)
        parts = Path(path).parts
        if len(parts) > 4:
            return "/".join(parts[-3:])
        return path
    s = re.sub(r"(?:/data|/home)[/A-Za-z0-9_.\-]+", _clip, s)
    return s
