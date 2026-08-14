"""Unit coverage for live terminology match dimension scoring."""

from __future__ import annotations

import copy
import unittest

from tests.unit.resume_core_test_utils import load_resume_core


resume_core = load_resume_core()


def _normalize_resume(resume: dict) -> dict:
    return resume_core.normalizeResume(copy.deepcopy(resume), {})["canonical_resume"]


def _base_resume(summary: str) -> dict:
    return {
        "schema_version": "canonical-resume.v1",
        "resume_id": "resume_terminology_dimension_unit",
        "source": {"kind": "unit"},
        "summary": summary,
        "experience": [],
        "skills": ["React"],
        "education": [],
    }


def _job(terminology: list[dict]) -> dict:
    return {
        "schema_version": "job-model.v1",
        "job_id": "job_terminology_dimension_unit",
        "requirements": [
            {
                "requirement_id": "req_react",
                "classification": "required",
                "concept": "React",
                "weight": 10,
                "source_text": "React",
                "normalized_terms": ["react"],
            }
        ],
        "preferred": [],
        "terminology": terminology,
    }


def _term(surface: str, canonical: str | None = None) -> dict:
    return {
        "surface": surface,
        "canonical": canonical or surface.lower(),
        "source": "requirement",
        "weight": 1.0,
    }


def _match(summary: str, terminology: list[dict], config: dict | None = None) -> dict:
    return resume_core.scoreMatch(_normalize_resume(_base_resume(summary)), _job(terminology), [], config or {})["match_result"]


def _dimensions(match: dict) -> dict[str, dict]:
    return {dimension["name"]: dimension for dimension in match["dimensions"]}


class TerminologyDimensionUnitTests(unittest.TestCase):
    def test_surface_mirroring_scores_higher_than_canonical_only_with_same_requirements(self):
        terms = [_term("responsive web apps", "responsive design")]

        surface_match = _match("Built responsive web apps with React.", terms)
        canonical_match = _match("Built responsive design systems with React.", terms)

        surface_dimension = _dimensions(surface_match)["terminology"]
        canonical_dimension = _dimensions(canonical_match)["terminology"]
        self.assertEqual(surface_dimension["score"], 1.0)
        self.assertEqual(canonical_dimension["score"], 0.0)
        self.assertGreater(surface_match["score"], canonical_match["score"])
        self.assertEqual(canonical_dimension["evidence"][0]["matched_form"], "canonical_only")
        self.assertEqual(canonical_dimension["evidence"][0]["where"][0]["field_path"], "summary")
        self.assertIn("claim_id", canonical_dimension["evidence"][0]["where"][0])
        self.assertEqual(surface_match["requirement_results"], canonical_match["requirement_results"])

    def test_java_surface_matching_does_not_match_javascript(self):
        match = _match("Built JavaScript applications with React.", [_term("Java")])

        terminology = _dimensions(match)["terminology"]

        self.assertEqual(terminology["score"], 0.0)
        self.assertEqual(terminology["evidence"][0]["matched_form"], "none")
        self.assertEqual(terminology["evidence"][0]["where"], [])

    def test_empty_job_terminology_is_neutral(self):
        match = _match("Built React interfaces.", [])

        terminology = _dimensions(match)["terminology"]

        self.assertEqual(terminology["score"], 1.0)
        self.assertEqual(terminology["contribution"], terminology["weight"])
        self.assertEqual(terminology["evidence"], [])

    def test_terminology_weight_zero_removes_score_influence(self):
        terms = [_term("responsive web apps", "responsive design")]
        config = {"matching": {"weights": {"terminology": 0}}}

        missing_surface_match = _match("Built React interfaces.", terms, config)
        no_terms_match = _match("Built React interfaces.", [], config)
        default_weight_match = _match("Built React interfaces.", terms)

        terminology = _dimensions(missing_surface_match)["terminology"]
        self.assertEqual(terminology["weight"], 0.0)
        self.assertEqual(terminology["score"], 0.0)
        self.assertEqual(terminology["contribution"], 0.0)
        self.assertEqual(missing_surface_match["score"], no_terms_match["score"])
        self.assertLess(default_weight_match["score"], missing_surface_match["score"])

    def test_dimensions_sum_to_score_with_live_terminology(self):
        match = _match(
            "Built responsive web apps with React.",
            [_term("responsive web apps", "responsive design"), _term("API architecture")],
        )

        weight_total = sum(dimension["weight"] for dimension in match["dimensions"])
        contribution_total = sum(dimension["contribution"] for dimension in match["dimensions"])
        reconstructed = round((contribution_total / weight_total) * match["max_score"], 4)

        self.assertEqual(match["score"], reconstructed)


if __name__ == "__main__":
    unittest.main()
