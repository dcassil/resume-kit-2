"""Contract-first tests for the future resume_render package."""

from __future__ import annotations

import asyncio
import base64
import binascii
import importlib
import inspect
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SURFACE = json.loads((ROOT / "resume-render" / "render_surface.json").read_text(encoding="utf-8"))
PUBLIC_FUNCTIONS = tuple(SURFACE["public_api"]["functions"])


CANONICAL_RESUME = {
    "schema_version": "test-1",
    "basics": {"name": "Daniel Candidate", "email": "candidate@example.com"},
    "sections": [
        {
            "id": "summary",
            "heading": "Summary",
            "items": ["Software engineer focused on React, TypeScript, REST APIs, and responsive web applications."],
        },
        {
            "id": "experience",
            "heading": "Experience",
            "items": [
                {
                    "company": "Example SaaS",
                    "title": "Software Engineer",
                    "start_date": "2019-01",
                    "end_date": "2024-06",
                    "bullets": [
                        "Built React and TypeScript user interfaces.",
                        "Designed REST API integrations for responsive web applications.",
                    ],
                }
            ],
        },
        {
            "id": "skills",
            "heading": "Skills",
            "items": ["React", "TypeScript", "REST APIs", "Responsive design"],
        },
    ],
    "internal_provenance": {"source": "must not appear in exported output"},
}

TEMPLATE = {
    "template_id": "ats-clean",
    "template_version": "1.0.0",
    "format_targets": ["markdown", "docx"],
    "section_order": ["summary", "experience", "skills"],
    "target_pages": 1,
}


def maybe_await(value):
    if inspect.isawaitable(value):
        return asyncio.run(value)
    return value


def load_render_module(test_case: unittest.TestCase):
    try:
        module = importlib.import_module("resume_render")
    except ModuleNotFoundError as exc:
        test_case.fail(
            "Expected importable package 'resume_render'. Implement the five renderer functions from "
            "resume-render/TEST_SPEC.md: renderMarkdown, renderDocx, renderPdf, measureLayout, and validateRenderedOutput."
        )
        raise exc
    for function_name in PUBLIC_FUNCTIONS:
        test_case.assertTrue(callable(getattr(module, function_name, None)), f"resume_render must expose {function_name}().")
    return module


def serialized(result: dict) -> str:
    return json.dumps(result, sort_keys=True).lower()


def assert_render_result(test_case: unittest.TestCase, result: dict, expected_format: str) -> None:
    test_case.assertIsInstance(result, dict)
    test_case.assertIn(result.get("status"), {"ok", "unsupported", "error"})
    test_case.assertEqual(result.get("format"), expected_format)
    test_case.assertIn("template_version", result)
    test_case.assertIn("semantic_fingerprint", result)
    test_case.assertIn("warnings", result)
    text = serialized(result)
    test_case.assertNotIn("internal_provenance", text)
    test_case.assertNotRegex(text, r"\b(official_score|overall_score|sqlite|traceback)\b")


def pdf_artifact_bytes(result: dict) -> bytes:
    artifact = result.get("artifact")
    if not isinstance(artifact, dict):
        return b""
    raw_bytes = artifact.get("bytes")
    if isinstance(raw_bytes, bytes):
        return raw_bytes
    encoded = artifact.get("content_base64")
    if isinstance(encoded, str):
        try:
            return base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError):
            return b""
    return b""


class ResumeRenderSurfaceManifestTests(unittest.TestCase):
    def test_manifest_declares_exact_public_functions(self):
        self.assertEqual(PUBLIC_FUNCTIONS, (
            "renderMarkdown",
            "renderDocx",
            "renderPdf",
            "measureLayout",
            "validateRenderedOutput",
        ))

    def test_manifest_defines_contracts_for_every_surface(self):
        surfaces = {surface["name"]: surface for surface in SURFACE["surfaces"]}
        self.assertEqual(set(surfaces), set(PUBLIC_FUNCTIONS))
        for name, surface in surfaces.items():
            with self.subTest(surface=name):
                self.assertIn("input_contract", surface)
                self.assertIn("output_contract", surface)
                self.assertTrue(surface["output_contract"]["required_fields"])

    def test_manifest_enumerates_pdf_unsupported_reasons(self):
        surfaces = {surface["name"]: surface for surface in SURFACE["surfaces"]}
        output_contract = surfaces["renderPdf"]["output_contract"]
        self.assertEqual(
            output_contract.get("unsupported_reasons"),
            [
                "format_targets_missing",
                "not_in_format_targets",
                "pdf_not_supported_in_mvp",
            ],
        )
        self.assertEqual(
            output_contract.get("unsupported_required_fields"),
            ["status", "reason", "format", "template_version"],
        )
        self.assertIn("artifact", output_contract.get("unsupported_must_not_include", []))


class ResumeRenderContractTests(unittest.TestCase):
    def setUp(self):
        self.renderer = load_render_module(self)

    def test_markdown_render_preserves_semantic_content_and_excludes_provenance(self):
        result = maybe_await(self.renderer.renderMarkdown(CANONICAL_RESUME, TEMPLATE))
        assert_render_result(self, result, "markdown")
        self.assertEqual(result["status"], "ok")
        content = result.get("content", "")
        for expected in [
            "Summary",
            "Experience",
            "Skills",
            "Software Engineer",
            "2019-01",
            "2024-06",
            "React",
            "TypeScript",
            "REST APIs",
            "Responsive design",
        ]:
            self.assertIn(expected, content)
        lowered = content.lower()
        self.assertNotIn("aws", lowered)
        self.assertNotIn("graphql", lowered)
        self.assertNotIn("staff software engineer", lowered)
        self.assertNotRegex(lowered, r"\b20 million\b|\b30 engineers\b")
        self.assertNotIn("internal_provenance", lowered)

    def test_markdown_respects_configured_section_order_and_bullets(self):
        result = maybe_await(self.renderer.renderMarkdown(CANONICAL_RESUME, TEMPLATE))
        content = result.get("content", "")
        self.assertLess(content.index("Summary"), content.index("Experience"))
        self.assertLess(content.index("Experience"), content.index("Skills"))
        self.assertRegex(content, r"(?m)^[-*] Built React")
        self.assertRegex(content, r"(?m)^[-*] Designed REST API")

    def test_docx_render_reports_artifact_template_version_and_preserves_sections(self):
        result = maybe_await(self.renderer.renderDocx(CANONICAL_RESUME, TEMPLATE))
        assert_render_result(self, result, "docx")
        self.assertEqual(result["status"], "ok")
        self.assertIn("artifact", result)
        self.assertEqual(result["template_version"], TEMPLATE["template_version"])
        self.assertEqual(result.get("sections"), TEMPLATE["section_order"])
        text = serialized(result)
        self.assertIn("software engineer", text)
        self.assertIn("react", text)
        self.assertNotIn("internal_provenance", text)

    def test_pdf_render_policy_contracts_return_exact_unsupported_reasons_without_artifacts(self):
        missing_targets = {key: value for key, value in TEMPLATE.items() if key != "format_targets"}
        cases = [
            ("missing targets", missing_targets, "format_targets_missing"),
            ("pdf excluded", TEMPLATE, "not_in_format_targets"),
            ("pdf included", {**TEMPLATE, "format_targets": ["markdown", "docx", "pdf"]}, "pdf_not_supported_in_mvp"),
        ]
        for label, template, reason in cases:
            with self.subTest(label=label):
                result = maybe_await(self.renderer.renderPdf(CANONICAL_RESUME, template))
                self.assertEqual(
                    result,
                    {
                        "status": "unsupported",
                        "reason": reason,
                        "format": "pdf",
                        "template_version": template["template_version"],
                    },
                )

    def test_pdf_render_status_artifact_invariant(self):
        templates = [
            {key: value for key, value in TEMPLATE.items() if key != "format_targets"},
            TEMPLATE,
            {**TEMPLATE, "format_targets": ["markdown", "docx", "pdf"]},
        ]
        for template in templates:
            result = maybe_await(self.renderer.renderPdf(CANONICAL_RESUME, template))
            if result.get("status") != "ok":
                self.assertNotIn("artifact", result)
                continue
            self.assertTrue(
                pdf_artifact_bytes(result).startswith(b"%PDF"),
                "ok PDF render results must include real PDF bytes.",
            )

    def test_layout_measurement_reports_overflow_constraints_without_shortening_content(self):
        long_resume = json.loads(json.dumps(CANONICAL_RESUME))
        long_resume["sections"][1]["items"][0]["bullets"] = [
            f"Built validated product capability {index} with React and REST APIs."
            for index in range(80)
        ]
        result = maybe_await(self.renderer.measureLayout(long_resume, {**TEMPLATE, "target_pages": 1}))
        self.assertIsInstance(result, dict)
        self.assertIn(result.get("status"), {"fits", "overflow", "error"})
        self.assertIn("estimated_pages", result)
        self.assertIn("target_pages", result)
        self.assertIn("required_reduction", result)
        self.assertIn("requiredReduction", result)
        if result["status"] == "overflow":
            self.assertGreater(result["estimated_pages"], result["target_pages"])
            self.assertGreater(result["required_reduction"], 0)
            self.assertEqual(result["requiredReduction"], result["required_reduction"])
            self.assertGreater(
                result["requiredReduction"],
                result["estimated_pages"] - result["target_pages"],
                "requiredReduction must be a character count, not a page delta.",
            )
            self.assertIn("constraints", result)
            self.assertEqual(result["constraints"]["requiredReduction"], result["requiredReduction"])
            self.assertTrue(result["offending_sections"])
            self.assertEqual(result["constraints"]["offending_sections"], result["offending_sections"])
        self.assertNotIn("shortened_content", result)
        self.assertNotIn("deleted_bullets", result)

    def test_validate_rendered_output_reports_parse_back_and_ats_findings(self):
        markdown = "# Summary\nSoftware engineer\n# Experience\nSoftware Engineer 2019-01 to 2024-06\n# Skills\nReact"
        result = maybe_await(self.renderer.validateRenderedOutput({"format": "markdown", "content": markdown, "expected_resume": CANONICAL_RESUME}))
        self.assertIsInstance(result, dict)
        self.assertIn(result.get("status"), {"pass", "fail", "unsupported"})
        self.assertEqual(result.get("format"), "markdown")
        for field in ["text_extracted", "missing_sections", "unsupported_characters", "semantic_differences", "warnings"]:
            self.assertIn(field, result)

    def test_malformed_inputs_return_typed_errors_without_tracebacks(self):
        invalid_calls = [
            (self.renderer.renderMarkdown, [{}, TEMPLATE]),
            (self.renderer.renderDocx, [CANONICAL_RESUME, {}]),
            (self.renderer.measureLayout, [{}, {"target_pages": 1}]),
            (self.renderer.validateRenderedOutput, [{}]),
        ]
        for function, args in invalid_calls:
            with self.subTest(function=function.__name__):
                result = maybe_await(function(*args))
                self.assertEqual(result["status"], "error")
                self.assertIn(result["error"]["type"], {"validation_error", "schema_error", "render_error"})
                self.assertNotRegex(serialized(result), r"\btraceback|sqlite|select|insert|update|delete\b")


if __name__ == "__main__":
    unittest.main()
