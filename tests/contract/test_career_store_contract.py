"""Contract-first tests for the future career_store package."""

from __future__ import annotations

import asyncio
import importlib
import inspect
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SURFACE = json.loads((ROOT / "career-store" / "store_surface.json").read_text(encoding="utf-8"))
PUBLIC_FUNCTIONS = tuple(SURFACE["public_api"]["functions"])
PUBLIC_TYPES = tuple(SURFACE["public_api"]["types"])
VERIFICATION_STATES = set(SURFACE["verification_states"])
RELATIONSHIP_TYPES = set(SURFACE["relationship_types"])
RESOLUTION_STATES = set(SURFACE["resolution_states"])


SOURCE_FACT = {
    "type": "skill",
    "text": "React",
    "normalized_terms": ["react"],
    "verification_state": "source_stated",
}

SOURCE_EVIDENCE = {
    "source": "resume",
    "source_id": "resume-main",
    "text": "React, TypeScript, Node.js",
}


def maybe_await(value):
    if inspect.isawaitable(value):
        return asyncio.run(value)
    return value


def load_store_module(test_case: unittest.TestCase):
    try:
        module = importlib.import_module("career_store")
    except ModuleNotFoundError as exc:
        test_case.fail(
            "Expected importable package 'career_store'. Implement a durable store factory and the public service "
            "surfaces from career-store/TEST_SPEC.md and career-store/store_surface.json."
        )
        raise exc
    for type_name in PUBLIC_TYPES:
        test_case.assertTrue(hasattr(module, type_name), f"career_store must expose {type_name}.")
    factory = getattr(module, "openCareerStore", None)
    test_case.assertTrue(callable(factory), "career_store must expose openCareerStore(database_path, clock=None).")
    return module


def open_isolated_store(test_case: unittest.TestCase):
    module = load_store_module(test_case)
    directory = tempfile.TemporaryDirectory()
    test_case.addCleanup(directory.cleanup)
    store = maybe_await(module.openCareerStore(str(Path(directory.name) / "career.db"), clock=lambda: "2026-01-01T00:00:00Z"))
    for function_name in PUBLIC_FUNCTIONS:
        test_case.assertTrue(callable(getattr(store, function_name, None)), f"store must expose {function_name}().")
    return store


def serialized(result: dict) -> str:
    return json.dumps(result, sort_keys=True).lower()


class CareerStoreSurfaceManifestTests(unittest.TestCase):
    def test_manifest_declares_exact_public_functions_and_types(self):
        self.assertEqual(
            PUBLIC_FUNCTIONS,
            (
                "searchFacts",
                "getFact",
                "upsertFact",
                "verifyFact",
                "addEvidence",
                "addRelationship",
                "findCandidateMatches",
                "recordJobMatch",
                "findConflicts",
            ),
        )
        self.assertEqual(
            set(PUBLIC_TYPES),
            {
                "CareerFact",
                "Evidence",
                "FactRelationship",
                "VerificationState",
                "ConflictRecord",
                "JobAssociation",
                "TransactionResult",
                "MigrationState",
            },
        )

    def test_manifest_keeps_truth_states_distinct(self):
        self.assertTrue({"source_stated", "user_verified", "inferred", "unknown", "explicitly_missing", "conflicted"} <= VERIFICATION_STATES)
        self.assertTrue({"alias", "equivalent", "related", "contradicts"} <= RELATIONSHIP_TYPES)
        self.assertTrue({"exact_match", "alias_match", "related_match", "possible_match", "unknown"} <= RESOLUTION_STATES)

    def test_manifest_defines_safe_contracts_for_every_surface(self):
        surfaces = {surface["name"]: surface for surface in SURFACE["surfaces"]}
        self.assertEqual(set(surfaces), set(PUBLIC_FUNCTIONS))
        for name, surface in surfaces.items():
            with self.subTest(surface=name):
                self.assertIn("input_contract", surface)
                self.assertIn("output_contract", surface)
                required_fields = set(surface["output_contract"]["required_fields"])
                self.assertTrue({"schema_version", "status", "audit"} <= required_fields)
                self.assertIn("must_not_include", surface["output_contract"])


class CareerStorePersistenceContractTests(unittest.TestCase):
    def setUp(self):
        self.store = open_isolated_store(self)

    def test_fact_upsert_persists_source_stated_fact_with_evidence(self):
        result = maybe_await(self.store.upsertFact(SOURCE_FACT, SOURCE_EVIDENCE, source="resume", policy={"allow_inferred_final": False}))
        self.assertIn(result.get("status"), {"created", "updated", "ok"})
        self.assertIn("fact_id", result)
        self.assertEqual(result.get("verification_state"), "source_stated")
        fetched = maybe_await(self.store.getFact(result["fact_id"]))
        text = serialized(fetched)
        self.assertIn("react", text)
        self.assertIn("evidence", text)
        self.assertNotRegex(text, r"\braw_sql|connection|traceback\b")

    def test_inferred_fact_cannot_be_silently_promoted_to_user_verified(self):
        created = maybe_await(
            self.store.upsertFact(
                {**SOURCE_FACT, "text": "AWS", "normalized_terms": ["aws"], "verification_state": "inferred"},
                {"source": "agent_proposal", "text": "possible AWS match"},
                source="agent_proposal",
                policy={"allow_inferred_final": False},
            )
        )
        result = maybe_await(self.store.verifyFact(created["fact_id"], "user_verified", confirmation=None, source="agent_proposal"))
        self.assertIn(result.get("status"), {"rejected", "error"})
        self.assertTrue(result.get("confirmation_required"))

    def test_related_relationship_does_not_become_equivalent_match_without_policy(self):
        azure = maybe_await(
            self.store.upsertFact(
                {**SOURCE_FACT, "text": "Azure", "normalized_terms": ["azure"]},
                {"source": "resume", "text": "Azure"},
                source="resume",
                policy={},
            )
        )
        aws = maybe_await(
            self.store.upsertFact(
                {**SOURCE_FACT, "text": "AWS", "normalized_terms": ["aws"], "verification_state": "unknown"},
                {"source": "job", "text": "AWS"},
                source="job",
                policy={},
            )
        )
        maybe_await(
            self.store.addRelationship(
                azure["fact_id"],
                aws["fact_id"],
                "related",
                evidence_or_rationale={"text": "both are cloud platforms"},
                policy={"requires_confirmation_for_equivalence": True},
            )
        )
        matches = maybe_await(
            self.store.findCandidateMatches(
                [{"requirement_id": "req_aws", "concept": "AWS", "normalized_terms": ["aws"]}],
                policy={"allow_related_as_equivalent": False},
            )
        )
        text = serialized(matches)
        self.assertIn("req_aws", text)
        self.assertNotIn("equivalent_match", text)

    def test_conflicting_claims_are_returned_without_overwriting_history(self):
        six = maybe_await(
            self.store.upsertFact(
                {**SOURCE_FACT, "text": "AWS, six years", "normalized_terms": ["aws", "six years"], "verification_state": "user_verified"},
                {"source": "user_answer", "text": "six years of AWS"},
                source="user_answer",
                policy={"explicit_confirmation": True},
            )
        )
        conflicts = maybe_await(
            self.store.findConflicts({"text": "AWS, ten years", "normalized_terms": ["aws", "ten years"], "fact_id": six["fact_id"]})
        )
        text = serialized(conflicts)
        self.assertIn("conflict", text)
        self.assertIn("six", text)
        self.assertIn("ten", text)

    def test_job_match_recording_does_not_mutate_resume_state_or_return_raw_database_handles(self):
        fact = maybe_await(self.store.upsertFact(SOURCE_FACT, SOURCE_EVIDENCE, source="resume", policy={}))
        result = maybe_await(self.store.recordJobMatch("job_a", "req_react", [fact["fact_id"]], "exact_match"))
        self.assertIn(result.get("status"), {"created", "updated", "ok"})
        text = serialized(result)
        self.assertNotRegex(text, r"\bresume_patch|working_resume|base_resume|raw_sql|connection\b")


if __name__ == "__main__":
    unittest.main()
