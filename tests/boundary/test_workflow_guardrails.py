"""Executable boundary tests for workflow guardrails."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GUARDRAIL = ROOT / "tools" / "workflow_guardrails.py"


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
    temp = Path(tempfile.mkdtemp(prefix="workflow-guardrail-"))
    (temp / "workflow").mkdir(parents=True)
    shutil.copy2(ROOT / "workflow" / "workflow_surface.json", temp / "workflow" / "workflow_surface.json")
    return temp


class WorkflowGuardrailTests(unittest.TestCase):
    def test_current_repo_guardrails_pass(self):
        result = run_guardrail(ROOT)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("guardrails passed", result.stdout)

    def test_private_package_imports_are_hard_blocked(self):
        temp = make_temp_repo()
        try:
            (temp / "workflow" / "state.py").write_text(
                "from resume_core._internal import validate_resume_schema\n",
                encoding="utf-8",
            )
            result = run_guardrail(temp)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("private package internals", result.stdout)
            self.assertIn("validate_resume_schema", result.stdout)
        finally:
            shutil.rmtree(temp)

    def test_alternate_scoring_validation_and_mutation_rules_are_hard_blocked(self):
        temp = make_temp_repo()
        try:
            (temp / "workflow" / "state.py").write_text(
                "scoring_weights = {'required': 10}\n"
                "def calculate_score(match): return 100\n"
                "def validate_job_schema(job): return True\n"
                "def apply_resume_change(doc, op): return doc\n",
                encoding="utf-8",
            )
            result = run_guardrail(temp)
            self.assertNotEqual(result.returncode, 0)
            for expected in ["scoring_weights", "calculate_score", "validate_job_schema", "apply_resume_change"]:
                self.assertIn(expected, result.stdout)
        finally:
            shutil.rmtree(temp)

    def test_direct_db_write_and_resume_mutation_are_hard_blocked(self):
        temp = make_temp_repo()
        try:
            (temp / "workflow" / "state.py").write_text(
                "import sqlite3\n"
                "conn = sqlite3.connect('data/career.db')\n"
                "conn.execute('insert into facts values (?)')\n"
                "Path('resume/working.json').write_text('{}')\n",
                encoding="utf-8",
            )
            result = run_guardrail(temp)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Forbidden import 'sqlite3'", result.stdout)
            self.assertIn("Direct career database", result.stdout)
            self.assertIn("resume files", result.stdout)
        finally:
            shutil.rmtree(temp)

    def test_checkpoint_skip_due_to_agent_plausibility_is_hard_blocked(self):
        temp = make_temp_repo()
        try:
            (temp / "workflow" / "state.py").write_text(
                "if agent_says_ok:\n"
                "    skip_checkpoint = 'VALIDATE_CHANGES'\n",
                encoding="utf-8",
            )
            result = run_guardrail(temp)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("agent_says_ok", result.stdout)
            self.assertIn("skip_checkpoint", result.stdout)
        finally:
            shutil.rmtree(temp)

    def test_manifest_checkpoint_drift_is_hard_blocked(self):
        temp = make_temp_repo()
        try:
            manifest_path = temp / "workflow" / "workflow_surface.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["canonical_checkpoints"].remove("GROUNDING_AUDIT")
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            result = run_guardrail(temp)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Canonical checkpoints", result.stdout)
        finally:
            shutil.rmtree(temp)

    def test_manifest_public_surface_drift_is_hard_blocked(self):
        temp = make_temp_repo()
        try:
            manifest_path = temp / "workflow" / "workflow_surface.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["public_api"]["functions"].append("computeScore")
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            result = run_guardrail(temp)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Declared public functions differ", result.stdout)
            self.assertIn("computeScore", result.stdout)
        finally:
            shutil.rmtree(temp)


if __name__ == "__main__":
    unittest.main()
