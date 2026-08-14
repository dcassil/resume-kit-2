"""Unit coverage for requirement classification inference."""

from __future__ import annotations

import unittest

from tests.unit.resume_core_test_utils import load_resume_core


resume_core = load_resume_core()


class InferClassificationUnitTests(unittest.TestCase):
    def test_plus_years_phrasings_infer_required(self):
        result = resume_core.normalizeJobModel(
            {
                "title": "Platform Engineer",
                "requirements": [
                    "5+ years of Python experience",
                    "10+ years building distributed systems",
                    "3+ years experience with APIs",
                ],
                "preferred": [],
            }
        )

        self.assertEqual(result["status"], "ok")
        classifications = [item["classification"] for item in result["job_model"]["requirements"]]
        self.assertEqual(classifications, ["required", "required", "required"])

    def test_explicit_preferred_classification_takes_precedence_over_plus_years(self):
        result = resume_core.normalizeJobModel(
            {
                "title": "Platform Engineer",
                "requirements": [
                    {
                        "requirement_id": "req_aws_preferred",
                        "classification": "preferred",
                        "concept": "AWS",
                        "source_text": "5+ years of AWS preferred",
                        "normalized_terms": ["aws"],
                    }
                ],
                "preferred": ["Preferred: 10+ years with Terraform"],
            }
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["job_model"]["requirements"], [])
        self.assertEqual([item["classification"] for item in result["job_model"]["preferred"]], ["preferred", "preferred"])


if __name__ == "__main__":
    unittest.main()
