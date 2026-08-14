"""Unit checks for JobModel section-4.2 fields and JobTerm determinism."""

from __future__ import annotations

import copy
import unittest

from resume_core_test_utils import load_resume_core


resume_core = load_resume_core()


def _source_job() -> dict:
    return {
        "schema_version": "job-model.v1",
        "job_id": "job_terms_unit",
        "title": "Senior Platform Engineer",
        "company": "Example SaaS",
        "description": "Build REST API architecture for responsive web products.",
        "requirements": [
            {
                "requirement_id": "req_react",
                "classification": "required",
                "concept": "React",
                "importance": "high",
                "weight": 10,
                "source_text": "Required React experience",
                "normalized_terms": ["react"],
            },
            "Required API architecture experience",
        ],
        "preferred": [
            {
                "requirement_id": "req_aws",
                "concept": "AWS",
                "importance": "medium",
                "weight": 3,
                "source_text": "Preferred AWS experience",
                "normalized_terms": ["aws"],
            }
        ],
    }


class JobModelJobTermDeterminismTests(unittest.TestCase):
    def test_section_4_2_fields_and_job_terms_are_deterministically_populated(self):
        first = resume_core.normalizeJobModel(copy.deepcopy(_source_job()))
        second = resume_core.normalizeJobModel(copy.deepcopy(_source_job()))

        self.assertEqual(first, second)
        self.assertEqual(first.get("status"), "ok", first)
        job_model = first["job_model"]
        self.assertEqual(job_model["seniority"], "senior")
        self.assertEqual(job_model["industries"], ["SaaS"])
        self.assertEqual(job_model["domains"], ["API architecture", "Cloud infrastructure", "Responsive design"])
        self.assertEqual([item["requirement_id"] for item in job_model["requirements"]], ["req_react", "req_1_da02a901"])
        self.assertEqual([item["requirement_id"] for item in job_model["preferred"]], ["req_aws"])
        self.assertTrue(job_model["terminology"])

        for term in job_model["terminology"]:
            with self.subTest(term=term):
                self.assertTrue(term.get("surface"))
                self.assertTrue(term.get("canonical"))
                self.assertIn(term.get("source"), {"title", "requirement", "description"})
                self.assertIsInstance(term.get("weight"), float)

    def test_preferred_requirements_remain_separate_from_required_requirements(self):
        result = resume_core.normalizeJobModel(_source_job())
        job_model = result["job_model"]
        required_ids = {item["requirement_id"] for item in job_model["requirements"]}
        preferred_ids = {item["requirement_id"] for item in job_model["preferred"]}

        self.assertEqual(result.get("status"), "ok", result)
        self.assertIn("req_aws", preferred_ids)
        self.assertNotIn("req_aws", required_ids)

    def test_invalid_requirement_shapes_warn_and_do_not_fabricate_job_terms(self):
        result = resume_core.normalizeJobModel(
            {
                "schema_version": "job-model.v1",
                "job_id": "job_invalid_requirements_unit",
                "requirements": {"concept": "React"},
                "preferred": {"concept": "AWS"},
            }
        )

        self.assertEqual(result.get("status"), "warning", result)
        self.assertEqual(result["job_model"]["requirements"], [])
        self.assertEqual(result["job_model"]["preferred"], [])
        self.assertEqual(result["job_model"]["terminology"], [])
        self.assertEqual(
            {warning.get("code") for warning in result.get("warnings", [])},
            {"invalid_requirements", "invalid_preferred"},
        )


if __name__ == "__main__":
    unittest.main()
