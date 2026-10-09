"""Tests for `omni doctor`'s Posture line, `--json` output and the cross-registry duplicate-id check (REQ-036).

The posture reads the newest Arbiter report under the gate rule's `--out` directory and says whether it still
describes HEAD; the functions are driven directly in a temporary workspace. Stdlib only. Run with:

    python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import argparse
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import make_ai as ma  # noqa: E402

GIT_ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
    "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid",
}


def requirement(req_id: str, status: str = "pending") -> dict:
    return {
        "id": req_id, "category": "Feature", "title": f"{req_id} title", "description": "d", "priority": "low",
        "status": status, "minimum_access_scope": [], "do_not_access": [], "acceptance_criteria": [],
        "validation_required": [], "documentation_required": [], "risk_notes": [],
    }


class PostureFixture(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name).resolve()
        self._cwd = Path.cwd()
        os.chdir(self.root)
        self.addCleanup(os.chdir, self._cwd)

    def write_rule(self, out: str | None = "arbiter-out/omni-gate") -> None:
        run = "arbiter gate . --changed {base} --format json" + (f" --out {out}" if out else "")
        rule = {
            "id": ma.ARBITER_GATE_RULE_ID, "severity": "required", "statement": "s", "scope": ["completion"],
            "validation": {"type": "command", "run": run, "when_changed": ["**"]},
        }
        ma.write_json(Path(".ai/rules/completion-workflow.json"), {"id": "completion", "rules": [rule]})

    def git_init(self) -> str:
        if shutil.which("git") is None:
            self.skipTest("git is not installed")
        subprocess.run(["git", "init", "-q"], check=True, env=GIT_ENV, capture_output=True)
        Path("tracked.txt").write_text("one\n", encoding="utf-8")
        subprocess.run(["git", "add", "tracked.txt"], check=True, env=GIT_ENV, capture_output=True)
        subprocess.run(["git", "commit", "-q", "-m", "init"], check=True, env=GIT_ENV, capture_output=True)
        head = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], check=True, env=GIT_ENV, capture_output=True, text=True,
        )
        return head.stdout.strip()

    def write_report(
        self, commit: str, started_at: str | None = None, passed: bool = True, reasons: list | None = None,
        overall: float | None = 87.5, coverage: float = 0.71, findings: list | None = None,
        path: str = "arbiter-out/omni-gate/report.json",
    ) -> Path:
        report = {
            "schema_version": "1.0",
            "repos": [{"id": "root", "commit": commit}],
            "started_at": started_at or datetime.now(timezone.utc).isoformat(),
            "scan_scope": {"mode": "partial"},
            "gate": {"passed": passed, "reasons": reasons or []},
            "scorecard": {"overall": overall, "coverage": coverage, "withheld": overall is None},
            "findings": findings or [],
        }
        target = Path(path)
        ma.write_json(target, report)
        return target


class TestArbiterPosture(PostureFixture):
    def test_no_rule_reads_not_wired(self) -> None:
        posture = ma.compute_posture()
        self.assertFalse(posture["arbiter"]["wired"])
        self.assertIn("arbiter not wired", ma.format_posture(posture))

    def test_rule_without_report_reads_no_report(self) -> None:
        self.write_rule()
        posture = ma.compute_posture()
        self.assertTrue(posture["arbiter"]["wired"])
        self.assertFalse(posture["arbiter"]["present"])
        self.assertIn("arbiter-out/omni-gate", posture["arbiter"]["reason"])
        self.assertIn("arbiter no report (run ./omni gate)", ma.format_posture(posture))

    def test_stale_report_is_named_with_its_reason(self) -> None:
        self.git_init()
        self.write_rule()
        self.write_report("0000000")
        posture = ma.compute_posture()
        arbiter = posture["arbiter"]
        self.assertTrue(arbiter["present"])
        self.assertFalse(arbiter["fresh"])
        self.assertIn("scanned 0000000", arbiter["reason"])
        line = ma.format_posture(posture)
        self.assertIn("arbiter stale: scanned 0000000", line)

    def test_fresh_report_shows_the_grade(self) -> None:
        head = self.git_init()
        self.write_rule()
        finding = {"severity": "high", "status": "new", "suppressed": False}
        existing = {"severity": "critical", "status": "existing", "suppressed": False}
        muted = {"severity": "high", "status": "new", "suppressed": True}
        self.write_report(head, findings=[finding, existing, muted])
        posture = ma.compute_posture()
        arbiter = posture["arbiter"]
        self.assertTrue(arbiter["fresh"], arbiter["reason"])
        self.assertEqual(arbiter["grade"], "87.5")
        self.assertEqual(arbiter["coverage"], 0.71)
        self.assertEqual(arbiter["new_high_or_above"], 1)
        self.assertEqual(arbiter["existing_high_or_above"], 1)
        self.assertTrue(arbiter["gate_passed"])
        self.assertEqual(arbiter["path"], "arbiter-out/omni-gate/report.json")
        line = ma.format_posture(posture)
        self.assertIn("arbiter score 87.5 (coverage 71%, new high+ 1, gate passed, fresh)", line)

    def test_withheld_grade_is_said_so(self) -> None:
        head = self.git_init()
        self.write_rule()
        self.write_report(head, overall=None)
        line = ma.format_posture(ma.compute_posture())
        self.assertIn("arbiter grade withheld (coverage 71%", line)

    def test_malformed_report_is_present_but_not_fresh(self) -> None:
        self.write_rule()
        Path("arbiter-out/omni-gate").mkdir(parents=True)
        Path("arbiter-out/omni-gate/report.json").write_text("{not json", encoding="utf-8")
        arbiter = ma.compute_posture()["arbiter"]
        self.assertTrue(arbiter["present"])
        self.assertFalse(arbiter["fresh"])
        self.assertTrue(arbiter["reason"].startswith("unreadable:"), arbiter["reason"])

    def test_freshness_flags_a_file_changed_after_the_scan(self) -> None:
        Path("touched.txt").write_text("x", encoding="utf-8")
        hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        report = {"repos": [{"commit": "abc1234"}], "started_at": hour_ago}
        fresh, reason = ma.arbiter_report_freshness(report, "abc1234def", {"touched.txt"})
        self.assertFalse(fresh)
        self.assertIn("touched.txt", reason)
        fresh, reason = ma.arbiter_report_freshness(report, "abc1234def", {"gone.txt"})
        self.assertTrue(fresh, reason)
        fresh, reason = ma.arbiter_report_freshness(report, "fff0000", {"gone.txt"})
        self.assertFalse(fresh)
        self.assertIn("HEAD is fff0000", reason)

    def test_out_dir_comes_from_the_rule(self) -> None:
        self.assertEqual(ma.arbiter_out_dir(None), Path("arbiter-out"))
        self.assertEqual(ma.arbiter_out_dir({"validation": {"run": "arbiter gate . --out custom/dir --format json"}}), Path("custom/dir"))
        self.assertEqual(ma.arbiter_out_dir({"validation": {"run": "arbiter gate . --out=x"}}), Path("x"))
        self.assertEqual(ma.arbiter_out_dir({"validation": {"run": "arbiter gate ."}}), Path("arbiter-out"))

    def test_newest_report_wins_by_mtime(self) -> None:
        older = self.write_report("aaa", path="arbiter-out/check/report.json")
        newer = self.write_report("bbb", path="arbiter-out/report.json")
        past = time.time() - 600
        os.utime(older, (past, past))
        self.assertEqual(ma.newest_arbiter_report(Path("arbiter-out")), newer)
        self.assertIsNone(ma.newest_arbiter_report(Path("nowhere")))

    def test_open_counts_follow_the_registries(self) -> None:
        ma.write_json(ma.REQUIREMENTS_PATH, {"requirements": [
            requirement("REQ-001", "pending"), requirement("REQ-002", "pending"), requirement("REQ-003", "proposed"),
            requirement("REQ-004", "completed"),
        ]})
        ma.write_json(ma.FAILURE_LEDGER_PATH, {"failures": [{"status": "open"}, {"status": "mitigated"}, {"status": "fixed"}]})
        posture = ma.compute_posture()
        self.assertEqual(posture["failures_open"], 2)
        self.assertEqual(posture["requirements_open"], {"pending": 2, "proposed": 1, "blocked": 0, "needs_review": 0, "total": 3})
        self.assertTrue(ma.format_posture(posture).endswith("failures open 2 · requirements open 3 (pending 2, proposed 1)"))


class TestDoctorReportOutput(PostureFixture):
    @staticmethod
    def printed(report: ma.DoctorReport) -> list[str]:
        out = io.StringIO()
        with redirect_stdout(out):
            report.print()
        return out.getvalue().splitlines()

    def test_result_line_is_identical_with_and_without_posture(self) -> None:
        report = ma.DoctorReport()
        report.pass_check("a")
        report.pass_check("b")
        report.warning("w")
        report.error("e")
        without = self.printed(report)
        report.posture = ma.compute_posture()
        with_posture = self.printed(report)
        self.assertEqual(without[-1], "Result: 2 passed, 1 warnings, 1 errors")
        self.assertEqual(with_posture[-2], without[-1])
        self.assertTrue(with_posture[-1].startswith("Posture: arbiter not wired"))
        self.assertNotIn("Posture", "\n".join(without))

    def test_to_json_carries_the_contract(self) -> None:
        report = ma.DoctorReport()
        report.error("e")
        report.posture = ma.compute_posture()
        data = report.to_json()
        self.assertEqual(data["schema_version"], 1)
        self.assertFalse(data["ok"])
        self.assertEqual(data["errors"], ["e"])
        self.assertIn("arbiter", data["posture"])
        json.dumps(data)  # must be serialisable as-is

    def test_run_doctor_json_prints_parseable_json(self) -> None:
        out = io.StringIO()
        with redirect_stdout(out):
            code = ma.run_doctor(argparse.Namespace(json=True))
        data = json.loads(out.getvalue())
        self.assertEqual(data["schema_version"], 1)
        self.assertEqual(code, 0 if data["ok"] else 1)
        self.assertIn("posture", data)
        self.assertIn("errors", data)


class TestDuplicateRequirementIds(PostureFixture):
    def vendor(self, ids: list[str]) -> None:
        ma.write_json(Path("pkg/.ai/omni-version.json"), {"source": "x", "ref": "y"})
        ma.write_json(Path("pkg/.ai/requirements/requirements.json"), {"requirements": [requirement(i) for i in ids]})

    def test_duplicate_across_root_and_vendored_workspace_is_an_error(self) -> None:
        ma.write_json(ma.REQUIREMENTS_PATH, {"requirements": [requirement("REQ-001")]})
        self.vendor(["REQ-001", "REQ-009"])
        report = ma.DoctorReport()
        ma.validate_requirement_ids(report)
        self.assertEqual(len(report.errors), 1, report.errors)
        self.assertIn("REQ-001", report.errors[0])
        self.assertIn(".ai/requirements/requirements.json", report.errors[0])
        self.assertIn("pkg/.ai/requirements/requirements.json", report.errors[0])

    def test_unique_ids_pass_without_an_archive(self) -> None:
        ma.write_json(ma.REQUIREMENTS_PATH, {"requirements": [requirement("REQ-001")]})
        self.vendor(["REQ-002"])
        report = ma.DoctorReport()
        ma.validate_requirement_ids(report)
        self.assertEqual(report.errors, [])
        self.assertEqual(len(report.passed), 1)
        self.assertIn("1 vendored workspace(s)", report.passed[0])

    def test_pair_inside_root_registries_is_left_to_the_registry_check(self) -> None:
        ma.write_json(ma.REQUIREMENTS_PATH, {"requirements": [requirement("REQ-001")]})
        ma.write_json(ma.REQUIREMENTS_ARCHIVE_PATH, {"requirements": [requirement("REQ-001", "completed")]})
        report = ma.DoctorReport()
        ma.validate_requirement_ids(report)
        self.assertEqual(report.errors, [])


if __name__ == "__main__":
    unittest.main()
