#!/usr/bin/env python3
"""Snapshot local virus_taxonomy + RVA coverage into a versioned knowledge pack."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_FAMILIES = ["Flaviviridae", "Coronaviridae", "Adenoviridae"]
KB = Path("/data/user/wangdaxi/Projects/virus_taxonomy/data/kb/kb.jsonl")
SPLIT = Path(
    "/data/user/wangdaxi/rna_virus_annotation/data/benchmarks/vertebrate_rna/intrafamily_split.json"
)
OUT_ROOT = Path("/data/user/guojindan/Projects/XvirMind/knowledge/releases")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def extract_kb(families: list[str], dest: Path) -> dict:
    wanted = {name.lower() for name in families}
    records = []
    with KB.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            rec = json.loads(line)
            taxon = rec.get("taxon") or {}
            family = str(taxon.get("family") or "")
            name = str(taxon.get("name") or "")
            if family.lower() in wanted or name.lower() in wanted:
                records.append(rec)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("w", encoding="utf-8") as out:
        for rec in records:
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return {"records": len(records), "families": families, "source": str(KB)}


def rva_families(query: list[str]) -> dict:
    if not SPLIT.exists():
        return {"families": [], "source": str(SPLIT), "exists": False}
    data = json.loads(SPLIT.read_text(encoding="utf-8"))
    names = sorted(data.keys()) if isinstance(data, dict) else []
    matched = [name for name in names if any(q.lower() in name.lower() for q in query)]
    return {
        "family_count": len(names),
        "matched": matched,
        "source": str(SPLIT),
        "exists": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default=None)
    parser.add_argument("--families", nargs="*", default=DEFAULT_FAMILIES)
    args = parser.parse_args()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    version = args.version or f"{stamp}-demo"
    dest = OUT_ROOT / version
    dest.mkdir(parents=True, exist_ok=True)
    kb_out = dest / "kb.jsonl"
    kb_meta = extract_kb(args.families, kb_out)
    rva = rva_families(args.families)
    (dest / "rva_families.json").write_text(json.dumps(rva, ensure_ascii=False, indent=2), encoding="utf-8")
    readme = dest / "README.md"
    readme.write_text(
        f"# knowledge pack {version}\n\n"
        f"- taxonomy subset from `{KB}`\n"
        f"- RVA family coverage from `{SPLIT}`\n"
        "This pack is a cited snapshot, not a rewrite of wangdaxi source trees.\n",
        encoding="utf-8",
    )
    manifest = {
        "pack_id": version,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "published",
        "pipeline": ["harvest", "validate-jsonl", "subset-families", "hash", "publish"],
        "sources": {
            "virus_taxonomy_kb": {"path": str(KB), "sha256": sha256(KB) if KB.exists() else None},
            "rva_split": {"path": str(SPLIT), "exists": SPLIT.exists()},
        },
        "artifacts": {
            "kb.jsonl": {"path": str(kb_out), "sha256": sha256(kb_out), "records": kb_meta["records"]},
            "rva_families.json": {"path": str(dest / "rva_families.json"), "sha256": sha256(dest / "rva_families.json")},
        },
        "families": args.families,
        "rva": rva,
        "citation": {
            "corpus": "ictv",
            "knowledge_release": f"knowledge/releases/{version}/kb.jsonl",
            "locator": "taxon.family",
        },
    }
    (dest / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    latest = OUT_ROOT / "latest"
    if latest.exists() or latest.is_symlink():
        latest.unlink()
    latest.symlink_to(dest)
    print(json.dumps({"pack": str(dest), "records": kb_meta["records"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
