"""Unit checks for restored verification and resolution enum membership."""

from __future__ import annotations

import unittest

from resume_core_test_utils import load_resume_core


resume_core = load_resume_core()


def _minimal_resume(verification_state: str) -> dict:
    return {
        "schema_version": "canonical-resume.v1",
        "resume_id": f"resume_{verification_state}",
        "source": {"kind": "unit"},
        "experience": [],
        "skills": [],
        "education": [],
        "verification_state": verification_state,
    }


class EnumMembershipTests(unittest.TestCase):
    def test_verification_state_set_accepts_imported_only_in_verification_domain(self):
        verification_states = {state.value for state in resume_core.VerificationState}

        self.assertEqual(
            verification_states,
            {"source_stated", "user_verified", "imported", "inferred", "unknown"},
        )
        self.assertIn("imported", verification_states)
        self.assertNotIn("explicitly_missing", verification_states)
        self.assertNotIn("conflicted", verification_states)
        self.assertEqual(
            set(resume_core.CANONICAL_RESUME_SCHEMA["properties"]["verification_state"]["enum"]),
            verification_states,
        )

    def test_resolution_state_set_keeps_explicit_absence_and_not_applicable(self):
        resolution_states = {state.value for state in resume_core.ResolutionState}

        self.assertEqual(
            resolution_states,
            {
                "exact_match",
                "alias_match",
                "verified_fact_match",
                "related_match",
                "possible_match",
                "unknown",
                "explicitly_missing",
                "not_applicable",
            },
        )
        self.assertEqual(resume_core.ResolutionState("explicitly_missing").value, "explicitly_missing")
        self.assertEqual(resume_core.ResolutionState("not_applicable").value, "not_applicable")
        self.assertNotIn("conflicted", resolution_states)

    def test_validate_resume_accepts_imported_and_rejects_resolution_only_state(self):
        imported = resume_core.validateResume(_minimal_resume("imported"))
        self.assertEqual(imported.get("status"), "ok", imported)

        explicitly_missing = resume_core.validateResume(_minimal_resume("explicitly_missing"))
        self.assertEqual(explicitly_missing.get("status"), "error", explicitly_missing)
        self.assertIn(
            "invalid_verification_state",
            {error.get("code") for error in explicitly_missing.get("errors", [])},
        )

    def test_conflicted_is_not_constructible_in_either_enum(self):
        for enum_type in (resume_core.VerificationState, resume_core.ResolutionState):
            with self.subTest(enum_type=enum_type.__name__):
                with self.assertRaises(ValueError):
                    enum_type("conflicted")


if __name__ == "__main__":
    unittest.main()
