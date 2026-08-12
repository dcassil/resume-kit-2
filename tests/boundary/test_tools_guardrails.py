"""Executable boundary tests for tools guardrails."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GUARDRAIL = ROOT / "tools" / "tools_guardrails.py"


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
    temp = Path(tempfile.mkdtemp(prefix="tools-guardrail-"))
    shutil.copytree(ROOT / "tools", temp / "tools")
    return temp


class ToolsGuardrailTests(unittest.TestCase):
    def test_current_repo_guardrails_pass(self):
        result = run_guardrail(ROOT)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("guardrails passed", result.stdout)

    def test_undocumented_primary_tool_is_hard_blocked(self):
        temp = make_temp_repo()
        try:
            (temp / "tools" / "new_guardrails.py").write_text("#!/usr/bin/env python3\n", encoding="utf-8")
            result = run_guardrail(temp)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("undocumented", result.stdout.lower())
            self.assertIn("new_guardrails.py", result.stdout)
        finally:
            shutil.rmtree(temp)

    def test_release_expectation_drift_is_hard_blocked(self):
        temp = make_temp_repo()
        try:
            manifest_path = temp / "tools" / "tool_manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["release_blocking_expectations"].remove("hallucination_rejection")
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            result = run_guardrail(temp)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Release-blocking expectations", result.stdout)
            self.assertIn("hallucination_rejection", result.stdout)
        finally:
            shutil.rmtree(temp)

    def test_hidden_scoring_logic_is_hard_blocked(self):
        temp = make_temp_repo()
        try:
            bad_tool = temp / "tools" / "bad_guardrails.py"
            bad_tool.write_text("def calculate_score(requirements):\n    return 100\n", encoding="utf-8")
            manifest_path = temp / "tools" / "tool_manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["tools"].append(
                {
                    "path": "tools/bad_guardrails.py",
                    "kind": "release_check",
                    "supports_gate": ["pr"],
                    "invokes_surfaces": ["none"],
                    "reads": [],
                    "writes": [],
                    "release_blocking": True,
                    "description": "Bad hidden logic tool"
                }
            )
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            result = run_guardrail(temp)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("hidden product behavior", result.stdout)
        finally:
            shutil.rmtree(temp)

    def test_non_blocking_tool_entry_is_hard_blocked(self):
        temp = make_temp_repo()
        try:
            manifest_path = temp / "tools" / "tool_manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["tools"][0]["release_blocking"] = False
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            result = run_guardrail(temp)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("release_blocking=true", result.stdout)
        finally:
            shutil.rmtree(temp)

    def test_unconditional_success_pattern_is_hard_blocked(self):
        temp = make_temp_repo()
        try:
            bad_tool = temp / "tools" / "always_green_guardrails.py"
            bad_tool.write_text("def main():\n    return 0\n", encoding="utf-8")
            manifest_path = temp / "tools" / "tool_manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["tools"].append(
                {
                    "path": "tools/always_green_guardrails.py",
                    "kind": "release_check",
                    "supports_gate": ["pr"],
                    "invokes_surfaces": ["none"],
                    "reads": [],
                    "writes": [],
                    "release_blocking": True,
                    "description": "Bad always green tool"
                }
            )
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            result = run_guardrail(temp)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("unconditionally returns success", result.stdout)
        finally:
            shutil.rmtree(temp)


if __name__ == "__main__":
    unittest.main()
