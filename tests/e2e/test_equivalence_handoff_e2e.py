"""E2E coverage for semantic-equivalence proposal handoff.

This test exercises the current handoff path without adding production surface:
resume-agent emits a fixture-pinned proposal, resume-core consumes the mapped
TermRelationship through the existing public ``scoreMatch`` entry point, and
career-store persists the relationship only after that validation step.

Enforced today:
- ``narrower_than`` maps to ``child`` with ``term_a`` as child and ``term_b`` as
  parent for both resume-core DTO consumption and career-store persistence.
- The store relationship is directional: child->parent can support the broader
  requirement only as ``related_match``; parent->child is only ``possible_match``.
- Rejected or unvalidated proposals leave the store relationship set unchanged.

Deferred/gap:
- resume-core has no dedicated equivalence validator and no ``equivalent`` term
  kind. ``scoreMatch(..., term_relationships=...)`` is the existing structural
  validation/consumption route. Its internal related-term index currently treats
  supplied ``parent``/``child`` relationships symmetrically, so reverse-direction
  authorization is enforced here at the handoff/store layer rather than by a
  core validator.
"""

from __future__ import annotations

import importlib
import inspect
import tempfile
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
FAKE_FIXTURES = ROOT / "fixtures" / "resume-agent" / "fake-adapter"
FIXED_TIME = "2026-01-01T00:00:00Z"
USER_PROVENANCE = [{"source": "user_answer", "text": "Confirmed after resume-core validation."}]

EQUIVALENCE_SUBSUMPTION_CONTEXT = {
    "candidate_pairs": [
        {
            "term_a": "React",
            "term_b": "JavaScript framework experience",
            "direction_hint": "narrower_than",
            "evidence_refs": ["ev_resume_react", "ev_job_js_framework"],
        }
    ],
    "evidence": [
        {
            "evidence_id": "ev_resume_react",
            "source": "resume",
            "text": "Experience building React and TypeScript front ends.",
        },
        {
            "evidence_id": "ev_job_js_framework",
            "source": "job",
            "text": "Requires JavaScript framework experience for frontend applications.",
        },
    ],
}

BASE_RESUME = {
    "schema_version": "canonical-resume.v1",
    "resume_id": "resume_equivalence_handoff",
    "source": {"kind": "test_fixture"},
    "summary": "Built React and TypeScript front ends.",
    "experience": [],
    "skills": [],
    "education": [],
}

REVERSE_RESUME = {
    **BASE_RESUME,
    "resume_id": "resume_equivalence_handoff_reverse",
    "summary": "Built JavaScript framework experience across product front ends.",
}

JOB_JS_FRAMEWORK = {
    "schema_version": "job-model.v1",
    "job_id": "job_js_framework",
    "requirements": [
        {
            "requirement_id": "req_js_framework",
            "classification": "required",
            "concept": "JavaScript framework experience",
            "importance": "high",
            "weight": 1.0,
            "source_text": "JavaScript framework experience",
            "normalized_terms": ["javascript framework experience"],
        }
    ],
    "preferred": [],
}

JOB_REACT = {
    "schema_version": "job-model.v1",
    "job_id": "job_react",
    "requirements": [
        {
            "requirement_id": "req_react",
            "classification": "required",
            "concept": "React",
            "importance": "high",
            "weight": 1.0,
            "source_text": "React",
            "normalized_terms": ["react"],
        }
    ],
    "preferred": [],
}


def maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        raise AssertionError("Equivalence handoff surfaces are expected to be synchronous in this E2E.")
    return value


def load_module(test_case: unittest.TestCase, module_name: str):
    try:
        return importlib.import_module(module_name)
    except ModuleNotFoundError:
        test_case.fail(f"Expected importable package {module_name!r}. Run 'pip install -e .' from the repo root first.")


def relationship_from_proposal(proposal: dict[str, Any]) -> dict[str, Any]:
    mapping = {
        "equivalent": "alias",
        "narrower_than": "child",
        "broader_than": "parent",
    }
    return {
        "from": proposal["term_a"],
        "to": proposal["term_b"],
        "kind": mapping[proposal["direction"]],
        "provenance": {
            "source": "resume-agent",
            "proposal_id": proposal["id"],
            "proposal_direction": proposal["direction"],
        },
    }


def store_relationship_type(proposal: dict[str, Any]) -> str:
    return {
        "equivalent": "equivalent",
        "narrower_than": "child",
        "broader_than": "parent",
    }[proposal["direction"]]


def requirement_state(match_payload: dict[str, Any], requirement_id: str) -> str:
    results = {
        item["requirement_id"]: item
        for item in match_payload["match_result"].get("requirement_results", [])
    }
    return results[requirement_id]["resolution_state"]


def relationship_ids(store: Any, *fact_ids: str) -> set[str]:
    ids: set[str] = set()
    for fact_id in fact_ids:
        result = store.getFact(fact_id)
        ids.update(relationship["relationship_id"] for relationship in result.get("relationships", []))
    return ids


def upsert_skill(store: Any, fact_id: str, text: str, terms: list[str]) -> str:
    result = store.upsertFact(
        {
            "fact_id": fact_id,
            "type": "skill",
            "text": text,
            "normalized_terms": terms,
            "verification_state": "unknown",
        },
        {"source": "test", "text": text},
        source="test",
        policy={},
    )
    assert result["status"] in {"created", "updated"}, result
    return result["fact_id"]


class EquivalenceHandoffE2ETests(unittest.TestCase):
    """Proposal -> core structural validation -> career-store relationship."""

    def setUp(self) -> None:
        self.resume_agent = load_module(self, "resume_agent")
        self.resume_core = load_module(self, "resume_core")
        self.career_store = load_module(self, "career_store")
        fake_adapter = load_module(self, "resume_agent._fake_adapter")
        self.adapter = fake_adapter.DeterministicFakeAdapter(fixture_dir=FAKE_FIXTURES)

    def proposed_subsumption(self) -> dict[str, Any]:
        result = maybe_await(
            self.resume_agent.proposeEquivalences(
                {
                    **EQUIVALENCE_SUBSUMPTION_CONTEXT,
                    "_adapter": self.adapter,
                }
            )
        )
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
        proposal = result[0]
        self.assertEqual(proposal["term_a"], "React")
        self.assertEqual(proposal["term_b"], "JavaScript framework experience")
        self.assertEqual(proposal["direction"], "narrower_than")
        self.assertIs(proposal["requires_validation"], True)
        return proposal

    def validate_with_resume_core(self, proposal: dict[str, Any]) -> dict[str, Any]:
        return maybe_await(
            self.resume_core.scoreMatch(
                BASE_RESUME,
                JOB_JS_FRAMEWORK,
                [],
                {},
                [relationship_from_proposal(proposal)],
            )
        )

    def open_store_with_terms(self, directory: str):
        store = self.career_store.openCareerStore(str(Path(directory) / "career.db"), clock=lambda: FIXED_TIME)
        react_id = upsert_skill(store, "fact_react", "React", ["react"])
        js_framework_id = upsert_skill(
            store,
            "fact_js_framework",
            "JavaScript framework experience",
            ["javascript framework experience"],
        )
        return store, react_id, js_framework_id

    def test_validated_subsumption_proposal_is_persisted_only_after_core_consumption(self):
        proposal = self.proposed_subsumption()
        relationship = relationship_from_proposal(proposal)
        self.assertEqual(relationship["kind"], "child")
        self.assertEqual(store_relationship_type(proposal), "child")

        with tempfile.TemporaryDirectory() as directory:
            store, react_id, js_framework_id = self.open_store_with_terms(directory)
            self.assertEqual(relationship_ids(store, react_id, js_framework_id), set())

            validation = self.validate_with_resume_core(proposal)
            self.assertEqual(validation["status"], "ok", validation)
            self.assertEqual(requirement_state(validation, "req_js_framework"), "related_match")
            self.assertEqual(relationship_ids(store, react_id, js_framework_id), set())

            created = store.addRelationship(
                react_id,
                js_framework_id,
                store_relationship_type(proposal),
                evidence_or_rationale={
                    "source": "resume_agent.proposeEquivalences",
                    "proposal_id": proposal["id"],
                    "text": proposal["rationale"],
                    "confidence": proposal["confidence"],
                },
                policy={},
            )
            self.assertEqual(created["status"], "created", created)
            confirmed = store.confirmRelationship(created["relationship_id"], USER_PROVENANCE)
            self.assertEqual(confirmed["status"], "updated", confirmed)

            stored = store.getFact(react_id)["relationships"]
            self.assertEqual(len(stored), 1)
            self.assertEqual(stored[0]["from_fact_id"], react_id)
            self.assertEqual(stored[0]["to_fact_id"], js_framework_id)
            self.assertEqual(stored[0]["relationship_type"], "child")
            self.assertEqual(stored[0]["confirmation_status"], "user_confirmed")

            child_to_parent = store.findCandidateMatches(
                [
                    {
                        "requirement_id": "req_js_framework",
                        "concept": "JavaScript framework experience",
                        "normalized_terms": ["javascript framework experience"],
                    }
                ],
                policy={},
            )
            parent_to_child = store.findCandidateMatches(
                [{"requirement_id": "req_react", "concept": "React", "normalized_terms": ["react"]}],
                policy={},
            )
            child_candidates = [
                candidate
                for match in child_to_parent["matches"]
                for candidate in match["supporting_facts"]
                if candidate.get("relationship_id") == created["relationship_id"]
            ]
            parent_candidates = [
                candidate
                for match in parent_to_child["matches"]
                for candidate in match["supporting_facts"]
                if candidate.get("relationship_id") == created["relationship_id"]
            ]
            self.assertEqual({candidate["matchType"] for candidate in child_candidates}, {"related_match"})
            self.assertEqual({candidate["matchType"] for candidate in parent_candidates}, {"possible_match"})

    def test_rejected_core_consumption_does_not_create_store_relationship(self):
        proposal = self.proposed_subsumption()
        rejected_relationship = relationship_from_proposal(proposal)
        rejected_relationship["kind"] = "equivalent"

        with tempfile.TemporaryDirectory() as directory:
            store, react_id, js_framework_id = self.open_store_with_terms(directory)
            before = relationship_ids(store, react_id, js_framework_id)
            validation = maybe_await(
                self.resume_core.scoreMatch(BASE_RESUME, JOB_JS_FRAMEWORK, [], {}, [rejected_relationship])
            )

            self.assertEqual(validation["status"], "rejected", validation)
            self.assertEqual(validation["errors"][0]["code"], "invalid_term_relationship_kind")
            self.assertEqual(relationship_ids(store, react_id, js_framework_id), before)

    def test_unvalidated_proposal_does_not_create_store_relationship_or_reverse_authority(self):
        proposal = self.proposed_subsumption()

        with tempfile.TemporaryDirectory() as directory:
            store, react_id, js_framework_id = self.open_store_with_terms(directory)
            self.assertEqual(relationship_ids(store, react_id, js_framework_id), set())
            self.assertEqual(proposal["direction"], "narrower_than")
            self.assertEqual(relationship_ids(store, react_id, js_framework_id), set())

            reverse_without_relationship = maybe_await(
                self.resume_core.scoreMatch(REVERSE_RESUME, JOB_REACT, [], {}, [])
            )
            self.assertEqual(reverse_without_relationship["status"], "ok", reverse_without_relationship)
            self.assertEqual(requirement_state(reverse_without_relationship, "req_react"), "unknown")


if __name__ == "__main__":
    unittest.main()
