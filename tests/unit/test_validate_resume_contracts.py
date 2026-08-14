"""Consolidated unit checks for schema-backed resume validation and dates."""

from __future__ import annotations

import copy
import unittest

from resume_core_test_utils import load_resume_core


resume_core = load_resume_core()


def _valid_resume() -> dict:
    return {
        "schema_version": "canonical-resume.v1",
        "resume_id": "resume_validation_unit",
        "source": {"kind": "unit"},
        "experience": [
            {
                "id": "exp_dates",
                "company": "Example Co",
                "title": "Engineer",
                "start_date": "2019",
                "end_date": "present",
            }
        ],
        "skills": [],
        "education": [],
    }


def _resume_with_dates(start_date: str, end_date: str | None = "present") -> dict:
    resume = _valid_resume()
    entry = resume["experience"][0]
    entry["start_date"] = start_date
    if end_date is None:
        entry.pop("end_date", None)
    else:
        entry["end_date"] = end_date
    return resume


class ValidateResumeRequiredFieldTests(unittest.TestCase):
    def test_valid_resume_satisfies_every_canonical_schema_required_field(self):
        required = set(resume_core.CANONICAL_RESUME_SCHEMA["required"])
        self.assertEqual(required, {"schema_version", "resume_id", "source", "experience", "skills", "education"})

        result = resume_core.validateResume(_valid_resume())

        self.assertEqual(result.get("status"), "ok", result)
        self.assertEqual(
            [error for error in result.get("errors", []) if error.get("code") == "missing_field"],
            [],
        )

    def test_each_canonical_schema_required_field_is_enforced(self):
        for field_name in resume_core.CANONICAL_RESUME_SCHEMA["required"]:
            with self.subTest(field_name=field_name):
                resume = _valid_resume()
                del resume[field_name]
                result = resume_core.validateResume(resume)
                missing_fields = {
                    error.get("field_path")
                    for error in result.get("errors", [])
                    if error.get("code") == "missing_field"
                }
                self.assertEqual(result.get("status"), "error", result)
                self.assertIn(field_name, missing_fields)

    def test_normalize_backfills_required_identity_fields_without_validation_errors(self):
        sparse = {"schema_version": "canonical-resume.v1", "experience": [], "skills": [], "education": []}
        normalized = resume_core.normalizeResume(sparse)["canonical_resume"]
        result = resume_core.validateResume(normalized)

        self.assertEqual(result.get("status"), "ok", result)
        self.assertIn("resume_id", normalized)
        self.assertIn("source", normalized)


class ValidateResumeDateTests(unittest.TestCase):
    def test_supported_date_shapes_canonicalize_deterministically(self):
        cases = (
            ("2019", "2019", []),
            ("2019-5", "2019-05", []),
            ("Jan 2019", "2019-01", ["ambiguous_start_date"]),
            ("01/2019", "2019-01", ["ambiguous_start_date"]),
        )

        for raw, canonical, expected_warning_codes in cases:
            with self.subTest(raw=raw):
                result = resume_core.validateResume(_resume_with_dates(raw))
                entry = result["canonical_resume"]["experience"][0]
                warning_codes = [warning.get("code") for warning in result.get("warnings", [])]

                self.assertEqual(result.get("status"), "ok", result)
                self.assertEqual(result.get("errors"), [])
                self.assertEqual(entry["start_date"], canonical)
                self.assertEqual(warning_codes, expected_warning_codes)

    def test_present_and_current_end_dates_are_preserved_without_invented_end_dates(self):
        for sentinel in ("present", "current"):
            with self.subTest(sentinel=sentinel):
                result = resume_core.validateResume(_resume_with_dates("2019-01", sentinel))
                entry = result["canonical_resume"]["experience"][0]

                self.assertEqual(result.get("status"), "ok", result)
                self.assertEqual(entry["end_date"], sentinel)

    def test_impossible_start_and_end_months_are_invalid_date_errors(self):
        cases = (
            ("2019-13", "present", "experience/0/start_date"),
            ("2019-01", "13/2020", "experience/0/end_date"),
        )

        for start_date, end_date, field_path in cases:
            with self.subTest(start_date=start_date, end_date=end_date):
                result = resume_core.validateResume(_resume_with_dates(start_date, end_date))
                matching_errors = [
                    error
                    for error in result.get("errors", [])
                    if error.get("code") == "invalid_date" and error.get("field_path") == field_path
                ]
                self.assertEqual(result.get("status"), "error", result)
                self.assertEqual(len(matching_errors), 1)

    def test_reversed_ranges_are_typed_errors_across_supported_shapes(self):
        cases = (
            ("2020", "2019"),
            ("2020-02", "2020-01"),
            ("Feb 2020", "Jan 2020"),
            ("02/2020", "01/2020"),
        )

        for start_date, end_date in cases:
            with self.subTest(start_date=start_date, end_date=end_date):
                result = resume_core.validateResume(_resume_with_dates(start_date, end_date))

                self.assertEqual(result.get("status"), "error", result)
                self.assertIn("reversed_range", {error.get("code") for error in result.get("errors", [])})

    def test_unparseable_date_remains_ambiguous_warning_not_typed_rejection(self):
        result = resume_core.validateResume(_resume_with_dates("spring", None))

        self.assertEqual(result.get("status"), "ok", result)
        self.assertEqual(result.get("errors"), [])
        self.assertIn("ambiguous_start_date", {warning.get("code") for warning in result.get("warnings", [])})

    def test_validate_resume_date_normalization_is_repeatable(self):
        resume = _resume_with_dates("01/2019", "02/2020")
        first = resume_core.validateResume(copy.deepcopy(resume))
        second = resume_core.validateResume(copy.deepcopy(resume))

        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
