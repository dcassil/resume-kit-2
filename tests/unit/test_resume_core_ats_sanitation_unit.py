"""Stable unit checks for ATS text sanitation.

RKIT-I-0001 chunk 6 (RKIT-T-0010) owns date, requirement, change, and enum
coverage. This module stays scoped to RKIT-I-0001-stable sanitizeText behavior.
"""

from __future__ import annotations

import unittest

from tests.unit.resume_core_test_utils import load_resume_core


resume_core = load_resume_core()


class AtsSanitationUnitTests(unittest.TestCase):
    def test_smart_quotes_bullets_and_fullwidth_characters_normalize_deterministically(self):
        raw = "Built \u201csmart\u201d APIs with bullet\u2022points and fullwidth \uff21\uff22\uff23."

        first = resume_core.sanitizeText(raw)
        second = resume_core.sanitizeText(raw)

        self.assertEqual(first, second)
        self.assertEqual(first.get("status"), "ok", first)
        self.assertEqual(first["text"], 'Built "smart" APIs with bullet-points and fullwidth ABC.')
        self.assertEqual(first["warnings"], [])

    def test_unsupported_control_characters_are_removed_with_stable_warning_details(self):
        raw = "Lead API work\u0008 across teams."

        result = resume_core.sanitizeText(raw)

        self.assertEqual(result.get("status"), "warning", result)
        self.assertEqual(result["text"], "Lead API work across teams.")
        self.assertEqual(
            result["warnings"],
            [
                {
                    "code": "unsupported_control_character",
                    "message": "Removed unsupported control character.",
                    "severity": "error",
                    "field_path": "text/13",
                    "details": {"codepoint": "U+0008"},
                }
            ],
        )

    def test_ats_safe_whitelisted_controls_are_preserved(self):
        raw = "Summary line\n\tIndented detail\r\n"

        result = resume_core.sanitizeText(raw)

        self.assertEqual(result.get("status"), "ok", result)
        self.assertEqual(result["text"], raw)
        self.assertEqual(result["warnings"], [])

    def test_missing_text_returns_error_without_throwing(self):
        result = resume_core.sanitizeText(None)

        self.assertEqual(result.get("status"), "error", result)
        self.assertEqual(result["text"], "")
        self.assertEqual({warning.get("code") for warning in result["warnings"]}, {"invalid_text"})


if __name__ == "__main__":
    unittest.main()
