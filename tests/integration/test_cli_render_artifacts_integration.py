"""Integration tests for real resume-cli render artifacts and audit evidence."""

from __future__ import annotations

import base64
import hashlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from typing import Any

import resume_cli
import resume_core
import resume_render


DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
TEMPLATE = {
    "template_id": "ats-clean",
    "template_version": "1.0.0",
    "format_targets": ["markdown", "docx"],
    "section_order": ["summary", "experience", "skills"],
    "target_pages": 1,
}
RENDERER_TEMPLATE_VERSION = "ats-clean@1.0.0"


def one_page_resume() -> dict[str, Any]:
    return {
        "schema_version": resume_core.CANONICAL_RESUME_SCHEMA_VERSION,
        "resume_id": "render_gate_one_page",
        "source": {"kind": "test_fixture", "internal_note": "provenance sentinel must not render"},
        "contact": {"name": "Dana Candidate", "email": "dana@example.com"},
        "summary": "Software engineer focused on React, TypeScript, REST APIs, and accessible web applications.",
        "experience": [
            {
                "company": "Example SaaS",
                "title": "Software Engineer",
                "start_date": "2020-01",
                "end_date": "2025-12",
                "bullets": [
                    "Built React and TypeScript user interfaces for billing workflows.",
                    "Designed REST API integrations for accessible web applications.",
                ],
            }
        ],
        "skills": ["React", "TypeScript", "REST APIs", "Accessibility"],
        "education": [],
        "provenance": [{"source": "test", "text": "provenance sentinel must not render"}],
        "internal_provenance": {"source": "provenance sentinel must not render"},
        "verification_state": "source_stated",
    }


def overflow_resume(summary_chars: int = 6022) -> dict[str, Any]:
    return {
        "schema_version": resume_core.CANONICAL_RESUME_SCHEMA_VERSION,
        "resume_id": "render_gate_overflow",
        "source": {"kind": "test_fixture"},
        "contact": {"name": "", "email": ""},
        "summary": "x" * summary_chars,
        "experience": [],
        "skills": [],
        "education": [],
        "verification_state": "source_stated",
    }


def run_cli(argv: list[str], workspace: Path, stdin: str | None = None) -> dict[str, Any]:
    result = resume_cli.main(argv=argv, cwd=workspace, stdin=stdin)
    if isinstance(result, int):
        return {"exit_code": result}
    return result


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True, indent=2), encoding="utf-8")


def renderable(canonical_resume: dict[str, Any]) -> dict[str, Any]:
    result = resume_core.toRenderableResume(canonical_resume, TEMPLATE)
    if result.get("status") != "ok":
        raise AssertionError(result)
    return result["renderable_resume"]


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def docx_payload_from_bytes(docx_bytes: bytes, expected_resume: dict[str, Any]) -> dict[str, Any]:
    return {
        "format": "docx",
        "artifact": {
            "kind": "docx",
            "media_type": DOCX_MEDIA_TYPE,
            "encoding": "utf-8",
            "declared_font_families": ["Aptos", "Aptos Display"],
            "content_base64": base64.b64encode(docx_bytes).decode("ascii"),
            "text": "renderer sidecar text must not certify bytes",
        },
        "expected_resume": expected_resume,
    }


def docx_with_added_paragraph(source: bytes, text: str) -> bytes:
    escaped = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").encode("utf-8")
    paragraph = (
        b'<w:p><w:pPr><w:pStyle w:val="body"/></w:pPr>'
        b'<w:r><w:t xml:space="preserve">' + escaped + b"</w:t></w:r></w:p>"
    )
    output = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(source)) as source_zip, zipfile.ZipFile(output, "w") as target_zip:
        for info in source_zip.infolist():
            payload = source_zip.read(info.filename)
            if info.filename == "word/document.xml":
                payload = payload.replace(b"</w:body>", paragraph + b"</w:body>")
            target_info = zipfile.ZipInfo(filename=info.filename, date_time=info.date_time)
            target_info.compress_type = info.compress_type
            target_info.external_attr = info.external_attr
            target_zip.writestr(target_info, payload)
    return output.getvalue()


def prepare_export_workspace(workspace: Path, canonical_resume: dict[str, Any]) -> dict[str, Any]:
    init = run_cli(["init"], workspace)
    if init.get("status") != "ok":
        raise AssertionError(init)
    write_json(workspace / "resume" / "base.json", canonical_resume)
    write_json(workspace / "resume" / "working.json", canonical_resume)
    export = run_cli(["export", "--format", "docx"], workspace)
    if export.get("status") != "ok":
        raise AssertionError(export)
    return export


def artifact_hashes(workspace: Path) -> dict[str, str]:
    return {
        "output/resume.md": sha256_bytes((workspace / "output" / "resume.md").read_bytes()),
        "output/resume.docx": sha256_bytes((workspace / "output" / "resume.docx").read_bytes()),
    }


def assert_render_evidence_payload(
    test_case: unittest.TestCase,
    evidence: dict[str, Any],
    workspace: Path,
    expected_hashes: dict[str, str],
) -> None:
    for field in ["template_version", "metrics_version", "artifact_fingerprints", "validation_summary"]:
        test_case.assertIn(field, evidence)
    test_case.assertEqual(evidence["template_version"], TEMPLATE["template_version"])
    test_case.assertEqual(evidence["metrics_version"], "layout-metrics.v1+glyph-widths.v1")
    test_case.assertEqual(evidence["artifact_fingerprints"], expected_hashes)
    for rel_path, expected_hash in evidence["artifact_fingerprints"].items():
        test_case.assertEqual(sha256_bytes((workspace / rel_path).read_bytes()), expected_hash)
    test_case.assertEqual(evidence["validation_summary"], {"markdown": "pass", "docx": "pass"})


class CliRenderArtifactsIntegrationTests(unittest.TestCase):
    def test_cli_export_real_artifact_bytes_validate_and_fingerprint_deterministically(self) -> None:
        first = tempfile.TemporaryDirectory()
        second = tempfile.TemporaryDirectory()
        self.addCleanup(first.cleanup)
        self.addCleanup(second.cleanup)
        first_workspace = Path(first.name)
        second_workspace = Path(second.name)
        canonical = one_page_resume()
        expected = renderable(canonical)
        fit = resume_render.measureLayout(expected, TEMPLATE)
        self.assertEqual(fit["status"], "fits", fit)

        first_export = prepare_export_workspace(first_workspace, canonical)
        second_export = prepare_export_workspace(second_workspace, canonical)
        self.assertEqual(first_export["template_version"], TEMPLATE["template_version"])
        self.assertEqual(second_export["template_version"], TEMPLATE["template_version"])
        self.assertEqual(artifact_hashes(first_workspace), artifact_hashes(second_workspace))

        markdown_bytes = (first_workspace / "output" / "resume.md").read_bytes()
        docx_bytes = (first_workspace / "output" / "resume.docx").read_bytes()
        self.assertTrue(docx_bytes.startswith(b"PK"))
        self.assertNotIn(b"provenance", markdown_bytes.lower())
        self.assertNotIn(b"internal_provenance", docx_bytes.lower())

        markdown_validation = resume_render.validateRenderedOutput(
            {"format": "markdown", "content": markdown_bytes.decode("utf-8"), "expected_resume": expected}
        )
        docx_validation = resume_render.validateRenderedOutput(docx_payload_from_bytes(docx_bytes, expected))
        self.assertEqual(markdown_validation["status"], "pass", markdown_validation)
        self.assertEqual(docx_validation["status"], "pass", docx_validation)
        self.assertNotIn("provenance sentinel", docx_validation["text_extracted"].lower())

        tampered_bytes = docx_with_added_paragraph(
            docx_bytes,
            "Managed 30 engineers and scaled GraphQL platform to 20 million users.",
        )
        tampered = resume_render.validateRenderedOutput(docx_payload_from_bytes(tampered_bytes, expected))
        self.assertEqual(tampered["status"], "fail", tampered)
        added_tokens = {item["token"] for item in tampered["semantic_differences"] if item["kind"] == "added"}
        self.assertTrue({"30", "graphql", "20", "million"}.issubset(added_tokens), tampered)

    def test_known_overflow_fixture_uses_layout_model_excess_and_reduces_to_fit(self) -> None:
        overflowing = renderable(overflow_resume(6022))
        layout = resume_render.measureLayout(overflowing, TEMPLATE)
        self.assertEqual(layout["status"], "overflow", layout)
        self.assertEqual(layout["requiredReduction"], 37)
        self.assertEqual(layout["constraints"]["metrics_version"], "layout-metrics.v1+glyph-widths.v1")

        reduced = renderable(overflow_resume(6022 - layout["requiredReduction"]))
        reduced_layout = resume_render.measureLayout(reduced, TEMPLATE)
        self.assertEqual(reduced_layout["status"], "fits", reduced_layout)
        self.assertEqual(reduced_layout["requiredReduction"], 0)

    def test_render_audit_evidence_uses_existing_manifest_refs_and_fails_missing_fields(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        workspace = Path(directory.name)
        canonical = one_page_resume()
        expected = renderable(canonical)
        prepare_export_workspace(workspace, canonical)
        hashes = artifact_hashes(workspace)
        markdown_status = resume_render.validateRenderedOutput(
            {"format": "markdown", "content": (workspace / "output" / "resume.md").read_text(encoding="utf-8"), "expected_resume": expected}
        )["status"]
        docx_status = resume_render.validateRenderedOutput(
            docx_payload_from_bytes((workspace / "output" / "resume.docx").read_bytes(), expected)
        )["status"]
        evidence = {
            "template_version": TEMPLATE["template_version"],
            "metrics_version": resume_render.measureLayout(expected, TEMPLATE)["constraints"]["metrics_version"],
            "artifact_fingerprints": hashes,
            "validation_summary": {"markdown": markdown_status, "docx": docx_status},
        }

        assert_render_evidence_payload(self, evidence, workspace, hashes)
        for field_name in ["template_version", "metrics_version", "artifact_fingerprints", "validation_summary"]:
            broken = dict(evidence)
            broken.pop(field_name)
            with self.subTest(missing=field_name):
                with self.assertRaises(AssertionError):
                    assert_render_evidence_payload(self, broken, workspace, hashes)


if __name__ == "__main__":
    unittest.main()
