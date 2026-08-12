"""Contract tests for stable fixture inputs and expected observations."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "fixtures"
MANIFEST = json.loads((FIXTURES / "fixture_manifest.json").read_text(encoding="utf-8"))


class FixturesContractTests(unittest.TestCase):
    def test_required_directories_exist(self):
        for directory in MANIFEST["required_directories"]:
            with self.subTest(directory=directory):
                self.assertTrue((FIXTURES / directory).is_dir())

    def test_resume_fixture_contains_required_truth_and_excludes_unsupported_truth(self):
        spec = MANIFEST["resume_fixture"]
        text = (FIXTURES / spec["path"]).read_text(encoding="utf-8")
        lowered = text.lower()
        for required in spec["must_include"]:
            self.assertIn(required.lower(), lowered)
        for forbidden in spec["must_not_include"]:
            self.assertNotIn(forbidden.lower(), lowered)
        self.assertRegex(text, r"[\u201c\u201d\u2018\u2019]")
        self.assertIn("\u00a0", text)
        self.assertIn("\u25e6", text)
        self.assertIn("2013 to Dec 2017", text)

    def test_job_fixtures_contain_required_and_preferred_terms(self):
        for job in MANIFEST["job_fixtures"]:
            with self.subTest(job=job["id"]):
                text = (FIXTURES / job["path"]).read_text(encoding="utf-8").lower()
                self.assertIn("required", text)
                self.assertIn("preferred", text)
                for term in [job["title"], *job["required_terms"], *job["preferred_terms"]]:
                    self.assertIn(term.lower(), text)

    def test_answer_fixtures_are_exact_and_stable(self):
        for answer in MANIFEST["answer_fixtures"]:
            with self.subTest(answer=answer["id"]):
                text = (FIXTURES / answer["path"]).read_text(encoding="utf-8").strip()
                self.assertEqual(text, answer["exact_text"])

    def test_invalid_operations_cover_required_honesty_failures_and_target_known_paths(self):
        reasons = set()
        canonical_paths = set(MANIFEST["canonical_paths"])
        for rel in MANIFEST["invalid_operations"]:
            with self.subTest(operation=rel):
                operation = json.loads((FIXTURES / rel).read_text(encoding="utf-8"))
                self.assertEqual(operation["expected_status"], "rejected")
                self.assertIn(operation["target_path"], canonical_paths)
                reasons.add(operation["expected_reason"])
        self.assertEqual(
            reasons,
            {
                "unsupported_scale",
                "unsupported_management_scope",
                "title_inflation",
                "years_inflation",
                "related_skill_overreach",
            },
        )

    def test_expected_snapshots_are_reviewed_contract_artifacts(self):
        self.assertEqual(len(MANIFEST["expected_snapshots"]), 13)
        for rel in MANIFEST["expected_snapshots"]:
            with self.subTest(snapshot=rel):
                snapshot = json.loads((FIXTURES / rel).read_text(encoding="utf-8"))
                self.assertTrue(snapshot["reviewed"])
                self.assertEqual(snapshot["schema_version"], "expected-snapshot.v1")
                self.assertEqual(snapshot["config_hash"], MANIFEST["config_hash"])
                self.assertTrue(snapshot["expected_observations"])


if __name__ == "__main__":
    unittest.main()
