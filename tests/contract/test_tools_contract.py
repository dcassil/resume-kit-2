"""Contract tests for local tools metadata and release-gate expectations."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
MANIFEST = json.loads((TOOLS / "tool_manifest.json").read_text(encoding="utf-8"))


class ToolsContractTests(unittest.TestCase):
    def test_manifest_declares_required_capabilities(self):
        self.assertEqual(
            set(MANIFEST["required_capabilities"]),
            {
                "test_runner_wrappers",
                "fixture_validators",
                "snapshot_review_helpers",
                "architecture_import_checkers",
                "migration_checkers",
                "release_checks",
                "audit_validators",
                "render_parse_back_validators",
            },
        )

    def test_release_blocking_expectations_are_declared(self):
        expectations = set(MANIFEST["release_blocking_expectations"])
        for expected in [
            "build_package_import_success",
            "pr_gate_tests",
            "full_smoke_test",
            "hallucination_rejection",
            "base_immutability",
            "deterministic_scoring",
            "render_validation",
            "audit_completeness",
            "full_e2e_for_release_candidate",
            "job_b_persistent_learning",
            "recovery_tests",
            "migration_upgrade_tests",
        ]:
            self.assertIn(expected, expectations)

    def test_primary_guardrail_tools_are_documented_and_release_blocking(self):
        documented = {entry["path"]: entry for entry in MANIFEST["tools"]}
        primary_guardrails = {
            str(path.relative_to(ROOT))
            for path in TOOLS.glob("*_guardrails.py")
            if not path.name.startswith("watch_")
        }
        self.assertTrue(primary_guardrails <= set(documented))
        for path in primary_guardrails:
            with self.subTest(path=path):
                entry = documented[path]
                self.assertTrue(entry["release_blocking"])
                self.assertTrue(entry["supports_gate"])
                self.assertTrue(entry["invokes_surfaces"])
                self.assertIn("reads", entry)
                self.assertIn("writes", entry)
                self.assertTrue(entry["description"])

    def test_every_documented_tool_exists(self):
        for entry in MANIFEST["tools"]:
            with self.subTest(path=entry["path"]):
                self.assertTrue((ROOT / entry["path"]).exists())

    def test_pr_gate_command_is_the_canonical_completion_command(self):
        self.assertEqual(MANIFEST["tools"][0]["path"], "tools/run_gate.py")
        self.assertEqual(MANIFEST["tools"][0]["supports_gate"], ["pr", "future_contract"])

    def test_pr_gate_delegates_to_current_test_runner(self):
        temp = Path(tempfile.mkdtemp(prefix="run-gate-contract-"))
        try:
            tools = temp / "tools"
            tools.mkdir()
            shutil.copy2(TOOLS / "run_gate.py", tools / "run_gate.py")
            marker = temp / "marker.txt"
            (tools / "run_tests.py").write_text(
                "\n".join(
                    [
                        "import sys",
                        "from pathlib import Path",
                        f"Path({str(marker)!r}).write_text(' '.join(sys.argv[1:]), encoding='utf-8')",
                        "raise SystemExit(7)",
                    ]
                ),
                encoding="utf-8",
            )

            result = subprocess.run(
                [sys.executable, str(tools / "run_gate.py"), "--pr", "--root", str(temp)],
                cwd=temp,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )

            self.assertEqual(result.returncode, 7, result.stdout)
            self.assertEqual(marker.read_text(encoding="utf-8"), f"--root {temp.resolve()}")
            self.assertIn("Running PR gate", result.stdout)
        finally:
            shutil.rmtree(temp)

    def test_future_contract_gate_delegates_to_current_test_runner(self):
        temp = Path(tempfile.mkdtemp(prefix="run-gate-future-contract-"))
        try:
            tools = temp / "tools"
            tools.mkdir()
            shutil.copy2(TOOLS / "run_gate.py", tools / "run_gate.py")
            marker = temp / "marker.txt"
            (tools / "run_tests.py").write_text(
                "\n".join(
                    [
                        "import sys",
                        "from pathlib import Path",
                        f"Path({str(marker)!r}).write_text(' '.join(sys.argv[1:]), encoding='utf-8')",
                        "raise SystemExit(7)",
                    ]
                ),
                encoding="utf-8",
            )

            result = subprocess.run(
                [sys.executable, str(tools / "run_gate.py"), "--future-contract", "--root", str(temp)],
                cwd=temp,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )

            self.assertEqual(result.returncode, 7, result.stdout)
            self.assertEqual(marker.read_text(encoding="utf-8"), f"--root {temp.resolve()} --future-contract")
            self.assertIn("Running future contract gate", result.stdout)
        finally:
            shutil.rmtree(temp)


if __name__ == "__main__":
    unittest.main()
