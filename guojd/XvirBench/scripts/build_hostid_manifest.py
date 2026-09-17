#!/usr/bin/env python3
"""从 allsampleinfo.txt + qcinfo 生成宿主鉴定样本表（含宿主类型与门过滤）。"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
XVIRBENCH_ROOT = Path(
    __import__("os").environ.get("XVIRBENCH_ROOT", SCRIPT_DIR.parent)
)
BATCH_ID = __import__("os").environ.get("BATCH_ID", "vazyme_fragment_test")
BATCH_DIR = XVIRBENCH_ROOT / "batches" / BATCH_ID
COHORT_DIR = BATCH_DIR / "cohorts"
ALLSAMPLEINFO = Path(
    "/data/user/guojindan/Projects/Workflows/benchmark/test/allsampleinfo.txt"
)
QCINFO = Path("/data/user/guojindan/Projects/vazyme/fragmentation_test/qcinfo.txt")
RUN_DIR = BATCH_DIR / "workflow_results"
ASM_BASE = RUN_DIR / "workflow1_upstream" / "assembly"

HOST_TAXFILTER = {
    "rat": ("mouse", "p=Chordata"),
    "mouse": ("mouse", "p=Chordata"),
    "tick": ("tick", "p=Arthropoda"),
    "mosquito": ("mosquito", "p=Arthropoda"),
}

PXY_SAMPLES = {"v61", "v64", "v67", "v70", "v73", "v76", "v78", "v79", "v82", "v85", "v88"}


def resolve_assembly(sn: str) -> str:
    for name in (f"{sn}.contigs.1kb.renamed.fa", f"{sn}.contigs.fa"):
        p = ASM_BASE / sn / name
        if p.is_file() and p.stat().st_size > 0:
            return str(p)
    return ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--output", type=Path, default=COHORT_DIR / "hostid_sample_manifest.tsv")
    args = ap.parse_args()

    rows = []
    for line in ALLSAMPLEINFO.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        p = line.split()
        if len(p) < 3:
            continue
        rows.append({"sn": p[0], "fq1": p[1], "fq2": p[2]})
    df = pd.DataFrame(rows).drop_duplicates("sn")

    qc = pd.read_csv(QCINFO, sep="\t")
    qc["sn"] = "v" + qc["id"].astype(str)
    host_df = qc[["sn", "host"]].drop_duplicates("sn")
    df = df.merge(host_df, on="sn", how="left")
    df["host"] = df["host"].fillna("rat")

    df["host_type"] = df["host"].map(lambda h: HOST_TAXFILTER.get(h, ("unknown", "p=Chordata"))[0])
    df["taxfilter"] = df["host"].map(lambda h: HOST_TAXFILTER.get(h, ("unknown", "p=Chordata"))[1])
    df["phylum"] = df["taxfilter"].str.replace("p=", "", regex=False)

    w1 = RUN_DIR / "workflow1_upstream"
    assemblies = []
    for _, r in df.iterrows():
        sn = r["sn"]
        if sn in PXY_SAMPLES:
            fq1 = w1 / "merge" / sn / "cleanreads_r1.fq"
            fq2 = w1 / "merge" / sn / "cleanreads_r2.fq"
            asm = w1 / "assembly" / sn / f"{sn}.contigs.1kb.renamed.fa"
            if fq1.is_file():
                df.loc[df["sn"] == sn, "fq1"] = str(fq1)
                df.loc[df["sn"] == sn, "fq2"] = str(fq2)
            if asm.is_file():
                assemblies.append(str(asm))
            else:
                assemblies.append(resolve_assembly(sn))
        else:
            assemblies.append(resolve_assembly(sn))
    df["assembly"] = assemblies

    missing_asm = df[df["assembly"] == ""]["sn"].tolist()
    if missing_asm:
        raise SystemExit(f"缺少 assembly: {missing_asm[:10]}{'...' if len(missing_asm)>10 else ''}")

    out_cols = ["sn", "fq1", "fq2", "assembly", "host", "host_type", "phylum", "taxfilter"]
    df[out_cols].to_csv(args.output, sep="\t", index=False)
    print(f"Wrote {len(df)} samples -> {args.output}")
    print(df.groupby(["host_type", "taxfilter"]).size().to_string())


if __name__ == "__main__":
    main()
