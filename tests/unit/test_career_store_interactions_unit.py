import ast
import inspect
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

from career_store import INTERACTION_TYPES, openCareerStore  # noqa: E402
import career_store.interactions as interactions_module  # noqa: E402


FIXED_TIME = "2026-01-01T00:00:00Z"


class MutableClock:
    def __init__(self, value: str) -> None:
        self.value = value

    def __call__(self) -> str:
        return self.value


class CareerStoreInteractionsUnitTests(unittest.TestCase):
    def test_schema_008_creates_append_only_interactions_table(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "career.db"
            store = openCareerStore(str(database_path), clock=lambda: FIXED_TIME)
            state = store.getMigrationState()

            self.assertEqual(state.applied_migrations[-1], "008_interactions_table")
            self.assertEqual(state.metadata["user_version"], 8)
            conn = sqlite3.connect(database_path)
            conn.row_factory = sqlite3.Row
            try:
                columns = [row["name"] for row in conn.execute("PRAGMA table_info(interactions)").fetchall()]
            finally:
                conn.close()
            self.assertEqual(
                columns,
                ["id", "interaction_type", "subject_id", "input_json", "result_json", "created_at"],
            )

            source = inspect.getsource(interactions_module).lower()
            self.assertNotIn(" update ", source)
            self.assertNotIn(" delete ", source)

    def test_record_interaction_uses_vocabulary_validation_transaction_and_replay_idempotency(self) -> None:
        clock = MutableClock("2026-01-01T00:00:00Z")
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "career.db"
            store = openCareerStore(str(database_path), clock=clock)

            first = store.recordInteraction(
                "answer_recorded",
                "operation_123",
                {"answer": "Yes", "question_id": "q1"},
                {"accepted": True},
            )
            clock.value = "2026-01-02T00:00:00Z"
            repeated = store.recordInteraction(
                "answer_recorded",
                "operation_123",
                {"question_id": "q1", "answer": "Yes"},
                {"accepted": False},
            )
            invalid = store.recordInteraction("unknown_type", "operation_123", {"answer": "Yes"})
            malformed = store.recordInteraction("answer_recorded", "operation_123", ["not", "object"])  # type: ignore[arg-type]

            self.assertIn("answer_recorded", INTERACTION_TYPES)
            self.assertEqual(first["status"], "created")
            self.assertEqual(repeated["status"], "unchanged")
            self.assertEqual(first["interaction_id"], repeated["interaction_id"])
            self.assertEqual(first["transaction_result"]["audit"]["operation"], "recordInteraction")
            self.assertEqual(first["transaction_result"]["ids"]["interaction_id"], first["interaction_id"])
            self.assertEqual(invalid["status"], "rejected")
            self.assertEqual(invalid["errors"][0]["type"], "UnknownInteractionTypeError")
            self.assertEqual(malformed["status"], "rejected")
            self.assertEqual(malformed["errors"][0]["type"], "MalformedInteractionError")
            conn = sqlite3.connect(database_path)
            try:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM interactions").fetchone()[0], 1)
                row = conn.execute("SELECT created_at, result_json FROM interactions").fetchone()
            finally:
                conn.close()
            self.assertEqual(row[0], "2026-01-01T00:00:00Z")
            self.assertEqual(row[1], '{"accepted":true}')

    def test_list_interactions_filters_deterministically_and_rejects_malformed_filters(self) -> None:
        clock = MutableClock("2026-01-01T00:00:00Z")
        with tempfile.TemporaryDirectory() as directory:
            store = openCareerStore(str(Path(directory) / "career.db"), clock=clock)
            first = store.recordInteraction("question_asked", "operation_a", {"question": "React?"})
            clock.value = "2026-01-03T00:00:00Z"
            second = store.recordInteraction("answer_recorded", "operation_a", {"answer": "Yes"})
            clock.value = "2026-01-02T00:00:00Z"
            third = store.recordInteraction("rewrite_rejected", "operation_b", {"operation": "rewrite-1"})

            all_rows = store.listInteractions()
            subject_rows = store.listInteractions({"subject_id": "operation_a"})
            type_rows = store.listInteractions({"interaction_type": "rewrite_rejected"})
            range_rows = store.listInteractions({"created_at_from": "2026-01-02T00:00:00Z", "created_at_to": "2026-01-03T00:00:00Z"})
            absent_rows = store.listInteractions({"subject_id": "missing"})
            malformed = store.listInteractions({"created_at_from": 123})

            self.assertEqual([row["interaction_id"] for row in (first, second, third)], [first["interaction_id"], second["interaction_id"], third["interaction_id"]])
            self.assertEqual([row["id"] for row in all_rows["interactions"]], [first["interaction_id"], third["interaction_id"], second["interaction_id"]])
            self.assertEqual([row["id"] for row in subject_rows["interactions"]], [first["interaction_id"], second["interaction_id"]])
            self.assertEqual([row["id"] for row in type_rows["interactions"]], [third["interaction_id"]])
            self.assertEqual([row["id"] for row in range_rows["interactions"]], [third["interaction_id"], second["interaction_id"]])
            self.assertEqual(absent_rows["interactions"], [])
            self.assertEqual(malformed["status"], "error")
            self.assertEqual(malformed["errors"][0]["type"], "MalformedInteractionFilterError")

    def test_fact_confirmed_interaction_does_not_mutate_verification_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "career.db"
            store = openCareerStore(str(database_path), clock=lambda: FIXED_TIME)
            fact = store.upsertFact(
                {"type": "skill", "text": "React", "normalized_terms": ["react"], "verification_state": "inferred"},
                {"source": "agent_proposal", "text": "possible React evidence"},
                source="agent_proposal",
                policy={"allow_inferred_final": True},
            )
            before = store.getFact(fact["fact_id"])["fact"]["verification_state"]

            interaction = store.recordInteraction(
                "fact_confirmed",
                fact["fact_id"],
                {"question_id": "q-react", "answer": "yes"},
                {"confirmed": True},
            )
            after = store.getFact(fact["fact_id"])["fact"]["verification_state"]

            self.assertEqual(interaction["status"], "created")
            self.assertEqual(before, "inferred")
            self.assertEqual(after, before)

    def test_interactions_module_has_no_verification_or_state_mutation_imports(self) -> None:
        blocked_modules = {"career_store.verification", "career_store.store", "career_store.store_support"}
        source = inspect.getsource(interactions_module)
        tree = ast.parse(source)
        imported_modules: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.add(node.module)

        self.assertTrue(blocked_modules.isdisjoint(imported_modules))
        for _, module in inspect.getmembers(interactions_module, inspect.ismodule):
            self.assertNotIn(module.__name__, blocked_modules)
        for _, value in inspect.getmembers(interactions_module):
            owner = inspect.getmodule(value)
            if owner is not None:
                self.assertNotIn(owner.__name__, blocked_modules)


if __name__ == "__main__":
    unittest.main()
