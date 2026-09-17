#!/usr/bin/env python3
"""合并 XvirBench 批次 W3 宿主鉴定结果，生成总报告（Markdown + Excel）。"""

from __future__ import annotations

import argparse
import re
from datetime import datetime
from pathlib import Path

import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
XVIRBENCH_ROOT = Path(
    __import__("os").environ.get("XVIRBENCH_ROOT", SCRIPT_DIR.parent)
)
BATCH_ID = __import__("os").environ.get("BATCH_ID", "vazyme_fragment_test")
BATCH_DIR = XVIRBENCH_ROOT / "batches" / BATCH_ID
COHORT_DIR = BATCH_DIR / "cohorts"
DEFAULT_RUN_DIR = BATCH_DIR / "workflow_results"
SAMPLEINFO = COHORT_DIR / "sampleinfo.tsv"
GROUPINFO = COHORT_DIR / "groupinfo_rep11.txt"


def load_sampleinfo(path: Path) -> pd.DataFrame:
    rows = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        p = line.split()
        if len(p) >= 4:
            rows.append(
                {
                    "run_id": p[0],
                    "sample_id": p[1],
                    "fq1": p[2],
                    "fq2": p[3],
                    "lane": re.search(r"/L(\d+)/", p[2]).group(1) if "/L" in p[2] else "",
                }
            )
    return pd.DataFrame(rows)


def load_allsampleinfo(path: Path) -> pd.DataFrame:
    rows = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        p = line.split()
        if len(p) >= 3:
            rows.append(
                {
                    "sample_id": p[0],
                    "fq1": p[1],
                    "fq2": p[2],
                }
            )
    return pd.DataFrame(rows)


def load_groupinfo(path: Path) -> pd.DataFrame:
    rows = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        p = line.split("\t")
        if len(p) >= 4:
            rows.append(
                {
                    "sample_num": p[0].strip(),
                    "library_id": p[1].strip(),
                    "host": p[2].strip(),
                    "library_method": p[3].strip(),
                }
            )
    return pd.DataFrame(rows)


def sample_num_from_id(sample_id: str) -> str:
    m = re.match(r"^v(\d+)$", sample_id)
    return m.group(1) if m else ""


def load_final_results(w3_dir: Path) -> pd.DataFrame:
    path = w3_dir / "final_results.xlsx"
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_excel(path, sheet_name=0)
    if "sn" not in df.columns:
        return df
    return df.drop_duplicates(subset=["sn"], keep="first").copy()


def marker_stats_from_depths(depths_path: Path) -> pd.DataFrame:
    if not depths_path.exists():
        return pd.DataFrame()
    cols = "sn rname startpos endpos numreads covbases coverage meandepth meanbaseq meanmapq".split()
    df = pd.read_table(depths_path, header=None, names=cols)
    df["sn"] = df["sn"].astype(str).str.split(":").str[-1]

    def marker_of(rname: str) -> str:
        for m in ("CYTB", "COI", "ND1"):
            if m in rname:
                return m
        return "other"

    df["marker"] = df["rname"].map(marker_of)
    agg = (
        df.groupby(["sn", "marker"])
        .agg(
            n_targets=("rname", "nunique"),
            max_coverage=("coverage", "max"),
            sum_numreads=("numreads", "sum"),
        )
        .reset_index()
    )
    wide = agg.pivot_table(
        index="sn",
        columns="marker",
        values=["n_targets", "max_coverage", "sum_numreads"],
        aggfunc="first",
    )
    wide.columns = [f"{a}_{b}" for a, b in wide.columns]
    return wide.reset_index()


def load_blast_top(w3_dir: Path, sample_ids: list[str], top_n: int = 3) -> pd.DataFrame:
    rows = []
    blast_dir = w3_dir / "EukaMarker_megablast" / "2.result_filtered"
    for sn in sample_ids:
        p = blast_dir / f"{sn}.blastn"
        if not p.exists():
            continue
        df = pd.read_table(
            p,
            header=None,
            names="sn query rname pident length mismatch gapopen qstart qend sstart send evalue bitscore".split(),
        )
        df["sn"] = df["sn"].astype(str).str.split(":").str[-1]
        best = df.sort_values("bitscore", ascending=False).head(top_n)
        for rank, (_, r) in enumerate(best.iterrows(), 1):
            rows.append(
                {
                    "sample_id": sn,
                    "blast_rank": rank,
                    "rname": r["rname"],
                    "pident": r["pident"],
                    "length": r["length"],
                    "bitscore": r["bitscore"],
                }
            )
    return pd.DataFrame(rows)


def build_report(
    run_dir: Path,
    out_dir: Path | None = None,
    *,
    allsampleinfo: Path | None = None,
    skip_samples: list[str] | None = None,
) -> tuple[Path, Path]:
    run_dir = run_dir.resolve()
    w3_dir = run_dir / "workflow3_hostid"
    out_dir = (out_dir or run_dir / "reports").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    batch_id = run_dir.name
    skip_set = set(skip_samples or [])
    if allsampleinfo and allsampleinfo.exists():
        manifest = load_allsampleinfo(allsampleinfo)
        manifest["run_id"] = manifest["sample_id"]
        sample_list_path = allsampleinfo
    else:
        manifest = load_sampleinfo(SAMPLEINFO)
        sample_list_path = SAMPLEINFO

    groups = load_groupinfo(GROUPINFO) if GROUPINFO.exists() else pd.DataFrame()
    final_df = load_final_results(w3_dir)
    depth_stats = marker_stats_from_depths(w3_dir / "depths.txt")

    sample_ids = sorted(manifest["sample_id"].unique())
    w3_status = []
    for sid in sample_ids:
        cov = w3_dir / "EukaMarker_Mapping" / "2.filteredcoverage_q0" / f"{sid}_coverage.txt"
        blast = w3_dir / "EukaMarker_megablast" / "2.result_filtered" / f"{sid}.blastn"
        final_ok = (
            not final_df.empty
            and sid in final_df.get("sn", pd.Series(dtype=str)).astype(str).values
        )
        w3_status.append(
            {
                "sample_id": sid,
                "w3_coverage_ok": cov.is_file() and cov.stat().st_size > 0,
                "w3_blast_ok": blast.is_file() and blast.stat().st_size > 0,
                "w3_in_final_results": final_ok,
                "w3_skip_rerun": sid in skip_set,
            }
        )
    status_df = pd.DataFrame(w3_status)

    if "lane" in manifest.columns:
        summary = (
            manifest.groupby("sample_id")
            .agg(n_runs=("run_id", "count"), lanes=("lane", lambda x: ",".join(sorted(set(x.astype(str))))))
            .reset_index()
        )
    else:
        summary = manifest[["sample_id"]].drop_duplicates().copy()
        summary["n_runs"] = 1
        summary["lanes"] = ""
    summary["sample_num"] = summary["sample_id"].map(sample_num_from_id)
    if not groups.empty:
        summary = summary.merge(groups, on="sample_num", how="left")
    summary = summary.merge(status_df, on="sample_id", how="left", suffixes=("", "_st"))
    if not final_df.empty:
        keep_cols = [
            c
            for c in [
                "sn",
                "inferred_mt_species",
                "inferred_mt_species_chinese",
                "inferred_mt_genus",
                "species_level_marker_count",
                "annotated_species_count",
                "known_species",
                "COI_species",
                "COI_pident",
                "CYTB_species",
                "CYTB_pident",
                "ND1_species",
                "ND1_pident",
                "notbest_genus",
                "notbest_genuslist",
            ]
            if c in final_df.columns
        ]
        summary = summary.merge(
            final_df[keep_cols].rename(columns={"sn": "sample_id"}),
            on="sample_id",
            how="left",
        )
    if not depth_stats.empty:
        summary = summary.merge(depth_stats, left_on="sample_id", right_on="sn", how="left")
        if "sn" in summary.columns:
            summary = summary.drop(columns=["sn"])

    blast_top = load_blast_top(w3_dir, sample_ids)
    run_meta = pd.DataFrame(
        [
            {
                "batch_id": batch_id,
                "generated_at": datetime.now().isoformat(timespec="seconds"),
                "sampleinfo": str(sample_list_path),
                "w3_outdir": str(w3_dir),
                "n_samples_total": len(sample_ids),
                "n_samples_skip_rerun": len(skip_set),
                "n_samples_w3_complete": int(status_df["w3_in_final_results"].sum()),
            }
        ]
    )

    n_done = int(status_df["w3_coverage_ok"].sum())
    n_final = int(status_df["w3_in_final_results"].sum())
    pending = status_df.loc[~status_df["w3_coverage_ok"], "sample_id"].tolist()

    md_lines = [
        f"# 宿主鉴定总报告 — {batch_id}",
        "",
        f"- 生成时间: {run_meta.iloc[0]['generated_at']}",
        f"- 样本表: `{sample_list_path}`",
        f"- W3 输出: `{w3_dir}`",
        f"- 跳过重跑（pxy 已完成）: {', '.join(sorted(skip_set)) if skip_set else '无'}",
        "",
        "## 1. 运行覆盖",
        "",
        f"| 指标 | 数值 |",
        f"|------|------|",
        f"| 总样本数 | {len(sample_ids)} |",
        f"| 已完成 coverage+blast | {n_done} |",
        f"| 已写入 final_results | {n_final} |",
        f"| 待补跑 | {', '.join(pending) if pending else '无'} |",
        "",
        "## 2. 按样本宿主推断（合并历史 + 最新 final_results）",
        "",
    ]
    show_cols = [
        "sample_id",
        "w3_skip_rerun",
        "library_method",
        "host",
        "inferred_mt_species",
        "inferred_mt_species_chinese",
        "known_species",
        "species_level_marker_count",
        "COI_pident",
        "CYTB_pident",
        "ND1_pident",
    ]
    show_cols = [c for c in show_cols if c in summary.columns]
    if show_cols:
        md_lines.append(summary[show_cols].to_markdown(index=False))
    else:
        md_lines.append("_无 final_results 数据_")

    md_lines.extend(
        [
            "",
            "## 3. 方法组汇总",
            "",
        ]
    )
    if "library_method" in summary.columns and "inferred_mt_species" in summary.columns:
        g = (
            summary.groupby("library_method")["inferred_mt_species"]
            .agg(lambda x: x.dropna().astype(str).nunique())
            .reset_index(name="n_distinct_species")
        )
        md_lines.append(g.to_markdown(index=False))
    md_lines.extend(
        [
            "",
            "## 4. 说明",
            "",
            "- 宿主鉴定基于 EukaMarker（CYTB / COI / ND1），汇总脚本见 `result_summarize.py`。",
            "- `depths.txt` / `blastresult.full.txt` 为 H4 整合结果；`final_results.xlsx` 为 H5 投票汇总。",
            "- 若某样本仅缺 sorted BAM 但 coverage/blast 齐全，可视为 W3 已完成，无需重跑 H1–H3。",
            "",
        ]
    )

    md_path = out_dir / f"{batch_id}_宿主鉴定总报告_全样本.md"
    xlsx_path = out_dir / f"{batch_id}_宿主鉴定总报告_全样本.xlsx"
    md_path.write_text("\n".join(md_lines), encoding="utf-8")

    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        run_meta.to_excel(writer, sheet_name="meta", index=False)
        status_df.to_excel(writer, sheet_name="W3_运行状态", index=False)
        summary.to_excel(writer, sheet_name="样本汇总", index=False)
        if not final_df.empty:
            final_df.to_excel(writer, sheet_name="final_results", index=False)
        if not blast_top.empty:
            blast_top.to_excel(writer, sheet_name="blast_top3", index=False)
        manifest.to_excel(writer, sheet_name="sampleinfo_runs", index=False)

    return md_path, xlsx_path


def main():
    ap = argparse.ArgumentParser(description="生成 W3 宿主鉴定总报告")
    ap.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument("--allsampleinfo", type=Path, default=SCRIPT_DIR / "allsampleinfo.txt")
    ap.add_argument("--skip-samples", nargs="*", default=[])
    args = ap.parse_args()
    ai = args.allsampleinfo if args.allsampleinfo.exists() else None
    md, xlsx = build_report(
        args.run_dir,
        args.out_dir,
        allsampleinfo=ai,
        skip_samples=args.skip_samples,
    )
    print(f"Markdown: {md}")
    print(f"Excel:    {xlsx}")


if __name__ == "__main__":
    main()
