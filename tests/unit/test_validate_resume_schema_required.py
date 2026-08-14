"""Unit checks for schema-backed resume validation."""

from __future__ import annotations

import unittest

import resume_core


def _minimal_resume() -> dict:
    return {
        "schema_version": "canonical-resume.v1",
        "experience": [],
        "skills": [],
        "education": [],
    }


class ValidateResumeSchemaRequiredTests(unittest.TestCase):
    def test_missing_schema_required_identity_fields_emit_typed_errors(self):
        result = resume_core.validateResume(_minimal_resume())

        missing_fields = {
            error.get("field_path")
            for error in result.get("errors", [])
            if error.get("code") == "missing_field"
        }
        self.assertIn("resume_id", missing_fields)
        self.assertIn("source", missing_fields)

    def test_normalize_backfills_required_fields_without_missing_field_errors(self):
        normalized = resume_core.normalizeResume(_minimal_resume())["canonical_resume"]
        result = resume_core.validateResume(normalized)

        self.assertEqual(result.get("status"), "ok", result)
        self.assertEqual(
            [error for error in result.get("errors", []) if error.get("code") == "missing_field"],
            [],
        )

    def test_imported_verification_state_is_valid(self):
        resume = {
            **_minimal_resume(),
            "resume_id": "resume_imported",
            "source": {},
            "verification_state": "imported",
        }
        result = resume_core.validateResume(resume)

        self.assertEqual(result.get("status"), "ok", result)
        self.assertNotIn("invalid_verification_state", {error.get("code") for error in result.get("errors", [])})

    def test_unknown_verification_state_is_rejected(self):
        resume = {
            **_minimal_resume(),
            "resume_id": "resume_bad_state",
            "source": {},
            "verification_state": "made_up",
        }
        result = resume_core.validateResume(resume)

        self.assertEqual(result.get("status"), "error", result)
        self.assertIn("invalid_verification_state", {error.get("code") for error in result.get("errors", [])})


if __name__ == "__main__":
    unittest.main()
