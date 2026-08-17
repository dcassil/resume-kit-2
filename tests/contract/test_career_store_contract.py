"""Contract-first tests for the future career_store package."""

from __future__ import annotations

import asyncio
import importlib
import inspect
import json
import sqlite3
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

EXPECTED_MIGRATIONS = [
    "001_initial",
    "002_section_6_fact_columns",
    "003_jobs_table_backfill",
    "004_match_relationship_columns",
    "005_enum_value_remap",
    "006_fact_merge_redirects",
    "007_relationship_confirmation_columns",
    "008_interactions_table",
    "009_conflict_lifecycle",
]


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


def interpretation_proposal(fact_id: str, text: str = "Yes, confirmed.") -> dict:
    return {
        "factId": fact_id,
        "outcome": "affirmed",
        "provenance": [{"source": "user_answer", "text": text}],
    }


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
                "getMigrationState",
                "mergeFacts",
                "confirmRelationship",
                "recordInteraction",
                "listInteractions",
                "adjudicateConflict",
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
        self.assertEqual(VERIFICATION_STATES, {"source_stated", "user_verified", "imported", "inferred", "unknown"})
        self.assertTrue({"alias", "equivalent", "related", "contradicts"} <= RELATIONSHIP_TYPES)
        self.assertEqual(
            RESOLUTION_STATES,
            {
                "exact_match",
                "alias_match",
                "verified_fact_match",
                "related_match",
                "possible_match",
                "unknown",
                "explicitly_missing",
                "not_applicable",
            },
        )

    def test_effective_store_enum_sets_match_shared_dtos_where_named_same(self):
        career_store = load_store_module(self)
        resume_core = importlib.import_module("resume_core")
        store_module = importlib.import_module("career_store.store")
        verification_states = {state.value for state in resume_core.VerificationState}
        resolution_states = {state.value for state in resume_core.ResolutionState}
        relationship_types = {"alias", "related", "parent", "child", "equivalent", "contradicts"}

        self.assertEqual({state.value for state in career_store.VerificationState}, verification_states)
        self.assertEqual(store_module._VERIFICATION_STATES, verification_states)
        self.assertEqual({state.value for state in career_store.ResolutionState}, resolution_states)
        self.assertEqual(store_module._RESOLUTION_STATES, resolution_states)
        self.assertEqual({state.value for state in career_store.RelationshipType}, relationship_types)
        self.assertEqual(store_module._RELATIONSHIP_TYPES, relationship_types)

    def test_manifest_defines_safe_contracts_for_every_surface(self):
        surfaces = {surface["name"]: surface for surface in SURFACE["surfaces"]}
        self.assertEqual(set(surfaces), set(PUBLIC_FUNCTIONS))
        for name, surface in surfaces.items():
            with self.subTest(surface=name):
                self.assertIn("input_contract", surface)
                self.assertIn("output_contract", surface)
                required_fields = set(surface["output_contract"]["required_fields"])
                if name == "getMigrationState":
                    self.assertEqual(
                        required_fields,
                        {"schema_version", "database_path", "applied_migrations", "pending_migrations", "status", "metadata"},
                    )
                else:
                    self.assertTrue({"schema_version", "status", "audit"} <= required_fields)
                self.assertIn("must_not_include", surface["output_contract"])


class CareerStoreSchemaStateContractTests(unittest.TestCase):
    def test_fresh_database_state_returns_all_applied_none_pending(self):
        module = load_store_module(self)
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "career.db"
            store = maybe_await(module.openCareerStore(str(database_path), clock=lambda: "2026-01-01T00:00:00Z"))
            state = maybe_await(store.getMigrationState())
            self.assertIsInstance(state, module.MigrationState)
            self.assertEqual(state.schema_version, "career-store.v1")
            self.assertEqual(state.database_path, str(database_path))
            self.assertEqual(state.applied_migrations, EXPECTED_MIGRATIONS)
            self.assertEqual(state.pending_migrations, [])
            self.assertEqual(state.status, "ok")
            self.assertEqual(state.metadata["user_version"], 9)
            with sqlite3.connect(database_path) as conn:
                rows = conn.execute("SELECT id, applied_at FROM schema_migrations ORDER BY id").fetchall()
                self.assertEqual(rows, [(migration_id, "2026-01-01T00:00:00Z") for migration_id in EXPECTED_MIGRATIONS])

    def test_reopen_is_idempotent(self):
        module = load_store_module(self)
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "career.db"
            first = maybe_await(module.openCareerStore(str(database_path), clock=lambda: "2026-01-01T00:00:00Z"))
            first_state = maybe_await(first.getMigrationState())
            with sqlite3.connect(database_path) as conn:
                before_schema_rows = conn.execute("SELECT id, applied_at FROM schema_migrations ORDER BY id").fetchall()
                before_legacy_rows = conn.execute("SELECT migration_id, schema_version, applied_at FROM migrations ORDER BY migration_id").fetchall()
                before_version = conn.execute("PRAGMA user_version").fetchone()[0]
            second = maybe_await(module.openCareerStore(str(database_path), clock=lambda: "2026-02-02T00:00:00Z"))
            second_state = maybe_await(second.getMigrationState())
            with sqlite3.connect(database_path) as conn:
                after_schema_rows = conn.execute("SELECT id, applied_at FROM schema_migrations ORDER BY id").fetchall()
                after_legacy_rows = conn.execute("SELECT migration_id, schema_version, applied_at FROM migrations ORDER BY migration_id").fetchall()
                after_version = conn.execute("PRAGMA user_version").fetchone()[0]
            self.assertEqual(second_state, first_state)
            self.assertEqual(after_schema_rows, before_schema_rows)
            self.assertEqual(after_legacy_rows, before_legacy_rows)
            self.assertEqual(after_version, before_version)

    def test_unsupported_schema_version_fails_open_with_typed_error(self):
        module = load_store_module(self)
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "career.db"
            with sqlite3.connect(database_path) as conn:
                conn.execute("PRAGMA user_version = 999")
            with self.assertRaises(module.IncompatibleSchemaVersionError) as raised:
                maybe_await(module.openCareerStore(str(database_path), clock=lambda: "2026-01-01T00:00:00Z"))
            self.assertEqual(raised.exception.found, 999)
            self.assertEqual(raised.exception.supported, 9)


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
        self.assertEqual(matches["matches"][0]["requirement_id"], "req_aws")
        self.assertEqual(matches["matches"][0]["fact_id"], azure["fact_id"])
        self.assertEqual(matches["matches"][0]["matchType"], "related_match")
        self.assertEqual(matches["matches"][0]["resolution_state"], "related_match")
        self.assertEqual(matches["matches"][0]["viaRelationships"][0]["type"], "related")
        self.assertEqual(matches["matches"][0]["viaRelationships"][0]["confirmationStatus"], "unconfirmed")
        self.assertEqual(matches["unresolved"][0]["requirement_id"], "req_aws")
        self.assertEqual(matches["unresolved"][0]["resolution_state"], "related_match")
        states = {
            candidate["matchType"]
            for match in matches["matches"]
            for candidate in match["supporting_facts"]
        } | {match["matchType"] for match in matches["matches"]}
        self.assertNotIn("exact_match", states)
        self.assertNotIn("alias_match", states)

    def test_compiled_dictionary_pairs_do_not_match_without_stored_relationships(self):
        cases = [
            ("System design", ["system design"], "API architecture", ["api architecture"]),
            ("Amazon Web Services", ["amazon web services"], "AWS", ["aws"]),
            ("GQL", ["gql"], "GraphQL", ["graphql"]),
            ("NodeJS", ["nodejs"], "Node", ["node"]),
            ("PostgreSQL", ["postgresql"], "Postgres", ["postgres"]),
        ]
        for fact_text, fact_terms, requirement_concept, requirement_terms in cases:
            with self.subTest(fact_text=fact_text, requirement_concept=requirement_concept):
                store = open_isolated_store(self)
                maybe_await(
                    store.upsertFact(
                        {**SOURCE_FACT, "text": fact_text, "normalized_terms": fact_terms},
                        {"source": "resume", "text": fact_text},
                        source="resume",
                        policy={},
                    )
                )
                matches = maybe_await(
                    store.findCandidateMatches(
                        [
                            {
                                "requirement_id": "req_dictionary_regression",
                                "concept": requirement_concept,
                                "normalized_terms": requirement_terms,
                            }
                        ],
                        policy={},
                    )
                )

                self.assertEqual(matches["matches"], [])
                self.assertEqual(matches["unresolved"][0]["requirement_id"], "req_dictionary_regression")
                self.assertEqual(matches["unresolved"][0]["resolution_state"], "unknown")

    def test_user_verified_direct_terms_emit_verified_candidate_without_relationship_path(self):
        fact = maybe_await(
            self.store.upsertFact(
                {**SOURCE_FACT, "text": "React", "normalized_terms": ["react"], "verification_state": "user_verified"},
                {"source": "user_answer", "text": "React"},
                source="user_answer",
                policy={"explicit_confirmation": True},
            )
        )

        matches = maybe_await(
            self.store.findCandidateMatches(
                [{"requirement_id": "req_react", "concept": "React", "normalized_terms": ["react"]}],
                policy={},
            )
        )

        candidate = matches["matches"][0]["supporting_facts"][0]
        self.assertEqual(candidate["factId"], fact["fact_id"])
        self.assertEqual(candidate["matchType"], "verified_fact_match")
        self.assertEqual(candidate["viaRelationships"], [])
        self.assertEqual(candidate["terms"], ["react"])

    def test_conflicting_claims_are_returned_without_overwriting_history(self):
        six = maybe_await(
            self.store.upsertFact(
                {**SOURCE_FACT, "text": "AWS, six years", "normalized_terms": ["aws", "six years"], "verification_state": "user_verified"},
                {"source": "user_answer", "text": "six years of AWS"},
                source="user_answer",
                policy={"explicit_confirmation": True},
            )
        )
        same_fact = maybe_await(
            self.store.findConflicts({"text": "AWS, ten years", "normalized_terms": ["aws", "ten years"], "fact_id": six["fact_id"]})
        )
        conflicts = maybe_await(
            self.store.findConflicts({"text": "AWS, ten years", "normalized_terms": ["aws", "ten years"], "fact_id": "fact_competing"})
        )
        self.assertEqual(same_fact["conflicts"], [])
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

    def test_write_paths_reject_removed_drifted_values_with_typed_errors(self):
        rejected = maybe_await(
            self.store.upsertFact(
                {**SOURCE_FACT, "text": "Conflicted drift", "normalized_terms": ["conflicted"], "verification_state": "conflicted"},
                SOURCE_EVIDENCE,
                source="resume",
                policy={},
            )
        )
        self.assertEqual(rejected["status"], "error")
        self.assertEqual(rejected["mutation_status"], "rejected")
        self.assertEqual(rejected["errors"][0]["code"], "invalid_verification_state")
        self.assertEqual(rejected["errors"][0]["field_path"], "verification_state")
        self.assertNotIn("conflicted", rejected["errors"][0]["allowed_values"])

        fact = maybe_await(self.store.upsertFact(SOURCE_FACT, SOURCE_EVIDENCE, source="resume", policy={}))
        verify_rejected = maybe_await(
            self.store.verifyFact(
                fact["fact_id"],
                "explicitly_missing",
                confirmation=interpretation_proposal(fact["fact_id"]),
                source="user_answer",
            )
        )
        self.assertEqual(verify_rejected["status"], "error")
        self.assertEqual(verify_rejected["errors"][0]["code"], "invalid_verification_state")

        match_rejected = maybe_await(self.store.recordJobMatch("job_a", "req_react", [fact["fact_id"]], "conflicted"))
        self.assertEqual(match_rejected["status"], "error")
        self.assertEqual(match_rejected["mutation_status"], "rejected")
        self.assertEqual(match_rejected["errors"][0]["code"], "invalid_resolution_state")

    def test_parent_child_relationship_types_are_accepted_by_effective_store(self):
        parent = maybe_await(
            self.store.upsertFact(
                {**SOURCE_FACT, "text": "Frontend architecture", "normalized_terms": ["frontend architecture"]},
                {"source": "resume", "text": "Frontend architecture"},
                source="resume",
                policy={},
            )
        )
        child = maybe_await(
            self.store.upsertFact(
                {**SOURCE_FACT, "text": "React", "normalized_terms": ["react"]},
                SOURCE_EVIDENCE,
                source="resume",
                policy={},
            )
        )
        for relationship_type in ("parent", "child"):
            with self.subTest(relationship_type=relationship_type):
                result = maybe_await(
                    self.store.addRelationship(
                        parent["fact_id"],
                        child["fact_id"],
                        relationship_type,
                        evidence_or_rationale={"text": relationship_type},
                        policy={},
                    )
                )
                self.assertIn(result["status"], {"created", "updated"})


if __name__ == "__main__":
    unittest.main()
