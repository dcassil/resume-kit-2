"""Unit coverage for section-13 workflow config resolution."""

from __future__ import annotations

import unittest

from resume_agent import AGENT_CONFIG_DEFAULTS
from workflow.config import DEFAULT_MAX_RENDER_OVERFLOW_ITERATIONS, resolve_workflow_config


class WorkflowConfigUnitTests(unittest.TestCase):
    def test_defaults_are_single_source(self):
        result = resolve_workflow_config({})

        self.assertTrue(result.ok)
        self.assertEqual(result.errors, [])
        self.assertEqual(result.warnings, [])
        self.assertEqual(result.config.max_render_overflow_iterations, DEFAULT_MAX_RENDER_OVERFLOW_ITERATIONS)
        self.assertEqual(
            result.config.to_dict(),
            {
                "maxRenderOverflowIterations": DEFAULT_MAX_RENDER_OVERFLOW_ITERATIONS,
                "agent": AGENT_CONFIG_DEFAULTS,
                "agent_config_hash": result.config.agent_config_hash,
            },
        )
        self.assertEqual(result.config.agent_config.to_dict(), AGENT_CONFIG_DEFAULTS)

    def test_valid_workflow_namespace_key_is_applied(self):
        result = resolve_workflow_config({"workflow": {"maxRenderOverflowIterations": 3}})

        self.assertTrue(result.ok)
        self.assertEqual(result.config.max_render_overflow_iterations, 3)
        self.assertEqual(result.config.agent_config.to_dict(), AGENT_CONFIG_DEFAULTS)

    def test_valid_agent_namespace_key_is_applied(self):
        result = resolve_workflow_config({"agent": {"model": "claude-sonnet-4-6-next"}})

        self.assertTrue(result.ok)
        self.assertEqual(result.config.agent_config.model, "claude-sonnet-4-6-next")

    def test_unknown_workflow_namespace_key_is_typed_error(self):
        result = resolve_workflow_config({"workflow": {"unexpected": True}})

        self.assertFalse(result.ok)
        self.assertEqual(result.errors[0]["code"], "unknown_workflow_config_key")
        self.assertEqual(result.errors[0]["field_path"], "workflow.unexpected")

    def test_unknown_agent_namespace_key_is_typed_error(self):
        result = resolve_workflow_config({"agent": {"bogus_key": True}})

        self.assertFalse(result.ok)
        self.assertEqual(result.errors[0]["code"], "unknown_agent_config_key")
        self.assertEqual(result.errors[0]["field_path"], "agent.bogus_key")

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
