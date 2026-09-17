#!/usr/bin/env python3
"""Rebuild FULL_PIPELINE_ANALYSIS_SYSTEM.md/.html from spec + package sources."""
from __future__ import annotations

from pathlib import Path
import markdown

ROOT = Path(__file__).resolve().parents[1]
SPEC = Path("/tmp/full_pipeline_spec.md")
# keep a copy next to this script
LOCAL_SPEC = Path(__file__).with_name("SPEC.md")


def main() -> None:
    spec_path = LOCAL_SPEC if LOCAL_SPEC.is_file() else SPEC
    spec = spec_path.read_text(encoding="utf-8")
    files = [
        ROOT / "package/requirements.txt",
        ROOT / "package/run_full_pipeline_analysis.py",
        ROOT / "package/xvir_full/__init__.py",
        ROOT / "package/xvir_full/config.py",
        ROOT / "package/xvir_full/discover.py",
        ROOT / "package/xvir_full/extract.py",
        ROOT / "package/xvir_full/tables.py",
        ROOT / "package/xvir_full/stats.py",
        ROOT / "package/xvir_full/plots_r.py",
        ROOT / "package/xvir_full/narrative.py",
        ROOT / "package/xvir_full/biology.py",
        ROOT / "package/xvir_full/display.py",
        ROOT / "package/xvir_full/report.py",
        ROOT / "package/r/00_sci_theme.R",
        ROOT / "package/r/make_figures.R",
    ]
    parts = [spec, "\n"]
    for f in files:
        rel = f.relative_to(ROOT)
        lang = "python" if f.suffix == ".py" else ("r" if f.suffix == ".R" else "text")
        parts.append(f"\n### `{rel}`\n\n```{lang}\n{f.read_text()}")
        if not parts[-1].endswith("\n"):
            parts.append("\n")
        parts.append("```\n")
    md_text = "".join(parts)
    md_path = ROOT / "FULL_PIPELINE_ANALYSIS_SYSTEM.md"
    md_path.write_text(md_text, encoding="utf-8")
    body = markdown.markdown(md_text, extensions=["tables", "fenced_code", "toc"])
    html = (
        "<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'/>"
        "<title>XvirBench 全流程分析体系</title></head><body>"
        + body
        + "</body></html>"
    )
    (ROOT / "FULL_PIPELINE_ANALYSIS_SYSTEM.html").write_text(html, encoding="utf-8")
    print("wrote", md_path)


if __name__ == "__main__":
    main()
