"""Executable boundary tests for resume-cli guardrails."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GUARDRAIL = ROOT / "tools" / "resume_cli_guardrails.py"


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
    temp = Path(tempfile.mkdtemp(prefix="resume-cli-guardrail-"))
    (temp / "resume-cli").mkdir(parents=True)
    shutil.copy2(ROOT / "resume-cli" / "cli_surface.json", temp / "resume-cli" / "cli_surface.json")
    return temp


class ResumeCliGuardrailTests(unittest.TestCase):
    def test_current_repo_guardrails_pass(self):
        result = run_guardrail(ROOT)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("guardrails passed", result.stdout)

    def test_direct_sqlite_and_table_writes_are_hard_blocked(self):
        temp = make_temp_repo()
        try:
            (temp / "resume-cli" / "cli.py").write_text(
                "import sqlite3\n"
                "conn = sqlite3.connect('data/career.db')\n"
                "conn.execute('insert into facts values (?)')\n",
                encoding="utf-8",
            )
            result = run_guardrail(temp)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Forbidden import 'sqlite3'", result.stdout)
            self.assertIn("Direct career database table write", result.stdout)
            self.assertIn("career-store", result.stdout)
        finally:
            shutil.rmtree(temp)

    def test_independent_scoring_logic_is_hard_blocked(self):
        temp = make_temp_repo()
        try:
            (temp / "resume-cli" / "cli.py").write_text(
                "scoring_weights = {'required': 10}\n"
                "score = react_points + aws_points * requirement_weight\n"
                "def calculate_score(requirements):\n"
                "    return 100\n",
                encoding="utf-8",
            )
            result = run_guardrail(temp)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("scoring_weights", result.stdout)
            self.assertIn("requirement_weight", result.stdout)
            self.assertIn("calculate_score", result.stdout)
            self.assertIn("resume-core", result.stdout)
        finally:
            shutil.rmtree(temp)

    def test_private_mutation_and_renderer_semantic_changes_are_hard_blocked(self):
        temp = make_temp_repo()
        try:
            (temp / "resume-cli" / "cli.py").write_text(
                "def apply_resume_change(doc, op):\n"
                "    return doc\n"
                "def export(doc):\n"
                "    return truncate_to_fit(doc)\n",
                encoding="utf-8",
            )
            result = run_guardrail(temp)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("apply_resume_change", result.stdout)
            self.assertIn("truncate_to_fit", result.stdout)
        finally:
            shutil.rmtree(temp)

    def test_plugin_behavior_import_is_hard_blocked(self):
        temp = make_temp_repo()
        try:
            (temp / "resume-cli" / "cli.py").write_text("import resume_plugin\nplugin_manifest = {}\n", encoding="utf-8")
            result = run_guardrail(temp)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Forbidden import 'resume_plugin'", result.stdout)
            self.assertIn("plugin_manifest", result.stdout)
        finally:
            shutil.rmtree(temp)

    def test_base_resume_write_without_reingest_guard_is_hard_blocked(self):
        temp = make_temp_repo()
        try:
            (temp / "resume-cli" / "cli.py").write_text(
                "from pathlib import Path\n"
                "Path('resume/base.json').write_text('{}')\n",
                encoding="utf-8",
            )
            result = run_guardrail(temp)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("resume/base.json", result.stdout)
            self.assertIn("explicit re-ingest", result.stdout)
        finally:
            shutil.rmtree(temp)

    def test_manifest_command_drift_is_hard_blocked(self):
        temp = make_temp_repo()
        try:
            manifest_path = temp / "resume-cli" / "cli_surface.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["required_commands"].append("resume debug sql")
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            result = run_guardrail(temp)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Declared command surface differs", result.stdout)
            self.assertIn("resume debug sql", result.stdout)
        finally:
            shutil.rmtree(temp)


if __name__ == "__main__":
    unittest.main()
