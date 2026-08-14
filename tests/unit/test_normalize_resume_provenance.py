"""Unit checks for normalizeResume provenance defaults and honesty."""

from __future__ import annotations

import copy
import unittest

from tests.unit.resume_core_test_utils import load_resume_core


resume_core = load_resume_core()


def _resume_with_claims() -> dict:
    return {
        "schema_version": "canonical-resume.v1",
        "resume_id": "resume_claim_fields",
        "source": {"kind": "unit"},
        "summary": "Builds React workflows.\nLeads API design.",
        "experience": [
            {
                "id": "exp_1",
                "company": "Example SaaS",
                "title": "Software Engineer",
                "bullets": [
                    {"value": "Built React workflows.", "claim_id": "claim_bullet_react"},
                    "Mentored engineers on API design.",
                ],
            }
        ],
        "skills": ["React"],
        "education": [],
        "provenance": [
            {
                "claim_id": "claim_bullet_react",
                "source": "resume",
                "text": "Built React workflows.",
                "verification_state": "source_stated",
            }
        ],
    }


class NormalizeResumeProvenanceTests(unittest.TestCase):
    def test_source_backed_claim_preserves_provenance_and_source_stated_state(self):
        result = resume_core.normalizeResume(_resume_with_claims())
        bullet = result["canonical_resume"]["experience"][0]["bullets"][0]

        self.assertEqual(result.get("status"), "ok", result)
        self.assertEqual(bullet["value"], "Built React workflows.")
        self.assertEqual(bullet["claim_id"], "claim_bullet_react")
        self.assertEqual(bullet["verification_state"], "source_stated")
        self.assertEqual(
            bullet["provenance"],
            [
                {
                    "claim_id": "claim_bullet_react",
                    "source": "resume",
                    "text": "Built React workflows.",
                    "verification_state": "source_stated",
                }
            ],
        )
        self.assertIn("claim_bullet_react", result["provenance_map"])

    def test_sourceless_claim_defaults_to_empty_provenance_and_unknown(self):
        result = resume_core.normalizeResume(_resume_with_claims())
        sourceless_fields = [
            *result["canonical_resume"]["summary"],
            result["canonical_resume"]["skills"][0],
            result["canonical_resume"]["experience"][0]["bullets"][1],
        ]

        for field in sourceless_fields:
            with self.subTest(claim_id=field["claim_id"]):
                self.assertEqual(field["provenance"], [])
                self.assertEqual(field["verification_state"], "unknown")
                self.assertNotEqual(field["verification_state"], "source_stated")

    def test_malformed_provenance_is_not_treated_as_source_stated_support(self):
        resume = _resume_with_claims()
        resume["provenance"] = [{"claim_id": "claim_bullet_react", "text": "Built React workflows."}]

        result = resume_core.normalizeResume(resume)
        bullet = result["canonical_resume"]["experience"][0]["bullets"][0]

        self.assertEqual(bullet["provenance"], [])
        self.assertEqual(bullet["verification_state"], "unknown")

    def test_claim_ids_and_provenance_defaults_are_repeatable(self):
        first = resume_core.normalizeResume(copy.deepcopy(_resume_with_claims()))["canonical_resume"]
        second = resume_core.normalizeResume(copy.deepcopy(_resume_with_claims()))["canonical_resume"]

        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
