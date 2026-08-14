"""Stable unit checks for deterministic scoreMatch math.

RKIT-I-0001 chunk 6 (RKIT-T-0010) owns date, requirement, change, and enum
coverage. This module stays scoped to RKIT-I-0001-stable scoring arithmetic.
"""

from __future__ import annotations

import copy
import unittest

from tests.unit.resume_core_test_utils import load_resume_core


resume_core = load_resume_core()


def _resume() -> dict:
    return {
        "schema_version": "canonical-resume.v1",
        "resume_id": "resume_scoring_math_unit",
        "source": {"kind": "unit"},
        "summary": "Built React interfaces and REST API services.",
        "experience": [],
        "skills": ["React"],
        "education": [],
    }


def _job() -> dict:
    return {
        "schema_version": "job-model.v1",
        "job_id": "job_scoring_math_unit",
        "requirements": [
            {
                "requirement_id": "req_react",
                "classification": "required",
                "concept": "React",
                "weight": 10,
                "source_text": "React",
                "normalized_terms": ["react"],
            },
            {
                "requirement_id": "req_node",
                "classification": "required",
                "concept": "Node.js",
                "weight": 5,
                "source_text": "Node.js",
                "normalized_terms": ["node.js"],
            },
        ],
        "preferred": [
            {
                "requirement_id": "pref_aws",
                "classification": "preferred",
                "concept": "AWS",
                "weight": 3,
                "source_text": "AWS",
                "normalized_terms": ["aws"],
            }
        ],
    }


class ScoringMathUnitTests(unittest.TestCase):
    def test_score_dimensions_and_percent_are_repeatable(self):
        first = resume_core.scoreMatch(copy.deepcopy(_resume()), copy.deepcopy(_job()), [], {})
        second = resume_core.scoreMatch(copy.deepcopy(_resume()), copy.deepcopy(_job()), [], {})

        self.assertEqual(first, second)
        match = first["match_result"]
        self.assertEqual(match["score"], 7.2)
        self.assertEqual(match["max_score"], 18.0)
        self.assertEqual(match["score_percent"], 40.0)
        self.assertEqual(match["algorithm_version"], "resume-core.match.v1")

    def test_missing_preferred_is_distinct_from_required_blockers(self):
        match = resume_core.scoreMatch(_resume(), _job(), [], {})["match_result"]

        self.assertEqual(match["unresolved_requirement_ids"], ["req_node"])
        self.assertEqual(match["preferred_unresolved_requirement_ids"], ["pref_aws"])
        result_by_id = {item["requirement_id"]: item for item in match["requirement_results"]}
        self.assertTrue(result_by_id["req_node"]["blocking"])
        self.assertFalse(result_by_id["pref_aws"]["blocking"])
        self.assertFalse(match["can_continue"])

    def test_verified_preferred_fact_increases_score_without_clearing_required_blocker(self):
        facts = [{"fact_id": "fact_aws", "text": "AWS", "verification_state": "user_verified"}]

        match = resume_core.scoreMatch(_resume(), _job(), facts, {})["match_result"]

        self.assertEqual(match["score"], 10.8)
        self.assertEqual(match["max_score"], 18.0)
        self.assertEqual(match["score_percent"], 60.0)
        self.assertEqual(match["unresolved_requirement_ids"], ["req_node"])
        self.assertEqual(match["preferred_unresolved_requirement_ids"], [])


if __name__ == "__main__":
    unittest.main()
