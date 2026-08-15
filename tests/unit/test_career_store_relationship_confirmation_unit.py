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
from career_store.store_support import _relationship_policy_match_type  # noqa: E402


FIXED_TIME = "2026-01-01T00:00:00Z"
LATER_TIME = "2026-01-02T00:00:00Z"
USER_PROVENANCE = [{"source": "user_answer", "text": "Yes, these terms are equivalent."}]


def _unknown_fact(store, text: str, terms: list[str]) -> dict:
    return store.upsertFact(
        {
            "type": "skill",
            "text": text,
            "normalized_terms": terms,
            "verification_state": "unknown",
        },
        {"source": "agent_proposal", "text": text},
        source="agent_proposal",
        policy={},
    )


def _relationship_candidates(result: dict, relationship_id: str) -> list[dict]:
    return [
        candidate
        for match in result["matches"]
        for candidate in match["supporting_facts"]
        if candidate.get("relationship_id") == relationship_id
    ]


def _match_types(result: dict) -> set[str]:
    return {match["matchType"] for match in result["matches"]} | {
        candidate["matchType"]
        for match in result["matches"]
        for candidate in match["supporting_facts"]
    }


class CareerStoreRelationshipConfirmationUnitTests(unittest.TestCase):
    def test_policy_function_maps_confirmation_status_and_config(self) -> None:
        self.assertEqual(_relationship_policy_match_type("alias", "user_confirmed", {}), "alias_match")
        self.assertEqual(_relationship_policy_match_type("equivalent", "user_confirmed", {}), "alias_match")
        self.assertEqual(_relationship_policy_match_type("alias", "unconfirmed", {}), "possible_match")
        self.assertEqual(
            _relationship_policy_match_type("alias", "unconfirmed", {"allowUnverifiedAliasCreation": True}),
            "alias_match",
        )
        self.assertEqual(_relationship_policy_match_type("related", "unconfirmed", {}), "related_match")
        self.assertEqual(
            _relationship_policy_match_type("related", "unconfirmed", {"allow_related_as_equivalent": True}),
            "alias_match",
        )
        self.assertEqual(_relationship_policy_match_type("parent", "unconfirmed", {}), "related_match")
        self.assertEqual(_relationship_policy_match_type("child", "unconfirmed", {}), "related_match")
        self.assertEqual(_relationship_policy_match_type("contradicts", "unconfirmed", {}), "possible_match")

    def test_unconfirmed_then_confirmed_alias_policy_applies_in_both_relationship_directions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = openCareerStore(str(Path(directory) / "career.db"), clock=lambda: FIXED_TIME)
            vue = _unknown_fact(store, "Vue", ["vue"])
            angular = _unknown_fact(store, "Angular", ["angular"])
            relationship = store.addRelationship(
                vue["fact_id"],
                angular["fact_id"],
                "alias",
                evidence_or_rationale={"source": "agent_proposal", "text": "Agent proposed equivalence."},
                policy={},
            )
            relationship_id = relationship["relationship_id"]
            self.assertEqual(relationship["confirmation_status"], "unconfirmed")

            angular_requirement = [{"requirement_id": "req_angular", "concept": "Angular", "normalized_terms": ["angular"]}]
            vue_requirement = [{"requirement_id": "req_vue", "concept": "Vue", "normalized_terms": ["vue"]}]
            unconfirmed_to = store.findCandidateMatches(angular_requirement, policy={})
            unconfirmed_from = store.findCandidateMatches(vue_requirement, policy={})

            for result in (unconfirmed_to, unconfirmed_from):
                candidates = _relationship_candidates(result, relationship_id)
                self.assertTrue(candidates)
                self.assertEqual({candidate["matchType"] for candidate in candidates}, {"possible_match"})
                self.assertEqual(candidates[0]["viaRelationships"][0]["confirmationStatus"], "unconfirmed")
                self.assertNotIn("alias_match", _match_types(result))

            confirmed = store.confirmRelationship(relationship_id, USER_PROVENANCE)
            self.assertEqual(confirmed["status"], "updated")
            self.assertEqual(confirmed["confirmation_status"], "user_confirmed")

            confirmed_to = store.findCandidateMatches(angular_requirement, policy={})
            confirmed_from = store.findCandidateMatches(vue_requirement, policy={})

            for result in (confirmed_to, confirmed_from):
                candidates = _relationship_candidates(result, relationship_id)
                self.assertTrue(candidates)
                self.assertEqual({candidate["matchType"] for candidate in candidates}, {"alias_match"})
                self.assertEqual(candidates[0]["viaRelationships"][0]["confirmationStatus"], "user_confirmed")

    def test_confirm_relationship_rejects_typed_errors_and_is_idempotent(self) -> None:
        clock_values = iter([FIXED_TIME, FIXED_TIME, FIXED_TIME, LATER_TIME, LATER_TIME])
        with tempfile.TemporaryDirectory() as directory:
            store = openCareerStore(str(Path(directory) / "career.db"), clock=lambda: next(clock_values, LATER_TIME))
            react = _unknown_fact(store, "React", ["react"])
            react_native = _unknown_fact(store, "React Native", ["react native"])
            relationship = store.addRelationship(
                react["fact_id"],
                react_native["fact_id"],
                "equivalent",
                evidence_or_rationale={"source": "agent_proposal", "text": "Agent proposed equivalence."},
                policy={},
            )

            missing = store.confirmRelationship("relationship_missing", USER_PROVENANCE)
            self.assertEqual(missing["status"], "error")
            self.assertEqual(missing["mutation_status"], "rejected")
            self.assertEqual(missing["errors"][0]["type"], "InvalidRelationshipConfirmationError")
            self.assertEqual(missing["errors"][0]["code"], "unknown_relationship_id")

            invalid = store.confirmRelationship(
                relationship["relationship_id"],
                [{"source": "agent_proposal", "text": "The agent inferred this."}],
            )
            self.assertEqual(invalid["status"], "error")
            self.assertEqual(invalid["mutation_status"], "rejected")
            self.assertEqual(invalid["errors"][0]["type"], "InvalidRelationshipConfirmationError")
            self.assertEqual(invalid["errors"][0]["code"], "missing_user_confirmation_source")

            first = store.confirmRelationship(relationship["relationship_id"], USER_PROVENANCE)
            second = store.confirmRelationship(relationship["relationship_id"], USER_PROVENANCE)

            self.assertEqual(first["status"], "updated")
            self.assertEqual(second["status"], "unchanged")
            self.assertEqual(second["mutation_status"], "unchanged")
            self.assertEqual(second["confirmation_status"], "user_confirmed")
            self.assertEqual(second["confirmed_by_provenance"], USER_PROVENANCE)
            self.assertEqual(second["confirmed_at"], first["confirmed_at"])


if __name__ == "__main__":
    unittest.main()
