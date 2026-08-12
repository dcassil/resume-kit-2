"""Contract-first tests for the future resume_plugin package."""

from __future__ import annotations

import asyncio
import importlib
import inspect
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SURFACE = json.loads((ROOT / "resume-plugin" / "plugin_surface.json").read_text(encoding="utf-8"))
PUBLIC_FUNCTIONS = tuple(SURFACE["public_api"]["functions"])


def maybe_await(value):
    if inspect.isawaitable(value):
        return asyncio.run(value)
    return value


def load_plugin_module(test_case: unittest.TestCase):
    try:
        module = importlib.import_module("resume_plugin")
    except ModuleNotFoundError as exc:
        test_case.fail(
            "Expected importable package 'resume_plugin'. Implement adapter functions from "
            "resume-plugin/TEST_SPEC.md: getPluginManifest, registerTools, mapConversationToWorkflow, "
            "presentConfirmationRequest, presentDiff, presentReport, and presentAuditSummary."
        )
        raise exc
    for function_name in PUBLIC_FUNCTIONS:
        test_case.assertTrue(callable(getattr(module, function_name, None)), f"resume_plugin must expose {function_name}().")
    return module


def serialized(value: object) -> str:
    return json.dumps(value, sort_keys=True).lower()


class ResumePluginSurfaceManifestTests(unittest.TestCase):
    def test_manifest_declares_exact_adapter_functions(self):
        self.assertEqual(PUBLIC_FUNCTIONS, (
            "getPluginManifest",
            "registerTools",
            "mapConversationToWorkflow",
            "presentConfirmationRequest",
            "presentDiff",
            "presentReport",
            "presentAuditSummary",
        ))

    def test_manifest_declares_adapter_only_contracts(self):
        surfaces = {surface["name"]: surface for surface in SURFACE["surfaces"]}
        self.assertEqual(set(surfaces), set(PUBLIC_FUNCTIONS))
        for name, surface in surfaces.items():
            with self.subTest(surface=name):
                self.assertIn("output_contract", surface)
                self.assertTrue(surface["output_contract"]["required_fields"])


class ResumePluginAdapterContractTests(unittest.TestCase):
    def setUp(self):
        self.plugin = load_plugin_module(self)

    def test_manifest_identifies_adapter_tools_and_version_metadata(self):
        manifest = maybe_await(self.plugin.getPluginManifest())
        for field in [
            "plugin_id",
            "plugin_version",
            "display_name",
            "tools",
            "skills",
            "compatibility",
            "underlying_package_versions",
            "schema_versions",
            "config_hash",
        ]:
            self.assertIn(field, manifest)
        text = serialized(manifest)
        self.assertNotIn("scoring_algorithm", text)
        self.assertNotIn("sqlite_schema", text)
        self.assertNotIn("canonical_resume_schema", text)

    def test_registered_tools_delegate_to_workflow_or_cli_commands(self):
        report = maybe_await(self.plugin.registerTools(host={"name": "test-host"}))
        self.assertEqual(report.get("status"), "ok")
        self.assertTrue(report.get("registered_tools"))
        for tool in report["registered_tools"]:
            with self.subTest(tool=tool.get("name")):
                self.assertIn("workflow_command", tool)
                self.assertIn("input_schema", tool)
                self.assertNotIn("sql", serialized(tool))
                self.assertNotIn("direct_db_write", serialized(tool))
        self.assertIn("underlying_package_versions", report)

    def test_conversation_mapping_routes_ingest_tailor_and_confirmation_to_workflow(self):
        cases = [
            ("ingest this resume", "ingest"),
            ("tailor my resume for this job", "run"),
            ("yes, I have six years of AWS experience", "resolve"),
        ]
        for message, expected_command_fragment in cases:
            with self.subTest(message=message):
                result = maybe_await(self.plugin.mapConversationToWorkflow(message=message, context={"selected_requirement_ids": ["req_aws"]}))
                self.assertEqual(result.get("status"), "ok")
                self.assertIn(expected_command_fragment, result.get("workflow_command", ""))
                self.assertIn("scope", result)
                text = serialized(result)
                self.assertNotIn("sql", text)
                self.assertNotIn("raw_career_db_context", text)

    def test_confirmation_presentation_preserves_code_selected_requirement_and_limits_context(self):
        request = {
            "selected_requirement_ids": ["req_aws"],
            "question": "Do you have AWS experience?",
            "fact_context": {"facts": [{"fact_id": "fact_react", "text": "React"}], "sensitive": "omit"},
        }
        result = maybe_await(self.plugin.presentConfirmationRequest(request))
        self.assertEqual(result.get("status"), "ok")
        self.assertEqual(result.get("selected_requirement_ids"), ["req_aws"])
        self.assertIn("prompt", result)
        self.assertTrue(result.get("sensitive_fields_omitted"))
        text = serialized(result)
        self.assertNotIn("raw_career_db_dump", text)
        self.assertNotIn("unrelated_facts", text)

    def test_diff_presentation_shows_applied_rejected_and_reasons_without_applying(self):
        operations = [
            {"operation_id": "op_1", "status": "applied", "before": "Built apps", "after": "Built React apps"},
            {"operation_id": "op_2", "status": "rejected", "reason": "unsupported AWS claim"},
        ]
        result = maybe_await(self.plugin.presentDiff(operations))
        self.assertEqual(result.get("status"), "ok")
        self.assertIn("applied_operations", result)
        self.assertIn("rejected_operations", result)
        self.assertIn("rejection_reasons", result)
        self.assertNotIn("mutation_application", serialized(result))

    def test_report_presentation_separates_requirement_groups_and_render_results(self):
        report = {
            "resolved_requirements": ["req_react"],
            "missing_requirements": ["req_aws"],
            "preferred_requirements": ["req_graphql"],
            "unresolved_requirements": ["req_saas"],
            "render_results": [{"format": "docx", "status": "ok"}],
        }
        result = maybe_await(self.plugin.presentReport(report))
        self.assertEqual(result.get("status"), "ok")
        for field in ["resolved_requirements", "missing_requirements", "preferred_requirements", "unresolved_requirements", "render_results"]:
            self.assertIn(field, result)
        text = serialized(result)
        self.assertNotIn("internal_provenance", text)
        self.assertNotIn("sensitive_raw_data", text)

    def test_audit_summary_includes_versions_and_omits_sensitive_raw_data(self):
        audit = {
            "run_identity": "run_1",
            "config_hash": "hash_1",
            "underlying_package_versions": {"resume-core": "1"},
            "schema_versions": {"canonical_resume": "1"},
            "fact_changes": ["fact_aws"],
            "operations": ["op_1"],
            "validations": ["grounding"],
            "outputs": ["resume.docx"],
            "raw_career_db_dump": "must omit",
        }
        result = maybe_await(self.plugin.presentAuditSummary(audit))
        self.assertEqual(result.get("status"), "ok")
        for field in ["run_identity", "config_hash", "underlying_package_versions", "schema_versions", "fact_changes", "operations", "validations", "outputs"]:
            self.assertIn(field, result)
        self.assertTrue(result.get("sensitive_fields_omitted"))
        self.assertNotIn("raw_career_db_dump", serialized(result))


if __name__ == "__main__":
    unittest.main()
