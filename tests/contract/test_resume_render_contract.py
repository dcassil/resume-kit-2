"""Contract-first tests for the future resume_render package."""

from __future__ import annotations

import asyncio
import base64
import binascii
import importlib
import inspect
import io
import json
import unittest
import zipfile
from pathlib import Path
from xml.etree import ElementTree

import resume_core


ROOT = Path(__file__).resolve().parents[2]
SURFACE = json.loads((ROOT / "resume-render" / "render_surface.json").read_text(encoding="utf-8"))
PUBLIC_FUNCTIONS = tuple(SURFACE["public_api"]["functions"])


CANONICAL_RESUME = {
    "schema_version": "canonical-resume.v1",
    "resume_id": "resume_render_contract",
    "source": {"kind": "test_fixture"},
    "contact": {"name": "Daniel Candidate", "email": "candidate@example.com"},
    "summary": "Software engineer focused on React, TypeScript, REST APIs, and responsive web applications.",
    "experience": [
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
    "skills": ["React", "TypeScript", "REST APIs", "Responsive design"],
    "education": [],
    "provenance": [{"source": "test", "text": "React"}],
    "verification_state": "source_stated",
    "internal_provenance": {"source": "must not appear in exported output"},
}

RENDERABLE_RESUME = {
    "schema_version": resume_core.RENDERABLE_RESUME_SCHEMA_VERSION,
    "contact": {"name": "Daniel Candidate", "email": "candidate@example.com", "phone": "", "links": []},
    "sections": [
        {
            "id": "summary",
            "title": "Summary",
            "format": "default",
            "entries": ["Software engineer focused on React, TypeScript, REST APIs, and responsive web applications."],
        },
        {
            "id": "experience",
            "title": "Experience",
            "format": "default",
            "entries": [
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
            "title": "Skills",
            "format": "skills",
            "entries": [{"skills": ["React", "TypeScript", "REST APIs", "Responsive design"]}],
        },
    ],
}

TEMPLATE = {
    "template_id": "ats-clean",
    "template_version": "1.0.0",
    "format_targets": ["markdown", "docx"],
    "section_order": ["summary", "experience", "skills"],
    "target_pages": 1,
}

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
NS = {"w": W_NS, "rel": REL_NS, "ct": CT_NS}


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
    return artifact_bytes(result)


def artifact_bytes(result: dict) -> bytes:
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


def docx_parts(result: dict) -> dict[str, bytes]:
    docx_bytes = artifact_bytes(result)
    with zipfile.ZipFile(io.BytesIO(docx_bytes)) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


def xml_part(parts: dict[str, bytes], name: str) -> ElementTree.Element:
    return ElementTree.fromstring(parts[name])


def docx_with_part(result: dict, part_name: str, replacement: bytes) -> dict:
    source = artifact_bytes(result)
    output = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(source)) as source_zip, zipfile.ZipFile(output, "w") as target_zip:
        for info in source_zip.infolist():
            payload = replacement if info.filename == part_name else source_zip.read(info.filename)
            target_info = zipfile.ZipInfo(filename=info.filename, date_time=info.date_time)
            target_info.compress_type = info.compress_type
            target_info.external_attr = info.external_attr
            target_zip.writestr(target_info, payload)
    mutated = json.loads(json.dumps(result))
    mutated["artifact"]["content_base64"] = base64.b64encode(output.getvalue()).decode("ascii")
    return mutated


def attr(node: ElementTree.Element, namespace: str, name: str) -> str | None:
    if node is None:
        return None
    if not namespace:
        return node.get(name)
    return node.get(f"{{{namespace}}}{name}")


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

    def test_manifest_status_table_represents_unsupported_reason_contracts_across_functions(self):
        status_rows = SURFACE["status_vocabulary"]["status_table"]
        unsupported_rows = {row["function"]: row for row in status_rows if row["status"] == "unsupported"}
        self.assertEqual(set(unsupported_rows), {"renderPdf", "validateRenderedOutput"})

        pdf_row = unsupported_rows["renderPdf"]
        self.assertIs(pdf_row.get("implemented"), True)
        self.assertIs(pdf_row.get("requires_reason"), True)
        self.assertEqual(pdf_row.get("reason_enum_ref"), "#/surfaces/renderPdf/output_contract/unsupported_reasons")

        validation_row = unsupported_rows["validateRenderedOutput"]
        self.assertIs(validation_row.get("implemented"), False)
        self.assertEqual(validation_row.get("owner"), "RKIT-I-0032")
        self.assertIs(validation_row.get("requires_reason"), True)
        self.assertEqual(
            validation_row.get("reason_ref"),
            "#/surfaces/renderPdf/output_contract/unsupported_reasons[pdf_not_supported_in_mvp]",
        )

    def test_manifest_status_table_matches_reachable_function_statuses(self):
        renderer = load_render_module(self)
        long_resume = json.loads(json.dumps(RENDERABLE_RESUME))
        long_resume["sections"][1]["entries"][0]["bullets"] = [
            f"Built validated product capability {index} with React and REST APIs."
            for index in range(80)
        ]
        missing_targets = {key: value for key, value in TEMPLATE.items() if key != "format_targets"}

        status_cases = {
            "renderMarkdown": [
                (renderer.renderMarkdown, (RENDERABLE_RESUME, TEMPLATE)),
                (renderer.renderMarkdown, ({}, TEMPLATE)),
            ],
            "renderDocx": [
                (renderer.renderDocx, (RENDERABLE_RESUME, TEMPLATE)),
                (renderer.renderDocx, (RENDERABLE_RESUME, {})),
            ],
            "renderPdf": [
                (renderer.renderPdf, (RENDERABLE_RESUME, missing_targets)),
                (renderer.renderPdf, ({}, TEMPLATE)),
            ],
            "measureLayout": [
                (renderer.measureLayout, (RENDERABLE_RESUME, {**TEMPLATE, "target_pages": 5})),
                (renderer.measureLayout, (long_resume, {**TEMPLATE, "target_pages": 1})),
                (renderer.measureLayout, (RENDERABLE_RESUME, {**TEMPLATE, "target_pages": 0})),
            ],
            "validateRenderedOutput": [
                (renderer.validateRenderedOutput, ({"format": "markdown", "content": "Readable text."},)),
                (renderer.validateRenderedOutput, ({"format": "markdown", "content": "Curly \u201cquote\u201d"},)),
                (renderer.validateRenderedOutput, ({},)),
                (renderer.validateRenderedOutput, ({"format": "pdf", "artifact": {"kind": "pdf", "media_type": "application/pdf"}},)),
            ],
        }

        emitted = {
            function_name: {maybe_await(function(*args))["status"] for function, args in cases}
            for function_name, cases in status_cases.items()
        }
        rows_by_function: dict[str, list[dict]] = {function_name: [] for function_name in PUBLIC_FUNCTIONS}
        for row in SURFACE["status_vocabulary"]["status_table"]:
            rows_by_function.setdefault(row["function"], []).append(row)

        surfaces = {surface["name"]: surface for surface in SURFACE["surfaces"]}
        for function_name in PUBLIC_FUNCTIONS:
            with self.subTest(function=function_name):
                table_statuses = {row["status"] for row in rows_by_function[function_name]}
                implemented_statuses = {
                    row["status"]
                    for row in rows_by_function[function_name]
                    if row.get("implemented") is True
                }
                future_statuses = {
                    row["status"]
                    for row in rows_by_function[function_name]
                    if row.get("implemented") is False
                }
                manifest_allowed = set(surfaces[function_name]["output_contract"].get("allowed_statuses", []))

                self.assertEqual(
                    manifest_allowed,
                    table_statuses,
                    f"{function_name} output_contract.allowed_statuses must match status_vocabulary rows.",
                )
                unreachable_claimed = implemented_statuses - emitted[function_name]
                emittable_unclaimed = emitted[function_name] - implemented_statuses
                emitted_future = emitted[function_name] & future_statuses
                self.assertEqual(
                    unreachable_claimed,
                    set(),
                    f"{function_name} claims implemented statuses that fixtures did not emit: {sorted(unreachable_claimed)}",
                )
                self.assertEqual(
                    emittable_unclaimed,
                    set(),
                    f"{function_name} emitted statuses missing implemented table rows: {sorted(emittable_unclaimed)}",
                )
                self.assertEqual(
                    emitted_future,
                    set(),
                    f"{function_name} emitted statuses marked implemented=false: {sorted(emitted_future)}",
                )


class ResumeRenderContractTests(unittest.TestCase):
    def setUp(self):
        self.renderer = load_render_module(self)

    def test_markdown_render_preserves_semantic_content_and_excludes_provenance(self):
        result = maybe_await(self.renderer.renderMarkdown(RENDERABLE_RESUME, TEMPLATE))
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

    def test_schema_driven_provenance_stripping_removes_sources_evidence_and_arbitrary_keys(self):
        resume = json.loads(json.dumps(RENDERABLE_RESUME))
        resume["sources"] = [{"text": "root source leak"}]
        resume["sections"][0]["sources"] = [{"text": "section source leak"}]
        resume["sections"][0]["evidence"] = [{"text": "section evidence leak"}]
        resume["sections"][0]["entries"].append(
            {
                "title": "Legitimate Title",
                "company": "Legitimate Company",
                "summary": "Legitimate summary survives.",
                "sources": [{"text": "entry source leak"}],
                "evidence": [{"text": "entry evidence leak"}],
                "arbitrary": "arbitrary leak",
            }
        )

        result = maybe_await(self.renderer.renderMarkdown(resume, TEMPLATE))
        self.assertEqual(result["status"], "ok", result)
        content = result["content"]
        self.assertIn("Legitimate Title - Legitimate Company", content)
        self.assertIn("Legitimate summary survives.", content)
        self.assertNotIn("source leak", content)
        self.assertNotIn("evidence leak", content)
        self.assertNotIn("arbitrary leak", content)

    def test_render_time_ats_sanitation_replaces_named_unsupported_characters(self):
        resume = json.loads(json.dumps(RENDERABLE_RESUME))
        resume["sections"][0]["entries"] = ["Built\u00a0React with \u201csmart quotes\u201d and \u2022 markers."]
        result = maybe_await(self.renderer.renderMarkdown(resume, TEMPLATE))
        self.assertEqual(result["status"], "ok", result)
        self.assertIn('Built React with "smart quotes" and - markers.', result["content"])
        self.assertNotIn("\u00a0", result["content"])
        self.assertTrue(any(warning.startswith("ats_unsupported_character_sanitized") for warning in result["warnings"]))

    def test_render_time_ats_sanitation_clean_pass_has_no_sanitation_warning(self):
        result = maybe_await(self.renderer.renderMarkdown(RENDERABLE_RESUME, TEMPLATE))
        self.assertEqual(result["status"], "ok", result)
        self.assertFalse(any(warning.startswith("ats_unsupported_character_sanitized") for warning in result["warnings"]))

    def test_skills_formatting_uses_section_metadata_not_section_id(self):
        resume = json.loads(json.dumps(RENDERABLE_RESUME))
        skills_section = resume["sections"][2]
        skills_section["id"] = "technical_toolbox"
        skills_section["title"] = "Technical Toolbox"
        skills_section["format"] = "skills"
        template = {**TEMPLATE, "section_order": ["summary", "experience", "technical_toolbox"]}

        result = maybe_await(self.renderer.renderMarkdown(resume, template))
        self.assertEqual(result["status"], "ok", result)
        self.assertIn("## Technical Toolbox\nReact, TypeScript, REST APIs, Responsive design", result["content"])

    def test_non_skills_section_never_gets_skills_formatting_without_metadata(self):
        resume = json.loads(json.dumps(RENDERABLE_RESUME))
        resume["sections"][2]["format"] = "default"
        resume["sections"][2]["entries"] = ["React", "TypeScript", "REST APIs", "Responsive design"]
        result = maybe_await(self.renderer.renderMarkdown(resume, TEMPLATE))
        self.assertEqual(result["status"], "ok", result)
        self.assertIn("React\nTypeScript\nREST APIs\nResponsive design", result["content"])
        self.assertNotIn("React, TypeScript, REST APIs, Responsive design", result["content"])

    def test_markdown_respects_configured_section_order_and_bullets(self):
        result = maybe_await(self.renderer.renderMarkdown(RENDERABLE_RESUME, TEMPLATE))
        content = result.get("content", "")
        self.assertLess(content.index("Summary"), content.index("Experience"))
        self.assertLess(content.index("Experience"), content.index("Skills"))
        self.assertRegex(content, r"(?m)^[-*] Built React")
        self.assertRegex(content, r"(?m)^[-*] Designed REST API")

    def test_docx_render_reports_artifact_template_version_and_preserves_sections(self):
        result = maybe_await(self.renderer.renderDocx(RENDERABLE_RESUME, TEMPLATE))
        assert_render_result(self, result, "docx")
        self.assertEqual(result["status"], "ok")
        self.assertIn("artifact", result)
        self.assertEqual(result["template_version"], TEMPLATE["template_version"])
        self.assertEqual(result.get("sections"), TEMPLATE["section_order"])
        text = serialized(result)
        self.assertIn("software engineer", text)
        self.assertIn("react", text)
        self.assertNotIn("internal_provenance", text)

    def test_docx_ok_artifact_has_media_type_matching_real_docx_bytes(self):
        result = maybe_await(self.renderer.renderDocx(RENDERABLE_RESUME, TEMPLATE))
        self.assertEqual(result["status"], "ok", result)
        artifact = result["artifact"]
        self.assertEqual(artifact["media_type"], "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        docx_bytes = artifact_bytes(result)
        with zipfile.ZipFile(io.BytesIO(docx_bytes)) as archive:
            self.assertIn("[Content_Types].xml", archive.namelist())
            self.assertIn("word/document.xml", archive.namelist())

    def test_docx_uses_numbering_part_and_real_list_paragraphs(self):
        result = maybe_await(self.renderer.renderDocx(RENDERABLE_RESUME, TEMPLATE))
        self.assertEqual(result["status"], "ok", result)
        parts = docx_parts(result)
        self.assertIn("word/numbering.xml", parts)
        self.assertIn("word/_rels/document.xml.rels", parts)

        document = xml_part(parts, "word/document.xml")
        numbering = xml_part(parts, "word/numbering.xml")
        rels = xml_part(parts, "word/_rels/document.xml.rels")
        content_types = xml_part(parts, "[Content_Types].xml")

        abstract_nums = numbering.findall("w:abstractNum", NS)
        nums = numbering.findall("w:num", NS)
        self.assertEqual(len(abstract_nums), 1)
        self.assertEqual(len(nums), 1)
        self.assertEqual(attr(abstract_nums[0], W_NS, "abstractNumId"), "0")
        self.assertEqual(attr(nums[0], W_NS, "numId"), "1")

        bullet_paragraphs = [
            paragraph
            for paragraph in document.findall(".//w:p", NS)
            if paragraph.find("w:pPr/w:numPr", NS) is not None
        ]
        self.assertGreaterEqual(len(bullet_paragraphs), 2)
        for paragraph in bullet_paragraphs:
            style = paragraph.find("w:pPr/w:pStyle", NS)
            num_id = paragraph.find("w:pPr/w:numPr/w:numId", NS)
            self.assertIsNotNone(style)
            self.assertIsNotNone(num_id)
            self.assertEqual(attr(style, W_NS, "val"), "ListParagraph")
            self.assertEqual(attr(num_id, W_NS, "val"), "1")

        relationship_targets = {
            attr(relationship, "", "Target")
            for relationship in rels.findall("rel:Relationship", NS)
        }
        self.assertIn("numbering.xml", relationship_targets)
        self.assertIn("styles.xml", relationship_targets)
        override_names = {
            attr(override, "", "PartName")
            for override in content_types.findall("ct:Override", NS)
        }
        self.assertIn("/word/numbering.xml", override_names)
        self.assertIn("/word/styles.xml", override_names)

    def test_docx_styles_part_defines_every_referenced_style(self):
        result = maybe_await(self.renderer.renderDocx(RENDERABLE_RESUME, TEMPLATE))
        self.assertEqual(result["status"], "ok", result)
        parts = docx_parts(result)
        self.assertIn("word/styles.xml", parts)

        document = xml_part(parts, "word/document.xml")
        styles = xml_part(parts, "word/styles.xml")
        referenced = {
            attr(style_ref, W_NS, "val")
            for style_ref in document.findall(".//w:pPr/w:pStyle", NS)
        }
        defined = {
            attr(style, W_NS, "styleId")
            for style in styles.findall("w:style", NS)
        }
        self.assertTrue({"Title", "Heading2", "body", "ListParagraph"}.issubset(referenced))
        self.assertTrue({"Title", "Heading1", "Heading2", "body", "ListParagraph"}.issubset(defined))
        self.assertTrue(referenced.issubset(defined), f"Undefined DOCX style IDs: {sorted(referenced - defined)}")

    def test_docx_layout_metrics_map_to_value_level_xml_and_defaults(self):
        template = {
            **TEMPLATE,
            "layout": {
                "version": "layout-metrics.v1",
                "fonts": {
                    "body": {"family": "Arial", "size_pt": 10.5},
                    "heading": {"family": "Georgia", "size_pt": 16},
                },
                "spacing": {"line": 1.2, "para_after_pt": 4},
                "margins_in": {"top": 0.75, "bottom": 0.8, "left": 0.65, "right": 0.7},
                "bullet": {"style": "bullet", "indent_in": 0.33},
            },
        }
        result = maybe_await(self.renderer.renderDocx(RENDERABLE_RESUME, template))
        self.assertEqual(result["status"], "ok", result)
        parts = docx_parts(result)
        document = xml_part(parts, "word/document.xml")
        styles = xml_part(parts, "word/styles.xml")
        numbering = xml_part(parts, "word/numbering.xml")

        body_style = styles.find("w:style[@w:styleId='body']", NS)
        heading_style = styles.find("w:style[@w:styleId='Heading2']", NS)
        self.assertIsNotNone(body_style)
        self.assertIsNotNone(heading_style)
        self.assertEqual(attr(body_style.find("w:rPr/w:rFonts", NS), W_NS, "ascii"), "Arial")
        self.assertEqual(attr(body_style.find("w:rPr/w:sz", NS), W_NS, "val"), "21")
        self.assertEqual(attr(heading_style.find("w:rPr/w:rFonts", NS), W_NS, "ascii"), "Georgia")
        self.assertEqual(attr(heading_style.find("w:rPr/w:sz", NS), W_NS, "val"), "32")

        body_spacing = body_style.find("w:pPr/w:spacing", NS)
        self.assertEqual(attr(body_spacing, W_NS, "after"), "80")
        self.assertEqual(attr(body_spacing, W_NS, "line"), "288")

        margins = document.find(".//w:sectPr/w:pgMar", NS)
        self.assertEqual(attr(margins, W_NS, "top"), "1080")
        self.assertEqual(attr(margins, W_NS, "bottom"), "1152")
        self.assertEqual(attr(margins, W_NS, "left"), "936")
        self.assertEqual(attr(margins, W_NS, "right"), "1008")

        bullet_indent = numbering.find(".//w:lvl/w:pPr/w:ind", NS)
        self.assertEqual(attr(bullet_indent, W_NS, "left"), "475")

        default_result = maybe_await(self.renderer.renderDocx(RENDERABLE_RESUME, TEMPLATE))
        default_margins = xml_part(docx_parts(default_result), "word/document.xml").find(".//w:sectPr/w:pgMar", NS)
        self.assertEqual(attr(default_margins, W_NS, "top"), "720")
        self.assertEqual(attr(default_margins, W_NS, "bottom"), "720")
        self.assertEqual(attr(default_margins, W_NS, "left"), "720")
        self.assertEqual(attr(default_margins, W_NS, "right"), "720")

    def test_docx_deterministic_bytes_and_layout_changes_bytes_not_semantics(self):
        first = maybe_await(self.renderer.renderDocx(RENDERABLE_RESUME, TEMPLATE))
        second = maybe_await(self.renderer.renderDocx(RENDERABLE_RESUME, TEMPLATE))
        self.assertEqual(first["status"], "ok", first)
        self.assertEqual(second["status"], "ok", second)
        self.assertEqual(artifact_bytes(first), artifact_bytes(second))
        self.assertEqual(first["semantic_fingerprint"], second["semantic_fingerprint"])

        spacious_template = {
            **TEMPLATE,
            "layout": {
                "margins_in": {"top": 0.75, "bottom": 0.75, "left": 0.75, "right": 0.75},
            },
        }
        spacious = maybe_await(self.renderer.renderDocx(RENDERABLE_RESUME, spacious_template))
        self.assertEqual(spacious["status"], "ok", spacious)
        self.assertNotEqual(artifact_bytes(first), artifact_bytes(spacious))
        self.assertEqual(first["semantic_fingerprint"], spacious["semantic_fingerprint"])

    def test_template_layout_validation_rejects_unknown_keys_and_markdown_ignores_metrics(self):
        invalid = maybe_await(self.renderer.renderDocx(RENDERABLE_RESUME, {**TEMPLATE, "layout": {"surprise": True}}))
        self.assertEqual(invalid["status"], "error")
        self.assertEqual(invalid["error"]["type"], "validation_error")
        self.assertIn("layout contains unknown key", invalid["error"]["message"])

        custom_layout = {
            **TEMPLATE,
            "layout": {
                "fonts": {"body": {"family": "Arial", "size_pt": 10}},
                "margins_in": {"top": 0.75, "bottom": 0.75, "left": 0.75, "right": 0.75},
            },
        }
        baseline = maybe_await(self.renderer.renderMarkdown(RENDERABLE_RESUME, TEMPLATE))
        customized = maybe_await(self.renderer.renderMarkdown(RENDERABLE_RESUME, custom_layout))
        self.assertEqual(baseline["status"], "ok", baseline)
        self.assertEqual(customized["status"], "ok", customized)
        self.assertEqual(baseline["content"], customized["content"])
        self.assertEqual(baseline["semantic_fingerprint"], customized["semantic_fingerprint"])

    def test_pdf_render_policy_contracts_return_exact_unsupported_reasons_without_artifacts(self):
        missing_targets = {key: value for key, value in TEMPLATE.items() if key != "format_targets"}
        cases = [
            ("missing targets", missing_targets, "format_targets_missing"),
            ("pdf excluded", TEMPLATE, "not_in_format_targets"),
            ("pdf included", {**TEMPLATE, "format_targets": ["markdown", "docx", "pdf"]}, "pdf_not_supported_in_mvp"),
        ]
        for label, template, reason in cases:
            with self.subTest(label=label):
                result = maybe_await(self.renderer.renderPdf(RENDERABLE_RESUME, template))
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
            result = maybe_await(self.renderer.renderPdf(RENDERABLE_RESUME, template))
            if result.get("status") != "ok":
                self.assertNotIn("artifact", result)
                continue
            self.assertTrue(
                pdf_artifact_bytes(result).startswith(b"%PDF"),
                "ok PDF render results must include real PDF bytes.",
            )

    def test_layout_measurement_reports_overflow_constraints_without_shortening_content(self):
        long_resume = json.loads(json.dumps(RENDERABLE_RESUME))
        long_resume["sections"][1]["entries"][0]["bullets"] = [
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

    def test_layout_measurement_uses_template_metrics_for_page_estimates_by_name(self):
        fixed_resume = {
            "schema_version": resume_core.RENDERABLE_RESUME_SCHEMA_VERSION,
            "contact": {"name": "", "email": "", "phone": "", "links": []},
            "sections": [
                {
                    "id": "summary",
                    "title": "Summary",
                    "format": "default",
                    "entries": ["x" * 12000],
                }
            ],
        }
        compact_template = {
            **TEMPLATE,
            "layout": {
                "version": "layout-metrics.v1",
                "fonts": {
                    "body": {"family": "Aptos", "size_pt": 10},
                    "heading": {"family": "Aptos Display", "size_pt": 12},
                },
                "spacing": {"line": 1, "para_after_pt": 0},
                "margins_in": {"top": 0.35, "bottom": 0.35, "left": 0.35, "right": 0.35},
                "bullet": {"style": "bullet", "indent_in": 0.2},
            },
        }
        roomy_template = {
            **TEMPLATE,
            "layout": {
                "version": "layout-metrics.v1",
                "fonts": {
                    "body": {"family": "Aptos", "size_pt": 12},
                    "heading": {"family": "Aptos Display", "size_pt": 16},
                },
                "spacing": {"line": 1.2, "para_after_pt": 3},
                "margins_in": {"top": 0.75, "bottom": 0.75, "left": 0.75, "right": 0.75},
                "bullet": {"style": "bullet", "indent_in": 0.35},
            },
        }

        compact = maybe_await(self.renderer.measureLayout(fixed_resume, compact_template))
        roomy = maybe_await(self.renderer.measureLayout(fixed_resume, roomy_template))

        compact_capacity = compact["constraints"]["line_capacity_per_page"] * compact["constraints"]["character_wrap_width"]
        roomy_capacity = roomy["constraints"]["line_capacity_per_page"] * roomy["constraints"]["character_wrap_width"]
        self.assertGreater(compact_capacity, roomy_capacity)
        self.assertNotEqual(compact["estimated_pages"], roomy["estimated_pages"])
        self.assertLess(compact["estimated_pages"], roomy["estimated_pages"])

    def test_layout_measurement_required_reduction_is_same_model_character_count_by_name(self):
        def resume_with_summary(character_count: int) -> dict:
            return {
                "schema_version": resume_core.RENDERABLE_RESUME_SCHEMA_VERSION,
                "contact": {"name": "", "email": "", "phone": "", "links": []},
                "sections": [
                    {
                        "id": "summary",
                        "title": "Summary",
                        "format": "default",
                        "entries": ["x" * character_count],
                    }
                ],
            }

        exact_fit = maybe_await(self.renderer.measureLayout(resume_with_summary(5985), {**TEMPLATE, "target_pages": 1}))
        self.assertEqual(exact_fit["status"], "fits", exact_fit)
        self.assertEqual(exact_fit["estimated_pages"], 1)
        self.assertEqual(exact_fit["required_reduction"], 0)
        self.assertEqual(exact_fit["constraints"]["per_section"][0]["overflow_chars"], 0)

        known_excess = maybe_await(self.renderer.measureLayout(resume_with_summary(6022), {**TEMPLATE, "target_pages": 1}))
        self.assertEqual(known_excess["status"], "overflow", known_excess)
        self.assertEqual(known_excess["requiredReduction"], 37)
        self.assertEqual(known_excess["required_reduction"], 37)
        self.assertEqual(known_excess["constraints"]["per_section"][0]["overflow_chars"], 37)
        self.assertEqual(known_excess["constraints"]["metrics_version"], "layout-metrics.v1+glyph-widths.v1")

        reduced = maybe_await(
            self.renderer.measureLayout(
                resume_with_summary(6022 - known_excess["requiredReduction"]),
                {**TEMPLATE, "target_pages": 1},
            )
        )
        self.assertEqual(reduced["status"], "fits", reduced)
        self.assertEqual(reduced["requiredReduction"], 0)

    def test_layout_measurement_itemizes_per_section_overflow_and_is_byte_deterministic_by_name(self):
        overflowing_resume = {
            "schema_version": resume_core.RENDERABLE_RESUME_SCHEMA_VERSION,
            "contact": {"name": "", "email": "", "phone": "", "links": []},
            "sections": [
                {"id": "summary", "title": "Summary", "format": "default", "entries": ["Concise summary."]},
                {"id": "skills", "title": "Skills", "format": "skills", "entries": [{"skills": ["React", "APIs"]}]},
                {"id": "experience", "title": "Experience", "format": "default", "entries": ["x" * 6022]},
            ],
        }
        template = {**TEMPLATE, "section_order": ["summary", "skills", "experience"], "target_pages": 1}

        first = maybe_await(self.renderer.measureLayout(overflowing_resume, template))
        second = maybe_await(self.renderer.measureLayout(overflowing_resume, template))

        self.assertEqual(json.dumps(first, sort_keys=True), json.dumps(second, sort_keys=True))
        per_section = {entry["id"]: entry for entry in first["constraints"]["per_section"]}
        self.assertEqual(set(per_section), {"summary", "skills", "experience"})
        self.assertEqual(per_section["summary"]["overflow_chars"], 0)
        self.assertEqual(per_section["skills"]["overflow_chars"], 0)
        self.assertGreater(per_section["experience"]["overflow_chars"], 0)
        self.assertEqual(first["offending_sections"], ["experience"])

    def test_validate_rendered_output_reports_parse_back_and_ats_findings(self):
        markdown = "# Summary\nSoftware engineer\n# Experience\nSoftware Engineer 2019-01 to 2024-06\n# Skills\nReact"
        result = maybe_await(self.renderer.validateRenderedOutput({"format": "markdown", "content": markdown, "expected_resume": RENDERABLE_RESUME}))
        self.assertIsInstance(result, dict)
        self.assertIn(result.get("status"), {"pass", "fail", "unsupported"})
        self.assertEqual(result.get("format"), "markdown")
        for field in ["text_extracted", "missing_sections", "unsupported_characters", "semantic_differences", "ats_findings", "warnings"]:
            self.assertIn(field, result)

    def test_validate_rendered_output_structural_checks_clean_pass_by_name(self):
        rendered = maybe_await(self.renderer.renderDocx(RENDERABLE_RESUME, TEMPLATE))
        result = maybe_await(self.renderer.validateRenderedOutput(rendered))
        self.assertEqual(result["status"], "pass", result)
        for finding in [
            "ats_encoding_decode",
            "ats_hostile_construct:w:tbl",
            "ats_hostile_construct:w:txbxContent",
            "ats_exotic_font",
            "ats_template_heading_mismatch",
        ]:
            self.assertFalse(any(warning.startswith(finding) for warning in result["warnings"]), finding)

    def test_validate_rendered_output_detects_declared_encoding_decode_failure_by_name(self):
        rendered = maybe_await(self.renderer.renderDocx(RENDERABLE_RESUME, TEMPLATE))
        parts = docx_parts(rendered)
        bad_styles = parts["word/styles.xml"] + b"\xff"
        mutated = docx_with_part(rendered, "word/styles.xml", bad_styles)

        result = maybe_await(self.renderer.validateRenderedOutput(mutated))
        self.assertEqual(result["status"], "fail", result)
        self.assertTrue(any(warning.startswith("ats_encoding_decode:word/styles.xml:utf-8") for warning in result["warnings"]))

    def test_validate_rendered_output_detects_tables_by_name(self):
        rendered = maybe_await(self.renderer.renderDocx(RENDERABLE_RESUME, TEMPLATE))
        document = docx_parts(rendered)["word/document.xml"].replace(
            b"</w:body>",
            b"<w:tbl><w:tr><w:tc><w:p><w:r><w:t>Table text</w:t></w:r></w:p></w:tc></w:tr></w:tbl></w:body>",
        )
        mutated = docx_with_part(rendered, "word/document.xml", document)

        result = maybe_await(self.renderer.validateRenderedOutput(mutated))
        self.assertEqual(result["status"], "fail", result)
        self.assertIn("ats_hostile_construct:w:tbl", result["warnings"])

    def test_validate_rendered_output_detects_text_boxes_by_name(self):
        rendered = maybe_await(self.renderer.renderDocx(RENDERABLE_RESUME, TEMPLATE))
        document = docx_parts(rendered)["word/document.xml"].replace(
            b"</w:body>",
            b"<w:p><w:r><w:txbxContent><w:p><w:r><w:t>Box text</w:t></w:r></w:p></w:txbxContent></w:r></w:p></w:body>",
        )
        mutated = docx_with_part(rendered, "word/document.xml", document)

        result = maybe_await(self.renderer.validateRenderedOutput(mutated))
        self.assertEqual(result["status"], "fail", result)
        self.assertIn("ats_hostile_construct:w:txbxContent", result["warnings"])

    def test_validate_rendered_output_detects_fonts_outside_layout_metrics_by_name(self):
        rendered = maybe_await(self.renderer.renderDocx(RENDERABLE_RESUME, TEMPLATE))
        styles = docx_parts(rendered)["word/styles.xml"].replace(b"Aptos", b"Papyrus", 1)
        mutated = docx_with_part(rendered, "word/styles.xml", styles)

        result = maybe_await(self.renderer.validateRenderedOutput(mutated))
        self.assertEqual(result["status"], "fail", result)
        self.assertIn("ats_exotic_font:Papyrus", result["warnings"])

    def test_validate_rendered_output_detects_template_heading_mismatch_by_name(self):
        rendered = maybe_await(self.renderer.renderMarkdown(RENDERABLE_RESUME, TEMPLATE))
        rendered["content"] = rendered["content"].replace("## Skills", "## Tools")

        result = maybe_await(self.renderer.validateRenderedOutput(rendered))
        self.assertEqual(result["status"], "fail", result)
        self.assertIn("ats_template_heading_mismatch", result["warnings"])
        self.assertIn("Skills", result["missing_sections"])

    def test_malformed_inputs_return_typed_errors_without_tracebacks(self):
        invalid_calls = [
            (self.renderer.renderMarkdown, [{}, TEMPLATE]),
            (self.renderer.renderDocx, [RENDERABLE_RESUME, {}]),
            (self.renderer.measureLayout, [{}, {"target_pages": 1}]),
            (self.renderer.validateRenderedOutput, [{}]),
        ]
        for function, args in invalid_calls:
            with self.subTest(function=function.__name__):
                result = maybe_await(function(*args))
                self.assertEqual(result["status"], "error")
                self.assertIn(result["error"]["type"], {"validation_error", "schema_error", "render_error"})
                self.assertNotRegex(serialized(result), r"\btraceback|sqlite|select|insert|update|delete\b")

    def test_core_derived_renderable_resume_renders_end_to_end(self):
        derived = maybe_await(self.renderer.renderMarkdown(resume_core.toRenderableResume(CANONICAL_RESUME, TEMPLATE)["renderable_resume"], TEMPLATE))
        self.assertEqual(derived.get("status"), "ok", derived)
        self.assertIn("Built React and TypeScript", derived.get("content", ""))

    def test_core_derived_object_bullets_survive_render_and_measurement(self):
        canonical = json.loads(json.dumps(CANONICAL_RESUME))
        canonical["experience"][0]["bullets"] = [
            {"id": "b1", "text": "Led the migration of critical systems to a new platform."},
            {"id": "b2", "text": "Mentored engineers across delivery teams."},
        ]
        renderable = resume_core.toRenderableResume(canonical, TEMPLATE)["renderable_resume"]
        rendered = maybe_await(self.renderer.renderMarkdown(renderable, TEMPLATE))
        self.assertEqual(rendered.get("status"), "ok", rendered)
        self.assertIn("Led the migration of critical systems", rendered.get("content", ""))
        measured = maybe_await(self.renderer.measureLayout(renderable, dict(TEMPLATE, target_pages=1)))
        experience = {section["id"]: section for section in measured["constraints"]["per_section"]}.get("experience", {})
        self.assertGreaterEqual(
            experience.get("estimated_lines", 0),
            3,
            "object-shaped canonical bullets must be measured, not silently stripped by the renderable schema",
        )


if __name__ == "__main__":
    unittest.main()
