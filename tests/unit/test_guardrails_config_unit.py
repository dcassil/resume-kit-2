"""Unit coverage for section-13 guardrails config resolution."""

from __future__ import annotations

import unittest

from tests.unit.resume_core_test_utils import load_resume_core


resume_core = load_resume_core()

from resume_core.guardrails_config import resolve_guardrails_config  # noqa: E402


class GuardrailsConfigUnitTests(unittest.TestCase):
    def test_defaults_are_single_source_and_strict(self):
        result = resolve_guardrails_config({})

        self.assertTrue(result.ok)
        self.assertEqual(result.errors, [])
        self.assertEqual(result.warnings, [])
        self.assertFalse(result.config.allow_inferred)
        self.assertEqual(result.config.to_dict(), {"allow_inferred_facts": False})

    def test_valid_guardrails_namespace_key_is_applied(self):
        result = resolve_guardrails_config({"guardrails": {"allow_inferred_facts": True}})

        self.assertTrue(result.ok)
        self.assertTrue(result.config.allow_inferred)

    def test_unknown_guardrails_namespace_key_is_typed_error(self):
        result = resolve_guardrails_config({"guardrails": {"unexpected": True}})

        self.assertFalse(result.ok)
        self.assertEqual(result.errors[0]["code"], "unknown_guardrails_config_key")
        self.assertEqual(result.errors[0]["field_path"], "guardrails.unexpected")

    def test_removed_flat_allow_inferred_facts_key_is_typed_unknown_key_error(self):
        result = resume_core.scoreMatch({}, {}, [], {"allow_inferred_facts": True})

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["errors"][0]["code"], "unknown_guardrails_config_key")
        self.assertEqual(result["errors"][0]["field_path"], "allow_inferred_facts")
        self.assertEqual(result["warnings"], [])

    def test_invalid_guardrails_namespace_type_is_typed_error(self):
        result = resolve_guardrails_config({"guardrails": True})

        self.assertFalse(result.ok)
        self.assertEqual(result.errors[0]["code"], "invalid_guardrails_config_type")
        self.assertEqual(result.errors[0]["field_path"], "guardrails")


if __name__ == "__main__":
    unittest.main()
