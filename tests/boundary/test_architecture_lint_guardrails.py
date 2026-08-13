"""Executable boundary tests for shared Python architecture lint."""

from __future__ import annotations

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
    temp = Path(tempfile.mkdtemp(prefix="architecture-lint-"))
    (temp / "resume-plugin").mkdir(parents=True)
    shutil.copy2(ROOT / "resume-plugin" / "plugin_surface.json", temp / "resume-plugin" / "plugin_surface.json")
    return temp


class ArchitectureLintGuardrailTests(unittest.TestCase):
    def test_private_cross_package_import_is_hard_blocked(self):
        temp = make_temp_repo()
        try:
            (temp / "resume-plugin" / "plugin.py").write_text(
                "from resume_core.domain import validateChange\n",
                encoding="utf-8",
            )
            result = run_guardrail(temp)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("reaches past the public package root", result.stdout)
            self.assertIn("from resume_core import Result", result.stdout)
        finally:
            shutil.rmtree(temp)

    def test_dynamic_cross_package_import_is_hard_blocked(self):
        temp = make_temp_repo()
        try:
            (temp / "resume-plugin" / "plugin.py").write_text(
                "import importlib\n"
                "domain = importlib.import_module('resume_core.domain')\n",
                encoding="utf-8",
            )
            result = run_guardrail(temp)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Dynamic import 'resume_core.domain'", result.stdout)
            self.assertIn("bypasses static package-boundary checks", result.stdout)
        finally:
            shutil.rmtree(temp)

    def test_wildcard_import_is_hard_blocked(self):
        temp = make_temp_repo()
        try:
            (temp / "resume-plugin" / "plugin.py").write_text(
                "from resume_core import *\n",
                encoding="utf-8",
            )
            result = run_guardrail(temp)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Wildcard imports hide the dependency graph", result.stdout)
        finally:
            shutil.rmtree(temp)

    def test_numeric_function_cap_is_hard_blocked(self):
        temp = make_temp_repo()
        try:
            body = "\n".join(f"    value += {index}" for index in range(141))
            (temp / "resume-plugin" / "plugin.py").write_text(
                "def oversized_adapter(value):\n"
                f"{body}\n"
                "    return value\n",
                encoding="utf-8",
            )
            result = run_guardrail(temp)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("over the 140-line cap", result.stdout)
            self.assertIn("Extract cohesive private helpers", result.stdout)
        finally:
            shutil.rmtree(temp)


if __name__ == "__main__":
    unittest.main()
