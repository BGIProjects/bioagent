"""加载批次 cohort 元数据。"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

METHOD_ORDER = ["cDNA_Frag_30C5Min", "RNA_Frag_85C6Min", "RNA_Frag_94C7Min"]
METHOD_LABEL = {
    "cDNA_Frag_30C5Min": "cDNA 30°C 5min",
    "RNA_Frag_85C6Min": "RNA 85°C 6min",
    "RNA_Frag_94C7Min": "RNA 94°C 7min",
}
HOST_ORDER = ["rat", "tick", "mosquito"]
LOW_DEPTH_READS = 5_000_000


def load_sampleinfo(cohort_dir: Path) -> pd.DataFrame:
    path = cohort_dir / "sampleinfo.tsv"
    if not path.is_file():
        raise FileNotFoundError(path)
    df = pd.read_csv(path, sep="\t")
    df["sample_id"] = "v" + df["id"].astype(str)
    df["method"] = pd.Categorical(df["method"], categories=METHOD_ORDER, ordered=True)
    df["method_label"] = df["method"].map(METHOD_LABEL)
    df["host"] = pd.Categorical(df["host"], categories=HOST_ORDER, ordered=True)
    return df


def cohort_overview(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for meth in METHOD_ORDER:
        sub = df[df["method"] == meth]
        for host in HOST_ORDER:
            h = sub[sub["host"] == host]
            rows.append(
                {
                    "method": meth,
                    "method_label": METHOD_LABEL[meth],
                    "host": host,
                    "n": len(h),
                    "sample_ids": ",".join(sorted(h["sample_id"])),
                }
            )
    return pd.DataFrame(rows)
