"""Executable boundary tests for resume-agent guardrails."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GUARDRAIL = ROOT / "tools" / "resume_agent_guardrails.py"


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
    temp = Path(tempfile.mkdtemp(prefix="resume-agent-guardrail-"))
    (temp / "resume-agent").mkdir(parents=True)
    shutil.copy2(ROOT / "resume-agent" / "agent_surface.json", temp / "resume-agent" / "agent_surface.json")
    return temp


class ResumeAgentGuardrailTests(unittest.TestCase):
    def test_current_repo_guardrails_pass(self):
        result = run_guardrail(ROOT)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("guardrails passed", result.stdout)

    def test_forbidden_persistence_imports_are_hard_blocked_with_solution(self):
        temp = make_temp_repo()
        try:
            (temp / "resume-agent" / "agent.py").write_text("import sqlite3\nimport career_store\n", encoding="utf-8")
            result = run_guardrail(temp)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Forbidden import 'sqlite3'", result.stdout)
            self.assertIn("Persist through career-store", result.stdout)
            self.assertIn("Forbidden import 'career_store'", result.stdout)
            self.assertIn("Possible solution", result.stdout)
        finally:
            shutil.rmtree(temp)

    def test_scoring_verification_and_workflow_authority_are_hard_blocked(self):
        temp = make_temp_repo()
        try:
            (temp / "resume-agent" / "agent.py").write_text(
                "official_score = 99\n"
                "final_verification_state = 'user_verified'\n"
                "workflow_transition = 'APPLY_CHANGES'\n",
                encoding="utf-8",
            )
            result = run_guardrail(temp)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("official_score", result.stdout)
            self.assertIn("final_verification_state", result.stdout)
            self.assertIn("workflow_transition", result.stdout)
        finally:
            shutil.rmtree(temp)

    def test_resume_file_mutation_and_full_resume_authority_are_hard_blocked(self):
        temp = make_temp_repo()
        try:
            (temp / "resume-agent" / "agent.py").write_text(
                "from pathlib import Path\n"
                "canonical_resume = {'name': 'X'}\n"
                "Path('resume/working.json').write_text('{}')\n",
                encoding="utf-8",
            )
            result = run_guardrail(temp)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("canonical_resume", result.stdout)
            self.assertIn("write resume/base.json or resume/working.json", result.stdout)
        finally:
            shutil.rmtree(temp)

    def test_unsupported_inflation_phrases_are_hard_blocked(self):
        temp = make_temp_repo()
        try:
            (temp / "resume-agent" / "agent.py").write_text(
                "SUGGESTION = 'Led 30 engineers and scaled apps to 20 million users as Staff Software Engineer.'\n",
                encoding="utf-8",
            )
            result = run_guardrail(temp)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("30 engineers", result.stdout)
            self.assertIn("20 million users", result.stdout)
            self.assertIn("staff software engineer", result.stdout.lower())
        finally:
            shutil.rmtree(temp)

    def test_manifest_surface_drift_is_hard_blocked(self):
        temp = make_temp_repo()
        try:
            manifest_path = temp / "resume-agent" / "agent_surface.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["public_api"]["functions"].append("applyResumeRewrite")
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            result = run_guardrail(temp)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Declared public functions differ", result.stdout)
            self.assertIn("applyResumeRewrite", result.stdout)
        finally:
            shutil.rmtree(temp)


if __name__ == "__main__":
    unittest.main()
