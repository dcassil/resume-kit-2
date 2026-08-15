import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
for package_dir in ("resume-core", "career-store"):
    package_path = str(ROOT / package_dir)
    if package_path not in sys.path:
        sys.path.insert(0, package_path)

from career_store import openCareerStore  # noqa: E402
from career_store.migrations import MIGRATIONS  # noqa: E402
import career_store.conflict_lifecycle as conflict_lifecycle_module  # noqa: E402


FIXED_TIME = "2026-01-01T00:00:00Z"
USER_PROVENANCE = [{"source": "user_answer", "text": "Six years is the correct AWS claim."}]
AGENT_PROVENANCE = [
    {
        "source": "agent_proposal",
        "text": "Agent selected the six-year AWS claim.",
        "metadata": {"agent_id": "agent-1"},
    }
]


class CareerStoreConflictLifecycleUnitTests(unittest.TestCase):
    def test_schema_009_adds_lifecycle_columns_and_backfills_open_without_rewriting_claim_payloads(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "career.db"
            _build_pre_009_conflict_database(database_path)

            store = openCareerStore(str(database_path), clock=lambda: FIXED_TIME)
            state = store.getMigrationState()

            self.assertEqual(state.applied_migrations[-1], "009_conflict_lifecycle")
            self.assertEqual(state.metadata["user_version"], 9)
            with sqlite3.connect(database_path) as conn:
                conn.row_factory = sqlite3.Row
                columns = {row["name"]: row for row in conn.execute("PRAGMA table_info(conflicts)").fetchall()}
                row = conn.execute("SELECT * FROM conflicts WHERE conflict_id = ?", ("conflict_legacy",)).fetchone()

            self.assertEqual(columns["status"]["dflt_value"], "'open'")
            self.assertTrue({"resolution_provenance_json", "resolved_at", "winning_claim_ref"} <= set(columns))
            self.assertEqual(row["status"], "open")
            self.assertEqual(json.loads(row["fact_ids_json"]), ["fact_a", "fact_b"])
            self.assertEqual(row["reason"], "legacy contradiction")
            self.assertEqual(json.loads(row["evidence_ids_json"]), ["ev_a", "ev_b"])
            self.assertEqual(json.loads(row["metadata_json"]), {"existing": "six", "proposed": "ten"})

    def test_resolve_conflict_records_answer_interaction_and_preserves_both_claims(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = openCareerStore(str(Path(directory) / "career.db"), clock=lambda: FIXED_TIME)
            six, ten, conflict = _conflicting_aws_claims(store)
            six_evidence_before = store.getFact(six["fact_id"])["evidence"]
            ten_evidence_before = store.getFact(ten["fact_id"])["evidence"]

            result = store.adjudicateConflict(
                conflict["conflict_id"],
                {"status": "resolved", "winning_claim_ref": six["fact_id"]},
                USER_PROVENANCE,
            )

            self.assertEqual(result["status"], "updated")
            self.assertEqual(result["conflict"]["status"], "resolved")
            self.assertEqual(result["conflict"]["winning_claim_ref"], six["fact_id"])
            self.assertEqual(result["conflict"]["resolution_provenance"]["interaction_type"], "answer_recorded")
            self.assertEqual(result["conflict"]["metadata"], conflict["metadata"])
            self.assertEqual(store.getFact(six["fact_id"])["fact"]["text"], "AWS, six years")
            self.assertEqual(store.getFact(ten["fact_id"])["fact"]["text"], "AWS, ten years")
            self.assertEqual(store.getFact(six["fact_id"])["evidence"], six_evidence_before)
            self.assertEqual(store.getFact(ten["fact_id"])["evidence"], ten_evidence_before)
            self.assertEqual(store.getFact(six["fact_id"])["conflicts"][0]["status"], "resolved")
            self.assertEqual(store.getFact(ten["fact_id"])["conflicts"][0]["status"], "resolved")

            interactions = store.listInteractions({"subject_id": conflict["conflict_id"]})
            self.assertEqual([row["interaction_type"] for row in interactions["interactions"]], ["answer_recorded"])
            self.assertEqual(interactions["interactions"][0]["result_json"]["status"], "resolved")

    def test_dismiss_conflict_records_answer_interaction_without_winner(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = openCareerStore(str(Path(directory) / "career.db"), clock=lambda: FIXED_TIME)
            _, _, conflict = _conflicting_aws_claims(store)

            result = store.adjudicateConflict(conflict["conflict_id"], "dismissed", USER_PROVENANCE)

            self.assertEqual(result["status"], "updated")
            self.assertEqual(result["conflict"]["status"], "dismissed")
            self.assertIsNone(result["conflict"]["winning_claim_ref"])
            interactions = store.listInteractions({"subject_id": conflict["conflict_id"]})
            self.assertEqual(interactions["interactions"][0]["interaction_type"], "answer_recorded")
            self.assertEqual(interactions["interactions"][0]["result_json"]["status"], "dismissed")

    def test_identical_readjudication_is_idempotent_but_different_readjudication_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = openCareerStore(str(Path(directory) / "career.db"), clock=lambda: FIXED_TIME)
            six, ten, conflict = _conflicting_aws_claims(store)
            decision = {"status": "resolved", "winning_claim_ref": six["fact_id"]}

            first = store.adjudicateConflict(conflict["conflict_id"], decision, USER_PROVENANCE)
            repeated = store.adjudicateConflict(conflict["conflict_id"], decision, USER_PROVENANCE)
            conflicting = store.adjudicateConflict(
                conflict["conflict_id"],
                {"status": "resolved", "winning_claim_ref": ten["fact_id"]},
                USER_PROVENANCE,
            )

            self.assertEqual(first["status"], "updated")
            self.assertEqual(repeated["status"], "unchanged")
            self.assertEqual(repeated["mutation_status"], "unchanged")
            self.assertEqual(conflicting["status"], "error")
            self.assertEqual(conflicting["errors"][0]["code"], "conflicting_readjudication")
            interactions = store.listInteractions({"subject_id": conflict["conflict_id"]})
            self.assertEqual(len(interactions["interactions"]), 1)

    def test_user_adjudication_routes_verification_change_through_engine(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = openCareerStore(str(Path(directory) / "career.db"), clock=lambda: FIXED_TIME)
            six, _, conflict = _conflicting_aws_claims(store)
            calls = []
            original = conflict_lifecycle_module.evaluate_verification_transition

            def observed_transition(*args, **kwargs):
                calls.append(args)
                return original(*args, **kwargs)

            with patch.object(conflict_lifecycle_module, "evaluate_verification_transition", side_effect=observed_transition):
                result = store.adjudicateConflict(
                    conflict["conflict_id"],
                    {
                        "status": "resolved",
                        "winning_claim_ref": six["fact_id"],
                        "verification_state": "user_verified",
                    },
                    USER_PROVENANCE,
                )

            self.assertEqual(result["status"], "updated")
            self.assertEqual(result["verification_state"], "user_verified")
            self.assertEqual(store.getFact(six["fact_id"])["fact"]["verification_state"], "user_verified")
            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0][0:3], (six["fact_id"], "inferred", "user_verified"))
            self.assertEqual(calls[0][3].authorityKind, "user_affirmed_proposal")
            transition_evidence = [
                item
                for item in store.getFact(six["fact_id"])["evidence"]
                if item["metadata"].get("verification_transition", {}).get("newState") == "user_verified"
            ]
            self.assertEqual(len(transition_evidence), 1)

    def test_agent_only_adjudication_cannot_change_verification_state_and_leaves_conflict_open(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = openCareerStore(str(Path(directory) / "career.db"), clock=lambda: FIXED_TIME)
            six, _, conflict = _conflicting_aws_claims(store)

            result = store.adjudicateConflict(
                conflict["conflict_id"],
                {
                    "status": "resolved",
                    "winning_claim_ref": six["fact_id"],
                    "verification_state": "user_verified",
                },
                AGENT_PROVENANCE,
            )

            self.assertEqual(result["status"], "error")
            self.assertEqual(result["errors"][0]["code"], "disallowed_verification_transition")
            self.assertEqual(store.getFact(six["fact_id"])["fact"]["verification_state"], "inferred")
            conflicts = store.findConflicts(
                {"fact_id": six["fact_id"], "text": "AWS, six years", "normalized_terms": ["aws", "six years"]}
            )["conflicts"]
            self.assertEqual(conflicts[0]["status"], "open")
            self.assertEqual(store.listInteractions({"subject_id": conflict["conflict_id"]})["interactions"], [])

    def test_unknown_conflict_invalid_decision_and_malformed_provenance_are_typed_errors(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = openCareerStore(str(Path(directory) / "career.db"), clock=lambda: FIXED_TIME)

            unknown = store.adjudicateConflict("conflict_missing", "dismissed", USER_PROVENANCE)
            invalid_decision = store.adjudicateConflict("conflict_missing", "accepted", USER_PROVENANCE)
            malformed = store.adjudicateConflict("conflict_missing", "dismissed", [{"source": "user_answer"}])

            self.assertEqual(unknown["errors"][0]["code"], "unknown_conflict_id")
            self.assertEqual(invalid_decision["errors"][0]["code"], "invalid_conflict_decision")
            self.assertEqual(malformed["errors"][0]["code"], "malformed_provenance")


def _conflicting_aws_claims(store):
    six = store.upsertFact(
        {
            "type": "skill",
            "text": "AWS, six years",
            "normalized_terms": ["aws", "six years"],
            "verification_state": "inferred",
        },
        {"source": "agent_proposal", "text": "AWS, six years"},
        source="agent_proposal",
        policy={"allow_inferred_final": True},
    )
    ten = store.upsertFact(
        {
            "type": "skill",
            "text": "AWS, ten years",
            "normalized_terms": ["aws", "ten years"],
            "verification_state": "inferred",
        },
        {"source": "agent_proposal", "text": "AWS, ten years"},
        source="agent_proposal",
        policy={"allow_inferred_final": True},
    )
    return six, ten, ten["conflicts"][0]


def _build_pre_009_conflict_database(database_path: Path) -> None:
    conn = sqlite3.connect(database_path)
    try:
        for index, migration in enumerate(MIGRATIONS[:8], start=1):
            migration.apply(conn)
            conn.execute("INSERT INTO schema_migrations (id, applied_at) VALUES (?, ?)", (migration.id, FIXED_TIME))
            conn.execute(
                "INSERT INTO migrations (migration_id, schema_version, applied_at) VALUES (?, ?, ?)",
                (migration.id, "career-store.v1", FIXED_TIME),
            )
            conn.execute(f"PRAGMA user_version = {index}")
        for fact_id, text in (("fact_a", "AWS, six years"), ("fact_b", "AWS, ten years")):
            conn.execute(
                """
                INSERT INTO facts (
                    fact_id, type, text, normalized_terms_json, verification_state, created_at, updated_at,
                    metadata_json, canonical_name, description, years, confidence, merged_into_fact_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    fact_id,
                    "skill",
                    text,
                    json.dumps(["aws"], sort_keys=True, separators=(",", ":")),
                    "inferred",
                    FIXED_TIME,
                    FIXED_TIME,
                    "{}",
                    None,
                    None,
                    None,
                    None,
                    None,
                ),
            )
        conn.execute(
            """
            INSERT INTO conflicts (
                conflict_id, fact_ids_json, reason, status, evidence_ids_json, metadata_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "conflict_legacy",
                json.dumps(["fact_a", "fact_b"], sort_keys=True, separators=(",", ":")),
                "legacy contradiction",
                "already_open",
                json.dumps(["ev_a", "ev_b"], sort_keys=True, separators=(",", ":")),
                json.dumps({"existing": "six", "proposed": "ten"}, sort_keys=True, separators=(",", ":")),
                FIXED_TIME,
            ),
        )
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    unittest.main()
