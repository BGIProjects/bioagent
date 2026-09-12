"""Filesystem boundaries for the isolated CLI, with synthetic data only."""

import json
import runpy
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
CLI = runpy.run_path(str(ROOT / "m0-replay.py"))


class ReplayCLITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.args = SimpleNamespace(run_root=str(self.root), ssh_host="")

    def test_output_is_new_flat_directory_inside_run_root(self):
        output = self.root / "m0-test"
        result = CLI["transport"](
            self.args,
            {"action": "write", "output": str(output)},
            payload={"report.html": "synthetic"},
        )
        self.assertEqual(json.loads(result)["output"], str(output))
        self.assertEqual((output / "report.html").read_text(), "synthetic")
        with self.assertRaises(RuntimeError):
            CLI["transport"](
                self.args,
                {"action": "write", "output": str(output)},
                payload={"report.html": "overwrite"},
            )
        self.assertEqual((output / "report.html").read_text(), "synthetic")
        for path in [self.root / "analysis-existing", self.root.parent / "m0-outside"]:
            with self.assertRaises(RuntimeError):
                CLI["transport"](
                    self.args, {"action": "check_output", "output": str(path)}
                )
        with self.assertRaises(RuntimeError):
            CLI["transport"](
                self.args,
                {"action": "write", "output": str(self.root / "m0-nested")},
                payload={"../escape": "bad"},
            )

    def test_read_rejects_symlinks_and_large_sources(self):
        source = self.root / "source.json"
        source.write_text("{}")
        alias = self.root / "alias.json"
        alias.symlink_to(source)
        with self.assertRaises(RuntimeError):
            CLI["transport"](self.args, {"action": "read", "path": str(alias)})
        source.write_bytes(b"x" * (2 * 1024 * 1024 + 1))
        with self.assertRaises(RuntimeError):
            CLI["transport"](self.args, {"action": "read", "path": str(source)})

    def test_release_corruption_cannot_be_silently_loaded(self):
        assets = self.root / "assets"
        shutil.copytree(ROOT / "agent/assets/m0", assets)
        CLI["load_release"](assets)
        (assets / "rules.json").write_text("{}")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            CLI["load_release"](assets)
