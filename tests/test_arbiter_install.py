"""Tests for `omni arbiter install` and `omni adopt --with-arbiter`: Arbiter (the repository evaluator this
workspace pairs with) is installed beside the workspace and wired in through three files. Pip is never run
here (`skip_pip`); the wiring is what these tests own. Stdlib only. Run with:

    python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import make_ai as ma  # noqa: E402


class ArbiterInstallFixture(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        (self.root / ".ai" / "rules").mkdir(parents=True)
        self.rulepack = self.root / ".ai" / "rules" / "completion-workflow.json"
        self.rulepack.write_text(json.dumps({
            "rulepack_id": "completion", "version": "1.0.0", "title": "t", "purpose": "p", "applies_to": [],
            "rules": [{"id": "completion.changelog_gate", "severity": "required", "statement": "s"}],
        }), encoding="utf-8")

    def install(self, dry_run: bool = False) -> tuple[int, str]:
        out = io.StringIO()
        with redirect_stdout(out):
            code = ma.arbiter_install(self.root, "../arbiter", skip_pip=True, dry_run=dry_run)
        return code, out.getvalue()

    def rules(self) -> list[dict]:
        return json.loads(self.rulepack.read_text(encoding="utf-8"))["rules"]


class TestWiring(ArbiterInstallFixture):
    def test_writes_the_three_wiring_files(self) -> None:
        code, _ = self.install()
        self.assertEqual(code, 0)
        mcp = json.loads((self.root / ".mcp.json").read_text(encoding="utf-8"))
        self.assertEqual(mcp["mcpServers"]["arbiter"], {"command": "arbiter", "args": ["mcp"]})
        gate = [r for r in self.rules() if r["id"] == ma.ARBITER_GATE_RULE_ID]
        self.assertEqual(len(gate), 1)
        self.assertEqual(gate[0]["validation"]["type"], "command")
        self.assertIn("arbiter gate --changed {base}", gate[0]["validation"]["run"])
        self.assertTrue((self.root / "arbiter.yaml").is_file())
        self.assertIn("arbiter-out/", (self.root / ".gitignore").read_text(encoding="utf-8"))

    def test_rerunning_changes_nothing(self) -> None:
        self.install()
        before = {p: (self.root / p).read_text(encoding="utf-8") for p in (".mcp.json", "arbiter.yaml", ".gitignore")}
        before_rules = self.rules()
        code, output = self.install()
        self.assertEqual(code, 0)
        self.assertIn("already", output)
        for p, text in before.items():
            self.assertEqual((self.root / p).read_text(encoding="utf-8"), text)
        self.assertEqual(self.rules(), before_rules)

    def test_existing_servers_and_policy_are_kept(self) -> None:
        (self.root / ".mcp.json").write_text(json.dumps({"mcpServers": {"omni": {"command": "python", "args": ["omni", "mcp", "serve"]}}}), encoding="utf-8")
        (self.root / "arbiter.yaml").write_text("version: 1\nprofile: ci\n", encoding="utf-8")
        self.install()
        mcp = json.loads((self.root / ".mcp.json").read_text(encoding="utf-8"))
        self.assertEqual(set(mcp["mcpServers"]), {"omni", "arbiter"})
        self.assertEqual((self.root / "arbiter.yaml").read_text(encoding="utf-8"), "version: 1\nprofile: ci\n")

    def test_dry_run_writes_nothing(self) -> None:
        code, output = self.install(dry_run=True)
        self.assertEqual(code, 0)
        self.assertIn("would", output)
        self.assertFalse((self.root / ".mcp.json").exists())
        self.assertFalse((self.root / "arbiter.yaml").exists())
        self.assertEqual(len(self.rules()), 1)

    def test_a_missing_rulepack_is_reported(self) -> None:
        self.rulepack.unlink()
        code, output = self.install()
        self.assertEqual(code, 1)
        self.assertIn("adopt the workspace first", output)


class TestPipCommand(unittest.TestCase):
    def test_local_checkout_installs_editable_with_the_mcp_extra(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
            command = ma._arbiter_pip_command(tmp)
        self.assertEqual(command[-2], "-e")
        self.assertTrue(command[-1].endswith(f"[{ma.ARBITER_PIP_EXTRAS}]"))

    def test_git_source_installs_the_named_distribution(self) -> None:
        command = ma._arbiter_pip_command(ma.ARBITER_DEFAULT_SOURCE)
        self.assertEqual(command[-1], f"arbiter-eval[{ma.ARBITER_PIP_EXTRAS}] @ {ma.ARBITER_DEFAULT_SOURCE}")


class TestAdoptFlag(unittest.TestCase):
    def test_adopt_accepts_with_arbiter_with_and_without_a_source(self) -> None:
        parser = ma.build_parser()
        args = parser.parse_args(["adopt", "--target", "x", "--with-arbiter"])
        self.assertEqual(args.with_arbiter, ma.ARBITER_DEFAULT_SOURCE)
        args = parser.parse_args(["adopt", "--target", "x", "--with-arbiter", "../arbiter", "--skip-pip"])
        self.assertEqual(args.with_arbiter, "../arbiter")
        self.assertTrue(args.skip_pip)
        self.assertIsNone(parser.parse_args(["adopt", "--target", "x"]).with_arbiter)


if __name__ == "__main__":
    unittest.main()
