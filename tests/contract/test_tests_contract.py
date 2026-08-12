"""Contract tests for the test-suite layout and gate manifest."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TESTS = ROOT / "tests"
MANIFEST = json.loads((TESTS / "suite_manifest.json").read_text(encoding="utf-8"))


class TestsSuiteContractTests(unittest.TestCase):
    def test_required_layout_exists(self):
        self.assertEqual(
            set(MANIFEST["required_layout"]),
            {"unit", "contract", "boundary", "integration", "smoke", "e2e", "fixtures", "snapshots"},
        )
        for directory in MANIFEST["required_layout"]:
            with self.subTest(directory=directory):
                self.assertTrue((TESTS / directory).is_dir())

    def test_required_gates_match_contract(self):
        self.assertEqual(
            set(MANIFEST["required_gates"]["pr"]),
            {"unit", "contract", "boundary", "deterministic_scoring_fixtures", "hallucination_rejection_fixtures"},
        )
        self.assertEqual(set(MANIFEST["required_gates"]["main"]), {"pr", "smoke"})
        self.assertEqual(set(MANIFEST["required_gates"]["release_candidate"]), {"main", "e2e", "renderer_parse_back", "migration_upgrade"})

    def test_release_blockers_are_encoded(self):
        blockers = set(MANIFEST["release_blockers"])
        for blocker in [
            "fabricated_skill_title_metric_years_responsibility_scale_or_outcome",
            "inferred_fact_treated_as_verified",
            "related_fact_treated_as_equivalent_without_relationship",
            "missing_provenance_for_generated_claim",
            "nondeterministic_official_score",
            "base_resume_mutation",
            "raw_sql_mcp_exposure",
            "renderer_semantic_mutation",
            "lost_learned_facts_between_jobs",
            "duplicate_questions_for_verified_facts",
            "false_resolution_of_unresolved_hard_requirement",
        ]:
            self.assertIn(blocker, blockers)

    def test_runner_commands_are_declared_for_current_and_future_gates(self):
        commands = MANIFEST["runner_commands"]
        for command_name in ["boundary", "fixtures", "contract_current", "contract_tdd", "guardrails"]:
            self.assertIn(command_name, commands)
            self.assertTrue(commands[command_name].startswith("python3"))


if __name__ == "__main__":
    unittest.main()
