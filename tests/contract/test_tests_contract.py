"""Contract tests for the test-suite layout and gate manifest."""

from __future__ import annotations

import json
import subprocess
import sys
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
        for command_name in ["boundary", "fixtures", "contract_current", "contract_tdd", "future_contract", "smoke", "main", "guardrails"]:
            self.assertIn(command_name, commands)
            self.assertTrue(commands[command_name].startswith("python3"))

    def test_render_gate_integration_and_e2e_modules_are_bridged_into_current_gate(self):
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "unittest",
                "tests.integration.test_cli_render_artifacts_integration",
                "tests.e2e.test_render_overflow_round_trip_e2e",
            ],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_resume_ingest_constructor_unit_module_is_bridged_into_current_gate(self):
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "unittest",
                "tests.unit.test_canonical_resume_from_extraction_unit",
            ],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_resume_ingest_fact_proposal_integration_module_is_bridged_into_current_gate(self):
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "unittest",
                "tests.integration.test_resume_ingest_fact_proposals_integration",
            ],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_job_ingest_modes_integration_module_is_bridged_into_current_gate(self):
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "unittest",
                "tests.integration.test_job_ingest_modes_integration",
            ],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_cli_match_decision_integration_module_is_bridged_into_current_gate(self):
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "unittest",
                "tests.integration.test_cli_match_decision_integration",
            ],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_cli_inspect_requirement_integration_module_is_bridged_into_current_gate(self):
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "unittest",
                "tests.integration.test_cli_inspect_requirement_integration",
            ],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_resume_cli_resolution_context_unit_module_is_bridged_into_current_gate(self):
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "unittest",
                "tests.unit.test_resume_cli_resolution_context_unit",
            ],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_cli_resolve_interactive_integration_module_is_bridged_into_current_gate(self):
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "unittest",
                "tests.integration.test_cli_resolve_interactive_integration",
            ],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_resume_cli_domain_regrowth_boundary_module_is_bridged_into_current_gate(self):
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "unittest",
                "tests.boundary.test_resume_cli_domain_regrowth",
            ],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout)


if __name__ == "__main__":
    unittest.main()
