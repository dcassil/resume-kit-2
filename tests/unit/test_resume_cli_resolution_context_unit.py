"""Unit coverage for CLI delegation to core unresolved-requirement selection."""

from __future__ import annotations

import importlib
import unittest
from unittest import mock


class ResumeCliResolutionContextUnitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cli = importlib.import_module("resume_cli")

    def test_resolution_context_uses_first_core_ranked_selection_verbatim(self) -> None:
        core_first = {
            "requirement_id": "req_aws",
            "classification": "preferred",
            "concept": "AWS",
            "source_text": "AWS experience.",
            "resolution_state": "unknown",
            "blocking": False,
        }
        core_second = {
            "requirement_id": "req_graphql",
            "classification": "preferred",
            "concept": "GraphQL",
            "source_text": "GraphQL API experience.",
            "resolution_state": "unknown",
            "blocking": False,
        }
        selection = {
            "status": "ok",
            "ranked_unresolved_requirements": [core_first, core_second],
            "unresolved_requirements": [core_first, core_second],
            "selected_requirement": core_first,
            "can_continue": False,
        }

        with mock.patch.object(self.cli, "getUnresolvedRequirements", return_value=selection) as unresolved:
            context = self.cli._resolution_context(
                {"requirement_results": [core_second, core_first]},
                [{"fact_id": "fact_react"}],
                {"matching": {"requireHardRequirementsResolved": True}},
            )

        self.assertEqual(context["status"], "ok")
        self.assertIs(context["requirement"], core_first)
        self.assertEqual(context["selected_requirement_ids"], ["req_aws"])
        self.assertEqual(context["topic"], "AWS")
        self.assertEqual(context["concept"], "AWS")
        self.assertEqual(context["unresolved_requirements"], [core_first, core_second])
        self.assertEqual(context["already_verified_fact_ids"], ["fact_react"])
        unresolved.assert_called_once_with({"requirement_results": [core_second, core_first]}, {"matching": {"requireHardRequirementsResolved": True}})

    def test_resolution_context_returns_typed_no_unresolved_when_core_selection_is_empty(self) -> None:
        selection = {
            "status": "ok",
            "ranked_unresolved_requirements": [],
            "unresolved_requirements": [],
            "selected_requirement": None,
            "can_continue": True,
        }

        with mock.patch.object(self.cli, "getUnresolvedRequirements", return_value=selection):
            context = self.cli._resolution_context({"requirement_results": []}, [], {})

        self.assertEqual(context["status"], "no_unresolved")
        self.assertEqual(context["exit_code"], 0)
        self.assertEqual(context["selected_requirement_ids"], [])
        self.assertIsNone(context["requirement"])
        self.assertNotIn("topic", context)
        self.assertNotIn("requirement_unresolved", repr(context))


if __name__ == "__main__":
    unittest.main()
