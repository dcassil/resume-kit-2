"""Unit coverage for section-13 matching config resolution."""

from __future__ import annotations

import unittest

from tests.unit.resume_core_test_utils import load_resume_core


resume_core = load_resume_core()

from resume_core.matching_config import DEFAULT_MATCHING_WEIGHTS, resolve_matching_config  # noqa: E402


class MatchingConfigUnitTests(unittest.TestCase):
    def test_defaults_are_single_source_and_behavior_preserving(self):
        result = resolve_matching_config({})

        self.assertTrue(result.ok)
        self.assertEqual(result.errors, [])
        self.assertEqual(result.warnings, [])
        self.assertEqual(result.config.score_auto_threshold, 7.5)
        self.assertEqual(result.config.weights, DEFAULT_MATCHING_WEIGHTS)
        self.assertFalse(result.config.require_hard_requirements_resolved)
        self.assertEqual(
            result.config.to_dict(),
            {
                "scoreAutoThreshold": 7.5,
                "weights": DEFAULT_MATCHING_WEIGHTS,
                "requireHardRequirementsResolved": False,
            },
        )

    def test_unknown_matching_namespace_key_is_typed_error(self):
        result = resolve_matching_config({"matching": {"unexpected": True}})

        self.assertFalse(result.ok)
        self.assertEqual(result.errors[0]["code"], "unknown_matching_config_key")
        self.assertEqual(result.errors[0]["field_path"], "matching.unexpected")

    def test_unknown_matching_weight_key_is_typed_error(self):
        result = resolve_matching_config({"matching": {"weights": {"requiredSkills": 0.4, "mystery": 0.6}}})

        self.assertFalse(result.ok)
        self.assertEqual(result.errors[0]["code"], "unknown_matching_config_key")
        self.assertEqual(result.errors[0]["field_path"], "matching.weights.mystery")
        self.assertEqual(result.config.weights["requiredSkills"], 0.4)

    def test_deprecated_flat_keys_map_with_warning(self):
        policy_result = resolve_matching_config({"policy": "strict"})
        boolean_result = resolve_matching_config({"require_hard_resolution": True})

        self.assertTrue(policy_result.ok)
        self.assertTrue(policy_result.config.require_hard_requirements_resolved)
        self.assertEqual({warning["code"] for warning in policy_result.warnings}, {"deprecated_matching_config_key"})
        self.assertTrue(boolean_result.ok)
        self.assertTrue(boolean_result.config.require_hard_requirements_resolved)
        self.assertEqual({warning["code"] for warning in boolean_result.warnings}, {"deprecated_matching_config_key"})

    def test_flat_key_conflict_with_matching_namespace_is_typed_error(self):
        result = resolve_matching_config({"matching": {"requireHardRequirementsResolved": False}, "policy": "strict"})

        self.assertFalse(result.ok)
        self.assertEqual(result.errors[0]["code"], "conflicting_matching_config_key")
        self.assertEqual(result.errors[0]["field_path"], "policy")

    def test_score_match_uses_resolved_flat_key_without_score_change(self):
        resume = {
            "schema_version": "canonical-resume.v1",
            "resume_id": "resume_matching_config_unit",
            "source": {"kind": "unit"},
            "experience": [],
            "skills": [],
            "education": [],
        }
        job = {
            "schema_version": "job-model.v1",
            "job_id": "job_matching_config_unit",
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
        }

        result = resume_core.scoreMatch(resume, job, [], {"policy": "strict"})

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["match_result"]["score"], 0.0)
        self.assertFalse(result["match_result"]["can_continue"])
        self.assertNotIn("warnings", result)


if __name__ == "__main__":
    unittest.main()
