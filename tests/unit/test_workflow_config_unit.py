"""Unit coverage for section-13 workflow config resolution."""

from __future__ import annotations

import unittest

from workflow.config import DEFAULT_MAX_RENDER_OVERFLOW_ITERATIONS, resolve_workflow_config


class WorkflowConfigUnitTests(unittest.TestCase):
    def test_defaults_are_single_source(self):
        result = resolve_workflow_config({})

        self.assertTrue(result.ok)
        self.assertEqual(result.errors, [])
        self.assertEqual(result.warnings, [])
        self.assertEqual(result.config.max_render_overflow_iterations, DEFAULT_MAX_RENDER_OVERFLOW_ITERATIONS)
        self.assertEqual(result.config.to_dict(), {"maxRenderOverflowIterations": DEFAULT_MAX_RENDER_OVERFLOW_ITERATIONS})

    def test_valid_workflow_namespace_key_is_applied(self):
        result = resolve_workflow_config({"workflow": {"maxRenderOverflowIterations": 3}})

        self.assertTrue(result.ok)
        self.assertEqual(result.config.max_render_overflow_iterations, 3)

    def test_unknown_workflow_namespace_key_is_typed_error(self):
        result = resolve_workflow_config({"workflow": {"unexpected": True}})

        self.assertFalse(result.ok)
        self.assertEqual(result.errors[0]["code"], "unknown_workflow_config_key")
        self.assertEqual(result.errors[0]["field_path"], "workflow.unexpected")

    def test_invalid_iteration_bound_is_typed_error(self):
        result = resolve_workflow_config({"workflow": {"maxRenderOverflowIterations": -1}})

        self.assertFalse(result.ok)
        self.assertEqual(result.errors[0]["code"], "invalid_workflow_config_value")
        self.assertEqual(result.errors[0]["field_path"], "workflow.maxRenderOverflowIterations")

    def test_invalid_workflow_namespace_type_is_typed_error(self):
        result = resolve_workflow_config({"workflow": True})

        self.assertFalse(result.ok)
        self.assertEqual(result.errors[0]["code"], "invalid_workflow_config_type")
        self.assertEqual(result.errors[0]["field_path"], "workflow")


if __name__ == "__main__":
    unittest.main()
