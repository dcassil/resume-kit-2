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
USER_PROVENANCE = [{"source": "user_answer", "text": "Yes, these terms are equivalent."}]


def _fact(store, fact_id: str, text: str, terms: list[str], state: str = "source_stated", **extra):
    return store.upsertFact(
        {
            "fact_id": fact_id,
            "type": "skill",
            "text": text,
            "normalized_terms": terms,
            "verification_state": state,
            **extra,
        },
        {"source": "resume", "source_id": "resume_1", "text": text},
        source="resume",
        policy={},
    )


class CareerStoreSearchFactsUnitTests(unittest.TestCase):
    def test_search_facts_filters_concept_terms_and_verification_state_composably(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = openCareerStore(str(Path(directory) / "career.db"), clock=lambda: FIXED_TIME)
            react = _fact(
                store,
                "fact_react",
                "Built React applications.",
                ["react"],
                canonical_name="React",
                description="frontend UI library",
            )
            _fact(
                store,
                "fact_react_inferred",
                "React prototype.",
                ["react"],
                state="inferred",
                canonical_name="React",
                description="frontend UI library",
            )
            _fact(store, "fact_python", "Python backend services.", ["python"], canonical_name="Python")

            result = store.searchFacts(
                "",
                filters={
                    "concept": "frontend",
                    "terms": ["react"],
                    "verification_state": "source_stated",
                },
            )

            self.assertEqual(result["status"], "ok")
            self.assertEqual([fact["fact_id"] for fact in result["facts"]], [react["fact_id"]])

    def test_search_facts_alias_filter_expands_terms_only_after_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = openCareerStore(str(Path(directory) / "career.db"), clock=lambda: FIXED_TIME)
            vue = _fact(store, "fact_vue", "Vue production apps.", ["vue"])
            angular = _fact(store, "fact_angular", "Angular applications.", ["angular"], state="unknown")
            relationship = store.addRelationship(
                vue["fact_id"],
                angular["fact_id"],
                "alias",
                {"source": "agent_proposal", "text": "Agent proposed equivalence."},
                policy={},
            )

            unconfirmed = store.searchFacts(
                "",
                filters={
                    "terms": ["angular"],
                    "alias": True,
                    "verification_state": "source_stated",
                },
            )
            self.assertEqual(unconfirmed["facts"], [])

            confirmed = store.confirmRelationship(relationship["relationship_id"], USER_PROVENANCE)
            self.assertEqual(confirmed["confirmation_status"], "user_confirmed")
            result = store.searchFacts(
                "",
                filters={
                    "terms": ["angular"],
                    "alias": True,
                    "verification_state": "source_stated",
                },
            )

            self.assertEqual([fact["fact_id"] for fact in result["facts"]], [vue["fact_id"]])

    def test_search_facts_include_evidence_returns_only_rows_matching_matched_terms(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = openCareerStore(str(Path(directory) / "career.db"), clock=lambda: FIXED_TIME)
            fact = store.upsertFact(
                {
                    "fact_id": "fact_react",
                    "type": "skill",
                    "text": "React",
                    "normalized_terms": ["react"],
                    "verification_state": "unknown",
                },
                {"source": "resume", "source_id": "resume_1", "text": "React production work"},
                source="resume",
                policy={},
            )
            store.addEvidence(fact["fact_id"], {"source": "resume", "text": "TypeScript migration"}, source="resume")
            store.addEvidence(fact["fact_id"], {"source": "resume", "text": "React hooks and components"}, source="resume")

            result = store.searchFacts("React", include_evidence=True)

            self.assertCountEqual(
                [item["text"] for item in result["facts"][0]["evidence"]],
                ["React production work", "React hooks and components"],
            )
            self.assertEqual(len(result["facts"][0]["evidence"]), 2)
            self.assertEqual(result["facts"][0]["evidence_ids"], [item["evidence_id"] for item in result["facts"][0]["evidence"]])

    def test_search_facts_redirected_facts_never_return_under_new_filters(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = openCareerStore(str(Path(directory) / "career.db"), clock=lambda: FIXED_TIME)
            survivor = _fact(store, "fact_node", "Node backend work.", ["node"], canonical_name="Node")
            merged = _fact(store, "fact_nodejs", "Node.js services.", ["node.js"], canonical_name="Node.js")
            store.mergeFacts(survivor["fact_id"], merged["fact_id"], {"source": "user_answer", "text": "same skill"})

            result = store.searchFacts("", filters={"terms": ["node.js"]})
            concept = store.searchFacts("", filters={"concept": "Node.js"})
            redirected_id = store.searchFacts(merged["fact_id"], filters={"terms": ["node.js"]})

            self.assertEqual([fact["fact_id"] for fact in result["facts"]], [survivor["fact_id"]])
            self.assertNotIn(merged["fact_id"], [fact["fact_id"] for fact in concept["facts"]])
            self.assertEqual([fact["fact_id"] for fact in redirected_id["facts"]], [survivor["fact_id"]])

    def test_search_facts_absent_values_are_empty_and_malformed_filters_are_typed_errors(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = openCareerStore(str(Path(directory) / "career.db"), clock=lambda: FIXED_TIME)
            _fact(store, "fact_python", "Python services.", ["python"])

            absent = store.searchFacts("", filters={"terms": ["rust"]})
            malformed = store.searchFacts("", filters={"terms": {"value": "python"}})

            self.assertEqual(absent["status"], "ok")
            self.assertEqual(absent["facts"], [])
            self.assertEqual(malformed["status"], "error")
            self.assertEqual(malformed["errors"][0]["type"], "InvalidSearchFilterError")
            self.assertEqual(malformed["errors"][0]["code"], "invalid_filter_shape")
            self.assertNotIn("sql", str(malformed).lower())


if __name__ == "__main__":
    unittest.main()
