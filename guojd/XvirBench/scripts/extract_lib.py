"""XvirBench 批次指标抽取库（供 extract_metrics.py 调用）。"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import pandas as pd
import yaml

XVIRBENCH_ROOT = Path(os.environ.get("XVIRBENCH_ROOT", Path(__file__).resolve().parent.parent))
WORKFLOWS_ROOT = Path(os.environ.get("WORKFLOWS_ROOT", "/data/user/guojindan/Projects/Workflows"))

WORKFLOW_ALIASES = {"workflow7": "workflow7_fragmentation_benchmark"}

WF_SHORT = {
    "workflow1_upstream": "workflow1",
    "workflow2_virusid": "workflow2",
    "workflow3_hostid": "workflow3",
    "workflow4_kraken_bracken": "workflow4",
    "workflow5_virus_quantification": "workflow5",
    "workflow6_virus_annotation": "workflow6",
    "workflow7_fragmentation_benchmark": "workflow7",
}

SHORT_TO_WF = {v: k for k, v in WF_SHORT.items()}
CLI_TO_WF = {
    **SHORT_TO_WF,
    **{k: k for k in WF_SHORT},
    "w1": "workflow1_upstream", "w2": "workflow2_virusid", "w3": "workflow3_hostid",
    "w4": "workflow4_kraken_bracken", "w5": "workflow5_virus_quantification",
    "w6": "workflow6_virus_annotation", "w7": "workflow7_fragmentation_benchmark",
}

WORKFLOW_EXTRACTORS = {
    "workflow1_upstream": ("workflow1_upstream/scripts/extract_results.py", {
        "qc_upstream_run": "run_qc",
        "qc_upstream_sample": "samples",
        "qc_upstream_summary": "summary",
    }),
    "workflow2_virusid": ("workflow2_virusid/scripts/extract_results.py", {
        "virus_identification_contigs": "contigs",
        "virus_identification_clusters": "cluster_summary",
        "virus_identification_sample": "sample_cluster",
    }),
    "workflow3_hostid": ("workflow3_hostid/scripts/extract_results.py", {
        "host_identification_contig": "host_contig",
        "host_identification_sample": "host_sample",
    }),
    "workflow4_kraken_bracken": ("workflow4_kraken_bracken/scripts/extract_results.py", {
        "microbiome_bracken_sample": "sample_qc",
        "microbiome_bracken_top15": "bracken_top15_species",
    }),
    "workflow5_virus_quantification": ("workflow5_virus_quantification/scripts/extract_results.py", {
        "virus_quantification_rpm": "rpm_full",
        "virus_quantification_sample": "sample_summary",
    }),
    "workflow6_virus_annotation": ("workflow6_virus_annotation/scripts/extract_results.py", {
        "virus_annotation_summary": "annotation_summary",
        "virus_annotation_checkv": "checkv",
    }),
    "workflow7_fragmentation_benchmark": ("workflow7_fragmentation_benchmark/scripts/extract_results.py", {
        "fragmentation_benchmark": "comparison",
        "fragmentation_method_summary": "method_summary",
    }),
}


def resolve_cli_workflow(name: str) -> str:
    key = name.strip().lower()
    if key in CLI_TO_WF:
        return CLI_TO_WF[key]
    raise ValueError(f"未知 workflow: {name}（可用 workflow1–7 或 all）")


def load_manifest(batch_id: str) -> Optional[Dict[str, Any]]:
    for path in (
        XVIRBENCH_ROOT / "batches" / batch_id / "manifest.yaml",
        XVIRBENCH_ROOT / "batches" / f"{batch_id}.yaml",
    ):
        if path.is_file():
            with path.open() as f:
                return yaml.safe_load(f)
    return None


def normalize_sample_id(value: Any) -> Any:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return value
    s = str(value).strip()
    if re.fullmatch(r"\d+", s):
        return f"v{s}"
    if re.fullmatch(r"v\d+", s):
        return s
    m = re.match(r"^(v\d+)", s)
    return m.group(1) if m else s


def batch_harmonized_dir(batch_id: str, wf: str) -> Path:
    return XVIRBENCH_ROOT / "batches" / batch_id / "harmonized" / WF_SHORT.get(wf, wf)


def resolve_path(base: Path, raw: str) -> Path:
    p = Path(raw)
    return p if p.is_absolute() else base / p


def resolve_batch_paths(batch_id: str, manifest: Optional[Dict[str, Any]]) -> Dict[str, Union[Path, Dict[str, Path]]]:
    batch_root = XVIRBENCH_ROOT / "batches" / batch_id
    legacy = Path(manifest["legacy_run_dir"]) if manifest and manifest.get("legacy_run_dir") else None
    base = batch_root / "workflow_results"
    if not base.is_dir():
        base = legacy if legacy and legacy.is_dir() else batch_root

    paths: Dict[str, Union[Path, Dict[str, Path]]] = {
        "workflow1_upstream": base / "workflow1_upstream",
        "workflow2_virusid": base / "workflow2_virusid",
        "workflow3_hostid": base / "workflow3_hostid",
        "workflow4_kraken_bracken": base / "workflow4_kraken_bracken",
        "workflow5_virus_quantification": base / "workflow5_virus_quantification",
        "workflow6_virus_annotation": base / "workflow6_virus_annotation",
        "workflow7_fragmentation_benchmark": base / "workflow7",
    }
    if not (base / "workflow7").is_dir():
        paths["workflow7_fragmentation_benchmark"] = base / "workflow7_fragmentation_benchmark"

    if manifest and manifest.get("workflows"):
        for wf_key, cfg in manifest["workflows"].items():
            wf = WORKFLOW_ALIASES.get(wf_key, wf_key)
            if cfg.get("outputs"):
                paths[wf] = {
                    h: resolve_path(batch_root, sub.replace("/runs/", "/workflow_results/"))
                    for h, sub in cfg["outputs"].items()
                }
            elif cfg.get("output_dir"):
                paths[wf] = resolve_path(batch_root, cfg["output_dir"].replace("/runs/", "/workflow_results/"))
    return paths


def load_allowlist(manifest: Optional[Dict[str, Any]], batch_root: Path) -> tuple[set[str], set[str]]:
    allowed: set[str] = set()
    paths: list[Path] = []
    if manifest and manifest.get("cohorts", {}).get("sampleinfo"):
        rel = manifest["cohorts"]["sampleinfo"]
        p = Path(rel)
        paths.append(p if p.is_absolute() else batch_root / rel)
    if manifest and manifest.get("sequencing", {}).get("sampleinfo_canonical"):
        paths.append(Path(manifest["sequencing"]["sampleinfo_canonical"]))
    paths.append(batch_root / "cohorts" / "sampleinfo.tsv")

    seen: set[Path] = set()
    for path in paths:
        path = path.resolve()
        if path in seen or not path.is_file():
            continue
        seen.add(path)
        with path.open() as fh:
            hdr = fh.readline().strip().split("\t")
            if "id" not in hdr:
                continue
            i = hdr.index("id")
            for line in fh:
                parts = line.strip().split("\t")
                if len(parts) > i:
                    allowed.add(f"v{parts[i].strip()}")

    run_ids: set[str] = set()
    raw = manifest.get("sequencing", {}).get("raw_sample_list") if manifest else None
    if raw and Path(raw).is_file():
        for line in Path(raw).read_text().splitlines():
            parts = line.split()
            if len(parts) >= 2 and normalize_sample_id(parts[1]) in allowed:
                run_ids.add(parts[0])
    return allowed, run_ids


def row_allowed(row: Dict[str, Any], allowed: set[str], run_ids: set[str]) -> bool:
    if not allowed:
        return True
    for col in ("sample_id", "sn", "source_sample"):
        if col in row and pd.notna(row[col]) and normalize_sample_id(row[col]) in allowed:
            return True
    if "run_id" in row and pd.notna(row["run_id"]):
        rid = str(row["run_id"])
        if rid in run_ids:
            return True
        m = re.match(r"^(\d+)_", rid)
        if m and f"v{m.group(1)}" in allowed:
            return True
    return False


def filter_payload(payload: Dict[str, Any], allowed: set[str], run_ids: set[str]) -> Dict[str, Any]:
    if not allowed:
        return payload
    tables = {k: [r for r in rows if row_allowed(r, allowed, run_ids)] for k, rows in payload.get("tables", {}).items()}
    return {**payload, "tables": tables}


def run_extractor(script: Path, result_dir: Path, sample_list: Optional[Path] = None) -> Dict[str, Any]:
    spec = importlib.util.spec_from_file_location("extract_mod", script)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载: {script}")
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(XVIRBENCH_ROOT / "scripts"))
    spec.loader.exec_module(mod)
    import inspect
    kw: Dict[str, Any] = {}
    if sample_list and sample_list.is_file() and "sample_list" in inspect.signature(mod.extract_all).parameters:
        kw["sample_list"] = sample_list
    return mod.extract_all(result_dir, **kw)


def merge_payloads(payloads: List[Dict[str, Any]], labels: List[str]) -> Dict[str, Any]:
    tables: Dict[str, List[Dict[str, Any]]] = {}
    for host, payload in zip(labels, payloads):
        for key, rows in payload.get("tables", {}).items():
            for row in rows:
                r = dict(row)
                r["host_group"] = host
                for c in ("sample_id", "sn", "source_sample"):
                    if c in r:
                        r[c] = normalize_sample_id(r[c])
                tables.setdefault(key, []).append(r)
    return {"tables": tables, "batch_summary": {}}


def table_to_df(rows: List[Dict[str, Any]], batch_id: str) -> pd.DataFrame:
    df = pd.DataFrame(rows) if rows else pd.DataFrame()
    if not df.empty:
        df.insert(0, "batch_id", batch_id)
        id_col = next((c for c in ("sample_id", "sn", "source_sample") if c in df.columns), None)
        if id_col:
            df["global_sample_id"] = df[id_col].map(
                lambda s: f"{batch_id}__{normalize_sample_id(s)}" if pd.notna(s) else None
            )
    df["extracted_at"] = datetime.now(timezone.utc).isoformat()
    return df


def write_tables(df: pd.DataFrame, harm_dir: Path, stem: str) -> int:
    if df.empty:
        return 0
    harm_dir.mkdir(parents=True, exist_ok=True)
    out = harm_dir / f"{stem}.tsv"
    try:
        df.to_parquet(out.with_suffix(".parquet"), index=False)
    except ImportError:
        df.to_csv(out, sep="\t", index=False)
    return len(df)


def w1_sample_list(batch_root: Path, run_ids: set[str]) -> Optional[Path]:
    if not run_ids:
        return None
    out = batch_root / "cohorts" / "lists" / "w1_extract_runs.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    raw = Path("/data/user/pengxinyue/Workflows/workflow1_upstream/data/samples.txt")
    lines = [ln for ln in raw.read_text().splitlines() if ln.split() and ln.split()[0] in run_ids] if raw.is_file() else []
    if not lines:
        return None
    out.write_text("\n".join(lines) + "\n")
    return out


def extract_one_workflow(
    wf: str,
    result_spec: Union[Path, Dict[str, Path]],
    batch_id: str,
    allowed: set[str],
    run_ids: set[str],
    w1_list: Optional[Path],
    write_json: bool = True,
) -> Dict[str, int]:
    rel, table_map = WORKFLOW_EXTRACTORS[wf]
    script = WORKFLOWS_ROOT / rel
    if not script.is_file():
        return {}

    if isinstance(result_spec, dict):
        payloads, labels = [], []
        for host, rd in sorted(result_spec.items()):
            if host == "pxy11" or not rd.is_dir():
                continue
            try:
                sl = w1_list if wf == "workflow1_upstream" else None
                payloads.append(run_extractor(script, rd, sl))
                labels.append(host)
            except Exception as exc:
                print(f"[WARN] {wf}/{host}: {exc}", file=sys.stderr)
        if not payloads:
            return {}
        payload = merge_payloads(payloads, labels)
    else:
        if not result_spec.is_dir():
            return {}
        sl = w1_list if wf == "workflow1_upstream" else None
        payload = run_extractor(script, result_spec, sl)
        for key, rows in payload.get("tables", {}).items():
            payload["tables"][key] = [
                {**r, **{c: normalize_sample_id(r[c]) for c in ("sample_id", "sn", "source_sample") if c in r}}
                for r in rows
            ]

    payload = filter_payload(payload, allowed, run_ids)
    harm_dir = batch_harmonized_dir(batch_id, wf)
    if write_json:
        harm_dir.mkdir(parents=True, exist_ok=True)
        (harm_dir / f"{WF_SHORT[wf]}_extracted.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str)
        )

    counts: Dict[str, int] = {}
    for stem, tkey in table_map.items():
        n = write_tables(table_to_df(payload.get("tables", {}).get(tkey, []), batch_id), harm_dir, stem)
        if n:
            counts[stem] = n
    return counts


def extract_batch(batch_id: str, workflows: Optional[List[str]] = None) -> Dict[str, int]:
    manifest = load_manifest(batch_id)
    batch_root = XVIRBENCH_ROOT / "batches" / batch_id
    paths = resolve_batch_paths(batch_id, manifest)
    allowed, run_ids = load_allowlist(manifest, batch_root)
    w1_list = w1_sample_list(batch_root, run_ids)

    targets = workflows or list(WORKFLOW_EXTRACTORS.keys())
    counts: Dict[str, int] = {}
    for wf in targets:
        spec = paths.get(wf)
        if not spec:
            continue
        for name, n in extract_one_workflow(wf, spec, batch_id, allowed, run_ids, w1_list).items():
            counts[name] = counts.get(name, 0) + n
    return counts
