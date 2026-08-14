"""Unit checks for claim-level ResumeField weaving in normalizeResume."""

from __future__ import annotations

import unittest

import resume_core


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


class NormalizeResumeClaimFieldsTests(unittest.TestCase):
    def test_bullet_provenance_defaults_and_provenance_map_round_trip(self):
        result = resume_core.normalizeResume(_resume_with_claims())

        self.assertEqual(result.get("status"), "ok", result)
        resume = result["canonical_resume"]
        bullets = resume["experience"][0]["bullets"]
        matched = bullets[0]
        unmatched = bullets[1]

        self.assertEqual(matched["value"], "Built React workflows.")
        self.assertEqual(matched["claim_id"], "claim_bullet_react")
        self.assertTrue(matched["provenance"])
        self.assertEqual(matched["verification_state"], "source_stated")

        self.assertEqual(unmatched["value"], "Mentored engineers on API design.")
        self.assertEqual(unmatched["provenance"], [])
        self.assertEqual(unmatched["verification_state"], "unknown")

        self.assertIn("claim_bullet_react", result["provenance_map"])
        self.assertEqual(result["provenance_map"]["claim_bullet_react"]["text"], "Built React workflows.")

    def test_claim_ids_are_deterministic_for_repeated_normalization(self):
        first = resume_core.normalizeResume(_resume_with_claims())["canonical_resume"]
        second = resume_core.normalizeResume(_resume_with_claims())["canonical_resume"]

        first_claim_ids = [
            first["summary"][0]["claim_id"],
            first["summary"][1]["claim_id"],
            first["skills"][0]["claim_id"],
            first["experience"][0]["bullets"][0]["claim_id"],
            first["experience"][0]["bullets"][1]["claim_id"],
        ]
        second_claim_ids = [
            second["summary"][0]["claim_id"],
            second["summary"][1]["claim_id"],
            second["skills"][0]["claim_id"],
            second["experience"][0]["bullets"][0]["claim_id"],
            second["experience"][0]["bullets"][1]["claim_id"],
        ]

        self.assertEqual(first_claim_ids, second_claim_ids)

    def test_summary_lines_and_skill_entries_are_resume_fields(self):
        resume = resume_core.normalizeResume(_resume_with_claims())["canonical_resume"]

        for field in [*resume["summary"], resume["skills"][0]]:
            with self.subTest(field=field["claim_id"]):
                self.assertIn("value", field)
                self.assertIn("claim_id", field)
                self.assertEqual(field["provenance"], [])
                self.assertEqual(field["verification_state"], "unknown")


if __name__ == "__main__":
    unittest.main()
