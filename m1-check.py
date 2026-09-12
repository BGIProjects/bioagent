#!/usr/bin/env python3
"""M1 development checks; outputs only new m1-* children of the run root."""

from __future__ import annotations

import argparse
import asyncio
import json
import runpy
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
# Reuse M0's bounded transport and numeric report replay, not a second I/O layer.
M0 = runpy.run_path(str(ROOT / "m0-replay.py"))

from evidence_replay import screening_candidate
from knowledge import KnowledgeStore, digest
from m1_assets import check_assets
from m1_evaluation import (
    evaluate,
    load_cases,
    negative_outputs,
    prepare,
    validate_output,
)
from provider import MiniMaxProvider
from workflow_adapters import AdapterSettings


def io(args, action, **fields):
    payload = fields.pop("payload", None)
    return M0["transport"](
        args, {"action": action, "output_prefix": "m1-", **fields}, payload=payload
    )


def current_inventory(args, bundle):
    settings = AdapterSettings.from_env()
    program = (ROOT / "agent/m1_assets.py").read_text()
    command = [args.remote_python if args.ssh_host else sys.executable, "-c", program]
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
        input=json.dumps(
            {"inventory": bundle["inventory"], "seqkit": str(settings.seqkit)}
        ),
        text=True,
        capture_output=True,
        check=False,
        timeout=90,
    )
    if result.returncode:
        raise RuntimeError(
            "remote asset observation unavailable; historical identity unchanged"
        )
    return json.loads(result.stdout)


async def run_checks(args, bundle, suite, candidate, work):
    _, assets = M0["load_release"](Path(args.assets))
    store = KnowledgeStore(
        Path(args.assets) / "knowledge.json", suite["asset_sha256"]["knowledge.json"]
    )
    rules = json.loads(assets["rules.json"])
    try:
        provider = (
            MiniMaxProvider(allow_cloud=args.allow_cloud, state_dir=work / "provider")
            if args.action == "evaluate"
            else None
        )

        def progress(case_id, passed, error):
            print(f"{case_id}: {'passed' if passed else error or 'failed'}", flush=True)

        results = await evaluate(
            suite, candidate, store, rules, provider=provider, progress=progress
        )
        if args.action == "offline":
            rejected = 0
            for case, row in zip(suite["cases"], results["records"], strict=True):
                request, evidence, retrieval, findings = await prepare(
                    case, candidate, store, rules
                )
                try:
                    validate_output(
                        case,
                        negative_outputs(case, row["result"]["output"]),
                        request,
                        evidence,
                        retrieval,
                        findings,
                        store,
                    )
                except ValueError:
                    rejected += 1
                except Exception as exc:
                    from jsonschema import ValidationError

                    if not isinstance(exc, ValidationError):
                        raise
                    rejected += 1
            request, *_ = await prepare(suite["cases"][0], candidate, store, rules)
            blocked = await MiniMaxProvider(allow_cloud=False).generate(request)
            results["negative_checks"] = {
                "injected_cases": 16,
                "rejected": rejected,
                "cloud_disabled": blocked.error_code == "CLOUD_DISABLED",
            }
            if (
                rejected != 16
                or blocked.error_code != "CLOUD_DISABLED"
                or not all(r["engineering_pass"] for r in results["records"])
            ):
                raise ValueError("offline engineering validation failed")
        return results
    finally:
        store.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("assets", "offline", "evaluate"))
    parser.add_argument("--ssh-host", default="")
    parser.add_argument(
        "--remote-python", default="/home/liufangzhou/.pixi/envs/snakemake/bin/python"
    )
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--bundle", required=True)
    parser.add_argument("--bundle-sha256", required=True)
    parser.add_argument("--assets", default=str(ROOT / "agent/assets/m0"))
    parser.add_argument(
        "--cases", default=str(ROOT / "agent/benchmarks/m1_development.json")
    )
    parser.add_argument("--allow-cloud", action="store_true")
    args = parser.parse_args()
    if args.allow_cloud and args.action != "evaluate":
        parser.error("--allow-cloud is only valid for evaluate")
    files = {}
    try:
        io(args, "check_output", output=args.output)
        raw = io(args, "read", path=args.bundle)
        if digest(raw.encode()) != args.bundle_sha256:
            raise ValueError("frozen bundle hash mismatch")
        bundle = json.loads(raw)
        suite = load_cases(Path(args.cases), args.bundle_sha256, Path(args.assets))
        M0["load_release"](Path(args.assets))
        with tempfile.TemporaryDirectory(prefix="bioagent-m1-") as temp:
            work = Path(temp)
            if set(bundle["contents"]) != set(bundle["manifest"]["files"]):
                raise ValueError("bundle source manifest mismatch")
            for name, content in bundle["contents"].items():
                rel = Path(name)
                if rel.is_absolute() or ".." in rel.parts:
                    raise ValueError("invalid bundle path")
                target = work / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content)
            candidate = screening_candidate(work, bundle["manifest"])
            if args.action == "assets":
                results = check_assets(
                    bundle, current_inventory(args, bundle), Path(args.assets)
                )
            else:
                results = asyncio.run(run_checks(args, bundle, suite, candidate, work))
                if args.action == "offline":
                    args.include_unreviewed = True
                    files.update(asyncio.run(M0["replay"](args, bundle)))
            files.update(
                {
                    "results.json": M0["serialize"](results),
                    "cases.json": Path(args.cases).read_text(),
                    "bundle.json": raw,
                }
            )
            for asset in Path(args.assets).glob("*.json"):
                files["input-" + asset.name] = asset.read_text()
            files["provenance.json"] = M0["serialize"](
                {
                    "action": args.action,
                    "cloud_authorized": args.allow_cloud,
                    "review_status": "pending",
                    "m0_complete": False,
                    "m1_complete": False,
                    "code_sha256": {
                        str(Path(module.__file__).relative_to(ROOT)): digest(
                            Path(module.__file__).read_bytes()
                        )
                        for module in tuple(sys.modules.values())
                        if getattr(module, "__file__", None)
                        and str(module.__file__).endswith(".py")
                        and ROOT in Path(module.__file__).parents
                    }
                    | {
                        name: digest((ROOT / name).read_bytes())
                        for name in ("m0-replay.py", "m1-check.py")
                    },
                }
            )
        total = sum(len(v.encode()) for v in files.values())
        if total > 50 * 1024 * 1024:
            raise ValueError("run output exceeds 50 MiB budget")
        files["files.json"] = M0["serialize"](
            {
                "payload_bytes": total,
                "sha256": {k: digest(v.encode()) for k, v in files.items()},
            }
        )
        print(io(args, "write", output=args.output, payload=files).strip())
        print(
            M0["serialize"](
                {
                    "summary": results.get("summary"),
                    "status": results.get("status"),
                    "payload_bytes": total,
                }
            ).strip()
        )
        return 0
    except (
        ValueError,
        KeyError,
        OSError,
        RuntimeError,
        subprocess.TimeoutExpired,
    ) as exc:
        failure = {
            "status": "failed",
            "error_type": type(exc).__name__,
            "m1_complete": False,
        }
        files["failure.json"] = M0["serialize"](failure)
        try:
            io(args, "write", output=args.output, payload=files)
        except (ValueError, OSError, RuntimeError):
            pass
        print(M0["serialize"](failure), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
