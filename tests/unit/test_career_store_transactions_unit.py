import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
for package_dir in ("resume-core", "career-store"):
    package_path = str(ROOT / package_dir)
    if package_path not in sys.path:
        sys.path.insert(0, package_path)

from career_store import openCareerStore  # noqa: E402


FIXED_TIME = "2026-01-01T00:00:00Z"


class CareerStoreTransactionUnitTests(unittest.TestCase):
    def test_upsert_rollback_after_conflict_detection_leaves_no_partial_rows_and_reports_transaction(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "career.db"
            store = openCareerStore(str(database_path), clock=lambda: FIXED_TIME)
            existing = store.upsertFact(
                {"type": "skill", "text": "AWS, six years", "normalized_terms": ["aws", "six years"], "verification_state": "source_stated"},
                {"source": "resume", "text": "six years of AWS"},
                source="resume",
                policy={},
            )

            def fail_after_conflict_detection(operation: str) -> None:
                self.assertEqual(operation, "upsertFact")
                raise RuntimeError("injected failure after conflict detection")

            with self.assertRaises(RuntimeError) as raised:
                store.upsertFact(
                    {
                        "type": "skill",
                        "text": "AWS, ten years",
                        "normalized_terms": ["aws", "ten years"],
                        "verification_state": "source_stated",
                    },
                    {"source": "resume", "text": "ten years of AWS"},
                    source="resume",
                    policy={"_after_conflict_detection": fail_after_conflict_detection},
                )

            transaction = raised.exception.transaction_result
            self.assertEqual(transaction.status, "rolled_back")
            self.assertEqual(transaction.mutation_status, "rolled_back")
            self.assertRegex(transaction.ids["fact_id"], r"^fact_[0-9a-f]{24}$")
            self.assertIn("conflict_", transaction.ids["conflict_ids"])
            self.assertEqual(store._last_transaction_result.status, "rolled_back")

            with sqlite3.connect(database_path) as conn:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM facts").fetchone()[0], 1)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM evidence").fetchone()[0], 1)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM conflicts").fetchone()[0], 0)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM facts WHERE text = ?", ("AWS, ten years",)).fetchone()[0], 0)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM evidence WHERE text = ?", ("ten years of AWS",)).fetchone()[0], 0)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM facts WHERE fact_id = ?", (existing["fact_id"],)).fetchone()[0], 1)

    def test_transaction_result_is_embedded_for_transactional_mutations(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "career.db"
            store = openCareerStore(str(database_path), clock=lambda: FIXED_TIME)

            react = store.upsertFact(
                {"type": "skill", "text": "React", "normalized_terms": ["react"], "verification_state": "source_stated"},
                {"source": "resume", "text": "React"},
                source="resume",
                policy={},
            )
            graphql = store.upsertFact(
                {"type": "skill", "text": "GraphQL", "normalized_terms": ["graphql"], "verification_state": "source_stated"},
                {"source": "resume", "text": "GraphQL"},
                source="resume",
                policy={},
            )
            evidence = store.addEvidence(react["fact_id"], {"source": "user_answer", "text": "Built React apps"}, source="user_answer")
            verified = store.verifyFact(
                react["fact_id"],
                "user_verified",
                confirmation={"source": "user_answer", "text": "I built React apps", "confirmed": True},
                source="user_answer",
            )
            relationship = store.addRelationship(
                react["fact_id"],
                graphql["fact_id"],
                "related",
                evidence_or_rationale={"text": "frontend and API experience"},
                policy={},
            )
            job_match = store.recordJobMatch("job_a", "req_react", [react["fact_id"]], "verified_fact_match")

            for result, id_key, operation in (
                (react, "fact_id", "upsertFact"),
                (evidence, "evidence_id", "addEvidence"),
                (verified, "fact_id", "verifyFact"),
                (relationship, "relationship_id", "addRelationship"),
                (job_match, "job_match_id", "recordJobMatch"),
            ):
                with self.subTest(id_key=id_key):
                    transaction = result["transaction_result"]
                    self.assertEqual(transaction["schema_version"], "career-store.v1")
                    self.assertEqual(transaction["status"], "committed")
                    self.assertEqual(transaction["ids"][id_key], result[id_key])
                    self.assertEqual(transaction["errors"], [])
                    self.assertEqual(transaction["audit"]["operation"], operation)

    def test_evidence_append_only_and_deterministic_ids_survive_transaction_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "career.db"
            store = openCareerStore(str(database_path), clock=lambda: FIXED_TIME)
            fact = store.upsertFact(
                {"type": "skill", "text": "React", "normalized_terms": ["react"], "verification_state": "source_stated"},
                {"source": "resume", "text": "React", "source_id": "resume-1"},
                source="resume",
                policy={},
            )

            first = store.addEvidence(
                fact["fact_id"],
                {"source": "user_answer", "text": "Built React accessibility features", "source_id": "answer-1"},
                source="user_answer",
            )
            second = store.addEvidence(
                fact["fact_id"],
                {"source": "user_answer", "text": "Built React performance work", "source_id": "answer-2"},
                source="user_answer",
            )
            repeated = store.addEvidence(
                fact["fact_id"],
                {"source": "user_answer", "text": "Built React performance work", "source_id": "answer-2"},
                source="user_answer",
            )

            fetched = store.getFact(fact["fact_id"])
            evidence_ids = [item["evidence_id"] for item in fetched["evidence"]]
            self.assertEqual(len(evidence_ids), 3)
            self.assertIn(first["evidence_id"], evidence_ids)
            self.assertIn(second["evidence_id"], evidence_ids)
            self.assertEqual(second["evidence_id"], repeated["evidence_id"])


if __name__ == "__main__":
    unittest.main()
