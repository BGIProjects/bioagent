"""Discover present workflows, sample metadata, and usable grouping factors."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from .config import (
    GROUP_CANDIDATES,
    MISSING_TOKENS,
    WORKFLOWS,
    WorkflowSpec,
)


@dataclass
class WorkflowPresence:
    spec: WorkflowSpec
    present: bool
    path: Optional[Path]
    reason: str


@dataclass
class Cohort:
    samples: pd.DataFrame  # one row per biological sample_id (vXX)
    runs: pd.DataFrame
    group_cols: list[str]
    grouping_notes: list[str]
    source_files: dict[str, str]


@dataclass
class Discovery:
    run_dir: Path
    batch_id: str
    workflows: list[WorkflowPresence]
    cohort: Cohort
    extra_notes: list[str] = field(default_factory=list)

    @property
    def present_specs(self) -> list[WorkflowSpec]:
        return [w.spec for w in self.workflows if w.present]

    def path_for(self, key: str) -> Optional[Path]:
        for w in self.workflows:
            if w.spec.key == key:
                return w.path
        return None


def _is_missing(val: Any) -> bool:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return True
    return str(val).strip() in MISSING_TOKENS


def detect_workflows(run_dir: Path, include_optional: bool = False) -> list[WorkflowPresence]:
    out: list[WorkflowPresence] = []
    for spec in WORKFLOWS:
        if not spec.default_report and not include_optional:
            continue
        root = run_dir / spec.dirname
        if not root.is_dir():
            out.append(WorkflowPresence(spec, False, None, f"directory {spec.dirname} not found"))
            continue
        hit = [m for m in spec.markers if (root / m).exists()]
        if hit:
            out.append(WorkflowPresence(spec, True, root, f"markers: {', '.join(hit)}"))
        else:
            # empty placeholder dir
            nonempty = any(root.iterdir())
            if nonempty:
                out.append(WorkflowPresence(spec, True, root, "directory exists without expected markers"))
            else:
                out.append(WorkflowPresence(spec, False, root, "directory empty"))
    return out


def _read_table_guess(path: Path) -> pd.DataFrame:
    if not path.is_file():
        return pd.DataFrame()
    sep = "\t" if path.suffix.lower() in {".tsv", ".txt"} else ","
    # try header first
    df = pd.read_csv(path, sep=sep, dtype=str, keep_default_na=False)
    if df.shape[1] == 1 and "\t" in str(df.columns[0]):
        df = pd.read_csv(path, sep="\t", dtype=str, keep_default_na=False)
    return df


def _normalize_sid(x: Any) -> Optional[str]:
    if _is_missing(x):
        return None
    s = str(x).strip()
    if s.startswith("v") and s[1:].isdigit():
        return s
    if s.isdigit():
        return f"v{s}"
    # 61_1 run-style
    if "_" in s and s.split("_")[0].isdigit():
        return f"v{s.split('_')[0]}"
    return s


def _search_meta(run_dir: Path, names: tuple[str, ...]) -> Optional[Path]:
    candidates = [
        run_dir / "cohorts",
        run_dir,
        run_dir.parent,
        run_dir.parent.parent,
        run_dir.parent.parent.parent,
    ]
    for folder in candidates:
        if not folder.is_dir():
            continue
        for name in names:
            p = folder / name
            if p.is_file():
                return p
    return None


def _parse_groupinfo(path: Path) -> pd.DataFrame:
    raw = path.read_text(errors="replace").splitlines()
    rows = []
    for ln in raw:
        ln = ln.strip()
        if not ln or ln.startswith("#"):
            continue
        parts = ln.split("\t") if "\t" in ln else ln.split()
        if len(parts) < 2:
            continue
        # detect header
        if parts[0].lower() in {"id", "sample", "sample_id", "sn"}:
            continue
        rec = {"raw_id": parts[0]}
        rec["sample_id"] = _normalize_sid(parts[0])
        if len(parts) >= 2:
            rec["sn"] = parts[1]
        if len(parts) >= 3:
            rec["host"] = parts[2]
        if len(parts) >= 4:
            rec["method"] = parts[3]
        if len(parts) >= 5:
            rec["group"] = parts[4]
        rows.append(rec)
    return pd.DataFrame(rows)


def _parse_sampleinfo(path: Path) -> pd.DataFrame:
    df = _read_table_guess(path)
    if df.empty:
        return df
    cols = [c.lower() for c in df.columns]
    # no-header 4-col: run_id, sample_id, fq1, fq2
    if df.shape[1] >= 2:
        rename = {}
        first = df.columns[0]
        second = df.columns[1]
        if first.lower() not in {"run_id", "id", "sample_id"}:
            rename[first] = "run_id"
            rename[second] = "sample_id"
            if df.shape[1] >= 3:
                rename[df.columns[2]] = "fq1"
            if df.shape[1] >= 4:
                rename[df.columns[3]] = "fq2"
            df = df.rename(columns=rename)
        else:
            mapping = {}
            for c in df.columns:
                cl = c.lower()
                if cl in {"run_id", "run"}:
                    mapping[c] = "run_id"
                elif cl in {"sample_id", "sample", "sn"}:
                    mapping[c] = "sample_id"
            df = df.rename(columns=mapping)
    if "sample_id" in df.columns:
        df["sample_id"] = df["sample_id"].map(_normalize_sid)
    return df


def usable_group_cols(df: pd.DataFrame) -> tuple[list[str], list[str]]:
    notes = []
    used = []
    for col in GROUP_CANDIDATES:
        if col not in df.columns:
            continue
        s = df[col].map(lambda x: None if _is_missing(x) else str(x).strip())
        vc = s.dropna().value_counts()
        if vc.empty:
            notes.append(f"{col}: all missing → skip")
            continue
        if vc.shape[0] < 2:
            notes.append(f"{col}: only one level ({vc.index[0]}) → overall analysis only for this factor")
            continue
        n_ok = int((vc >= 2).sum())
        if n_ok < 2:
            notes.append(f"{col}: fewer than two levels with n≥2 → skip group test")
            continue
        used.append(col)
        small = vc[vc < 3]
        extra = f"; levels with n<3: {', '.join(f'{k}={v}' for k,v in small.items())}" if not small.empty else ""
        notes.append(f"{col}: {vc.shape[0]} levels, usable for overall + grouped comparison{extra}")
    if not used:
        notes.append("No usable grouping factor → overall analysis only.")
    return used, notes


def load_cohort(run_dir: Path) -> Cohort:
    sources: dict[str, str] = {}
    gpath = _search_meta(run_dir, ("groupinfo.txt", "groupinfo.tsv", "groups.tsv"))
    spath = _search_meta(run_dir, ("sampleinfo.txt", "sampleinfo.tsv", "samples.tsv"))
    groups = _parse_groupinfo(gpath) if gpath else pd.DataFrame()
    runs = _parse_sampleinfo(spath) if spath else pd.DataFrame()
    if gpath:
        sources["groupinfo"] = str(gpath)
    if spath:
        sources["sampleinfo"] = str(spath)

    if groups.empty and not runs.empty and "sample_id" in runs.columns:
        samples = (
            runs.dropna(subset=["sample_id"])
            .drop_duplicates("sample_id")[["sample_id"]]
            .copy()
        )
    elif not groups.empty:
        samples = groups.drop_duplicates("sample_id").copy()
    else:
        samples = pd.DataFrame(columns=["sample_id"])

    if not runs.empty and "sample_id" in runs.columns:
        nrun = runs.dropna(subset=["sample_id"]).groupby("sample_id").size().rename("n_runs")
        samples = samples.merge(nrun, on="sample_id", how="left")

    group_cols, notes = usable_group_cols(samples)
    return Cohort(
        samples=samples.reset_index(drop=True),
        runs=runs,
        group_cols=group_cols,
        grouping_notes=notes,
        source_files=sources,
    )


def discover(run_dir: Path, batch_id: Optional[str] = None) -> Discovery:
    run_dir = Path(run_dir).resolve()
    bid = batch_id or run_dir.name
    wfs = detect_workflows(run_dir, include_optional=False)
    cohort = load_cohort(run_dir)
    notes = []
    if cohort.samples.empty:
        notes.append("No sample metadata parsed; sample IDs will come from extracted tables.")
    return Discovery(run_dir=run_dir, batch_id=bid, workflows=wfs, cohort=cohort, extra_notes=notes)
