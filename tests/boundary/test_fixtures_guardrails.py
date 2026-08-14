"""Executable boundary tests for fixture guardrails."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GUARDRAIL = ROOT / "tools" / "fixtures_guardrails.py"


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
    temp = Path(tempfile.mkdtemp(prefix="fixtures-guardrail-"))
    shutil.copytree(ROOT / "fixtures", temp / "fixtures")
    return temp


class FixturesGuardrailTests(unittest.TestCase):
    def test_current_repo_guardrails_pass(self):
        result = run_guardrail(ROOT)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("guardrails passed", result.stdout)

    def test_resume_unsupported_truth_is_hard_blocked(self):
        temp = make_temp_repo()
        try:
            resume = temp / "fixtures" / "resumes" / "resume-main.txt"
            resume.write_text(resume.read_text(encoding="utf-8") + "\nAWS and GraphQL at global scale for 20 million users.\n", encoding="utf-8")
            result = run_guardrail(temp)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("unsupported truth 'AWS'", result.stdout)
            self.assertIn("20 million users", result.stdout)
            self.assertIn("Possible solution", result.stdout)
        finally:
            shutil.rmtree(temp)

    def test_answer_text_drift_is_hard_blocked(self):
        temp = make_temp_repo()
        try:
            (temp / "fixtures" / "answers" / "aws.txt").write_text("Yes, I have ten years of AWS.", encoding="utf-8")
            result = run_guardrail(temp)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Answer fixture text drifted", result.stdout)
        finally:
            shutil.rmtree(temp)

    def test_missing_invalid_operation_coverage_is_hard_blocked(self):
        temp = make_temp_repo()
        try:
            manifest_path = temp / "fixtures" / "fixture_manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["invalid_operations"] = [
                rel for rel in manifest["invalid_operations"] if "title-inflation" not in rel
            ]
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            result = run_guardrail(temp)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("title_inflation", result.stdout)
        finally:
            shutil.rmtree(temp)

    def test_snapshot_without_review_metadata_is_hard_blocked(self):
        temp = make_temp_repo()
        try:
            snapshot = temp / "fixtures" / "expected" / "run-manifest.json"
            data = json.loads(snapshot.read_text(encoding="utf-8"))
            del data["config_hash"]
            data["reviewed"] = False
            snapshot.write_text(json.dumps(data), encoding="utf-8")
            result = run_guardrail(temp)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("config_hash", result.stdout)
            self.assertIn("reviewed=true", result.stdout)
        finally:
            shutil.rmtree(temp)

    def test_snapshot_without_data_envelope_is_hard_blocked(self):
        temp = make_temp_repo()
        try:
            snapshot = temp / "fixtures" / "expected" / "run-manifest.json"
            data = json.loads(snapshot.read_text(encoding="utf-8"))
            del data["data"]
            snapshot.write_text(json.dumps(data), encoding="utf-8")
            result = run_guardrail(temp)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Expected snapshot is missing 'data'", result.stdout)
            self.assertIn("T-0012 expected snapshot envelope", result.stdout)
        finally:
            shutil.rmtree(temp)

    def test_snapshot_without_comment_is_hard_blocked(self):
        temp = make_temp_repo()
        try:
            snapshot = temp / "fixtures" / "expected" / "run-manifest.json"
            data = json.loads(snapshot.read_text(encoding="utf-8"))
            del data["comment"]
            snapshot.write_text(json.dumps(data), encoding="utf-8")
            result = run_guardrail(temp)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Expected snapshot is missing 'comment'", result.stdout)
            self.assertIn("T-0012 expected snapshot envelope", result.stdout)
        finally:
            shutil.rmtree(temp)

    def test_snapshot_null_data_without_deferral_comment_is_hard_blocked(self):
        temp = make_temp_repo()
        try:
            snapshot = temp / "fixtures" / "expected" / "run-manifest.json"
            data = json.loads(snapshot.read_text(encoding="utf-8"))
            data["data"] = None
            snapshot.write_text(json.dumps(data), encoding="utf-8")
            result = run_guardrail(temp)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("data=null without a comment explaining the deferral", result.stdout)
            self.assertIn("Populate data with structured snapshot contents", result.stdout)
        finally:
            shutil.rmtree(temp)

    def test_operation_targeting_unknown_path_is_hard_blocked(self):
        temp = make_temp_repo()
        try:
            operation = temp / "fixtures" / "operations" / "invalid-years-inflation.json"
            data = json.loads(operation.read_text(encoding="utf-8"))
            data["target_path"] = "/unknown/path"
            operation.write_text(json.dumps(data), encoding="utf-8")
            result = run_guardrail(temp)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("not in manifest canonical_paths", result.stdout)
        finally:
            shutil.rmtree(temp)


if __name__ == "__main__":
    unittest.main()
