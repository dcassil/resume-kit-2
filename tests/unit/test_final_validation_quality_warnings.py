"""Unit coverage for final-validation duplicate and stuffing warnings."""

from __future__ import annotations

import unittest

from tests.unit.resume_core_test_utils import load_resume_core


resume_core = load_resume_core()

EMPTY_JOB = {
    "schema_version": "job-model.v1",
    "job_id": "job_quality_warning_unit",
    "requirements": [],
    "preferred": [],
}


def _base_resume() -> dict:
    return {
        "schema_version": "canonical-resume.v1",
        "resume_id": "resume_quality_warning_unit",
        "source": {"kind": "unit"},
        "summary": "Platform builder.",
        "experience": [],
        "skills": [],
        "education": [],
        "provenance": [],
    }


class FinalValidationQualityWarningsTests(unittest.TestCase):
    def test_repeated_experience_entries_and_bullets_are_reported(self):
        resume = _base_resume()
        resume["experience"] = [
            {
                "id": "exp_alpha",
                "company": "Acme",
                "title": "Developer",
                "bullets": ["Built billing tools.", "Reduced release risk."],
            },
            {
                "id": "exp_beta",
                "company": "Acme",
                "title": "Developer",
                "bullets": ["Built billing tools.", "Reduced release risk."],
            },
        ]

        result = resume_core.validateFinalResume(resume, EMPTY_JOB, [], {})

        warning_codes = [warning["code"] for warning in result["warnings"]]
        self.assertEqual(result["status"], "pass", result)
        self.assertIn("duplicate_experience_entry", warning_codes)
        self.assertEqual(warning_codes.count("duplicate_experience_bullet"), 2)
        self.assertEqual(
            [warning["field_path"] for warning in result["warnings"] if warning["code"] == "duplicate_experience_bullet"],
            ["experience.1.bullets.0", "experience.1.bullets.1"],
        )

    def test_keyword_stuffing_reports_every_repeated_term_in_stable_order(self):
        resume = _base_resume()
        resume["summary"] = " ".join(["django"] * 9 + ["python"] * 9 + ["delivery", "platform"])

        first = resume_core.validateFinalResume(resume, EMPTY_JOB, [], {})
        second = resume_core.validateFinalResume(resume, EMPTY_JOB, [], {})

        stuffed_terms = [
            warning["details"]["term"]
            for warning in first["warnings"]
            if warning["code"] == "possible_keyword_stuffing"
        ]
        self.assertEqual(first, second)
        self.assertEqual(first["status"], "pass", first)
        self.assertEqual(stuffed_terms, ["django", "python"])


if __name__ == "__main__":
    unittest.main()
