import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
for package_dir in ("resume-core", "career-store", "career-store/tools"):
    package_path = str(ROOT / package_dir)
    if package_path not in sys.path:
        sys.path.insert(0, package_path)

from career_store import openCareerStore  # noqa: E402
from career_store.migrations import _stable_id  # noqa: E402
from pre_realignment_fixture import (  # noqa: E402
    EXPECTED_MIGRATIONS,
    FIXED_TIME,
    _canonical_sqlite_dump,
    build_pre_realignment_database,
)


class CareerStoreRealignmentTests(unittest.TestCase):
    def test_pre_realignment_registry_prefix_migrates_rows_and_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "career.db"
            build_pre_realignment_database(database_path)

            store = openCareerStore(str(database_path), clock=lambda: FIXED_TIME)
            state = store.getMigrationState()

            self.assertEqual(state.applied_migrations, EXPECTED_MIGRATIONS)
            self.assertEqual(state.pending_migrations, [])
            self.assertEqual(state.metadata["user_version"], 5)
            with sqlite3.connect(database_path) as conn:
                conn.row_factory = sqlite3.Row
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM facts").fetchone()[0], 2)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM relationships").fetchone()[0], 1)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM job_matches").fetchone()[0], 3)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0], 2)
                self.assertEqual(
                    [tuple(row) for row in conn.execute("SELECT source_job_id FROM jobs ORDER BY source_job_id").fetchall()],
                    [("job_a",), ("job_b",)],
                )
                fact_columns = {row["name"] for row in conn.execute("PRAGMA table_info(facts)").fetchall()}
                self.assertTrue({"canonical_name", "description", "years", "confidence"} <= fact_columns)
                match_columns = {row["name"] for row in conn.execute("PRAGMA table_info(job_matches)").fetchall()}
                self.assertTrue({"match_type", "confidence", "user_confirmed"} <= match_columns)
                relationship_columns = {row["name"] for row in conn.execute("PRAGMA table_info(relationships)").fetchall()}
                self.assertIn("confidence", relationship_columns)

    def test_jobs_backfill_is_deterministic_for_identical_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            first_path = Path(directory) / "first.db"
            second_path = Path(directory) / "second.db"
            build_pre_realignment_database(first_path)
            build_pre_realignment_database(second_path)

            openCareerStore(str(first_path), clock=lambda: FIXED_TIME)
            openCareerStore(str(second_path), clock=lambda: FIXED_TIME)

            self.assertEqual(_canonical_sqlite_dump(first_path), _canonical_sqlite_dump(second_path))

    def test_drifted_enum_values_migrate_row_by_row_and_preserve_conflicts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "career.db"
            build_drifted_enum_database(database_path)

            store = openCareerStore(str(database_path), clock=lambda: FIXED_TIME)
            state = store.getMigrationState()

            self.assertEqual(state.applied_migrations, EXPECTED_MIGRATIONS)
            with sqlite3.connect(database_path) as conn:
                conn.row_factory = sqlite3.Row
                facts = {
                    row["fact_id"]: row["verification_state"]
                    for row in conn.execute("SELECT fact_id, verification_state FROM facts ORDER BY fact_id").fetchall()
                }
                self.assertEqual(
                    facts,
                    {
                        "fact_canonical": "source_stated",
                        "fact_conflicted_existing": "unknown",
                        "fact_conflicted_new": "unknown",
                        "fact_explicitly_missing": "unknown",
                        "fact_made_up": "unknown",
                    },
                )
                job_matches = {
                    row["job_match_id"]: row["resolution_state"]
                    for row in conn.execute("SELECT job_match_id, resolution_state FROM job_matches ORDER BY job_match_id").fetchall()
                }
                self.assertEqual(job_matches, {"match_conflicted": "unknown", "match_not_applicable": "not_applicable"})
                conflicts = {
                    row["conflict_id"]: {
                        "fact_ids": json.loads(row["fact_ids_json"]),
                        "reason": row["reason"],
                        "status": row["status"],
                        "metadata": json.loads(row["metadata_json"]),
                    }
                    for row in conn.execute("SELECT * FROM conflicts ORDER BY conflict_id").fetchall()
                }
                existing_id = _legacy_conflict_id("fact_conflicted_existing")
                created_id = _legacy_conflict_id("fact_conflicted_new")
                self.assertEqual(conflicts[existing_id]["status"], "already_open")
                self.assertEqual(conflicts[existing_id]["metadata"]["preserved"], True)
                self.assertEqual(conflicts[created_id]["fact_ids"], ["fact_conflicted_new"])
                self.assertEqual(conflicts[created_id]["reason"], "legacy conflicted verification state")
                self.assertEqual(conflicts[created_id]["metadata"]["verification_state"], "conflicted")


class CareerStoreJobsUnitTests(unittest.TestCase):
    def test_record_job_match_creates_stable_job_identity_row(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "career.db"
            store = openCareerStore(str(database_path), clock=lambda: FIXED_TIME)
            fact = store.upsertFact(
                {
                    "type": "skill",
                    "text": "React",
                    "normalized_terms": ["react"],
                    "verification_state": "source_stated",
                    "canonical_name": "React",
                    "description": "React production UI experience",
                    "years": 6,
                    "confidence": 0.9,
                },
                {"source": "resume", "text": "React"},
                source="resume",
                policy={},
            )

            result = store.recordJobMatch(
                "job_a",
                "req_react",
                [fact["fact_id"]],
                "exact_match",
                {"title": "Senior Frontend Engineer", "confidence": 0.82, "user_confirmed": True},
            )

            self.assertEqual(result["match_type"], "exact_match")
            self.assertEqual(result["confidence"], 0.82)
            self.assertEqual(result["user_confirmed"], 1)
            fetched = store.getFact(fact["fact_id"])["fact"]
            self.assertEqual(fetched["canonical_name"], "React")
            self.assertEqual(fetched["years"], 6)
            with sqlite3.connect(database_path) as conn:
                conn.row_factory = sqlite3.Row
                job = conn.execute("SELECT * FROM jobs WHERE source_job_id = ?", ("job_a",)).fetchone()
                self.assertIsNotNone(job)
                self.assertRegex(job["job_id"], r"^job_[0-9a-f]{24}$")
                self.assertEqual(json.loads(job["metadata_json"]), {"title": "Senior Frontend Engineer"})
                match = conn.execute("SELECT * FROM job_matches WHERE job_match_id = ?", (result["job_match_id"],)).fetchone()
                self.assertEqual(match["match_type"], "exact_match")
                self.assertEqual(match["confidence"], 0.82)
                self.assertEqual(match["user_confirmed"], 1)

    def test_record_job_match_preserves_job_associations_by_job(self) -> None:
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
                {"type": "skill", "text": "GraphQL", "normalized_terms": ["graphql"], "verification_state": "user_verified"},
                {"source": "user_answer", "text": "I built GraphQL APIs", "metadata": {"confirmed": True}},
                source="user_answer",
                policy={"explicit_confirmation": True},
            )

            store.recordJobMatch("job_a", "req_react", [react["fact_id"]], "exact_match")
            store.recordJobMatch("job_b", "req_graphql", [graphql["fact_id"]], "verified_fact_match")

            with sqlite3.connect(database_path) as conn:
                conn.row_factory = sqlite3.Row
                jobs = [tuple(row) for row in conn.execute("SELECT source_job_id FROM jobs ORDER BY source_job_id").fetchall()]
                self.assertEqual(jobs, [("job_a",), ("job_b",)])
                rows = conn.execute(
                    "SELECT job_id, requirement_id, fact_ids_json FROM job_matches ORDER BY job_id, requirement_id"
                ).fetchall()
                self.assertEqual(
                    [(row["job_id"], row["requirement_id"], json.loads(row["fact_ids_json"])) for row in rows],
                    [
                        ("job_a", "req_react", [react["fact_id"]]),
                        ("job_b", "req_graphql", [graphql["fact_id"]]),
                    ],
                )


def _legacy_conflict_id(fact_id: str) -> str:
    return _stable_id("conflict", fact_id, "legacy conflicted verification state")


def build_drifted_enum_database(database_path: Path) -> None:
    from career_store.migrations import MIGRATIONS  # noqa: PLC0415

    conn = sqlite3.connect(database_path)
    try:
        for index, migration in enumerate(MIGRATIONS[:4], start=1):
            migration.apply(conn)
            conn.execute(
                "INSERT INTO schema_migrations (id, applied_at) VALUES (?, ?)",
                (migration.id, FIXED_TIME),
            )
            conn.execute(
                "INSERT INTO migrations (migration_id, schema_version, applied_at) VALUES (?, ?, ?)",
                (migration.id, "career-store.v1", FIXED_TIME),
            )
            conn.execute(f"PRAGMA user_version = {index}")
        for fact_id, state in (
            ("fact_canonical", "source_stated"),
            ("fact_conflicted_existing", "conflicted"),
            ("fact_conflicted_new", "conflicted"),
            ("fact_explicitly_missing", "explicitly_missing"),
            ("fact_made_up", "made_up"),
        ):
            conn.execute(
                """
                INSERT INTO facts (
                    fact_id, type, text, normalized_terms_json, verification_state, created_at, updated_at,
                    metadata_json, canonical_name, description, years, confidence
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    fact_id,
                    "skill",
                    fact_id.replace("_", " "),
                    json.dumps([fact_id], sort_keys=True, separators=(",", ":")),
                    state,
                    FIXED_TIME,
                    FIXED_TIME,
                    "{}",
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
                _legacy_conflict_id("fact_conflicted_existing"),
                json.dumps(["fact_conflicted_existing"], sort_keys=True, separators=(",", ":")),
                "legacy conflicted verification state",
                "already_open",
                "[]",
                json.dumps({"preserved": True}, sort_keys=True, separators=(",", ":")),
                FIXED_TIME,
            ),
        )
        for match_id, resolution_state in (
            ("match_conflicted", "conflicted"),
            ("match_not_applicable", "not_applicable"),
        ):
            conn.execute(
                """
                INSERT INTO job_matches (
                    job_match_id, job_id, requirement_id, fact_ids_json, resolution_state, created_at, metadata_json,
                    match_type, confidence, user_confirmed
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    match_id,
                    "job_a",
                    f"req_{match_id}",
                    json.dumps(["fact_canonical"], sort_keys=True, separators=(",", ":")),
                    resolution_state,
                    FIXED_TIME,
                    "{}",
                    None,
                    None,
                    None,
                ),
            )
        conn.commit()
    finally:
        conn.close()
