"""Unit coverage for MatchResult weighted dimensions."""

from __future__ import annotations

import copy
import unittest

from tests.unit.resume_core_test_utils import load_resume_core


resume_core = load_resume_core()


def _resume() -> dict:
    return {
        "schema_version": "canonical-resume.v1",
        "resume_id": "resume_match_dimensions_unit",
        "source": {"kind": "unit"},
        "summary": "Senior engineer with 12 years of software engineering experience building React and SaaS APIs.",
        "experience": [],
        "skills": ["React", "API architecture", "SaaS"],
        "education": [],
    }


def _job() -> dict:
    return {
        "schema_version": "job-model.v1",
        "job_id": "job_match_dimensions_unit",
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
                "requirement_id": "req_years",
                "classification": "required",
                "concept": "8+ years of software engineering experience",
                "weight": 10,
                "source_text": "8+ years of software engineering experience",
                "normalized_terms": ["8 years", "software engineering experience"],
            },
            {
                "requirement_id": "req_role",
                "classification": "contextual",
                "concept": "Senior engineer role alignment",
                "weight": 2,
                "source_text": "Senior engineer role alignment",
                "normalized_terms": ["senior engineer"],
            },
            {
                "requirement_id": "req_domain",
                "classification": "required",
                "concept": "SaaS product background",
                "weight": 10,
                "source_text": "SaaS product background",
                "normalized_terms": ["saas"],
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


def _dimensions(match: dict) -> dict[str, dict]:
    return {dimension["name"]: dimension for dimension in match["dimensions"]}


class MatchDimensionsUnitTests(unittest.TestCase):
    def test_weight_variation_changes_contribution_deterministically(self):
        default_match = resume_core.scoreMatch(copy.deepcopy(_resume()), copy.deepcopy(_job()), [], {})["match_result"]
        varied_match = resume_core.scoreMatch(
            copy.deepcopy(_resume()),
            copy.deepcopy(_job()),
            [],
            {"matching": {"weights": {"requiredSkills": 0.6}}},
        )["match_result"]

        default_required = _dimensions(default_match)["requiredSkills"]
        varied_required = _dimensions(varied_match)["requiredSkills"]

        self.assertEqual(default_required["score"], varied_required["score"])
        self.assertEqual(default_required["weight"], 0.3)
        self.assertEqual(varied_required["weight"], 0.6)
        self.assertEqual(varied_required["contribution"], round(0.6 * varied_required["score"], 6))
        self.assertNotEqual(default_match["score"], varied_match["score"])
        repeated_match = resume_core.scoreMatch(
            copy.deepcopy(_resume()),
            copy.deepcopy(_job()),
            [],
            {"matching": {"weights": {"requiredSkills": 0.6}}},
        )["match_result"]
        self.assertEqual(varied_match, repeated_match)

    def test_dimensions_sum_to_score_at_match_precision(self):
        match = resume_core.scoreMatch(_resume(), _job(), [], {})["match_result"]

        weight_total = sum(dimension["weight"] for dimension in match["dimensions"])
        contribution_total = sum(dimension["contribution"] for dimension in match["dimensions"])
        reconstructed = round((contribution_total / weight_total) * match["max_score"], 4)

        self.assertEqual(match["score"], reconstructed)

    def test_empty_terminology_dimension_is_neutral(self):
        match = resume_core.scoreMatch(
            _resume(),
            _job(),
            [],
            {"matching": {"weights": {"terminology": 0.2}}},
        )["match_result"]

        terminology = _dimensions(match)["terminology"]

        self.assertEqual(terminology["weight"], 0.2)
        self.assertEqual(terminology["score"], 1.0)
        self.assertEqual(terminology["contribution"], 0.2)
        self.assertEqual(terminology["evidence"], [])


if __name__ == "__main__":
    unittest.main()
