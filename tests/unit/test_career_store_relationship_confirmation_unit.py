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
        for relationship_type in ("parent", "child"):
            self.assertEqual(
                _relationship_policy_match_type(relationship_type, "unconfirmed", {}, "child_to_parent"),
                "related_match",
            )
            self.assertEqual(
                _relationship_policy_match_type(
                    relationship_type,
                    "unconfirmed",
                    {"allow_related_as_equivalent": True},
                    "child_to_parent",
                ),
                "related_match",
            )
            self.assertEqual(
                _relationship_policy_match_type(relationship_type, "user_confirmed", {}, "parent_to_child"),
                "possible_match",
            )
            self.assertEqual(
                _relationship_policy_match_type(
                    relationship_type,
                    "user_confirmed",
                    {
                        "allow_related_as_equivalent": True,
                        "allowUnverifiedAliasCreation": True,
                    },
                    "parent_to_child",
                ),
                "possible_match",
            )
        self.assertIsNone(_relationship_policy_match_type("contradicts", "unconfirmed", {}))

    def test_parent_child_relationships_are_directional_and_never_exact_or_alias(self) -> None:
        cases = [
            ("parent", "parent_fact", "child_fact"),
            ("child", "child_fact", "parent_fact"),
        ]
        for relationship_type, from_key, to_key in cases:
            with self.subTest(relationship_type=relationship_type):
                with tempfile.TemporaryDirectory() as directory:
                    store = openCareerStore(str(Path(directory) / "career.db"), clock=lambda: FIXED_TIME)
                    facts = {
                        "parent_fact": _unknown_fact(store, "Frontend architecture", ["frontend architecture"]),
                        "child_fact": _unknown_fact(store, "React", ["react"]),
                    }
                    relationship = store.addRelationship(
                        facts[from_key]["fact_id"],
                        facts[to_key]["fact_id"],
                        relationship_type,
                        evidence_or_rationale={"source": "agent_proposal", "text": "Taxonomy path."},
                        policy={},
                    )
                    relationship_id = relationship["relationship_id"]

                    parent_requirement = [
                        {
                            "requirement_id": "req_frontend_architecture",
                            "concept": "Frontend architecture",
                            "normalized_terms": ["frontend architecture"],
                        }
                    ]
                    child_requirement = [
                        {
                            "requirement_id": "req_react",
                            "concept": "React",
                            "normalized_terms": ["react"],
                        }
                    ]

                    child_to_parent = store.findCandidateMatches(
                        parent_requirement,
                        policy={"allow_related_as_equivalent": True},
                    )
                    child_candidates = _relationship_candidates(child_to_parent, relationship_id)
                    self.assertTrue(child_candidates)
                    self.assertEqual({candidate["matchType"] for candidate in child_candidates}, {"related_match"})
                    self.assertEqual(child_candidates[0]["fact_id"], facts["child_fact"]["fact_id"])
                    self.assertEqual(child_candidates[0]["viaRelationships"][0]["direction"], "child_to_parent")

                    parent_to_child = store.findCandidateMatches(
                        child_requirement,
                        policy={
                            "allow_related_as_equivalent": True,
                            "allowUnverifiedAliasCreation": True,
                        },
                    )
                    parent_candidates = _relationship_candidates(parent_to_child, relationship_id)
                    self.assertTrue(parent_candidates)
                    self.assertEqual({candidate["matchType"] for candidate in parent_candidates}, {"possible_match"})
                    self.assertEqual(parent_candidates[0]["fact_id"], facts["parent_fact"]["fact_id"])
                    self.assertEqual(parent_candidates[0]["viaRelationships"][0]["direction"], "parent_to_child")

                    relationship_match_types = {
                        candidate["matchType"]
                        for result in (child_to_parent, parent_to_child)
                        for candidate in _relationship_candidates(result, relationship_id)
                    }
                    self.assertNotIn("exact_match", relationship_match_types)
                    self.assertNotIn("alias_match", relationship_match_types)

    def test_contradicts_relationship_emits_conflict_signal_and_no_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = openCareerStore(str(Path(directory) / "career.db"), clock=lambda: FIXED_TIME)
            react = _unknown_fact(store, "React", ["react"])
            angular = _unknown_fact(store, "Angular", ["angular"])
            relationship = store.addRelationship(
                react["fact_id"],
                angular["fact_id"],
                "contradicts",
                evidence_or_rationale={"source": "agent_proposal", "text": "User cannot truthfully claim both."},
                policy={},
            )
            relationship_id = relationship["relationship_id"]

            result = store.findCandidateMatches(
                [{"requirement_id": "req_angular", "concept": "Angular", "normalized_terms": ["angular"]}],
                policy={
                    "allow_related_as_equivalent": True,
                    "allowUnverifiedAliasCreation": True,
                },
            )

            self.assertEqual(
                result["conflict_signals"],
                [
                    {
                        "type": "contradicts",
                        "factId": react["fact_id"],
                        "relationshipId": relationship_id,
                        "contradictedFactId": angular["fact_id"],
                        "requirementId": "req_angular",
                    }
                ],
            )
            self.assertFalse(_relationship_candidates(result, relationship_id))
            self.assertNotIn("contradicts", {via["type"] for match in result["matches"] for via in match["viaRelationships"]})

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
