import inspect
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
for package_dir in ("resume-core", "career-store"):
    package_path = str(ROOT / package_dir)
    if package_path not in sys.path:
        sys.path.insert(0, package_path)

import career_store  # noqa: E402
from career_store import CareerStore, openCareerStore  # noqa: E402


FIXED_TIME = "2026-01-01T00:00:00Z"
SCORING_NAMES = {"score", "match_score", "official_score", "score_percent", "max_score", "threshold", "dimensions"}
ALLOWED_PUBLIC_METHODS = {
    "addEvidence",
    "addRelationship",
    "findCandidateMatches",
    "findConflicts",
    "getFact",
    "getMigrationState",
    "mergeFacts",
    "recordJobMatch",
    "searchFacts",
    "upsertFact",
    "verifyFact",
}


class CareerStoreNoScoringContractTests(unittest.TestCase):
    def test_package_exports_no_public_scoring_shaped_callable(self) -> None:
        exported_callables = {
            name
            for name in getattr(career_store, "__all__", [])
            if callable(getattr(career_store, name, None))
        }
        scoring_exports = {name for name in exported_callables if _is_scoring_name(name)}

        self.assertEqual(scoring_exports, set())

    def test_store_public_methods_exclude_scoring_surface(self) -> None:
        public_methods = {
            name
            for name, member in inspect.getmembers(CareerStore, predicate=inspect.isfunction)
            if not name.startswith("_")
        }
        scoring_methods = {name for name in public_methods if _is_scoring_name(name)}

        self.assertEqual(scoring_methods, set())
        self.assertLessEqual(public_methods, ALLOWED_PUBLIC_METHODS)

    def test_candidate_matching_outputs_do_not_return_scores(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "career.db"
            store = openCareerStore(str(database_path), clock=lambda: FIXED_TIME)
            fact = store.upsertFact(
                {
                    "type": "skill",
                    "text": "React",
                    "normalized_terms": ["react"],
                    "verification_state": "source_stated",
                },
                {"source": "resume", "text": "React"},
                source="resume",
                policy={},
            )

            candidate_matches = store.findCandidateMatches(
                [{"requirement_id": "req_react", "concept": "React", "source_text": "React"}],
                policy={},
                job_id="job_a",
            )
            job_match = store.recordJobMatch("job_a", "req_react", [fact["fact_id"]], "exact_match")

            self.assertEqual(_scoring_keys(candidate_matches), set())
            self.assertEqual(_scoring_keys(job_match), set())


def _is_scoring_name(name: str) -> bool:
    normalized = name.replace("-", "_")
    return normalized in SCORING_NAMES or normalized.startswith("score_") or normalized.endswith("_score")


def _scoring_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        keys = {str(key) for key in value if str(key) in SCORING_NAMES}
        for item in value.values():
            keys.update(_scoring_keys(item))
        return keys
    if isinstance(value, list):
        keys: set[str] = set()
        for item in value:
            keys.update(_scoring_keys(item))
        return keys
    return set()


if __name__ == "__main__":
    unittest.main()
