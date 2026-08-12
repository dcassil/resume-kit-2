"""Executable boundary tests for resume-render guardrails."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GUARDRAIL = ROOT / "tools" / "resume_render_guardrails.py"


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
    temp = Path(tempfile.mkdtemp(prefix="resume-render-guardrail-"))
    (temp / "resume-render").mkdir(parents=True)
    shutil.copy2(ROOT / "resume-render" / "render_surface.json", temp / "resume-render" / "render_surface.json")
    return temp


class ResumeRenderGuardrailTests(unittest.TestCase):
    def test_current_repo_guardrails_pass(self):
        result = run_guardrail(ROOT)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("guardrails passed", result.stdout)

    def test_forbidden_career_imports_are_hard_blocked_with_solution(self):
        temp = make_temp_repo()
        try:
            (temp / "resume-render" / "renderer.py").write_text("import career_store\nimport career_mcp\n", encoding="utf-8")
            result = run_guardrail(temp)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Forbidden import 'career_store'", result.stdout)
            self.assertIn("validated resume DTOs", result.stdout)
            self.assertIn("Forbidden import 'career_mcp'", result.stdout)
            self.assertIn("Possible solution", result.stdout)
        finally:
            shutil.rmtree(temp)

    def test_scoring_rewrite_and_change_application_are_hard_blocked(self):
        temp = make_temp_repo()
        try:
            (temp / "resume-render" / "renderer.py").write_text(
                "official_score = 99\n"
                "resume_change_operation = {'status': 'applied'}\n"
                "def rewrite_bullet(text):\n"
                "    return text\n",
                encoding="utf-8",
            )
            result = run_guardrail(temp)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("official_score", result.stdout)
            self.assertIn("resume_change_operation", result.stdout)
            self.assertIn("rewrite_bullet", result.stdout)
        finally:
            shutil.rmtree(temp)

    def test_resume_file_mutation_is_hard_blocked(self):
        temp = make_temp_repo()
        try:
            (temp / "resume-render" / "renderer.py").write_text(
                "from pathlib import Path\n"
                "Path('resume/working.json').write_text('{}')\n",
                encoding="utf-8",
            )
            result = run_guardrail(temp)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("write resume/base.json or resume/working.json", result.stdout)
        finally:
            shutil.rmtree(temp)

    def test_unsupported_additions_are_hard_blocked(self):
        temp = make_temp_repo()
        try:
            (temp / "resume-render" / "renderer.py").write_text(
                "OUTPUT = 'Staff Software Engineer with AWS, GraphQL, 30 engineers, and 20 million users.'\n",
                encoding="utf-8",
            )
            result = run_guardrail(temp)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("staff software engineer", result.stdout.lower())
            self.assertIn("aws", result.stdout.lower())
            self.assertIn("graphql", result.stdout.lower())
            self.assertIn("30 engineers", result.stdout)
            self.assertIn("20 million users", result.stdout)
        finally:
            shutil.rmtree(temp)

    def test_silent_truncation_without_overflow_reporting_is_hard_blocked(self):
        temp = make_temp_repo()
        try:
            (temp / "resume-render" / "renderer.js").write_text(
                "export function renderMarkdown(resume, template) { return resume.text.slice(0, maxLength); }\n",
                encoding="utf-8",
            )
            result = run_guardrail(temp)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("silent content truncation", result.stdout)
            self.assertIn("overflow", result.stdout)
        finally:
            shutil.rmtree(temp)

    def test_manifest_surface_drift_is_hard_blocked(self):
        temp = make_temp_repo()
        try:
            manifest_path = temp / "resume-render" / "render_surface.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["public_api"]["functions"].append("rewriteToFit")
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            result = run_guardrail(temp)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Declared public functions differ", result.stdout)
            self.assertIn("rewriteToFit", result.stdout)
        finally:
            shutil.rmtree(temp)


if __name__ == "__main__":
    unittest.main()
