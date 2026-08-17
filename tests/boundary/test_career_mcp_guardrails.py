"""Executable boundary tests for career-mcp guardrails."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GUARDRAIL = ROOT / "tools" / "career_mcp_guardrails.py"


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
    temp = Path(tempfile.mkdtemp(prefix="career-mcp-guardrail-"))
    (temp / "career-mcp" / "career_mcp").mkdir(parents=True)
    (temp / "tools").mkdir()
    shutil.copy2(ROOT / "career-mcp" / "career_mcp" / "tool_surface.json", temp / "career-mcp" / "career_mcp" / "tool_surface.json")
    shutil.copy2(ROOT / "career-mcp" / "tool_surface.json", temp / "career-mcp" / "tool_surface.json")
    return temp


class CareerMcpGuardrailTests(unittest.TestCase):
    def test_current_repo_guardrails_pass(self):
        result = run_guardrail(ROOT)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("guardrails passed", result.stdout)

    def test_forbidden_raw_sql_tool_is_hard_blocked_with_solution(self):
        temp = make_temp_repo()
        try:
            bad_surface = json.loads((temp / "career-mcp" / "tool_surface.json").read_text(encoding="utf-8"))
            bad_surface["tools"].append(
                {
                    "name": "execute_sql",
                    "description": "Run SQL directly",
                    "mutates": True,
                    "input_schema": {"type": "object"},
                    "response_contract": {"required_fields": ["rows"]},
                }
            )
            bad_payload = json.dumps(bad_surface)
            (temp / "career-mcp" / "career_mcp" / "tool_surface.json").write_text(bad_payload, encoding="utf-8")
            (temp / "career-mcp" / "tool_surface.json").write_text(bad_payload, encoding="utf-8")
            result = run_guardrail(temp)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Forbidden unrestricted database tools", result.stdout)
            self.assertIn("Possible solution", result.stdout)
        finally:
            shutil.rmtree(temp)

    def test_forbidden_import_is_hard_blocked_with_boundary_message(self):
        temp = make_temp_repo()
        try:
            (temp / "career-mcp" / "server.py").write_text("import sqlite3\nimport resume_plugin\n", encoding="utf-8")
            result = run_guardrail(temp)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Forbidden import 'sqlite3'", result.stdout)
            self.assertIn("career-store service", result.stdout)
            self.assertIn("Forbidden import 'resume_plugin'", result.stdout)
        finally:
            shutil.rmtree(temp)

    def test_resume_mutation_and_scoring_are_hard_blocked(self):
        temp = make_temp_repo()
        try:
            (temp / "career-mcp" / "server.py").write_text(
                "from pathlib import Path\n"
                "official_score = 100\n"
                "Path('resume/working.json').write_text('{}')\n",
                encoding="utf-8",
            )
            result = run_guardrail(temp)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("official_score", result.stdout)
            self.assertIn("write resume/base.json or resume/working.json", result.stdout)
        finally:
            shutil.rmtree(temp)

    def test_undeclared_career_tool_is_hard_blocked(self):
        temp = make_temp_repo()
        try:
            (temp / "career-mcp" / "server.py").write_text('TOOL_NAME = "career.execute_sql"\n', encoding="utf-8")
            result = run_guardrail(temp)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Undeclared MCP tool 'career.execute_sql'", result.stdout)
        finally:
            shutil.rmtree(temp)


if __name__ == "__main__":
    unittest.main()
