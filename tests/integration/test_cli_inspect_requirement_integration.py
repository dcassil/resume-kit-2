"""Integration coverage for persisted-only requirement inspection."""

from __future__ import annotations

import importlib
import json
import tempfile
import unittest
from pathlib import Path

from career_store import openCareerStore


def load_cli():
    return importlib.import_module("resume_cli")


def run_cli(module, argv: list[str], cwd: Path):
    return module.main(argv=argv, cwd=cwd)


class ResumeCliInspectRequirementIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cli = load_cli()
        self.tempdir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tempdir.name)
        run_cli(self.cli, ["init"], self.workspace)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_fresh_workspace_requirement_inspect_returns_no_data_not_fabricated_state(self) -> None:
        result = run_cli(self.cli, ["inspect", "requirement", "req_react"], self.workspace)

        self.assertEqual(result["status"], "no_data", result)
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(result["reason"], "missing_match_report")
        self.assertNotIn("resolution_state", result)
        self.assertNotIn("exact_match", json.dumps(result, sort_keys=True))

    def test_requirement_inspect_states_are_subset_of_persisted_match_states(self) -> None:
        store = openCareerStore(str(self.workspace / "data" / "career.db"))
        store.upsertFact(
            {
                "fact_id": "fact_react",
                "type": "skill",
                "text": "React production applications.",
                "normalized_terms": ["react"],
                "verification_state": "source_stated",
            },
            {"source": "resume", "text": "React production applications.", "evidence_id": "ev_react"},
            source="resume",
            policy={},
        )
        match_result = {
            "schema_version": "match-result.v1",
            "match_id": "match_inspect",
            "requirement_results": [
                {
                    "requirement_id": "req_react",
                    "classification": "required",
                    "concept": "React",
                    "source_text": "Strong React experience.",
                    "normalized_terms": ["react"],
                    "resolution_state": "exact_match",
                    "matched_fact_ids": ["fact_react"],
                    "evidence": [{"source": "resume", "fact_id": "fact_react", "terms": ["react"]}],
                },
                {
                    "requirement_id": "req_graphql",
                    "classification": "preferred",
                    "concept": "GraphQL",
                    "source_text": "GraphQL API experience.",
                    "normalized_terms": ["graphql"],
                    "resolution_state": "unknown",
                    "matched_fact_ids": [],
                    "evidence": [],
                },
            ],
            "requirements": [],
        }
        (self.workspace / "reports" / "match.json").write_text(json.dumps(match_result), encoding="utf-8")

        inspected = [
            run_cli(self.cli, ["inspect", "requirement", "req_react"], self.workspace),
            run_cli(self.cli, ["inspect", "requirement", "req_graphql"], self.workspace),
        ]
        persisted_states = {item["resolution_state"] for item in match_result["requirement_results"]}
        inspect_states = {item["resolution_state"] for item in inspected if item.get("status") == "ok"}

        self.assertTrue(inspect_states <= persisted_states)
        react = inspected[0]
        self.assertEqual(react["resolution_state"], "exact_match")
        self.assertEqual(react["supporting_fact_ids"], ["fact_react"])
        self.assertEqual(react["supporting_facts"][0]["fact"]["fact_id"], "fact_react")
        self.assertTrue(react["supporting_evidence_refs"])


if __name__ == "__main__":
    unittest.main()
