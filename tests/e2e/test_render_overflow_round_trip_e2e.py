"""E2E render-overflow loop-back through workflow checkpoints."""

from __future__ import annotations

import base64
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

import resume_cli
import resume_core
import resume_render
import workflow


DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
TEMPLATE = {
    "template_id": "ats-clean",
    "template_version": "1.0.0",
    "format_targets": ["markdown", "docx"],
    "section_order": ["summary", "experience", "skills"],
    "target_pages": 1,
}
RENDERER_TEMPLATE_VERSION = "ats-clean@1.0.0"


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True, indent=2), encoding="utf-8")


def write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def artifact_ref(workspace: Path, relative_path: str, payload: Any = None, *, raw: bytes | None = None) -> dict[str, Any]:
    path = workspace / relative_path
    if raw is not None:
        write_bytes(path, raw)
    elif payload is None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"artifact:{relative_path}", encoding="utf-8")
    else:
        write_json(path, payload)
    return {"kind": "artifact", "path": relative_path, "sha256": sha256_bytes(path.read_bytes())}


def dto_ref(schema_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"kind": "dto", "schema_id": schema_id, "payload": payload or {"status": "passed"}}


def operation_state_ref(*operation_ids: str) -> dict[str, Any]:
    return {"kind": "run_state", "key": "operation_statuses", "operation_ids": list(operation_ids)}


def overflow_canonical_resume(summary_chars: int) -> dict[str, Any]:
    return {
        "schema_version": resume_core.CANONICAL_RESUME_SCHEMA_VERSION,
        "resume_id": f"render_overflow_{summary_chars}",
        "source": {"kind": "test_fixture"},
        "contact": {"name": "", "email": ""},
        "summary": "x" * summary_chars,
        "experience": [],
        "skills": [],
        "education": [],
        "verification_state": "source_stated",
    }


def renderable(canonical_resume: dict[str, Any]) -> dict[str, Any]:
    result = resume_core.toRenderableResume(canonical_resume, TEMPLATE)
    if result.get("status") != "ok":
        raise AssertionError(result)
    return result["renderable_resume"]


def docx_payload_from_result(result: dict[str, Any], expected_resume: dict[str, Any]) -> dict[str, Any]:
    artifact = result["artifact"]
    return {
        "format": "docx",
        "artifact": {
            "kind": "docx",
            "media_type": DOCX_MEDIA_TYPE,
            "encoding": "utf-8",
            "declared_font_families": artifact.get("declared_font_families", ["Aptos", "Aptos Display"]),
            "content_base64": artifact["content_base64"],
            "text": "validation must parse real bytes",
        },
        "expected_resume": expected_resume,
    }


def docx_bytes(result: dict[str, Any]) -> bytes:
    return base64.b64decode(result["artifact"]["content_base64"], validate=True)


def advance_ok(run_state: dict[str, Any], target: str, evidence: dict[str, Any]) -> dict[str, Any]:
    advanced = workflow.advanceCheckpoint(run_state, target, evidence)
    if advanced["status"] != "ok":
        raise AssertionError(advanced)
    return advanced


def record_ok(run_state: dict[str, Any], checkpoint: str, result: dict[str, Any]) -> dict[str, Any]:
    recorded = workflow.recordCheckpointResult(run_state, checkpoint, result)
    if recorded["status"] != "ok":
        raise AssertionError(recorded)
    return recorded


def match_result() -> dict[str, Any]:
    return {
        "schema_version": "match-result.v1",
        "score": 8.0,
        "threshold": 7.5,
        "hardRequirementsResolved": True,
        "decision": "continue",
        "can_continue": True,
        "requirement_results": [],
        "unresolved_requirement_ids": [],
        "preferred_unresolved_requirement_ids": [],
        "explanations": [],
    }


def drive_initial_checkpoints(workspace: Path, run_state: dict[str, Any]) -> None:
    match = match_result()
    advance_ok(run_state, "INGEST_RESUME", {"config_validated": dto_ref("WorkflowStatusEvidence")})
    advance_ok(run_state, "VALIDATE_BASE", {"canonical_resume_exists": artifact_ref(workspace, "resume/base.json", {"resume_id": "base_1"})})
    advance_ok(run_state, "EXTRACT_PERSIST_CAREER_FACTS", {"base_validation": dto_ref("WorkflowStatusEvidence")})
    advance_ok(run_state, "INGEST_JOB", {"career_facts_persisted": artifact_ref(workspace, "data/career.db", raw=b"career-db")})
    advance_ok(run_state, "NORMALIZE_JOB", {"job_ingested": artifact_ref(workspace, "job/current.json", {"job_id": "job_1"})})
    advance_ok(run_state, "MATCH_BASE", {"job_normalized": dto_ref("WorkflowStatusEvidence")})
    record_ok(run_state, "MATCH_BASE", {"match_result": match})
    advance_ok(run_state, "RESOLVE_GAPS", {"match_result": dto_ref("MatchResultEvidence", {"status": "ok", "match_result": match})})


def drive_tail_from_selection(workspace: Path, run_state: dict[str, Any], operation_id: str) -> None:
    record_ok(run_state, "BUILD_SELECTION_PLAN", {"operations_proposed": [operation_id]})
    advance_ok(run_state, "PROPOSE_TAILORING_CHANGES", {"proposed_operations": operation_state_ref(operation_id)})
    record_ok(run_state, "PROPOSE_TAILORING_CHANGES", {"operations_validated": [operation_id]})
    advance_ok(run_state, "VALIDATE_CHANGES", {"validated_operations": operation_state_ref(operation_id)})
    record_ok(run_state, "VALIDATE_CHANGES", {"operations_applied": [operation_id]})
    advance_ok(run_state, "APPLY_CHANGES", {"applied_operations": operation_state_ref(operation_id)})
    advance_ok(run_state, "FINAL_MATCH", {"match_report": artifact_ref(workspace, f"reports/final-match-{operation_id}.json", {"status": "passed"})})
    advance_ok(run_state, "GROUNDING_AUDIT", {"grounding_audit": artifact_ref(workspace, f"reports/grounding-{operation_id}.json", {"status": "passed"})})
    advance_ok(run_state, "ATS_STRUCTURE_VALIDATION", {"ats_report": artifact_ref(workspace, f"reports/ats-{operation_id}.json", {"status": "passed"})})


def render_outputs(workspace: Path, expected_resume: dict[str, Any], prefix: str) -> dict[str, Any]:
    markdown = resume_render.renderMarkdown(expected_resume, TEMPLATE)
    docx = resume_render.renderDocx(expected_resume, TEMPLATE)
    if markdown["status"] != "ok" or docx["status"] != "ok":
        raise AssertionError({"markdown": markdown, "docx": docx})
    markdown_path = f"output/{prefix}.md"
    docx_path = f"output/{prefix}.docx"
    write_bytes(workspace / markdown_path, markdown["content"].encode("utf-8"))
    write_bytes(workspace / docx_path, docx_bytes(docx))
    return {
        "markdown": markdown,
        "docx": docx,
        "paths": [markdown_path, docx_path],
        "fingerprints": {
            markdown_path: sha256_bytes((workspace / markdown_path).read_bytes()),
            docx_path: sha256_bytes((workspace / docx_path).read_bytes()),
        },
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


class RenderOverflowRoundTripE2ETests(unittest.TestCase):
    def test_resume_run_current_cli_contract_is_owner_marked_until_checkpoint_driver_lands(self) -> None:
        # OWNER: RKIT-I-0040. resume run still returns the canonical checkpoint
        # list and output files, but does not expose I-0027 render_overflow
        # loop-back details. The next test drives the landed workflow surface.
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            resume_file = workspace / "resume.txt"
            job_file = workspace / "job.txt"
            resume_file.write_text("Dana Candidate\nReact TypeScript API engineer.\n", encoding="utf-8")
            job_file.write_text("Required: React, TypeScript, API architecture.\n", encoding="utf-8")

            result = resume_cli.main(argv=["run", str(resume_file), str(job_file)], cwd=workspace)

            self.assertEqual(result.get("status"), "ok", result)
            self.assertEqual(result.get("checkpoints"), list(workflow.CHECKPOINT_ORDER))
            self.assertTrue((workspace / "output" / "resume.md").exists())
            self.assertTrue((workspace / "output" / "resume.docx").exists())
            self.assertNotIn("render_overflow", result)

    def test_overflow_constraints_loop_back_content_reduction_and_manifest_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            config = {
                "schemaVersion": "1.0",
                "matching": {"requireHardRequirementsResolved": True},
                "schema_versions": {"renderer_template": RENDERER_TEMPLATE_VERSION},
                "workflow": {"maxRenderOverflowIterations": 2},
            }
            run_state = workflow.createRun(workspace=workspace, config=config)
            run_state.update(
                {
                    "base_resume_id": "base_1",
                    "base_resume_hash": "hash_base_1",
                    "job_id": "job_1",
                    "renderer_template_version": RENDERER_TEMPLATE_VERSION,
                    "initial_score": 8.0,
                    "final_score": 8.4,
                    "validation_status": "passed",
                }
            )
            drive_initial_checkpoints(workspace, run_state)

            overflowing = renderable(overflow_canonical_resume(6022))
            overflow_layout = resume_render.measureLayout(overflowing, TEMPLATE)
            self.assertEqual(overflow_layout["status"], "overflow", overflow_layout)
            self.assertEqual(overflow_layout["requiredReduction"], 37)
            self.assertEqual(overflow_layout["constraints"]["metrics_version"], "layout-metrics.v1+glyph-widths.v1")
            self.assertNotIn("shortened_content", overflow_layout)
            self.assertNotIn("deleted_bullets", overflow_layout)

            advance_ok(run_state, "BUILD_SELECTION_PLAN", {"selection_plan": artifact_ref(workspace, "plans/initial-selection.json", {"status": "ok"})})
            drive_tail_from_selection(workspace, run_state, "op_initial")
            overflow_outputs = render_outputs(workspace, overflowing, "overflow-resume")
            advance_ok(
                run_state,
                "RENDER",
                {
                    "render_output": artifact_ref(workspace, "output/overflow-resume.md", raw=(workspace / "output" / "overflow-resume.md").read_bytes()),
                    "measure_layout": artifact_ref(workspace, "reports/overflow-layout.json", overflow_layout),
                },
            )
            overflow_record = workflow.recordCheckpointResult(
                run_state,
                "RENDER",
                {
                    **overflow_layout,
                    "render_refs": [artifact_ref(workspace, "reports/overflow-layout-ref.json", overflow_layout)],
                    "artifact_refs": [
                        {"kind": "artifact", "path": overflow_outputs["paths"][0], "sha256": overflow_outputs["fingerprints"][overflow_outputs["paths"][0]]},
                        {"kind": "artifact", "path": overflow_outputs["paths"][1], "sha256": overflow_outputs["fingerprints"][overflow_outputs["paths"][1]]},
                    ],
                },
            )
            self.assertEqual(overflow_record["status"], "ok", overflow_record)
            constraint_ref = overflow_record["render_overflow"]["constraint_ref"]
            self.assertIsInstance(constraint_ref, dict)
            decision = workflow.getNextCheckpoint(run_state)
            self.assertEqual(decision["next_checkpoint"], "BUILD_SELECTION_PLAN", decision)
            self.assertIn("render_overflow_constraints", decision["required_inputs"])
            self.assertEqual(decision["render_overflow"]["predicate"]["overflow_constraints"]["requiredReduction"], 37)

            advance_ok(
                run_state,
                "BUILD_SELECTION_PLAN",
                {
                    "selection_plan": artifact_ref(workspace, "plans/reduced-selection.json", {"status": "ok", "uses": "render overflow constraint"}),
                    "render_overflow_constraints": constraint_ref,
                },
            )
            self.assertEqual(run_state["render_overflow_state"]["status"], "consumed")

            reduced = renderable(overflow_canonical_resume(6022 - overflow_layout["requiredReduction"]))
            reduced_layout = resume_render.measureLayout(reduced, TEMPLATE)
            self.assertEqual(reduced_layout["status"], "fits", reduced_layout)
            self.assertEqual(reduced_layout["requiredReduction"], 0)
            reduced_outputs = render_outputs(workspace, reduced, "resume")
            markdown_validation = resume_render.validateRenderedOutput(
                {
                    "format": "markdown",
                    "content": (workspace / "output" / "resume.md").read_text(encoding="utf-8"),
                    "expected_resume": reduced,
                }
            )
            docx_validation = resume_render.validateRenderedOutput(docx_payload_from_result(reduced_outputs["docx"], reduced))
            self.assertEqual(markdown_validation["status"], "pass", markdown_validation)
            self.assertEqual(docx_validation["status"], "pass", docx_validation)

            drive_tail_from_selection(workspace, run_state, "op_reduce_1")
            advance_ok(
                run_state,
                "RENDER",
                {
                    "render_output": {"kind": "artifact", "path": "output/resume.md", "sha256": reduced_outputs["fingerprints"]["output/resume.md"]},
                    "measure_layout": artifact_ref(workspace, "reports/reduced-layout.json", reduced_layout),
                },
            )
            render_record = record_ok(
                run_state,
                "RENDER",
                {
                    "status": "fits",
                    "requiredReduction": 0,
                    "render_refs": [artifact_ref(workspace, "reports/reduced-layout-ref.json", reduced_layout)],
                    "artifact_refs": [
                        {"kind": "artifact", "path": "output/resume.md", "sha256": reduced_outputs["fingerprints"]["output/resume.md"]},
                        {"kind": "artifact", "path": "output/resume.docx", "sha256": reduced_outputs["fingerprints"]["output/resume.docx"]},
                    ],
                },
            )
            self.assertEqual(render_record["render_overflow"]["status"], "fits")

            validation_report = {"status": "pass", "validation_summary": {"markdown": "pass", "docx": "pass"}}
            validation_ref = artifact_ref(workspace, "reports/render-validation.json", validation_report)
            advance_ok(run_state, "RENDER_VALIDATION", {"render_validation_report": validation_ref})

            render_evidence = {
                "template_version": TEMPLATE["template_version"],
                "metrics_version": reduced_layout["constraints"]["metrics_version"],
                "artifact_fingerprints": reduced_outputs["fingerprints"],
                "validation_summary": {"markdown": markdown_validation["status"], "docx": docx_validation["status"]},
            }
            evidence_ref = artifact_ref(workspace, "reports/render-audit-evidence.json", render_evidence)
            assert_render_evidence_payload(self, render_evidence, workspace, reduced_outputs["fingerprints"])
            for field_name in ["template_version", "metrics_version", "artifact_fingerprints", "validation_summary"]:
                broken = dict(render_evidence)
                broken.pop(field_name)
                with self.subTest(missing=field_name):
                    with self.assertRaises(AssertionError):
                        assert_render_evidence_payload(self, broken, workspace, reduced_outputs["fingerprints"])

            run_state["output_artifact_paths"] = ["output/resume.md", "output/resume.docx"]
            run_state["render_validation_report_ref"] = validation_ref
            run_state["audit_refs"] = ["reports/render-audit-evidence.json"]
            complete_ref = artifact_ref(workspace, "reports/audit-manifest.json", {"status": "passed", "render_evidence": evidence_ref})
            can_complete = workflow.assertCanComplete({**run_state, "audit_ref": complete_ref})
            self.assertEqual(can_complete["status"], "ok", can_complete)
            advance_ok(run_state, "COMPLETE", {"audit_ref": complete_ref})

            manifest = workflow.buildRunManifest(run_state)
            self.assertEqual(manifest["renderer_template_version"], RENDERER_TEMPLATE_VERSION)
            self.assertEqual(manifest["output_artifact_paths"], ["output/resume.md", "output/resume.docx"])
            self.assertEqual(manifest["audit_refs"], ["reports/render-audit-evidence.json"])
            self.assertIn("render_refs", run_state)
            self.assertIn("validation_refs", run_state)
            loaded_evidence = json.loads((workspace / manifest["audit_refs"][0]).read_text(encoding="utf-8"))
            assert_render_evidence_payload(self, loaded_evidence, workspace, reduced_outputs["fingerprints"])


if __name__ == "__main__":
    unittest.main()
