"""Stable unit checks for requirement relationship matching.

RKIT-I-0001 chunk 6 (RKIT-T-0010) owns date, requirement, change, and enum
coverage. This module stays scoped to stable scoreMatch relationship outcomes.
"""

from __future__ import annotations

import copy
import unittest

from tests.unit.resume_core_test_utils import load_resume_core


resume_core = load_resume_core()


def _requirement(requirement_id: str, concept: str, terms: list[str] | None = None) -> dict:
    return {
        "requirement_id": requirement_id,
        "classification": "required",
        "concept": concept,
        "weight": 1,
        "source_text": concept,
        "normalized_terms": terms or [concept.lower()],
    }


def _resume() -> dict:
    return {
        "schema_version": "canonical-resume.v1",
        "resume_id": "resume_relationship_unit",
        "source": {"kind": "unit"},
        "summary": "Built Vue dashboards, REST API integrations, and React component libraries.",
        "experience": [],
        "skills": [],
        "education": [],
    }


def _job() -> dict:
    return {
        "schema_version": "job-model.v1",
        "job_id": "job_relationship_unit",
        "requirements": [
            _requirement("req_react", "React"),
            _requirement("req_angular", "Angular"),
            _requirement("req_kubernetes", "Kubernetes"),
            _requirement("req_graphql", "GraphQL"),
            _requirement("req_react_native", "React Native", ["react native"]),
            _requirement("req_aws", "AWS"),
        ],
        "preferred": [],
    }


def _facts() -> list[dict]:
    return [
        {"fact_id": "fact_kubernetes", "text": "Kubernetes", "verification_state": "user_verified"},
        {
            "fact_id": "fact_aws_missing",
            "text": "AWS",
            "verification_state": "unknown",
            "resolution_state": "explicitly_missing",
        },
    ]


class RelationshipMatchingUnitTests(unittest.TestCase):
    def test_resolution_states_remain_distinct_and_repeatable(self):
        config = {"aliases": {"angular": ["vue"]}}

        first = resume_core.scoreMatch(copy.deepcopy(_resume()), copy.deepcopy(_job()), copy.deepcopy(_facts()), config)
        second = resume_core.scoreMatch(copy.deepcopy(_resume()), copy.deepcopy(_job()), copy.deepcopy(_facts()), config)

        self.assertEqual(first, second)
        results = {item["requirement_id"]: item for item in first["match_result"]["requirement_results"]}
        self.assertEqual(results["req_react"]["resolution_state"], "exact_match")
        self.assertEqual(results["req_angular"]["resolution_state"], "alias_match")
        self.assertEqual(results["req_kubernetes"]["resolution_state"], "verified_fact_match")
        self.assertEqual(results["req_graphql"]["resolution_state"], "related_match")
        self.assertEqual(results["req_react_native"]["resolution_state"], "possible_match")
        self.assertEqual(results["req_aws"]["resolution_state"], "explicitly_missing")

    def test_only_equivalent_relationships_receive_score(self):
        match = resume_core.scoreMatch(_resume(), _job(), _facts(), {"aliases": {"angular": ["vue"]}})["match_result"]
        scores = {item["requirement_id"]: item["score"] for item in match["requirement_results"]}

        self.assertEqual(scores["req_react"], 1.0)
        self.assertEqual(scores["req_angular"], 1.0)
        self.assertEqual(scores["req_kubernetes"], 1.0)
        self.assertEqual(scores["req_graphql"], 0.0)
        self.assertEqual(scores["req_react_native"], 0.0)
        self.assertEqual(scores["req_aws"], 0.0)
        self.assertEqual(match["score"], 4.0)
        self.assertEqual(match["max_score"], 6.0)


if __name__ == "__main__":
    unittest.main()
