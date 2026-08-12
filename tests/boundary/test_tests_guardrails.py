"""Executable boundary tests for test-suite guardrails."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GUARDRAIL = ROOT / "tools" / "tests_guardrails.py"


def run_guardrail(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(GUARDRAIL), "--root", str(root)],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def make_temp_repo() -> Path:
    temp = Path(tempfile.mkdtemp(prefix="tests-guardrail-"))
    shutil.copytree(ROOT / "tests", temp / "tests")
    return temp


class TestsGuardrailTests(unittest.TestCase):
    def test_current_repo_guardrails_pass(self):
        result = run_guardrail(ROOT)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("guardrails passed", result.stdout)

    def test_missing_required_directory_is_hard_blocked(self):
        temp = make_temp_repo()
        try:
            shutil.rmtree(temp / "tests" / "e2e")
            result = run_guardrail(temp)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Required test directory is missing", result.stdout)
        finally:
            shutil.rmtree(temp)

    def test_pr_gate_drift_is_hard_blocked(self):
        temp = make_temp_repo()
        try:
            manifest_path = temp / "tests" / "suite_manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["required_gates"]["pr"].remove("hallucination_rejection_fixtures")
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            result = run_guardrail(temp)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("PR gate", result.stdout)
        finally:
            shutil.rmtree(temp)

    def test_release_blocker_drift_is_hard_blocked(self):
        temp = make_temp_repo()
        try:
            manifest_path = temp / "tests" / "suite_manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["release_blockers"].remove("raw_sql_mcp_exposure")
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            result = run_guardrail(temp)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Release blockers", result.stdout)
            self.assertIn("raw_sql_mcp_exposure", result.stdout)
        finally:
            shutil.rmtree(temp)

    def test_hidden_business_logic_in_tests_is_hard_blocked(self):
        temp = make_temp_repo()
        try:
            bad_test = temp / "tests" / "unit" / "test_hidden_logic.py"
            bad_test.write_text("def calculate_score(requirements):\n    return 100\n", encoding="utf-8")
            result = run_guardrail(temp)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("hidden business logic", result.stdout)
        finally:
            shutil.rmtree(temp)

    def test_weak_assertion_is_hard_blocked(self):
        temp = make_temp_repo()
        try:
            bad_test = temp / "tests" / "contract" / "test_weak.py"
            bad_test.write_text("def test_nothing():\n    assert True\n", encoding="utf-8")
            result = run_guardrail(temp)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("gate-weakening pattern", result.stdout)
        finally:
            shutil.rmtree(temp)


if __name__ == "__main__":
    unittest.main()
