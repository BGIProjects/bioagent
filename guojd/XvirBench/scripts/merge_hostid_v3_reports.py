#!/usr/bin/env python3
"""合并 by_sample_v3 下各样本 HostIdentification_result.xlsx 为总表。"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

import pandas as pd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--by-sample-dir", type=Path, required=True)
    ap.add_argument("--output-dir", type=Path, required=True)
    args = ap.parse_args()

    manifest = pd.read_csv(args.manifest, sep="\t")
    rows = []
    status = []
    for _, m in manifest.iterrows():
        sn = m["sn"]
        xlsx = args.by_sample_dir / sn / "HostIdentification_result.xlsx"
        ok = xlsx.is_file()
        status.append(
            {
                "sn": sn,
                "host_type": m.get("host_type", ""),
                "phylum": m.get("phylum", ""),
                "taxfilter": m.get("taxfilter", ""),
                "has_v3_result": ok,
                "result_path": str(xlsx) if ok else "",
            }
        )
        if ok:
            df = pd.read_excel(xlsx)
            df["sn"] = sn
            df["host_type_manifest"] = m.get("host_type", "")
            df["taxfilter_used"] = m.get("taxfilter", "")
            rows.append(df)

    out_dir = args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    combined = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    status_df = pd.DataFrame(status)

    xlsx_path = out_dir / f"pxy_V350399508_宿主鉴定V3_全样本合并_{stamp}.xlsx"
    md_path = out_dir / f"pxy_V350399508_宿主鉴定V3_全样本合并_{stamp}.md"

    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as w:
        status_df.to_excel(w, sheet_name="运行状态", index=False)
        manifest.to_excel(w, sheet_name="样本门信息", index=False)
        if not combined.empty:
            combined.to_excel(w, sheet_name="合并结果", index=False)

    lines = [
        "# 宿主鉴定 V3 全样本合并报告",
        "",
        f"- 生成时间: {datetime.now().isoformat(timespec='seconds')}",
        f"- 完成样本: {status_df['has_v3_result'].sum()} / {len(status_df)}",
        f"- 每样本目录: `{args.by_sample_dir}/<sn>/`",
        "",
        "## 门信息统计",
        "",
        status_df.groupby(["host_type", "phylum"]).size().reset_index(name="n").to_markdown(index=False),
        "",
    ]
    if not combined.empty and "inferred_species" in combined.columns:
        lines.append("## 物种推断分布（合并）")
        lines.append("")
        lines.append(
            combined.groupby(["host_type_manifest", "inferred_species"])
            .size()
            .reset_index(name="n")
            .to_markdown(index=False)
        )
    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Excel: {xlsx_path}")
    print(f"Markdown: {md_path}")


if __name__ == "__main__":
    main()
