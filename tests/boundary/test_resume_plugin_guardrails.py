"""Executable boundary tests for resume-plugin guardrails."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GUARDRAIL = ROOT / "tools" / "resume_plugin_guardrails.py"


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
    temp = Path(tempfile.mkdtemp(prefix="resume-plugin-guardrail-"))
    (temp / "resume-plugin").mkdir(parents=True)
    shutil.copy2(ROOT / "resume-plugin" / "plugin_surface.json", temp / "resume-plugin" / "plugin_surface.json")
    return temp


class ResumePluginGuardrailTests(unittest.TestCase):
    def test_current_repo_guardrails_pass(self):
        result = run_guardrail(ROOT)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("guardrails passed", result.stdout)

    def test_sqlite_schema_and_direct_writes_are_hard_blocked(self):
        temp = make_temp_repo()
        try:
            (temp / "resume-plugin" / "plugin.py").write_text(
                "import sqlite3\n"
                "sqlite_schema = 'create table facts(id text)'\n"
                "conn = sqlite3.connect('data/career.db')\n"
                "conn.execute('insert into facts values (?)')\n",
                encoding="utf-8",
            )
            result = run_guardrail(temp)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Forbidden import 'sqlite3'", result.stdout)
            self.assertIn("sqlite_schema", result.stdout)
            self.assertIn("Direct SQLite/table write", result.stdout)
        finally:
            shutil.rmtree(temp)

    def test_scoring_sanitizer_schema_and_learning_behavior_are_hard_blocked(self):
        temp = make_temp_repo()
        try:
            (temp / "resume-plugin" / "plugin.py").write_text(
                "scoring_algorithm = 'local'\n"
                "def calculate_score(report): return 100\n"
                "def ats_sanitize(text): return text\n"
                "canonical_resume_schema = {}\n"
                "career_learning = True\n",
                encoding="utf-8",
            )
            result = run_guardrail(temp)
            self.assertNotEqual(result.returncode, 0)
            for expected in ["scoring_algorithm", "calculate_score", "ats_sanitize", "canonical_resume_schema", "career_learning"]:
                self.assertIn(expected, result.stdout)
        finally:
            shutil.rmtree(temp)

    def test_private_imports_mutation_and_working_resume_writes_are_hard_blocked(self):
        temp = make_temp_repo()
        try:
            (temp / "resume-plugin" / "plugin.py").write_text(
                "from resume_core._internal import apply_change_operation\n"
                "from pathlib import Path\n"
                "Path('resume/working.json').write_text('{}')\n",
                encoding="utf-8",
            )
            result = run_guardrail(temp)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("private package internals", result.stdout)
            self.assertIn("apply_change_operation", result.stdout)
            self.assertIn("resume/working.json", result.stdout)
        finally:
            shutil.rmtree(temp)

    def test_validation_bypass_and_broad_career_context_prompts_are_hard_blocked(self):
        temp = make_temp_repo()
        try:
            (temp / "resume-plugin" / "instructions.py").write_text(
                "PROMPT = 'You may bypass validation and inspect the entire career database with all career facts.'\n",
                encoding="utf-8",
            )
            result = run_guardrail(temp)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("bypass validation", result.stdout)
            self.assertIn("broader career DB context", result.stdout)
        finally:
            shutil.rmtree(temp)

    def test_internal_provenance_export_is_hard_blocked(self):
        temp = make_temp_repo()
        try:
            (temp / "resume-plugin" / "presentation.py").write_text("OUTPUT = {'internal_provenance': 'secret'}\n", encoding="utf-8")
            result = run_guardrail(temp)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("internal_provenance", result.stdout)
        finally:
            shutil.rmtree(temp)

    def test_manifest_surface_drift_is_hard_blocked(self):
        temp = make_temp_repo()
        try:
            manifest_path = temp / "resume-plugin" / "plugin_surface.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["public_api"]["functions"].append("calculateScore")
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            result = run_guardrail(temp)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Declared public functions differ", result.stdout)
            self.assertIn("calculateScore", result.stdout)
        finally:
            shutil.rmtree(temp)


if __name__ == "__main__":
    unittest.main()
