#!/usr/bin/env python3
"""Build the knowledge-pack demo: subset KB, fixture candidates, sample report, seed ops."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path("/data/user/guojindan/Projects/XvirMind")
sys.path.insert(0, str(ROOT / "xvirmind"))

from xvirmind.ops.rva import job_status
from xvirmind.ops.service import OpsService
from xvirmind.ops.specialist_report import render_specialist_html


def main() -> None:
    subprocess.check_call(
        [sys.executable, str(ROOT / "xvirmind/scripts/publish_knowledge_pack.py"), "--version", "20260911-demo"],
    )
    ops = OpsService(ROOT / "xvirmind/runs/ops", ROOT / "testdata", ROOT / "knowledge")
    # seed queue with W1-W6 + RVA estimates
    existing = {job["kind"] for job in ops.list_jobs()}
    for kind, prio in (
        ("workflow1", "high"),
        ("workflow2", "standard"),
        ("workflow3", "standard"),
        ("workflow4", "standard"),
        ("workflow6", "low"),
        ("rva", "high"),
    ):
        if kind not in existing:
            job = ops.enqueue("guojindan", "proj-testdata", kind, prio, {"testdata": "reads/single"})
            if kind == "workflow1":
                ops.set_job_status(job["id"], "paused", checkpoint="megahit", extra={"note": "受控恢复点：组装后"})
            if kind == "rva":
                ops.set_job_status(job["id"], "running", checkpoint="rva_annotate")

    candidates = [
        {
            "id": "KP641127",
            "family": "Flaviviridae",
            "rva_family": "Flaviviridae",
            "taxonomy": {
                "locator": "virus_taxonomy/data/kb/kb.jsonl#Flaviviridae",
                "name": "Flaviviridae",
            },
            "evidence": [{"type": "kb", "locator": "taxon.family=Flaviviridae"}],
            "rva_status": "running",
        },
        {
            "id": "conflict-demo",
            "family": "Coronaviridae",
            "rva_family": "Flaviviridae",
            "taxonomy": {},
            "evidence": [],
            "rva_status": "NOT_RUN",
        },
    ]
    rules = ops.evaluate_candidates(candidates)
    rva = job_status(ROOT / "xvirmind/runs/rva/kp641127")
    packs = ops.list_packs()
    pack = packs[-1] if packs else {}
    taxonomy = {
        "status": "ok",
        "family": "Flaviviridae",
        "name": "Flaviviridae",
        "mode": "kb-query",
        "knowledge_release": pack.get("citation", {}).get("knowledge_release")
        or "virus_taxonomy/data/kb/kb.jsonl",
    }
    citations = [
        {
            "corpus": "ictv",
            "knowledge_release": taxonomy["knowledge_release"],
            "locator": "taxon.family=Flaviviridae",
            "name": "Flaviviridae demarcation rules",
            "content": "本地 kb.jsonl 科级规则；未跑 classify_sequence 时不定种到种。",
        }
    ]
    review = ops.submit_review(
        "wangdaxi",
        "proj-testdata",
        "demo-kp641127",
        "reject",
        "冲突候选未消解，打回补齐 locator 后再审。",
        rules.get("findings"),
    )
    specialist = {
        "taxonomy": taxonomy,
        "rva": {
            "status": rva.get("status"),
            "family": "Flaviviridae",
            "n_features": (rva.get("summary") or {}).get("n_features"),
            "output": rva.get("output"),
            "gpu": rva.get("gpu"),
        },
        "citations": citations,
        "rules": rules,
        "review": review,
        "candidates": candidates,
    }
    spec_path = ROOT / "xvirmind/runs/ops/specialist.json"
    spec_path.write_text(json.dumps(specialist, ensure_ascii=False, indent=2), encoding="utf-8")
    html = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8"/><title>交付报告预览 · 定种/RVA/引用</title>
<style>body{font:15px/1.6 sans-serif;max-width:900px;margin:32px auto;padding:0 16px;color:#243} table{border-collapse:collapse;width:100%;margin:8px 0 18px} th,td{border:1px solid #dce5ec;padding:6px 8px;text-align:left} th{background:#ecf3f4}</style>
</head><body>
<h1>分析交付报告预览（demo）</h1>
<p>测试包 testdata/reads/single 与 contig KP641127。W1–W4+W6 进入优先级队列；RVA 使用 rnavirus 实跑。</p>
""" + render_specialist_html(
        taxonomy=taxonomy, rva=specialist["rva"], citations=citations, rules=rules, review=review
    ) + "</body></html>"
    report = ROOT / "knowledge/demo/delivery_report_preview.html"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(html, encoding="utf-8")
    (ROOT / "knowledge/demo/candidates.json").write_text(json.dumps(candidates, ensure_ascii=False, indent=2), encoding="utf-8")
    (ROOT / "knowledge/demo/rules.json").write_text(json.dumps(rules, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"specialist": str(spec_path), "report": str(report), "rules": rules["completeness"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
