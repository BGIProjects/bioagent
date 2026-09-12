#!/usr/bin/env python3
"""Isolated M0 replay. Writes only new m0-* directories below the chosen run root."""

from __future__ import annotations

import argparse
import asyncio
import json
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT / "agent"), str(ROOT / "open-webui/backend")]

from evidence_contract import AssetRelease, ReleaseSet
from evidence_replay import explain, safe_file, screening_candidate
from knowledge import KnowledgeStore, digest
from m0_baseline import capability_baseline
from open_webui.utils.analysis_delivery_report import (
    render_analysis_delivery_report,
)
from open_webui.utils.report_evidence import verify_report_evidence
from provider import MiniMaxProvider
from workflow_adapters import AdapterSettings

# This transport program is standard-library-only and cannot launch workflows.
# It runs on the selected filesystem, locally or via SSH, without deploying a worker.
IO_PROGRAM = r"""
import hashlib, json, os, re, sys
from pathlib import Path
request = json.loads(sys.argv[1])
root = Path(request["run_root"]).resolve(strict=True)
def checked(path):
    p = Path(path)
    if not p.is_absolute() or ".." in p.parts:
        raise ValueError("absolute path inside run root required")
    resolved = p.resolve()
    if resolved == root or root not in resolved.parents:
        raise ValueError("path outside run root")
    cursor = p
    while cursor != root and cursor != cursor.parent:
        if cursor.is_symlink(): raise ValueError("symlink forbidden")
        cursor = cursor.parent
    return resolved
def small_read(path):
    before = path.stat()
    if before.st_size > 2 * 1024 * 1024: raise ValueError("source too large")
    raw = path.read_bytes()
    after = path.stat()
    if (before.st_ino,before.st_size,before.st_mtime_ns) != (after.st_ino,after.st_size,after.st_mtime_ns):
        raise ValueError("source changed while reading")
    return raw.decode("utf-8")
action = request["action"]
prefix = request.get("output_prefix", "m0-")
if prefix not in {"m0-", "m1-"}: raise ValueError("unsupported output prefix")
if action == "freeze":
    run = checked(request["source_run"])
    state = json.loads(small_read(checked(str(run / ".bioagent/state.json"))))
    telemetry = json.loads(small_read(checked(str(run / ".bioagent/telemetry.json"))))
    sample = telemetry["delivery_report"]["screening"]["samples"]
    if len(sample) != 1: raise ValueError("one screening sample required")
    sample = sample[0]
    sid = sample["sample_id"]
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", sid): raise ValueError("invalid sample")
    files = [".bioagent/state.json", ".bioagent/telemetry.json", ".bioagent/routing.json", ".bioagent/screening.log", f"results/screening/{sid}/kraken.report", f"results/screening/{sid}/fastp.json"]
    contents = {rel: small_read(checked(str(run/rel))) for rel in files}
    manifest = {"schema_version":1,"source_run":str(run),"run_id":state["run_id"],"sample_id":sid,"taxid":sample["top_species"]["taxid"],"files":{rel:hashlib.sha256(text.encode()).hexdigest() for rel,text in contents.items()},"source_kind":"real_observation","historical_identity":"recorded run and source files; no biological ground truth"}
    inventory = {}
    for workflow, folder in request["workflows"].items():
        path = Path(folder)/"config/config.yaml"
        item = {"config_path":str(path),"status":"missing","dependencies":[],"resources":{}}
        if path.is_file():
            text = small_read(path)
            item.update(status="observed",config_sha256=hashlib.sha256(text.encode()).hexdigest())
            section = ""
            for number,line in enumerate(text.splitlines(),1):
                clean = line.split("#",1)[0].rstrip()
                if not clean.strip() or ":" not in clean: continue
                key,value = clean.strip().split(":",1)
                value = value.strip().strip("\"'")
                if not clean.startswith(" "): section = key if not value else ""
                if section in {"resource","threads"}: item["resources"][f"line:{number}"] = clean.strip()
                if section not in {"software","softwares","database"} or not value: continue
                p = Path(value)
                kind = "reference" if section == "database" else "software"
                exists = p.exists()
                prefix = not exists and p.parent.is_dir() and any(p.parent.glob(p.name + ".*"))
                item["dependencies"].append({"name":key,"kind":kind,"path":value,"locator":f"line:{number}","status":"present" if exists else "prefix_present" if prefix else "missing","executable":os.access(p,os.X_OK) if kind == "software" else None,"version":"unknown","license":"unknown","integrity":"not_checked"})
        inventory[workflow] = item
    database = Path(telemetry["delivery_report"]["screening"]["database"])
    observed = []
    if database.is_dir():
        for p in sorted(database.iterdir()):
            if p.is_file():
                st = p.stat()
                observed.append({"name":p.name,"size":st.st_size,"mtime_ns":st.st_mtime_ns})
    manifest["reference"] = {"path":str(database),"version":"unknown","license":"unknown","integrity":"not_checked","observed_files":observed}
    print(json.dumps({"manifest":manifest,"contents":contents,"inventory":inventory},ensure_ascii=False))
elif action == "read":
    print(small_read(checked(request["path"])),end="")
elif action == "check_output":
    output = checked(request["output"])
    if output.parent != root or not output.name.startswith(prefix) or output.exists():
        raise ValueError("output must be a new " + prefix + "* child of run root")
    print("ready")
elif action == "write":
    output = checked(request["output"])
    if output.parent != root or not output.name.startswith(prefix): raise ValueError("output must be a new " + prefix + "* child of run root")
    payload = sys.stdin.read(50*1024*1024 + 1)
    if len(payload.encode()) > 50*1024*1024: raise ValueError("output exceeds budget")
    files = json.loads(payload)
    if any(Path(name).name != name for name in files): raise ValueError("flat output filenames required")
    output.mkdir(exist_ok=False)
    for name,text in files.items(): (output/name).write_text(text,encoding="utf-8")
    print(json.dumps({"output":str(output),"files":list(files)}))
else:
    raise ValueError("unsupported transport action")
"""


def transport(args, request: dict, *, payload: dict | None = None) -> str:
    request["run_root"] = args.run_root
    python = args.remote_python if args.ssh_host else sys.executable
    command = [python, "-c", IO_PROGRAM, json.dumps(request)]
    if args.ssh_host:
        command = [
            "ssh",
            "-o",
            "ClearAllForwardings=yes",
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=8",
            args.ssh_host,
            shlex.join(command),
        ]
    result = subprocess.run(
        command,
        input=json.dumps(payload, ensure_ascii=False) if payload is not None else "",
        text=True,
        capture_output=True,
        timeout=90,
        check=False,
    )
    if result.returncode:
        # These operations contain no provider credentials. Keep errors out of the report.
        raise RuntimeError(result.stderr[-1800:])
    return result.stdout


def serialize(value) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"


def load_release(assets: Path) -> tuple[ReleaseSet, dict[str, str]]:
    release = ReleaseSet.model_validate_json((assets / "releases.json").read_text())
    files = {}
    for item in release.releases:
        for name, expected in item.files.items():
            raw = safe_file(assets, name).read_bytes()
            if digest(raw) != expected:
                raise ValueError("asset release hash mismatch")
            files[name] = raw.decode()
    if set(files) != {"knowledge.json", "rules.json"}:
        raise ValueError("M0 requires exactly one knowledge and rules package")
    return release, files


async def replay(args, bundle: dict) -> dict[str, str]:
    with tempfile.TemporaryDirectory(prefix="bioagent-m0-") as temp:
        work = Path(temp)
        manifest = bundle["manifest"]
        if set(manifest["files"]) != set(bundle["contents"]):
            raise ValueError("bundle source manifest mismatch")
        for name, content in bundle["contents"].items():
            rel = Path(name)
            if rel.is_absolute() or ".." in rel.parts:
                raise ValueError("invalid bundle source path")
            path = work / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        candidate = screening_candidate(work, manifest)
        telemetry = json.loads((work / ".bioagent/telemetry.json").read_text())
        state = json.loads((work / ".bioagent/state.json").read_text())
        verified = verify_report_evidence(telemetry=telemetry, run_dir=work)
        release, assets = load_release(Path(args.assets))
        knowledge_release = next(
            item for item in release.releases if item.asset_type == "knowledge"
        )
        baseline = capability_baseline(bundle["inventory"])
        release.releases.extend(
            [
                AssetRelease(
                    asset_id="screening-kraken",
                    asset_type="reference",
                    version="unknown",
                    source=manifest["reference"]["path"],
                ),
                AssetRelease(
                    asset_id="capability-catalog",
                    asset_type="capability",
                    version="1",
                    source="existing catalog and observed configs",
                    files={"baseline.json": digest(serialize(baseline).encode())},
                ),
                AssetRelease(
                    asset_id="minimax-m3",
                    asset_type="model",
                    version="unknown",
                    source="MiniMax cloud API; provider-reported MiniMax-M3; no weights available",
                ),
            ]
        )
        store = KnowledgeStore(
            Path(args.assets) / "knowledge.json",
            knowledge_release.files["knowledge.json"],
        )
        try:
            assessment, retrieval, trace = await explain(
                candidate,
                store=store,
                rules=json.loads(assets["rules.json"]),
                release_set=release,
                provider=MiniMaxProvider(allow_cloud=args.allow_cloud),
                include_unreviewed=args.include_unreviewed,
            )
        finally:
            store.close()
        release.releases[-1].source = (
            "MiniMax cloud API; requested MiniMax-M3; weights/version unknown; "
            f"claude-agent-sdk={trace.get('result', {}).get('backend_version', 'not_loaded')}"
        )
        envelope = {
            "candidate": candidate.model_dump(),
            "assessment": assessment.model_dump(),
            "retrieval": retrieval.model_dump(),
        }
        document = render_analysis_delivery_report(
            state=state, telemetry=telemetry, run_dir=work, replay=envelope
        )
        validation = {
            "status": "draft_generated"
            if assessment.status == "draft"
            else "numeric_only",
            "legacy_evidence": verified,
            "raw_observations": len(candidate.observations),
            "source_kind": manifest["source_kind"],
            "cloud_authorized": args.allow_cloud,
            "unreviewed_development_mode": args.include_unreviewed,
            "m0_complete": False,
            "pending": ["local_model", "offline_model_generation", "domain_review"],
            "bundle_sha256": args.bundle_sha256,
            "code_sha256": {
                str(Path(module.__file__).relative_to(ROOT)): digest(
                    Path(module.__file__).read_bytes()
                )
                for module in tuple(sys.modules.values())
                if getattr(module, "__file__", None)
                and str(module.__file__).endswith(".py")
                and ROOT in Path(module.__file__).parents
            }
            | {"m0-replay.py": digest(Path(__file__).read_bytes())},
        }
        return {
            **assets,
            "releases.json": serialize(release.model_dump()),
            "evidence.json": serialize(candidate.model_dump()),
            "citations.json": serialize(retrieval.model_dump()),
            "assessment.json": serialize(assessment.model_dump()),
            "provider-trace.json": serialize(trace),
            "baseline.json": serialize(baseline),
            "report.html": document,
            "validation.json": serialize(validation),
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["freeze", "run"])
    parser.add_argument("--ssh-host", default="")
    parser.add_argument(
        "--remote-python", default="/home/liufangzhou/.pixi/envs/snakemake/bin/python"
    )
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--source-run")
    parser.add_argument("--bundle")
    parser.add_argument("--bundle-sha256")
    parser.add_argument("--assets", default=str(ROOT / "agent/assets/m0"))
    parser.add_argument("--allow-cloud", action="store_true")
    parser.add_argument("--include-unreviewed", action="store_true")
    args = parser.parse_args()
    try:
        transport(args, {"action": "check_output", "output": args.output})
        if args.action == "freeze":
            if not args.source_run:
                parser.error("freeze requires --source-run")
            settings = AdapterSettings.from_env()
            bundle = json.loads(
                transport(
                    args,
                    {
                        "action": "freeze",
                        "source_run": args.source_run,
                        "workflows": {
                            f"workflow{i}": str(
                                getattr(settings, f"workflow{i}_source")
                            )
                            for i in range(1, 7)
                        },
                    },
                )
            )
            # Validate before freezing: a corrupt source is never a successful baseline.
            with tempfile.TemporaryDirectory(prefix="bioagent-m0-check-") as temp:
                for name, content in bundle["contents"].items():
                    path = Path(temp) / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(content)
                screening_candidate(Path(temp), bundle["manifest"])
            raw = serialize(bundle)
            print(
                transport(
                    args,
                    {"action": "write", "output": args.output},
                    payload={"bundle.json": raw},
                ).strip()
            )
            print(
                serialize(
                    {"bundle_sha256": digest(raw.encode()), "bytes": len(raw.encode())}
                ).strip()
            )
        else:
            if not args.bundle or not args.bundle_sha256:
                parser.error("run requires --bundle and its frozen --bundle-sha256")
            raw = transport(args, {"action": "read", "path": args.bundle})
            if digest(raw.encode()) != args.bundle_sha256:
                raise ValueError("frozen bundle hash mismatch")
            files = asyncio.run(replay(args, json.loads(raw)))
            print(
                transport(
                    args, {"action": "write", "output": args.output}, payload=files
                ).strip()
            )
            print(files["validation.json"].strip())
        return 0
    except (ValueError, KeyError, OSError, RuntimeError) as exc:
        failure = serialize(
            {"status": "failed", "error": str(exc), "m0_complete": False}
        )
        try:
            transport(
                args,
                {"action": "write", "output": args.output},
                payload={"validation.json": failure},
            )
        except (ValueError, OSError, RuntimeError):
            pass  # A disconnected or invalid destination can only be reported on stderr.
        print(
            failure,
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
