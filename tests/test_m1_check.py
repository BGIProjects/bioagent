"""CLI isolation and local transport checks using a synthetic run root."""

import json
import runpy
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
CLI = runpy.run_path(str(ROOT / "m1-check.py"))
sys.path.insert(0, str(ROOT / "agent/tests"))
from knowledge import digest
from test_evidence_replay import synthetic_bundle


class M1CLITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        source = self.root / "source"
        source.mkdir()
        manifest = synthetic_bundle(source)
        bundle = {
            "manifest": manifest,
            "contents": {
                name: (source / name).read_text() for name in manifest["files"]
            },
            "inventory": {},
        }
        self.bundle = self.root / "bundle.json"
        self.bundle.write_text(json.dumps(bundle))
        self.sha = digest(self.bundle.read_bytes())
        suite = json.loads((ROOT / "agent/benchmarks/m1_development.json").read_text())
        suite["bundle_sha256"] = self.sha
        self.cases = self.root / "cases.json"
        self.cases.write_text(json.dumps(suite))

    def test_evaluation_without_cloud_flag_writes_only_new_run_and_records_failures(
        self,
    ):
        output = self.root / "m1-test"
        argv = [
            "m1-check.py",
            "evaluate",
            "--run-root",
            str(self.root),
            "--output",
            str(output),
            "--bundle",
            str(self.bundle),
            "--bundle-sha256",
            self.sha,
            "--cases",
            str(self.cases),
        ]
        before = self.bundle.read_bytes()
        with patch.object(sys, "argv", argv), redirect_stdout(StringIO()):
            self.assertEqual(CLI["main"](), 0)
        result = json.loads((output / "results.json").read_text())
        self.assertEqual(len(result["records"]), 16)
        self.assertEqual(
            {r["result"]["error_code"] for r in result["records"]}, {"CLOUD_DISABLED"}
        )
        files = json.loads((output / "files.json").read_text())
        for name, expected in files["sha256"].items():
            self.assertEqual(digest((output / name).read_bytes()), expected)
        self.assertEqual(before, self.bundle.read_bytes())
        args = type("Args", (), {"run_root": str(self.root), "ssh_host": ""})()
        with self.assertRaises(RuntimeError):
            CLI["io"](
                args, "write", output=str(output), payload={"results.json": "overwrite"}
            )
        for target in (
            self.root / "analysis-existing",
            self.root.parent / "m1-outside",
        ):
            with self.assertRaises(RuntimeError):
                CLI["io"](args, "check_output", output=str(target))
