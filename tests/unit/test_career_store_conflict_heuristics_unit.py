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


class CareerStoreConflictHeuristicUnitTests(unittest.TestCase):
    def test_react_version_numbers_do_not_create_years_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = openCareerStore(str(Path(directory) / "career.db"), clock=lambda: FIXED_TIME)
            store.upsertFact(
                {
                    "type": "skill",
                    "text": "React 18",
                    "normalized_terms": ["react", "18"],
                    "verification_state": "source_stated",
                },
                {"source": "resume", "text": "React 18"},
                source="resume",
                policy={},
            )

            result = store.findConflicts(
                {
                    "text": "React 17 migration",
                    "normalized_terms": ["react", "17", "migration"],
                }
            )

            self.assertEqual(result["conflicts"], [])

    def test_explicit_digit_years_conflict_on_same_concept(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = openCareerStore(str(Path(directory) / "career.db"), clock=lambda: FIXED_TIME)
            store.upsertFact(
                {
                    "type": "skill",
                    "text": "AWS, 5 years",
                    "normalized_terms": ["aws", "5 years"],
                    "verification_state": "source_stated",
                },
                {"source": "resume", "text": "5 years of AWS"},
                source="resume",
                policy={},
            )

            result = store.findConflicts({"text": "AWS, 8 years", "normalized_terms": ["aws", "8 years"]})

            self.assertEqual(len(result["conflicts"]), 1)
            self.assertEqual(result["conflicts"][0]["metadata"]["existing_claim"], {"concept": "aws", "years": 5})
            self.assertEqual(result["conflicts"][0]["metadata"]["proposed_claim"], {"concept": "aws", "years": 8})

    def test_duplicate_conflict_creation_replays_produce_single_open_conflict_row(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "career.db"
            store = openCareerStore(str(database_path), clock=lambda: FIXED_TIME)
            store.upsertFact(
                {
                    "fact_id": "fact_aws_5",
                    "type": "skill",
                    "text": "AWS, 5 years",
                    "normalized_terms": ["aws", "5 years"],
                    "verification_state": "source_stated",
                },
                {"source": "resume", "text": "5 years of AWS"},
                source="resume",
                policy={},
            )
            competing_claim = {
                "fact_id": "fact_aws_8",
                "type": "skill",
                "text": "AWS, 8 years",
                "normalized_terms": ["aws", "8 years"],
                "verification_state": "source_stated",
            }

            first = store.upsertFact(competing_claim, {"source": "resume", "text": "8 years of AWS"}, source="resume", policy={})
            replay = store.upsertFact(competing_claim, {"source": "resume", "text": "8 years of AWS"}, source="resume", policy={})

            self.assertEqual(first["status"], "created")
            self.assertEqual(replay["status"], "updated")
            self.assertEqual(len(first["conflicts"]), 1)
            self.assertEqual(replay["conflicts"], first["conflicts"])
            self.assertEqual(first["transaction_result"]["ids"]["conflict_ids"], first["conflicts"][0]["conflict_id"])
            with sqlite3.connect(database_path) as conn:
                rows = conn.execute("SELECT conflict_id, status, metadata_json FROM conflicts").fetchall()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0][0], first["conflicts"][0]["conflict_id"])
            self.assertEqual(rows[0][1], "open")

    def test_number_word_above_ten_years_claim_parses_and_conflicts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = openCareerStore(str(Path(directory) / "career.db"), clock=lambda: FIXED_TIME)
            store.upsertFact(
                {
                    "type": "skill",
                    "text": "Python, ten years",
                    "normalized_terms": ["python", "ten years"],
                    "verification_state": "source_stated",
                },
                {"source": "resume", "text": "ten years of Python"},
                source="resume",
                policy={},
            )

            result = store.findConflicts({"text": "Python, twelve years", "normalized_terms": ["python", "twelve years"]})

            self.assertEqual(len(result["conflicts"]), 1)
            self.assertEqual(result["conflicts"][0]["metadata"]["proposed_claim"], {"concept": "python", "years": 12})

    def test_structured_title_claims_conflict_for_same_role_slot_outside_legacy_title_list(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = openCareerStore(str(Path(directory) / "career.db"), clock=lambda: FIXED_TIME)
            store.upsertFact(
                {
                    "type": "employment_title",
                    "text": "Current ExampleCo title",
                    "canonical_name": "Engineering Manager",
                    "description": "ExampleCo current role slot",
                    "normalized_terms": ["exampleco current role slot", "employment title"],
                    "verification_state": "source_stated",
                },
                {"source": "resume", "text": "Engineering Manager"},
                source="resume",
                policy={},
            )

            result = store.findConflicts(
                {
                    "type": "employment_title",
                    "text": "Proposed ExampleCo title",
                    "canonical_name": "Director of Engineering",
                    "description": "ExampleCo current role slot",
                    "normalized_terms": ["exampleco current role slot", "employment title"],
                }
            )

            self.assertEqual(len(result["conflicts"]), 1)
            self.assertEqual(result["conflicts"][0]["metadata"]["existing_claim"]["title"], "engineering manager")
            self.assertEqual(result["conflicts"][0]["metadata"]["proposed_claim"]["title"], "director of engineering")

    def test_staff_title_fixture_conflicts_via_structured_title_model(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = openCareerStore(str(Path(directory) / "career.db"), clock=lambda: FIXED_TIME)
            store.upsertFact(
                {
                    "type": "employment_title",
                    "text": "Formal employment title was Senior Software Developer.",
                    "canonical_name": "Senior Software Developer",
                    "description": "Formal employment title",
                    "normalized_terms": ["formal employment title"],
                    "verification_state": "source_stated",
                },
                {"source": "resume", "text": "Senior Software Developer"},
                source="resume",
                policy={},
            )

            result = store.findConflicts(
                {
                    "type": "employment_title",
                    "text": "Proposed Staff Software Engineer title",
                    "canonical_name": "Staff Software Engineer",
                    "description": "Formal employment title",
                    "normalized_terms": ["formal employment title"],
                }
            )

            self.assertEqual(len(result["conflicts"]), 1)
            self.assertEqual(result["conflicts"][0]["metadata"]["existing_claim"]["title"], "senior software developer")
            self.assertEqual(result["conflicts"][0]["metadata"]["proposed_claim"]["title"], "staff software engineer")

    def test_claim_fact_id_is_not_checked_against_itself_but_competing_claim_conflicts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = openCareerStore(str(Path(directory) / "career.db"), clock=lambda: FIXED_TIME)
            six = store.upsertFact(
                {
                    "type": "skill",
                    "text": "AWS, six years",
                    "normalized_terms": ["aws", "six years"],
                    "verification_state": "source_stated",
                },
                {"source": "resume", "text": "six years of AWS"},
                source="resume",
                policy={},
            )

            self_claim = store.findConflicts(
                {
                    "fact_id": six["fact_id"],
                    "text": "AWS, ten years",
                    "normalized_terms": ["aws", "ten years"],
                }
            )
            competing_claim = store.findConflicts({"text": "AWS, ten years", "normalized_terms": ["aws", "ten years"]})

            self.assertEqual(self_claim["conflicts"], [])
            self.assertEqual(len(competing_claim["conflicts"]), 1)


if __name__ == "__main__":
    unittest.main()
