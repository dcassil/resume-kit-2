"""Executable boundary tests for career-store guardrails."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GUARDRAIL = ROOT / "tools" / "career_store_guardrails.py"


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
    temp = Path(tempfile.mkdtemp(prefix="career-store-guardrail-"))
    (temp / "career-store").mkdir(parents=True)
    shutil.copy2(ROOT / "career-store" / "store_surface.json", temp / "career-store" / "store_surface.json")
    return temp


class CareerStoreGuardrailTests(unittest.TestCase):
    def test_current_repo_guardrails_pass(self):
        result = run_guardrail(ROOT)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("guardrails passed", result.stdout)

    def test_adapter_agent_renderer_and_cli_imports_are_hard_blocked(self):
        temp = make_temp_repo()
        try:
            (temp / "career-store" / "store.py").write_text(
                "import career_mcp\n"
                "import resume_agent\n"
                "import resume_render\n"
                "import resume_cli\n",
                encoding="utf-8",
            )
            result = run_guardrail(temp)
            self.assertNotEqual(result.returncode, 0)
            for expected in ["career_mcp", "resume_agent", "resume_render", "resume_cli"]:
                self.assertIn(f"Forbidden import '{expected}'", result.stdout)
            self.assertIn("Possible solution", result.stdout)
        finally:
            shutil.rmtree(temp)

    def test_raw_sql_public_api_is_hard_blocked_even_though_store_owns_sql_internals(self):
        temp = make_temp_repo()
        try:
            (temp / "career-store" / "store.py").write_text(
                "def executeSql(sql, params=None):\n"
                "    return []\n"
                "def runQuery(query):\n"
                "    return []\n",
                encoding="utf-8",
            )
            result = run_guardrail(temp)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("executeSql", result.stdout)
            self.assertIn("runQuery", result.stdout)
            self.assertIn("Raw SQL", result.stdout)
        finally:
            shutil.rmtree(temp)

    def test_prompting_rendering_and_resume_mutation_are_hard_blocked(self):
        temp = make_temp_repo()
        try:
            (temp / "career-store" / "store.py").write_text(
                "from pathlib import Path\n"
                "def askUser(topic):\n"
                "    return input(topic)\n"
                "def upsertFact(fact):\n"
                "    renderMarkdown(fact)\n"
                "    Path('resume/base.json').write_text('{}')\n",
                encoding="utf-8",
            )
            result = run_guardrail(temp)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Natural-language questioning", result.stdout)
            self.assertIn("Rendering behavior", result.stdout)
            self.assertIn("resume/base.json or resume/working.json", result.stdout)
        finally:
            shutil.rmtree(temp)

    def test_silent_verification_promotion_is_hard_blocked(self):
        temp = make_temp_repo()
        try:
            (temp / "career-store" / "store.py").write_text(
                "def verifyFact(fact):\n"
                "    if fact['verification_state'] == 'inferred':\n"
                "        fact['verification_state'] = 'user_verified'\n"
                "    return fact\n",
                encoding="utf-8",
            )
            result = run_guardrail(temp)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("inferred-to-user_verified", result.stdout)
            self.assertIn("confirmation", result.stdout)
        finally:
            shutil.rmtree(temp)

    def test_manifest_surface_drift_is_hard_blocked(self):
        temp = make_temp_repo()
        try:
            manifest_path = temp / "career-store" / "store_surface.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["public_api"]["functions"].append("executeSql")
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            result = run_guardrail(temp)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Declared public functions differ", result.stdout)
            self.assertIn("executeSql", result.stdout)
        finally:
            shutil.rmtree(temp)


if __name__ == "__main__":
    unittest.main()
