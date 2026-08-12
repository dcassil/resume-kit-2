"""Executable boundary tests for resume-core guardrails."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GUARDRAIL = ROOT / "tools" / "resume_core_guardrails.py"


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
    temp = Path(tempfile.mkdtemp(prefix="resume-core-guardrail-"))
    (temp / "resume-core").mkdir(parents=True)
    shutil.copy2(ROOT / "resume-core" / "core_surface.json", temp / "resume-core" / "core_surface.json")
    return temp


class ResumeCoreGuardrailTests(unittest.TestCase):
    def test_current_repo_guardrails_pass(self):
        result = run_guardrail(ROOT)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("guardrails passed", result.stdout)

    def test_adapter_store_sql_and_renderer_imports_are_hard_blocked(self):
        temp = make_temp_repo()
        try:
            (temp / "resume-core" / "domain.py").write_text(
                "import sqlite3\n"
                "import career_store\n"
                "import resume_render\n"
                "import resume_agent\n",
                encoding="utf-8",
            )
            result = run_guardrail(temp)
            self.assertNotEqual(result.returncode, 0)
            for expected in ["sqlite3", "career_store", "resume_render", "resume_agent"]:
                self.assertIn(f"Forbidden import '{expected}'", result.stdout)
            self.assertIn("Possible solution", result.stdout)
        finally:
            shutil.rmtree(temp)

    def test_file_io_llm_mcp_and_terminal_ui_are_hard_blocked(self):
        temp = make_temp_repo()
        try:
            (temp / "resume-core" / "domain.py").write_text(
                "import openai\n"
                "import click\n"
                "def normalizeResume(path, config):\n"
                "    text = open(path).read()\n"
                "    call_tool('career.search_facts', {})\n"
                "    return {'status': 'ok'}\n",
                encoding="utf-8",
            )
            result = run_guardrail(temp)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Forbidden import 'openai'", result.stdout)
            self.assertIn("Forbidden import 'click'", result.stdout)
            self.assertIn("File IO appears", result.stdout)
            self.assertIn("call_tool", result.stdout)
        finally:
            shutil.rmtree(temp)

    def test_workflow_and_resume_artifact_writes_are_hard_blocked(self):
        temp = make_temp_repo()
        try:
            (temp / "resume-core" / "domain.py").write_text(
                "from pathlib import Path\n"
                "def validateFinalResume(resume, job, facts, config):\n"
                "    advanceCheckpoint('COMPLETE')\n"
                "    Path('resume/working.json').write_text('{}')\n"
                "    return resume\n",
                encoding="utf-8",
            )
            result = run_guardrail(temp)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("advanceCheckpoint", result.stdout)
            self.assertIn("File IO appears", result.stdout)
            self.assertIn("resume/base.json or resume/working.json", result.stdout)
        finally:
            shutil.rmtree(temp)

    def test_public_surface_drift_is_hard_blocked(self):
        temp = make_temp_repo()
        try:
            manifest_path = temp / "resume-core" / "core_surface.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["public_api"]["functions"].append("renderResume")
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            result = run_guardrail(temp)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Declared public functions differ", result.stdout)
            self.assertIn("renderResume", result.stdout)
        finally:
            shutil.rmtree(temp)

    def test_public_api_scanner_ignores_method_and_helper_calls(self):
        temp = make_temp_repo()
        try:
            (temp / "resume-core" / "domain.py").write_text(
                "import unicodedata\n"
                "def sanitizeText(payload):\n"
                "    text = payload.get('text', '')\n"
                "    return {'status': 'ok', 'text': unicodedata.normalize('NFKC', text), 'warnings': []}\n",
                encoding="utf-8",
            )
            result = run_guardrail(temp)
            self.assertEqual(result.returncode, 0, result.stdout)
        finally:
            shutil.rmtree(temp)

    def test_public_api_scanner_ignores_nested_helpers_and_methods(self):
        temp = make_temp_repo()
        try:
            (temp / "resume-core" / "domain.py").write_text(
                "class DraftNormalizer:\n"
                "    def normalize(self, value):\n"
                "        return value\n"
                "def sanitizeText(payload):\n"
                "    def validate_helper(value):\n"
                "        return value\n"
                "    return {'status': 'ok', 'text': validate_helper(payload['text']), 'warnings': []}\n",
                encoding="utf-8",
            )
            result = run_guardrail(temp)
            self.assertEqual(result.returncode, 0, result.stdout)
        finally:
            shutil.rmtree(temp)

    def test_unapproved_public_function_definition_is_hard_blocked(self):
        temp = make_temp_repo()
        try:
            (temp / "resume-core" / "domain.py").write_text(
                "def validateHelper(payload):\n"
                "    return {'status': 'ok'}\n",
                encoding="utf-8",
            )
            result = run_guardrail(temp)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("validateHelper", result.stdout)
            self.assertIn("Potential public resume-core function", result.stdout)
        finally:
            shutil.rmtree(temp)

    def test_unapproved_exported_public_name_is_hard_blocked(self):
        temp = make_temp_repo()
        try:
            (temp / "resume-core" / "domain.py").write_text(
                "__all__ = ['rankHelper']\n",
                encoding="utf-8",
            )
            result = run_guardrail(temp)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("rankHelper", result.stdout)
            self.assertIn("Exported resume-core name", result.stdout)
        finally:
            shutil.rmtree(temp)


if __name__ == "__main__":
    unittest.main()
