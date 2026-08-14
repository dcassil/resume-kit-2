"""Unit checks for canonical resume date validation."""

from __future__ import annotations

import unittest

import resume_core


def _resume(start_date: str, end_date: str | None = None) -> dict:
    entry = {
        "id": "exp_dates",
        "company": "Example Co",
        "title": "Engineer",
        "start_date": start_date,
    }
    if end_date is not None:
        entry["end_date"] = end_date
    return {
        "schema_version": "canonical-resume.v1",
        "resume_id": "resume_dates",
        "source": {"kind": "test_fixture"},
        "experience": [entry],
        "skills": [],
        "education": [],
    }


class ValidateResumeDateTests(unittest.TestCase):
    def test_ambiguous_but_possible_dates_warn_and_canonicalize(self):
        for value in ("Jan 2019", "01/2019"):
            with self.subTest(value=value):
                resume = _resume(value, "present")
                result = resume_core.validateResume(resume)

                self.assertEqual(result.get("status"), "ok", result)
                self.assertEqual(result.get("errors"), [])
                self.assertEqual(result["canonical_resume"]["experience"][0]["start_date"], "2019-01")
                warning_codes = {warning.get("code") for warning in result.get("warnings", [])}
                self.assertIn("ambiguous_start_date", warning_codes)
                self.assertIn(
                    {"canonical": "2019-01"},
                    [warning.get("details") for warning in result.get("warnings", [])],
                )

    def test_canonical_year_and_year_month_dates_are_clean(self):
        for start_date, end_date in (("2019", "present"), ("2019-05", "current")):
            with self.subTest(start_date=start_date, end_date=end_date):
                resume = _resume(start_date, end_date)
                result = resume_core.validateResume(resume)

                self.assertEqual(result.get("status"), "ok", result)
                self.assertEqual(result.get("errors"), [])
                self.assertEqual(result.get("warnings"), [])

    def test_impossible_month_is_invalid_date_not_ambiguous(self):
        resume = _resume("2019-13")
        result = resume_core.validateResume(resume)

        self.assertEqual(result.get("status"), "error", result)
        self.assertIn("invalid_date", {error.get("code") for error in result.get("errors", [])})
        self.assertNotIn("ambiguous_start_date", {warning.get("code") for warning in result.get("warnings", [])})

    def test_reversed_range_is_typed_error(self):
        resume = _resume("2020", "2019")
        result = resume_core.validateResume(resume)

        self.assertEqual(result.get("status"), "error", result)
        self.assertIn("reversed_range", {error.get("code") for error in result.get("errors", [])})

    def test_unparseable_date_remains_ambiguous_warning(self):
        resume = _resume("spring")
        result = resume_core.validateResume(resume)

        self.assertEqual(result.get("status"), "ok", result)
        self.assertEqual(result.get("errors"), [])
        self.assertIn("ambiguous_start_date", {warning.get("code") for warning in result.get("warnings", [])})


if __name__ == "__main__":
    unittest.main()
