"""Contract-first tests for the future workflow package."""

from __future__ import annotations

import asyncio
import hashlib
import importlib
import inspect
import json
import tempfile
import unittest
from dataclasses import asdict
from importlib import metadata as importlib_metadata
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
SURFACE = json.loads((ROOT / "workflow" / "workflow_surface.json").read_text(encoding="utf-8"))
PUBLIC_FUNCTIONS = tuple(SURFACE["public_api"]["functions"])
CHECKPOINTS = tuple(SURFACE["canonical_checkpoints"])
MANIFEST_FIELDS = set(SURFACE["run_manifest_required_fields"])


def maybe_await(value):
    if inspect.isawaitable(value):
        return asyncio.run(value)
    return value


def load_workflow_module(test_case: unittest.TestCase):
    try:
        module = importlib.import_module("workflow")
    except ModuleNotFoundError as exc:
        test_case.fail(
            "Expected importable package 'workflow'. Implement createRun, getNextCheckpoint, "
            "advanceCheckpoint, recordCheckpointResult, buildRunManifest, recoverRun, and assertCanComplete."
        )
        raise exc
    for function_name in PUBLIC_FUNCTIONS:
        test_case.assertTrue(callable(getattr(module, function_name, None)), f"workflow must expose {function_name}().")
    return module


def serialized(value: object) -> str:
    return json.dumps(value, sort_keys=True).lower()


def contains_value(value: object, expected: object) -> bool:
    if value == expected:
        return True
    if isinstance(value, dict):
        return any(contains_value(item, expected) for item in value.values())
    if isinstance(value, list):
        return any(contains_value(item, expected) for item in value)
    return False


class CareerStoreDouble:
    def __init__(self, state):
        self.state = dict(state)
        self.calls = 0
        self.getMigrationState = self.read_state

    def read_state(self):
        self.calls += 1
        return dict(self.state)


class WorkflowSurfaceManifestTests(unittest.TestCase):
    def test_manifest_declares_exact_public_functions(self):
        self.assertEqual(PUBLIC_FUNCTIONS, (
            "createRun",
            "getNextCheckpoint",
            "advanceCheckpoint",
            "recordCheckpointResult",
            "buildRunManifest",
            "recoverRun",
            "assertCanComplete",
        ))

    def test_manifest_declares_canonical_checkpoint_order_and_manifest_fields(self):
        self.assertEqual(CHECKPOINTS, (
            "INIT",
            "INGEST_RESUME",
            "VALIDATE_BASE",
            "EXTRACT_PERSIST_CAREER_FACTS",
            "INGEST_JOB",
            "NORMALIZE_JOB",
            "MATCH_BASE",
            "RESOLVE_GAPS",
            "BUILD_SELECTION_PLAN",
            "PROPOSE_TAILORING_CHANGES",
            "VALIDATE_CHANGES",
            "APPLY_CHANGES",
            "FINAL_MATCH",
            "GROUNDING_AUDIT",
            "ATS_STRUCTURE_VALIDATION",
            "RENDER",
            "RENDER_VALIDATION",
            "COMPLETE",
        ))
        for field in [
            "run_id",
            "base_resume_hash",
            "config_hash",
            "initial_score",
            "final_score",
            "facts_added",
            "facts_verified",
            "operations_applied",
            "operations_rejected",
            "validation_status",
            "output_artifact_paths",
        ]:
            self.assertIn(field, MANIFEST_FIELDS)

    def test_surface_declares_typed_recovery_plan_fields(self):
        recover_surface = next(entry for entry in SURFACE["surfaces"] if entry["name"] == "recoverRun")
        self.assertEqual(
            recover_surface["output_contract"]["required_fields"],
            [
                "status",
                "run_id",
                "resume_from_checkpoint",
                "already_applied_operations",
                "already_asked_questions",
                "already_written_facts",
                "last_match_fact_watermark",
                "resolution_loop_state",
                "resolution_blocking_reasons",
                "render_overflow_state",
                "render_overflow_blocking_reasons",
                "required_reruns",
                "integrity",
                "resumable",
            ],
        )

    def test_surface_declares_typed_checkpoint_duplicate_fields(self):
        record_surface = next(entry for entry in SURFACE["surfaces"] if entry["name"] == "recordCheckpointResult")
        self.assertIn("fact_results", record_surface["output_contract"]["required_fields"])
        self.assertIn("operation_results", record_surface["output_contract"]["required_fields"])


class WorkflowPublicSurfaceBoundaryTests(unittest.TestCase):
    def test_workflow_exports_only_manifested_non_interactive_public_surface(self):
        module = load_workflow_module(self)
        expected_exports = (
            "RUN_MANIFEST_SCHEMA",
            "SCHEMAS",
            "Checkpoint",
            "RunManifest",
            "RunManifestValidationError",
            "UnknownRunError",
            "createRun",
            "getNextCheckpoint",
            "advanceCheckpoint",
            "recordCheckpointResult",
            "buildRunManifest",
            "reconstructRunManifest",
            "recoverRun",
            "assertCanComplete",
        )
        self.assertEqual(tuple(module.__all__), expected_exports)
        self.assertEqual(
            tuple(name for name in module.__all__ if inspect.isfunction(getattr(module, name, None))),
            (
                "createRun",
                "getNextCheckpoint",
                "advanceCheckpoint",
                "recordCheckpointResult",
                "buildRunManifest",
                "reconstructRunManifest",
                "recoverRun",
                "assertCanComplete",
            ),
        )

    def test_exported_workflow_functions_have_no_interaction_question_api_shape(self):
        module = load_workflow_module(self)
        forbidden_terms = ("ask", "prompt", "question", "answer", "interact", "user_input")
        for name in module.__all__:
            value = getattr(module, name)
            if not inspect.isfunction(value):
                continue
            signature = inspect.signature(value)
            public_tokens = [name, *signature.parameters]
            self.assertFalse(
                any(term in token.lower() for token in public_tokens for term in forbidden_terms),
                f"{name}{signature} must remain orchestration-only, not a user-interaction API.",
            )


class WorkflowStateMachineContractTests(unittest.TestCase):
    def setUp(self):
        self.workflow = load_workflow_module(self)
        self.tempdir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tempdir.name)
        self.config = {"schemaVersion": "1.0", "matching": {"requireHardRequirementsResolved": True}}

    def tearDown(self):
        self.tempdir.cleanup()

    def create_run(self):
        return maybe_await(self.workflow.createRun(workspace=self.workspace, config=self.config))

    def persist_run_state(self, run_state):
        path = self.workspace / ".workflow" / "runs" / f"{run_state['run_id']}.json"
        path.write_text(json.dumps(run_state, sort_keys=True, indent=2), encoding="utf-8")

    def persisted_run_state(self, run_state):
        path = self.workspace / ".workflow" / "runs" / f"{run_state['run_id']}.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def store_state(self, *, schema_version=None, status="ok", pending=None):
        import career_store

        return {
            "schema_version": schema_version or career_store.CAREER_STORE_SCHEMA_VERSION,
            "database_path": str(self.workspace / "data" / "career.db"),
            "applied_migrations": ["001_initial"],
            "pending_migrations": list(pending or []),
            "status": status,
            "metadata": {"source": "test-double"},
        }

    def run_with_verified_base_and_career_db(self, *, recorded_schema_version=None):
        run_state = self.create_run()
        base_ref = self.artifact_ref("resume/base.json", {"resume_id": "base_1", "summary": "Built React systems."})
        schema_version = recorded_schema_version or self.store_state()["schema_version"]
        run_state.update(
            {
                "base_resume_id": "base_1",
                "base_resume_hash": base_ref["sha256"],
                "careerDbVersion": {
                    "schema_version": schema_version,
                    "database_path": str(self.workspace / "data" / "career.db"),
                    "applied_migrations": ["001_initial"],
                    "pending_migrations": [],
                    "status": "ok",
                    "metadata": {"source": "recorded"},
                },
                "stage_state": {
                    **run_state.get("stage_state", {}),
                    "VALIDATE_BASE": {"canonical_resume_exists": dict(base_ref)},
                },
                "verified_evidence": {
                    **run_state.get("verified_evidence", {}),
                    "VALIDATE_BASE": {"canonical_resume_exists": dict(base_ref)},
                },
            }
        )
        self.persist_run_state(run_state)
        return run_state, base_ref

    def dto_ref(self, schema_id, payload=None):
        return {"kind": "dto", "schema_id": schema_id, "payload": payload or {"status": "passed"}}

    def artifact_ref(self, relative_path, payload=None):
        path = self.workspace / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        if payload is None:
            path.write_text(f"artifact:{relative_path}", encoding="utf-8")
        else:
            path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        return {"kind": "artifact", "path": relative_path, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

    def operation_state_ref(self, *operation_ids):
        return {"kind": "run_state", "key": "operation_statuses", "operation_ids": list(operation_ids)}

    def advance_ok(self, run_state, target, evidence):
        advanced = maybe_await(self.workflow.advanceCheckpoint(run_state, target, evidence))
        self.assertEqual(advanced["status"], "ok", advanced.get("blocking_reasons"))
        return advanced

    def enter_resolve_gaps_with_recorded_match(self, match_result):
        run_state = self.create_run()
        self.advance_ok(run_state, "INGEST_RESUME", {"config_validated": self.dto_ref("WorkflowStatusEvidence")})
        self.advance_ok(run_state, "VALIDATE_BASE", {"canonical_resume_exists": self.artifact_ref("resume/base.json", {"resume_id": "base_1"})})
        self.advance_ok(run_state, "EXTRACT_PERSIST_CAREER_FACTS", {"base_validation": self.dto_ref("WorkflowStatusEvidence")})
        self.advance_ok(run_state, "INGEST_JOB", {"career_facts_persisted": self.artifact_ref("data/career.db")})
        self.advance_ok(run_state, "NORMALIZE_JOB", {"job_ingested": self.artifact_ref("job/current.json", {"job_id": "job_1"})})
        self.advance_ok(run_state, "MATCH_BASE", {"job_normalized": self.dto_ref("WorkflowStatusEvidence")})
        recorded = maybe_await(self.workflow.recordCheckpointResult(run_state, "MATCH_BASE", {"match_result": match_result}))
        self.assertEqual(recorded["status"], "ok")
        self.advance_ok(
            run_state,
            "RESOLVE_GAPS",
            {"match_result": self.dto_ref("MatchResultEvidence", {"status": "ok", "match_result": match_result})},
        )
        return run_state

    def match_result(self, decision, requirements=None, unresolved=None, preferred=None, explanations=None):
        requirements = list(requirements or [])
        unresolved = list(unresolved or [])
        preferred = list(preferred or [])
        return {
            "schema_version": "match-result.v1",
            "score": 7.0,
            "threshold": 7.5,
            "hardRequirementsResolved": decision != "blocked",
            "decision": decision,
            "can_continue": decision == "continue",
            "requirement_results": requirements,
            "unresolved_requirement_ids": unresolved,
            "preferred_unresolved_requirement_ids": preferred,
            "explanations": explanations or [],
        }

    def requirement_result(self, requirement_id, impact_rank, *, classification="required", unresolved=True, blocking=False):
        return {
            "requirement_id": requirement_id,
            "classification": classification,
            "impact_rank": impact_rank,
            "resolution_state": "unknown" if unresolved else "verified_fact_match",
            "unresolved": unresolved,
            "blocking": blocking,
            "max_score": impact_rank,
        }

    def advance_tail_to_complete_gate(self, run_state):
        self.advance_tail_to_render_checkpoint(run_state)
        self.advance_ok(
            run_state,
            "RENDER",
            {
                "render_output": self.artifact_ref("render/resume.md", {"status": "rendered"}),
                "measure_layout": self.artifact_ref("render/measure-layout.json", {"status": "fits", "required_reduction": 0}),
            },
        )
        rendered = maybe_await(self.workflow.recordCheckpointResult(run_state, "RENDER", {"status": "fits", "requiredReduction": 0}))
        self.assertEqual(rendered["status"], "ok")
        self.advance_ok(run_state, "RENDER_VALIDATION", {"render_validation_report": self.artifact_ref("reports/render-validation.json", {"status": "pass"})})

        complete_decision = maybe_await(self.workflow.getNextCheckpoint(run_state))
        self.assertEqual(complete_decision["next_checkpoint"], "COMPLETE")
        self.assertNotIn("render_validation", complete_decision["blocking_reasons"])
        self.assertIn("audit_ref", complete_decision["blocking_reasons"])
        return complete_decision

    def advance_tail_to_render_checkpoint(self, run_state):
        self.advance_ok(run_state, "BUILD_SELECTION_PLAN", {"selection_plan": self.artifact_ref("plans/selection-plan.json", {"status": "ok", "selection_plan": {}})})
        proposed = maybe_await(self.workflow.recordCheckpointResult(run_state, "BUILD_SELECTION_PLAN", {"operations_proposed": ["op_1"]}))
        self.assertEqual(proposed["status"], "ok")
        self.advance_ok(run_state, "PROPOSE_TAILORING_CHANGES", {"proposed_operations": self.operation_state_ref("op_1")})
        validated = maybe_await(self.workflow.recordCheckpointResult(run_state, "PROPOSE_TAILORING_CHANGES", {"operations_validated": ["op_1"]}))
        self.assertEqual(validated["status"], "ok")
        self.advance_ok(run_state, "VALIDATE_CHANGES", {"validated_operations": self.operation_state_ref("op_1")})
        applied = maybe_await(self.workflow.recordCheckpointResult(run_state, "VALIDATE_CHANGES", {"operations_applied": ["op_1"]}))
        self.assertEqual(applied["status"], "ok")
        self.advance_ok(run_state, "APPLY_CHANGES", {"applied_operations": self.operation_state_ref("op_1")})
        self.advance_ok(run_state, "FINAL_MATCH", {"match_report": self.artifact_ref("reports/final-match.json", {"status": "passed"})})
        self.advance_ok(run_state, "GROUNDING_AUDIT", {"grounding_audit": self.artifact_ref("reports/grounding-audit.json", {"status": "passed"})})
        self.advance_ok(run_state, "ATS_STRUCTURE_VALIDATION", {"ats_report": self.artifact_ref("reports/ats.json", {"status": "passed"})})

    def advance_looped_selection_to_render_checkpoint(self, run_state, operation_id):
        recorded = maybe_await(self.workflow.recordCheckpointResult(run_state, "BUILD_SELECTION_PLAN", {"operations_proposed": [operation_id]}))
        self.assertEqual(recorded["status"], "ok")
        self.advance_ok(run_state, "PROPOSE_TAILORING_CHANGES", {"proposed_operations": self.operation_state_ref(operation_id)})
        validated = maybe_await(self.workflow.recordCheckpointResult(run_state, "PROPOSE_TAILORING_CHANGES", {"operations_validated": [operation_id]}))
        self.assertEqual(validated["status"], "ok")
        self.advance_ok(run_state, "VALIDATE_CHANGES", {"validated_operations": self.operation_state_ref(operation_id)})
        applied = maybe_await(self.workflow.recordCheckpointResult(run_state, "VALIDATE_CHANGES", {"operations_applied": [operation_id]}))
        self.assertEqual(applied["status"], "ok")
        self.advance_ok(run_state, "APPLY_CHANGES", {"applied_operations": self.operation_state_ref(operation_id)})
        self.advance_ok(run_state, "FINAL_MATCH", {"match_report": self.artifact_ref(f"reports/final-match-{operation_id}.json", {"status": "passed"})})
        self.advance_ok(run_state, "GROUNDING_AUDIT", {"grounding_audit": self.artifact_ref(f"reports/grounding-audit-{operation_id}.json", {"status": "passed"})})
        self.advance_ok(run_state, "ATS_STRUCTURE_VALIDATION", {"ats_report": self.artifact_ref(f"reports/ats-{operation_id}.json", {"status": "passed"})})

    def overflow_layout_payload(self):
        import resume_render

        long_resume = {
            "schema_version": "test-1",
            "basics": {"name": "Candidate"},
            "sections": [
                {"id": "summary", "heading": "Summary", "items": ["React platform engineer."]},
                {
                    "id": "experience",
                    "heading": "Experience",
                    "items": [
                        {
                            "company": "Example SaaS",
                            "title": "Engineer",
                            "bullets": [
                                f"Built validated product capability {index} with React, TypeScript, and REST API delivery."
                                for index in range(95)
                            ],
                        }
                    ],
                },
            ],
        }
        template = {"template_version": "1.0.0", "section_order": ["summary", "experience"], "target_pages": 1}
        layout = maybe_await(resume_render.measureLayout(long_resume, template))
        self.assertEqual(layout["status"], "overflow", layout)
        self.assertGreater(layout["requiredReduction"], layout["estimated_pages"] - layout["target_pages"])
        return layout

    def valid_manifest_run_state(self):
        run_state = self.create_run()
        run_state.update(
            {
                "base_resume_id": "base_1",
                "base_resume_hash": "hash_base",
                "job_id": "job_1",
                "renderer_template_version": "ats-clean@1",
                "initial_score": 6.4,
                "final_score": 8.2,
            }
        )
        return run_state

    def test_create_run_records_versions_config_hash_stage_recovery_metadata_and_match_watermark(self):
        run_state = self.create_run()
        for field in [
            "run_id",
            "current_checkpoint",
            "config_hash",
            "schema_versions",
            "package_versions",
            "stage_state",
            "recovery_markers",
            "last_match_fact_watermark",
        ]:
            self.assertIn(field, run_state)
        self.assertEqual(run_state["current_checkpoint"], "INIT")
        self.assertEqual(run_state["last_match_fact_watermark"], [])

    def test_collect_versions_uses_installed_metadata_schema_constants_and_core_matching_surface(self):
        import career_store
        import resume_core
        from workflow.versions import CAREER_DB_VERSION_UNAVAILABLE, collectVersions

        versions = collectVersions(workspace=self.workspace, config=self.config)
        installed_version = importlib_metadata.version("resume-kit")
        self.assertEqual(
            versions["package_versions"],
            {
                "workflow": installed_version,
                "resume-core": installed_version,
                "career-store": installed_version,
            },
        )
        self.assertEqual(versions["schema_versions"]["canonical_resume"], resume_core.CANONICAL_RESUME_SCHEMA_VERSION)
        self.assertEqual(versions["schema_versions"]["job"], resume_core.JOB_MODEL_SCHEMA_VERSION)
        self.assertEqual(versions["schema_versions"]["career_db"], career_store.CAREER_STORE_SCHEMA_VERSION)
        self.assertEqual(versions["schema_versions"]["change_operation"], resume_core.RESUME_CHANGE_OPERATION_SCHEMA_VERSION)
        self.assertEqual(versions["schema_versions"]["run_manifest"], self.workflow.RUN_MANIFEST_SCHEMA["schema_version"])
        self.assertEqual(
            {
                "matching_algorithm_version": versions["matching_algorithm_version"],
                "matching_config_version": versions["matching_config_version"],
            },
            resume_core.matchingVersions(),
        )
        self.assertEqual(versions["careerDbVersion"], CAREER_DB_VERSION_UNAVAILABLE)

    def test_collect_versions_raises_typed_error_when_installed_source_is_unavailable(self):
        import workflow.versions as version_module

        with mock.patch.object(version_module.importlib_metadata, "packages_distributions", return_value={}):
            with mock.patch.object(
                version_module.importlib_metadata,
                "version",
                side_effect=version_module.importlib_metadata.PackageNotFoundError,
            ):
                with self.assertRaises(version_module.VersionSourceUnavailableError) as raised:
                    version_module.collectVersions(workspace=self.workspace, config=self.config)
        self.assertEqual(raised.exception.source, "package_versions.workflow")

    def test_same_config_runs_get_distinct_ids_and_coexisting_persisted_state(self):
        first = self.create_run()
        advanced = maybe_await(
            self.workflow.advanceCheckpoint(
                first,
                "INGEST_RESUME",
                {"config_validated": self.dto_ref("WorkflowStatusEvidence")},
            )
        )
        self.assertEqual(advanced["status"], "ok")

        second = self.create_run()
        self.assertNotEqual(first["run_id"], second["run_id"])
        self.assertEqual(first["config_hash"], second["config_hash"])

        runs_dir = self.workspace / ".workflow" / "runs"
        self.assertTrue((runs_dir / f"{first['run_id']}.json").exists())
        self.assertTrue((runs_dir / f"{second['run_id']}.json").exists())

        recovered_first = maybe_await(self.workflow.recoverRun(workspace=self.workspace, run_id=first["run_id"]))
        self.assertEqual(recovered_first["resume_from_checkpoint"], "INGEST_RESUME")
        recovered_second = maybe_await(self.workflow.recoverRun(workspace=self.workspace, run_id=second["run_id"]))
        self.assertEqual(recovered_second["resume_from_checkpoint"], "INIT")

    def test_create_run_config_hash_includes_validated_agent_config_defaults_and_model(self):
        absent_agent = self.create_run()
        self.config = {
            "schemaVersion": "1.0",
            "matching": {"requireHardRequirementsResolved": True},
            "agent": {
                "model": "claude-sonnet-4-6",
                "schema_mode": "json_schema",
                "timeout_ms": 60000,
                "max_retries": 2,
                "cost_ceiling": 1.0,
            },
        }
        explicit_defaults = self.create_run()
        self.config = {
            "schemaVersion": "1.0",
            "matching": {"requireHardRequirementsResolved": True},
            "agent": {"model": "claude-sonnet-4-6-next"},
        }
        changed_model = self.create_run()

        self.assertEqual(absent_agent["config_hash"], explicit_defaults["config_hash"])
        self.assertNotEqual(explicit_defaults["config_hash"], changed_model["config_hash"])
        self.assertEqual(changed_model["agent_model_config"]["model"], "claude-sonnet-4-6-next")

    def test_recover_run_unknown_run_raises_unknown_run_error(self):
        with self.assertRaises(self.workflow.UnknownRunError) as raised:
            maybe_await(self.workflow.recoverRun(workspace=self.workspace, run_id="run_missing"))

        self.assertEqual(raised.exception.run_id, "run_missing")
        self.assertEqual(raised.exception.workspace, str(self.workspace))

    def test_recover_run_never_fabricates_payload_for_missing_run_file(self):
        runs_dir = self.workspace / ".workflow" / "runs"
        runs_dir.mkdir(parents=True)
        missing_path = runs_dir / "run_missing.json"
        self.assertFalse(missing_path.exists())

        with self.assertRaises(self.workflow.UnknownRunError):
            maybe_await(self.workflow.recoverRun(workspace=self.workspace, run_id="run_missing"))

        self.assertFalse(missing_path.exists())

    def test_recover_run_returns_real_structured_integrity_results(self):
        run_state = self.create_run()

        recovery = maybe_await(self.workflow.recoverRun(workspace=self.workspace, run_id=run_state["run_id"]))

        self.assertNotIn("transactional_integrity", recovery)
        self.assertFalse(recovery["resumable"])
        self.assertEqual(set(recovery["integrity"]), {"career_db", "base_resume", "rejected_operations"})
        for check in recovery["integrity"].values():
            self.assertIsInstance(check, dict)
            self.assertIn("status", check)
            self.assertIn("evidence_ref", check)
            self.assertIn("reason", check)
        self.assertEqual(recovery["integrity"]["career_db"]["status"], "unverified")
        self.assertEqual(recovery["integrity"]["career_db"]["reason"], "career_db_not_configured")
        self.assertEqual(recovery["integrity"]["base_resume"]["status"], "failed")
        self.assertEqual(recovery["integrity"]["base_resume"]["reason"], "base_resume_hash_not_recorded")
        self.assertEqual(recovery["integrity"]["rejected_operations"]["status"], "verified")
        self.assertEqual(recovery["integrity"]["rejected_operations"]["reason"], "no_operations_recorded")

    def test_recover_run_career_db_pending_schema_update_fails_via_store_double(self):
        run_state, _ = self.run_with_verified_base_and_career_db()
        store = CareerStoreDouble(self.store_state(status="pending", pending=["002_pending"]))

        recovery = maybe_await(self.workflow.recoverRun(workspace=self.workspace, run_id=run_state["run_id"], career_store=store))

        self.assertEqual(store.calls, 1)
        self.assertEqual(recovery["integrity"]["career_db"]["status"], "failed")
        self.assertIn("status_not_ok:pending", recovery["integrity"]["career_db"]["reason"])
        self.assertIn("pending_migrations:002_pending", recovery["integrity"]["career_db"]["reason"])
        self.assertEqual(recovery["integrity"]["career_db"]["evidence_ref"]["state"]["pending_migrations"], ["002_pending"])

    def test_recover_run_career_db_version_mismatch_fails(self):
        run_state, _ = self.run_with_verified_base_and_career_db(recorded_schema_version="career-store.v0")
        store = CareerStoreDouble(self.store_state(schema_version="career-store.v1"))

        recovery = maybe_await(self.workflow.recoverRun(workspace=self.workspace, run_id=run_state["run_id"], career_store=store))

        self.assertEqual(recovery["integrity"]["career_db"]["status"], "failed")
        self.assertIn("schema_version_mismatch", recovery["integrity"]["career_db"]["reason"])
        self.assertIn("recorded=career-store.v0", recovery["integrity"]["career_db"]["reason"])
        self.assertIn("consulted=career-store.v1", recovery["integrity"]["career_db"]["reason"])

    def test_recover_run_tampered_base_resume_fails_with_hash_mismatch(self):
        run_state, _ = self.run_with_verified_base_and_career_db()
        (self.workspace / "resume" / "base.json").write_text(json.dumps({"resume_id": "base_1", "summary": "tampered"}), encoding="utf-8")

        recovery = maybe_await(
            self.workflow.recoverRun(
                workspace=self.workspace,
                run_id=run_state["run_id"],
                career_store=CareerStoreDouble(self.store_state()),
            )
        )

        self.assertFalse(recovery["resumable"])
        self.assertEqual(recovery["integrity"]["base_resume"]["status"], "failed")
        self.assertIn("base_resume_hash_mismatch", recovery["integrity"]["base_resume"]["reason"])
        self.assertEqual(recovery["integrity"]["base_resume"]["evidence_ref"]["path"], "resume/base.json")

    def test_recover_run_rejected_then_applied_operation_fails_and_lists_id(self):
        run_state, _ = self.run_with_verified_base_and_career_db()
        maybe_await(self.workflow.recordCheckpointResult(run_state, "VALIDATE_CHANGES", {"operations_rejected": ["op_bad"]}))
        maybe_await(self.workflow.recordCheckpointResult(run_state, "APPLY_CHANGES", {"operations_applied": ["op_bad"]}))

        recovery = maybe_await(
            self.workflow.recoverRun(
                workspace=self.workspace,
                run_id=run_state["run_id"],
                career_store=CareerStoreDouble(self.store_state()),
            )
        )

        self.assertFalse(recovery["resumable"])
        self.assertEqual(recovery["integrity"]["rejected_operations"]["status"], "failed")
        self.assertIn("rejected_operation_applied_later:op_bad", recovery["integrity"]["rejected_operations"]["reason"])
        self.assertEqual(recovery["integrity"]["rejected_operations"]["evidence_ref"]["offending_operation_ids"], ["op_bad"])

    def test_recover_run_clean_full_run_verifies_all_integrity_checks_with_evidence(self):
        run_state, base_ref = self.run_with_verified_base_and_career_db()
        maybe_await(self.workflow.recordCheckpointResult(run_state, "VALIDATE_CHANGES", {"operations_rejected": ["op_rejected"]}))
        store = CareerStoreDouble(self.store_state())

        recovery = maybe_await(self.workflow.recoverRun(workspace=self.workspace, run_id=run_state["run_id"], career_store=store))

        self.assertTrue(recovery["resumable"])
        self.assertEqual(store.calls, 1)
        for name, check in recovery["integrity"].items():
            with self.subTest(name=name):
                self.assertEqual(check["status"], "verified")
                self.assertIsInstance(check["evidence_ref"], dict)
        self.assertEqual(recovery["integrity"]["career_db"]["evidence_ref"]["state"]["schema_version"], self.store_state()["schema_version"])
        self.assertEqual(recovery["integrity"]["base_resume"]["evidence_ref"]["sha256"], base_ref["sha256"])
        self.assertEqual(recovery["integrity"]["rejected_operations"]["evidence_ref"]["rejected_operation_ids"], ["op_rejected"])

    def test_recovery_at_apply_changes_requires_grounding_and_final_match_reruns_before_completion(self):
        run_state = self.create_run()
        run_state["current_checkpoint"] = "APPLY_CHANGES"
        self.persist_run_state(run_state)

        recovery = maybe_await(self.workflow.recoverRun(workspace=self.workspace, run_id=run_state["run_id"]))

        self.assertEqual(recovery["required_reruns"], ["GROUNDING_AUDIT", "FINAL_MATCH"])
        persisted = self.persisted_run_state(run_state)
        self.assertEqual(
            persisted["recovery_events"][-1],
            {
                "recovered_at_checkpoint": "APPLY_CHANGES",
                "required_reruns": ["GROUNDING_AUDIT", "FINAL_MATCH"],
                "recovery_sequence": 1,
            },
        )
        run_state.update(self.passing_completion_gate_state())

        blocked = maybe_await(self.workflow.assertCanComplete(run_state))
        self.assertFalse(blocked["can_complete"])
        self.assertIn("recovery_reruns", blocked["failed_gates"])
        self.assertEqual(
            blocked["failed_gate_reasons"]["recovery_reruns"]["missing_or_stale_checkpoints"],
            ["GROUNDING_AUDIT", "FINAL_MATCH"],
        )

        maybe_await(self.workflow.recordCheckpointResult(run_state, "GROUNDING_AUDIT", {"status": "passed"}))
        still_blocked = maybe_await(self.workflow.assertCanComplete(run_state))
        self.assertFalse(still_blocked["can_complete"])
        self.assertEqual(
            still_blocked["failed_gate_reasons"]["recovery_reruns"]["missing_or_stale_checkpoints"],
            ["FINAL_MATCH"],
        )

        maybe_await(self.workflow.recordCheckpointResult(run_state, "FINAL_MATCH", {"status": "passed"}))
        allowed = maybe_await(self.workflow.assertCanComplete(run_state))
        self.assertTrue(allowed["can_complete"], allowed)

    def test_pre_recovery_rerun_results_do_not_satisfy_recovery_completion_gate(self):
        run_state = self.create_run()
        maybe_await(self.workflow.recordCheckpointResult(run_state, "GROUNDING_AUDIT", {"status": "passed"}))
        maybe_await(self.workflow.recordCheckpointResult(run_state, "FINAL_MATCH", {"status": "passed"}))
        run_state["current_checkpoint"] = "APPLY_CHANGES"
        self.persist_run_state(run_state)

        maybe_await(self.workflow.recoverRun(workspace=self.workspace, run_id=run_state["run_id"]))
        run_state.update(self.passing_completion_gate_state())

        blocked = maybe_await(self.workflow.assertCanComplete(run_state))

        self.assertFalse(blocked["can_complete"])
        self.assertEqual(
            blocked["failed_gate_reasons"]["recovery_reruns"]["missing_or_stale_checkpoints"],
            ["GROUNDING_AUDIT", "FINAL_MATCH"],
        )

    def test_recovery_at_ingest_job_has_empty_rerun_set_and_vacuous_completion_gate(self):
        run_state = self.create_run()
        run_state["current_checkpoint"] = "INGEST_JOB"
        self.persist_run_state(run_state)

        recovery = maybe_await(self.workflow.recoverRun(workspace=self.workspace, run_id=run_state["run_id"]))
        run_state.update(self.passing_completion_gate_state())
        allowed = maybe_await(self.workflow.assertCanComplete(run_state))

        self.assertEqual(recovery["required_reruns"], [])
        self.assertTrue(allowed["can_complete"], allowed)

    def test_latest_recovery_event_governs_recovery_rerun_gate(self):
        run_state = self.create_run()
        run_state["current_checkpoint"] = "APPLY_CHANGES"
        self.persist_run_state(run_state)
        first_recovery = maybe_await(self.workflow.recoverRun(workspace=self.workspace, run_id=run_state["run_id"]))
        self.assertEqual(first_recovery["required_reruns"], ["GROUNDING_AUDIT", "FINAL_MATCH"])
        maybe_await(self.workflow.recordCheckpointResult(run_state, "FINAL_MATCH", {"status": "passed"}))

        run_state["current_checkpoint"] = "FINAL_MATCH"
        self.persist_run_state(run_state)
        second_recovery = maybe_await(self.workflow.recoverRun(workspace=self.workspace, run_id=run_state["run_id"]))
        run_state.update(self.passing_completion_gate_state())
        blocked = maybe_await(self.workflow.assertCanComplete(run_state))

        self.assertEqual(second_recovery["required_reruns"], ["FINAL_MATCH"])
        self.assertEqual(self.persisted_run_state(run_state)["recovery_events"][-1]["recovery_sequence"], 2)
        self.assertFalse(blocked["can_complete"])
        self.assertEqual(
            blocked["failed_gate_reasons"]["recovery_reruns"]["missing_or_stale_checkpoints"],
            ["FINAL_MATCH"],
        )

        maybe_await(self.workflow.recordCheckpointResult(run_state, "FINAL_MATCH", {"status": "passed"}))
        allowed = maybe_await(self.workflow.assertCanComplete(run_state))
        self.assertTrue(allowed["can_complete"], allowed)

    def test_recovery_at_render_requires_render_and_render_validation_not_final_match(self):
        run_state = self.create_run()
        run_state["current_checkpoint"] = "RENDER"
        self.persist_run_state(run_state)

        recovery = maybe_await(self.workflow.recoverRun(workspace=self.workspace, run_id=run_state["run_id"]))

        self.assertEqual(recovery["required_reruns"], ["RENDER", "RENDER_VALIDATION"])
        self.assertNotEqual(recovery["required_reruns"], ["FINAL_MATCH"])

    def test_create_run_tolerates_malformed_workspace_index(self):
        runs_dir = self.workspace / ".workflow" / "runs"
        runs_dir.mkdir(parents=True)
        (runs_dir / "index.json").write_text("[]", encoding="utf-8")
        run_state = self.create_run()
        index = json.loads((runs_dir / "index.json").read_text(encoding="utf-8"))
        self.assertEqual(index.get(run_state["config_hash"]), [run_state["run_id"]])

    def test_workspace_run_index_maps_config_hash_to_all_run_ids(self):
        first = self.create_run()
        second = self.create_run()
        index_path = self.workspace / ".workflow" / "runs" / "index.json"
        self.assertTrue(index_path.exists())
        index = json.loads(index_path.read_text(encoding="utf-8"))
        self.assertEqual(index.get(first["config_hash"]), [first["run_id"], second["run_id"]])

    def test_valid_transition_sequence_requires_grounded_checkpoint_evidence(self):
        run_state = self.create_run()
        transitions = [
            ("INGEST_RESUME", {"config_validated": self.dto_ref("WorkflowStatusEvidence")}),
            ("VALIDATE_BASE", {"canonical_resume_exists": self.artifact_ref("resume/base.json", {"resume_id": "base_1"})}),
            ("EXTRACT_PERSIST_CAREER_FACTS", {"base_validation": self.dto_ref("WorkflowStatusEvidence")}),
            ("INGEST_JOB", {"career_facts_persisted": self.artifact_ref("data/career.db")}),
            ("NORMALIZE_JOB", {"job_ingested": self.artifact_ref("job/current.json", {"job_id": "job_1"})}),
            ("MATCH_BASE", {"job_normalized": self.dto_ref("WorkflowStatusEvidence")}),
        ]
        for target, evidence in transitions:
            with self.subTest(target=target):
                decision = maybe_await(self.workflow.getNextCheckpoint(run_state))
                self.assertEqual(decision["next_checkpoint"], target)
                for required_name in evidence:
                    self.assertIn(required_name, decision["blocking_reasons"])
                advanced = maybe_await(self.workflow.advanceCheckpoint(run_state, target, evidence))
                self.assertEqual(advanced["status"], "ok")
                self.assertEqual(advanced["current_checkpoint"], target)
                self.assertEqual(advanced["verified_evidence"], evidence)
                run_state["current_checkpoint"] = target

    def test_bare_boolean_checkpoint_evidence_is_typed_rejection(self):
        run_state = self.create_run()
        result = maybe_await(self.workflow.advanceCheckpoint(run_state, "INGEST_RESUME", {"config_validated": True}))
        self.assertEqual(result["status"], "blocked")
        self.assertIn("config_validated", result["blocking_reasons"])
        self.assertIn("evidence_errors", result)
        self.assertEqual(result["evidence_errors"][0]["type"], "invalid_evidence_ref")
        self.assertEqual(result["evidence_errors"][0]["requirement"], "config_validated")

    def test_legacy_persisted_boolean_evidence_is_ungrounded(self):
        run_state = self.create_run()
        run_state["stage_state"]["INGEST_RESUME"] = {"config_validated": True}
        run_state["verified_evidence"] = {"INGEST_RESUME": {"config_validated": True}}
        result = maybe_await(self.workflow.advanceCheckpoint(run_state, "INGEST_RESUME", {}))
        self.assertEqual(result["status"], "blocked")
        self.assertIn("config_validated", result["blocking_reasons"])

    def test_run_state_evidence_must_exist_in_persisted_checkpoint_result(self):
        run_state = self.create_run()
        run_state["current_checkpoint"] = "BUILD_SELECTION_PLAN"
        blocked = maybe_await(
            self.workflow.advanceCheckpoint(
                run_state,
                "PROPOSE_TAILORING_CHANGES",
                {"proposed_operations": self.operation_state_ref("op_1")},
            )
        )
        self.assertEqual(blocked["status"], "blocked")
        self.assertIn("proposed_operations", blocked["blocking_reasons"])
        self.assertEqual(blocked["evidence_errors"][0]["type"], "operation_status_missing")

        record = maybe_await(self.workflow.recordCheckpointResult(run_state, "BUILD_SELECTION_PLAN", {"operations_proposed": ["op_1"]}))
        self.assertEqual(record["status"], "ok")
        advanced = maybe_await(
            self.workflow.advanceCheckpoint(
                run_state,
                "PROPOSE_TAILORING_CHANGES",
                {"proposed_operations": self.operation_state_ref("op_1")},
            )
        )
        self.assertEqual(advanced["status"], "ok")

    def test_invalid_transitions_are_blocked_with_reasons(self):
        run_state = self.create_run()
        invalid_targets = ["BUILD_SELECTION_PLAN", "APPLY_CHANGES", "RENDER", "COMPLETE"]
        for target in invalid_targets:
            with self.subTest(target=target):
                result = maybe_await(self.workflow.advanceCheckpoint(run_state, target, evidence={}))
                self.assertEqual(result["status"], "blocked")
                self.assertIn("blocking_reasons", result)
                self.assertTrue(result["blocking_reasons"])

    def test_render_overflow_routes_back_with_character_count_constraint_evidence(self):
        run_state = self.enter_resolve_gaps_with_recorded_match(self.match_result("continue"))
        self.advance_tail_to_render_checkpoint(run_state)
        layout = self.overflow_layout_payload()

        self.advance_ok(
            run_state,
            "RENDER",
            {
                "render_output": self.artifact_ref("render/overflow-resume.md", {"status": "rendered"}),
                "measure_layout": self.artifact_ref("render/overflow-measure-layout.json", layout),
            },
        )
        recorded = maybe_await(self.workflow.recordCheckpointResult(run_state, "RENDER", layout))

        self.assertEqual(recorded["status"], "ok", recorded.get("blocking_reasons"))
        self.assertEqual(run_state["overflow_iteration"], 1)
        constraints = recorded["render_overflow"]["constraints"]
        self.assertEqual(constraints["requiredReduction"], layout["requiredReduction"])
        self.assertIsInstance(constraints["requiredReduction"], int)
        self.assertGreater(constraints["requiredReduction"], layout["estimated_pages"] - layout["target_pages"])
        self.assertEqual(constraints["offending_sections"], layout["offending_sections"])

        decision = maybe_await(self.workflow.getNextCheckpoint(run_state))
        self.assertEqual(decision["next_checkpoint"], "BUILD_SELECTION_PLAN")
        self.assertEqual(decision["render_overflow"]["predicate"]["branch"], "render_overflow_loop_back")
        self.assertIn("selection_plan", decision["required_inputs"])
        self.assertIn("render_overflow_constraints", decision["required_inputs"])

        looped = maybe_await(
            self.workflow.advanceCheckpoint(
                run_state,
                "BUILD_SELECTION_PLAN",
                {
                    "selection_plan": self.artifact_ref("plans/selection-plan-overflow.json", {"status": "ok", "selection_plan": {}}),
                    "render_overflow_constraints": recorded["render_overflow"]["constraint_ref"],
                },
            )
        )
        self.assertEqual(looped["status"], "ok", looped.get("blocking_reasons"))
        self.assertEqual(run_state["render_overflow_state"]["status"], "consumed")
        self.assertEqual(
            run_state["verified_evidence"]["BUILD_SELECTION_PLAN"]["render_overflow_constraints"],
            recorded["render_overflow"]["constraint_ref"],
        )

    def test_render_overflow_bound_exhaustion_blocks_with_persisted_reasons(self):
        self.config = {
            "schemaVersion": "1.0",
            "matching": {"requireHardRequirementsResolved": True},
            "workflow": {"maxRenderOverflowIterations": 1},
        }
        run_state = self.enter_resolve_gaps_with_recorded_match(self.match_result("continue"))
        first_layout = self.overflow_layout_payload()
        self.advance_tail_to_render_checkpoint(run_state)
        self.advance_ok(
            run_state,
            "RENDER",
            {
                "render_output": self.artifact_ref("render/overflow-first.md", {"status": "rendered"}),
                "measure_layout": self.artifact_ref("render/overflow-first-layout.json", first_layout),
            },
        )
        first_recorded = maybe_await(self.workflow.recordCheckpointResult(run_state, "RENDER", first_layout))
        self.assertEqual(first_recorded["status"], "ok", first_recorded.get("blocking_reasons"))
        self.advance_ok(
            run_state,
            "BUILD_SELECTION_PLAN",
            {
                "selection_plan": self.artifact_ref("plans/selection-plan-overflow-first.json", {"status": "ok"}),
                "render_overflow_constraints": first_recorded["render_overflow"]["constraint_ref"],
            },
        )

        self.advance_looped_selection_to_render_checkpoint(run_state, "op_2")
        second_layout = self.overflow_layout_payload()
        self.advance_ok(
            run_state,
            "RENDER",
            {
                "render_output": self.artifact_ref("render/overflow-second.md", {"status": "rendered"}),
                "measure_layout": self.artifact_ref("render/overflow-second-layout.json", second_layout),
            },
        )
        second_recorded = maybe_await(self.workflow.recordCheckpointResult(run_state, "RENDER", second_layout))

        self.assertEqual(second_recorded["status"], "blocked")
        self.assertEqual(run_state["overflow_iteration"], 2)
        self.assertIn("render_overflow_bound_exhausted", second_recorded["blocking_reasons"])
        persisted = json.loads((self.workspace / ".workflow" / "runs" / f"{run_state['run_id']}.json").read_text(encoding="utf-8"))
        self.assertEqual(persisted["render_overflow_state"]["status"], "blocked")
        self.assertIn("workflow.maxRenderOverflowIterations:1", persisted["render_overflow_blocking_reasons"])

        decision = maybe_await(self.workflow.getNextCheckpoint(run_state))
        self.assertEqual(decision["status"], "blocked")
        self.assertEqual(decision["next_checkpoint"], "RENDER")
        self.assertIn("render_overflow_bound_exhausted", decision["blocking_reasons"])
        blocked_complete = maybe_await(
            self.workflow.advanceCheckpoint(
                run_state,
                "COMPLETE",
                {"audit_ref": self.artifact_ref("reports/audit-after-overflow-block.json", {"status": "passed"})},
            )
        )
        self.assertEqual(blocked_complete["status"], "blocked")
        self.assertNotEqual(run_state["current_checkpoint"], "COMPLETE")
        run_state.update(self.passing_completion_gate_state())
        complete_gate = maybe_await(self.workflow.assertCanComplete(run_state))
        self.assertFalse(complete_gate["can_complete"])
        self.assertIn("render_overflow", complete_gate["failed_gates"])

    def test_deadlock_regression_verified_fact_reruns_match_then_reaches_complete_gate(self):
        run_state = self.create_run()
        run_state["current_checkpoint"] = "RESOLVE_GAPS"
        result = maybe_await(
            self.workflow.recordCheckpointResult(
                run_state,
                "RESOLVE_GAPS",
                {"facts_verified": ["fact_aws"], "question_answer_log_refs": ["qa_aws"]},
            )
        )
        self.assertEqual(result["status"], "ok")
        decision = maybe_await(self.workflow.getNextCheckpoint(run_state))
        self.assertEqual(decision["next_checkpoint"], "MATCH_BASE")

        def advance(target, evidence):
            advanced = maybe_await(self.workflow.advanceCheckpoint(run_state, target, evidence))
            self.assertEqual(advanced["status"], "ok", advanced.get("blocking_reasons"))
            run_state["current_checkpoint"] = target
            run_state.setdefault("verified_evidence", {})[target] = advanced.get("verified_evidence", {})
            return advanced

        advance("MATCH_BASE", {"job_normalized": self.dto_ref("WorkflowStatusEvidence")})
        match_record = maybe_await(self.workflow.recordCheckpointResult(run_state, "MATCH_BASE", {"match_result": {"score": 7.4}}))
        self.assertEqual(match_record["status"], "ok")
        self.assertEqual(run_state["last_match_fact_watermark"], ["fact_aws"])

        advance("RESOLVE_GAPS", {"match_result": self.dto_ref("MatchResultEvidence", {"status": "ok", "match_result": {"score": 7.4}})})
        decision = maybe_await(self.workflow.getNextCheckpoint(run_state))
        self.assertEqual(decision["next_checkpoint"], "BUILD_SELECTION_PLAN")
        self.assertIn("selection_plan", decision["blocking_reasons"])

        self.advance_tail_to_complete_gate(run_state)

        complete_decision = maybe_await(self.workflow.getNextCheckpoint(run_state))
        self.assertEqual(complete_decision["next_checkpoint"], "COMPLETE")
        self.assertEqual(complete_decision["blocking_reasons"], ["audit_ref"])

    def test_resolution_loop_identical_fact_batch_triggers_only_one_match_rerun(self):
        run_state = self.enter_resolve_gaps_with_recorded_match(
            self.match_result(
                "resolve_gaps",
                [self.requirement_result("req_aws", 8.0, classification="required")],
                unresolved=["req_aws"],
            )
        )
        self.assertEqual(run_state["resolution_loop_state"]["iteration_count"], 0)

        recorded = maybe_await(
            self.workflow.recordCheckpointResult(
                run_state,
                "RESOLVE_GAPS",
                {"facts_verified": ["fact_aws"], "question_answer_log_refs": ["qa_aws"]},
            )
        )
        self.assertEqual(recorded["status"], "ok")
        rerun_decision = maybe_await(self.workflow.getNextCheckpoint(run_state))
        self.assertEqual(rerun_decision["resolution_loop"]["predicate"]["branch"], "rerun_match_for_new_facts")
        self.assertEqual(rerun_decision["next_checkpoint"], "MATCH_BASE")

        self.advance_ok(run_state, "MATCH_BASE", {"job_normalized": self.dto_ref("WorkflowStatusEvidence")})
        self.assertEqual(run_state["last_match_fact_watermark"], [])
        self.assertEqual(run_state["resolution_loop_state"]["facts_since_last_match"], ["fact_aws"])
        match_result = self.match_result("continue", [self.requirement_result("req_aws", 8.0, classification="required", unresolved=False)])
        match_record = maybe_await(self.workflow.recordCheckpointResult(run_state, "MATCH_BASE", {"match_result": match_result}))
        self.assertEqual(match_record["status"], "ok")
        self.assertEqual(run_state["last_match_fact_watermark"], ["fact_aws"])
        self.assertEqual(run_state["facts_verified"], ["fact_aws"])
        self.assertEqual(run_state["resolution_loop_state"]["facts_since_last_match"], [])
        self.assertEqual(run_state["resolution_loop_state"]["iteration_count"], 1)

        self.advance_ok(
            run_state,
            "RESOLVE_GAPS",
            {"match_result": self.dto_ref("MatchResultEvidence", {"status": "ok", "match_result": match_result})},
        )
        duplicate_record = maybe_await(self.workflow.recordCheckpointResult(run_state, "RESOLVE_GAPS", {"facts_verified": ["fact_aws"]}))
        self.assertEqual(duplicate_record["status"], "ok")
        self.assertEqual(run_state["facts_verified"], ["fact_aws"])

        continue_decision = maybe_await(self.workflow.getNextCheckpoint(run_state))
        self.assertEqual(continue_decision["resolution_loop"]["predicate"]["branch"], "a_continue")
        self.assertEqual(continue_decision["next_checkpoint"], "BUILD_SELECTION_PLAN")
        self.assertEqual(continue_decision["resolution_loop"]["state"]["iteration_count"], 1)
        repeated_decision = maybe_await(self.workflow.getNextCheckpoint(run_state))
        self.assertEqual(repeated_decision["next_checkpoint"], "BUILD_SELECTION_PLAN")

    def test_multi_iteration_resolution_loop_two_fact_batches_reaches_complete_gate(self):
        run_state = self.enter_resolve_gaps_with_recorded_match(
            self.match_result(
                "resolve_gaps",
                [
                    self.requirement_result("req_aws", 8.0, classification="required"),
                    self.requirement_result("req_gcp", 7.0, classification="required"),
                ],
                unresolved=["req_aws", "req_gcp"],
            )
        )
        self.assertEqual(run_state["resolution_loop_state"]["iteration_count"], 0)

        first_batch = maybe_await(self.workflow.recordCheckpointResult(run_state, "RESOLVE_GAPS", {"facts_verified": ["fact_aws"]}))
        self.assertEqual(first_batch["status"], "ok")
        first_rerun = maybe_await(self.workflow.getNextCheckpoint(run_state))
        self.assertEqual(first_rerun["next_checkpoint"], "MATCH_BASE")
        self.assertEqual(first_rerun["resolution_loop"]["predicate"]["branch"], "rerun_match_for_new_facts")

        self.advance_ok(run_state, "MATCH_BASE", {"job_normalized": self.dto_ref("WorkflowStatusEvidence")})
        first_rerun_match = self.match_result(
            "resolve_gaps",
            [
                self.requirement_result("req_aws", 8.0, classification="required", unresolved=False),
                self.requirement_result("req_gcp", 7.0, classification="required"),
            ],
            unresolved=["req_gcp"],
        )
        self.assertEqual(
            maybe_await(self.workflow.recordCheckpointResult(run_state, "MATCH_BASE", {"match_result": first_rerun_match}))["status"],
            "ok",
        )
        self.assertEqual(run_state["resolution_loop_state"]["iteration_count"], 1)
        self.assertEqual(run_state["resolution_loop_state"]["facts_since_last_match"], [])
        self.assertEqual(run_state["last_match_fact_watermark"], ["fact_aws"])
        self.assertEqual(run_state["facts_verified"], ["fact_aws"])

        self.advance_ok(
            run_state,
            "RESOLVE_GAPS",
            {"match_result": self.dto_ref("MatchResultEvidence", {"status": "ok", "match_result": first_rerun_match})},
        )
        next_topic = maybe_await(self.workflow.getNextCheckpoint(run_state))
        self.assertEqual(next_topic["next_checkpoint"], "RESOLVE_GAPS")
        self.assertEqual(next_topic["resolution_loop"]["predicate"]["branch"], "b_resolve_gaps_next_topic")
        self.assertEqual(next_topic["resolution_loop"]["next_topic"]["requirement_id"], "req_gcp")

        second_batch = maybe_await(self.workflow.recordCheckpointResult(run_state, "RESOLVE_GAPS", {"facts_verified": ["fact_gcp"]}))
        self.assertEqual(second_batch["status"], "ok")
        mid_recovery = maybe_await(self.workflow.recoverRun(workspace=self.workspace, run_id=run_state["run_id"]))
        self.assertEqual(mid_recovery["resolution_loop_state"]["iteration_count"], 1)
        self.assertEqual(mid_recovery["resolution_loop_state"]["facts_since_last_match"], ["fact_gcp"])
        second_rerun = maybe_await(self.workflow.getNextCheckpoint(run_state))
        self.assertEqual(second_rerun["next_checkpoint"], "MATCH_BASE")
        self.assertEqual(second_rerun["resolution_loop"]["predicate"]["branch"], "rerun_match_for_new_facts")

        self.advance_ok(run_state, "MATCH_BASE", {"job_normalized": self.dto_ref("WorkflowStatusEvidence")})
        self.assertEqual(run_state["last_match_fact_watermark"], ["fact_aws"])
        self.assertEqual(run_state["resolution_loop_state"]["facts_since_last_match"], ["fact_gcp"])
        final_match = self.match_result(
            "continue",
            [
                self.requirement_result("req_aws", 8.0, classification="required", unresolved=False),
                self.requirement_result("req_gcp", 7.0, classification="required", unresolved=False),
            ],
        )
        self.assertEqual(maybe_await(self.workflow.recordCheckpointResult(run_state, "MATCH_BASE", {"match_result": final_match}))["status"], "ok")
        self.assertEqual(run_state["resolution_loop_state"]["iteration_count"], 2)
        self.assertEqual(run_state["resolution_loop_state"]["facts_since_last_match"], [])
        self.assertEqual(run_state["last_match_fact_watermark"], ["fact_aws", "fact_gcp"])
        self.assertEqual(run_state["facts_verified"], ["fact_aws", "fact_gcp"])

        self.advance_ok(
            run_state,
            "RESOLVE_GAPS",
            {"match_result": self.dto_ref("MatchResultEvidence", {"status": "ok", "match_result": final_match})},
        )
        continue_decision = maybe_await(self.workflow.getNextCheckpoint(run_state))
        self.assertEqual(continue_decision["resolution_loop"]["predicate"]["branch"], "a_continue")
        self.assertEqual(continue_decision["next_checkpoint"], "BUILD_SELECTION_PLAN")

        self.advance_tail_to_complete_gate(run_state)

    def test_resolution_loop_branch_a_continue_advances_to_build_selection_plan(self):
        run_state = self.enter_resolve_gaps_with_recorded_match(self.match_result("continue"))

        decision = maybe_await(self.workflow.getNextCheckpoint(run_state))

        self.assertEqual(decision["resolution_loop"]["predicate"]["branch"], "a_continue")
        self.assertEqual(decision["next_checkpoint"], "BUILD_SELECTION_PLAN")
        advanced = maybe_await(
            self.workflow.advanceCheckpoint(
                run_state,
                "BUILD_SELECTION_PLAN",
                {"selection_plan": self.artifact_ref("plans/selection-plan.json", {"status": "ok", "selection_plan": {}})},
            )
        )
        self.assertEqual(advanced["status"], "ok", advanced.get("blocking_reasons"))

    def test_resolution_loop_branch_b_resolve_gaps_selects_next_topic_by_impact_rank(self):
        run_state = self.enter_resolve_gaps_with_recorded_match(
            self.match_result(
                "resolve_gaps",
                [
                    self.requirement_result("req_low", 2.0, classification="preferred"),
                    self.requirement_result("req_high", 9.0, classification="required"),
                    self.requirement_result("req_high_tiebreak", 9.0, classification="required"),
                ],
                unresolved=["req_low", "req_high_tiebreak", "req_high"],
            )
        )

        decision = maybe_await(self.workflow.getNextCheckpoint(run_state))

        self.assertEqual(decision["resolution_loop"]["predicate"]["branch"], "b_resolve_gaps_next_topic")
        self.assertEqual(decision["next_checkpoint"], "RESOLVE_GAPS")
        self.assertEqual(decision["resolution_loop"]["next_topic"]["requirement_id"], "req_high")
        blocked = maybe_await(
            self.workflow.advanceCheckpoint(
                run_state,
                "BUILD_SELECTION_PLAN",
                {"selection_plan": self.artifact_ref("plans/selection-plan-blocked.json", {"status": "ok"})},
            )
        )
        self.assertEqual(blocked["status"], "blocked")
        self.assertIn("expected RESOLVE_GAPS after RESOLVE_GAPS", blocked["blocking_reasons"])

    def test_resolution_loop_branch_c_resolve_gaps_all_exhausted_advances_with_unresolved_recorded(self):
        run_state = self.enter_resolve_gaps_with_recorded_match(
            self.match_result(
                "resolve_gaps",
                [
                    self.requirement_result("req_aws", 8.0, classification="required"),
                    self.requirement_result("pref_k8s", 3.0, classification="preferred"),
                ],
                unresolved=["req_aws"],
                preferred=["pref_k8s"],
            )
        )
        recorded = maybe_await(
            self.workflow.recordCheckpointResult(
                run_state,
                "RESOLVE_GAPS",
                {
                    "exhausted_requirements": ["req_aws", "pref_k8s"],
                    "question_answers": [
                        {
                            "question_id": "q_aws",
                            "requirement_id": "req_aws",
                            "interaction_ref": "career-store/interactions/int_aws",
                            "question_text": "Should not be stored in loop state",
                        }
                    ],
                },
            )
        )
        self.assertEqual(recorded["status"], "ok")

        decision = maybe_await(self.workflow.getNextCheckpoint(run_state))

        self.assertEqual(decision["resolution_loop"]["predicate"]["branch"], "c_resolve_gaps_all_exhausted")
        self.assertEqual(decision["next_checkpoint"], "BUILD_SELECTION_PLAN")
        self.assertIsNone(decision["resolution_loop"]["next_topic"])
        self.assertEqual(
            {item["requirement_id"]: item["status"] for item in decision["resolution_loop"]["state"]["open_requirements"]},
            {"req_aws": "exhausted", "pref_k8s": "exhausted"},
        )
        self.assertNotIn("question_text", json.dumps(decision["resolution_loop"]["state"], sort_keys=True))
        advanced = maybe_await(
            self.workflow.advanceCheckpoint(
                run_state,
                "BUILD_SELECTION_PLAN",
                {"selection_plan": self.artifact_ref("plans/selection-plan-exhausted.json", {"status": "ok"})},
            )
        )
        self.assertEqual(advanced["status"], "ok", advanced.get("blocking_reasons"))
        manifest_state = {
            **run_state,
            "base_resume_id": "base_1",
            "base_resume_hash": "hash_base",
            "job_id": "job_1",
            "renderer_template_version": "ats-clean@1",
        }
        built = maybe_await(self.workflow.buildRunManifest(manifest_state))
        reconstructed = maybe_await(self.workflow.reconstructRunManifest(run_state["run_id"], workspace=self.workspace))
        self.assertEqual(
            run_state["unresolved_requirements"],
            [
                {"requirement_id": "req_aws", "resolution_state": "exhausted", "reason": "exhausted"},
                {"requirement_id": "pref_k8s", "resolution_state": "exhausted", "reason": "exhausted"},
            ],
        )
        self.assertEqual(reconstructed["unresolved_requirements"], built["unresolved_requirements"])
        self.assertEqual(reconstructed["unresolved_requirements"], run_state["unresolved_requirements"])

    def test_resolution_loop_branch_c_records_user_declined_reason_in_manifest(self):
        run_state = self.enter_resolve_gaps_with_recorded_match(
            self.match_result(
                "resolve_gaps",
                [
                    self.requirement_result("req_aws", 8.0, classification="required"),
                    self.requirement_result("pref_k8s", 3.0, classification="preferred"),
                ],
                unresolved=["req_aws"],
                preferred=["pref_k8s"],
            )
        )
        run_state.update(
            {
                "base_resume_id": "base_1",
                "base_resume_hash": "hash_base",
                "job_id": "job_1",
                "renderer_template_version": "ats-clean@1",
                "initial_score": 6.4,
                "final_score": 8.2,
            }
        )
        recorded = maybe_await(
            self.workflow.recordCheckpointResult(
                run_state,
                "RESOLVE_GAPS",
                {
                    "user_declined_requirements": ["req_aws"],
                    "exhausted_requirements": ["pref_k8s"],
                },
            )
        )
        self.assertEqual(recorded["status"], "ok")
        decision = maybe_await(self.workflow.getNextCheckpoint(run_state))
        self.assertEqual(decision["resolution_loop"]["predicate"]["branch"], "c_resolve_gaps_all_exhausted")

        advanced = maybe_await(
            self.workflow.advanceCheckpoint(
                run_state,
                "BUILD_SELECTION_PLAN",
                {"selection_plan": self.artifact_ref("plans/selection-plan-declined.json", {"status": "ok"})},
            )
        )
        self.assertEqual(advanced["status"], "ok", advanced.get("blocking_reasons"))
        built = maybe_await(self.workflow.buildRunManifest(run_state))
        reconstructed = maybe_await(self.workflow.reconstructRunManifest(run_state["run_id"], workspace=self.workspace))

        self.assertEqual(
            built["unresolved_requirements"],
            [
                {"requirement_id": "req_aws", "resolution_state": "user_declined", "reason": "user_declined"},
                {"requirement_id": "pref_k8s", "resolution_state": "exhausted", "reason": "exhausted"},
            ],
        )
        self.assertEqual(reconstructed, built)

    def test_resolution_loop_branch_d_blocks_unresolved_hard_requirement_when_required(self):
        run_state = self.enter_resolve_gaps_with_recorded_match(
            self.match_result(
                "blocked",
                [self.requirement_result("req_node", 10.0, classification="required", blocking=True)],
                unresolved=["req_node"],
                explanations=["Required unresolved requirements block continuation."],
            )
        )

        decision = maybe_await(self.workflow.getNextCheckpoint(run_state))

        self.assertEqual(decision["status"], "blocked")
        self.assertEqual(decision["resolution_loop"]["predicate"]["branch"], "d_blocked_hard_requirement")
        self.assertEqual(decision["next_checkpoint"], "RESOLVE_GAPS")
        self.assertIn("unresolved_hard_requirement:req_node", decision["blocking_reasons"])
        blocked = maybe_await(
            self.workflow.advanceCheckpoint(
                run_state,
                "BUILD_SELECTION_PLAN",
                {"selection_plan": self.artifact_ref("plans/selection-plan-hard-blocked.json", {"status": "ok"})},
            )
        )
        self.assertEqual(blocked["status"], "blocked")

    def test_resolution_loop_state_persists_to_recovery_losslessly(self):
        run_state = self.enter_resolve_gaps_with_recorded_match(
            self.match_result(
                "resolve_gaps",
                [self.requirement_result("req_aws", 8.0, classification="required")],
                unresolved=["req_aws"],
            )
        )
        maybe_await(
            self.workflow.recordCheckpointResult(
                run_state,
                "RESOLVE_GAPS",
                {
                    "facts_verified": ["fact_aws"],
                    "question_answers": [
                        {
                            "question_id": "q_aws",
                            "requirement_id": "req_aws",
                            "interaction_ref": "career-store/interactions/int_aws",
                            "question_text": "Do you have AWS experience?",
                            "answer_text": "Yes.",
                        }
                    ],
                },
            )
        )

        recovery = maybe_await(self.workflow.recoverRun(workspace=self.workspace, run_id=run_state["run_id"]))

        self.assertEqual(recovery["resolution_loop_state"]["facts_since_last_match"], ["fact_aws"])
        self.assertEqual(recovery["resolution_loop_state"]["iteration_count"], 0)
        self.assertEqual(
            recovery["resolution_loop_state"]["asked_questions"],
            [{"question_id": "q_aws", "requirement_id": "req_aws", "interaction_ref": "career-store/interactions/int_aws"}],
        )
        self.assertNotIn("question_text", json.dumps(recovery["resolution_loop_state"], sort_keys=True))
        self.assertNotIn("answer_text", json.dumps(recovery["resolution_loop_state"], sort_keys=True))

    def test_match_fact_watermark_persists_to_recovery_and_legacy_runs_default_to_zero(self):
        run_state = self.create_run()
        run_state["current_checkpoint"] = "MATCH_BASE"
        run_state["facts_verified"] = ["fact_react", "fact_aws"]
        result = maybe_await(self.workflow.recordCheckpointResult(run_state, "MATCH_BASE", {"match_result": {"score": 7.4}}))
        self.assertEqual(result["status"], "ok")

        persisted = json.loads((self.workspace / ".workflow" / "runs" / f"{run_state['run_id']}.json").read_text(encoding="utf-8"))
        self.assertEqual(persisted["last_match_fact_watermark"], ["fact_react", "fact_aws"])
        recovery = maybe_await(self.workflow.recoverRun(workspace=self.workspace, run_id=run_state["run_id"]))
        self.assertEqual(recovery["last_match_fact_watermark"], ["fact_react", "fact_aws"])

        legacy_run = self.create_run()
        legacy_run.update({"current_checkpoint": "RESOLVE_GAPS", "facts_verified": ["fact_legacy"]})
        legacy_path = self.workspace / ".workflow" / "runs" / f"{legacy_run['run_id']}.json"
        legacy_persisted = dict(legacy_run)
        legacy_persisted.pop("last_match_fact_watermark", None)
        legacy_path.write_text(json.dumps(legacy_persisted, sort_keys=True, indent=2), encoding="utf-8")

        legacy_recovery = maybe_await(self.workflow.recoverRun(workspace=self.workspace, run_id=legacy_run["run_id"]))
        self.assertEqual(legacy_recovery["last_match_fact_watermark"], [])
        legacy_decision = maybe_await(self.workflow.getNextCheckpoint(legacy_persisted))
        self.assertEqual(legacy_decision["next_checkpoint"], "MATCH_BASE")

    def test_completion_gate_requires_real_artifact_refs_for_each_persisted_gate(self):
        gate_state_keys = {
            "final_match": "match_report_ref",
            "grounding": "grounding_audit_ref",
            "ats": "ats_report_ref",
            "render_validation": "render_validation_report_ref",
            "audit_ref": "audit_ref",
        }
        for gate, state_key in gate_state_keys.items():
            with self.subTest(gate=gate):
                run_state = self.create_run()
                run_state.update(self.passing_completion_gate_state())
                run_state.pop(state_key)

                blocked = maybe_await(self.workflow.assertCanComplete(run_state))

                self.assertFalse(blocked["can_complete"])
                self.assertIn(gate, blocked["failed_gates"])
                self.assertEqual(blocked["failed_gate_reasons"][gate], "missing_ref")

    def test_completion_gate_blocks_hash_mismatched_artifact_refs_for_each_persisted_gate(self):
        gate_state_keys = {
            "final_match": "match_report_ref",
            "grounding": "grounding_audit_ref",
            "ats": "ats_report_ref",
            "render_validation": "render_validation_report_ref",
            "audit_ref": "audit_ref",
        }
        for gate, state_key in gate_state_keys.items():
            with self.subTest(gate=gate):
                run_state = self.create_run()
                run_state.update(self.passing_completion_gate_state())
                artifact_path = self.workspace / run_state[state_key]["path"]
                artifact_path.write_text(json.dumps({"status": "tampered"}, sort_keys=True), encoding="utf-8")

                blocked = maybe_await(self.workflow.assertCanComplete(run_state))

                self.assertFalse(blocked["can_complete"])
                self.assertIn(gate, blocked["failed_gates"])
                self.assertEqual(blocked["failed_gate_reasons"][gate], "artifact_hash_mismatch")

    def test_complete_checkpoint_succeeds_only_with_all_real_gate_artifacts_present(self):
        run_state = self.enter_resolve_gaps_with_recorded_match(self.match_result("continue"))
        self.advance_tail_to_complete_gate(run_state)

        completed = maybe_await(
            self.workflow.advanceCheckpoint(
                run_state,
                "COMPLETE",
                {"audit_ref": self.artifact_ref("reports/audit-trail.json", {"status": "passed", "events": []})},
            )
        )

        self.assertEqual(completed["status"], "ok", completed.get("blocking_reasons"))
        self.assertEqual(completed["current_checkpoint"], "COMPLETE")

    def test_completion_gate_blocks_hallucination_flagged_non_rejected_operation_from_persisted_state(self):
        run_state = self.create_run()
        maybe_await(
            self.workflow.recordCheckpointResult(
                run_state,
                "VALIDATE_CHANGES",
                {
                    "operation_statuses": [
                        {
                            "operation_id": "op_hallucinated_scale",
                            "status": "proposed",
                            "validation": self.hallucination_rejection_validation(),
                        }
                    ]
                },
            )
        )
        run_state.pop("operation_statuses", None)
        run_state.update(self.passing_completion_gate_state())

        blocked = maybe_await(self.workflow.assertCanComplete(run_state))

        self.assertFalse(blocked["can_complete"])
        self.assertIn("hallucination_rejection", blocked["required_gates"])
        self.assertIn("hallucination_rejection", blocked["failed_gates"])

    def test_completion_gate_allows_hallucination_flagged_persisted_rejected_operation(self):
        run_state = self.create_run()
        maybe_await(
            self.workflow.recordCheckpointResult(
                run_state,
                "VALIDATE_CHANGES",
                {
                    "rejected": [
                        {
                            "operation_id": "op_hallucinated_scale",
                            "status": "rejected",
                            "validation": self.hallucination_rejection_validation(),
                        }
                    ]
                },
            )
        )
        run_state.pop("operation_statuses", None)
        run_state.update(self.passing_completion_gate_state())

        allowed = maybe_await(self.workflow.assertCanComplete(run_state))

        self.assertTrue(allowed["can_complete"], allowed)
        self.assertIn("hallucination_rejection", allowed["required_gates"])

    def test_completion_gate_hallucination_rejection_passes_vacuously_without_flagged_operations(self):
        run_state = self.create_run()
        maybe_await(
            self.workflow.recordCheckpointResult(
                run_state,
                "VALIDATE_CHANGES",
                {
                    "operation_statuses": [
                        {
                            "operation_id": "op_grounded_react",
                            "status": "validated",
                            "validation": {
                                "status": "ok",
                                "operation_id": "op_grounded_react",
                                "validation_state": "validated",
                                "errors": [],
                                "grounding": {"supported": True},
                            },
                        }
                    ]
                },
            )
        )
        run_state.pop("operation_statuses", None)
        run_state.update(self.passing_completion_gate_state())

        allowed = maybe_await(self.workflow.assertCanComplete(run_state))

        self.assertTrue(allowed["can_complete"], allowed)
        self.assertIn("hallucination_rejection", allowed["required_gates"])

    def test_run_manifest_records_traceability_fields(self):
        run_state = self.create_run()
        run_state.update(
            {
                "base_resume_id": "base_1",
                "base_resume_hash": "hash_base",
                "job_id": "job_1",
                "career_db_schema_version": "1",
                "renderer_template_version": "ats-clean@1",
                "agent_model_config": {"model": "fixed-test"},
                "initial_score": 6.4,
                "final_score": 8.2,
                "facts_added": ["fact_aws"],
                "facts_verified": ["fact_aws"],
                "operations_applied": ["op_1"],
                "operations_rejected": ["op_bad"],
                "question_answer_log_refs": ["qa_aws"],
                "unresolved_requirements": [
                    {
                        "requirement_id": "req_k8s",
                        "resolution_state": "unknown",
                        "reason": "Awaiting user confirmation.",
                    }
                ],
                "validation_status": "passed",
                "output_artifact_paths": ["output/resume.docx"],
            }
        )
        manifest = maybe_await(self.workflow.buildRunManifest(run_state))
        self.assertTrue(MANIFEST_FIELDS <= set(manifest))
        self.assertEqual(manifest["facts_verified"], ["fact_aws"])
        self.assertEqual(manifest["operations_rejected"], ["op_bad"])
        self.assertEqual(manifest["question_answer_log_refs"], ["qa_aws"])
        self.assertEqual(
            manifest["unresolved_requirements"],
            [
                {
                    "requirement_id": "req_k8s",
                    "resolution_state": "unknown",
                    "reason": "Awaiting user confirmation.",
                }
            ],
        )

    def test_run_manifest_emits_explicit_empty_audit_field_defaults(self):
        manifest = maybe_await(self.workflow.buildRunManifest(self.valid_manifest_run_state()))
        self.assertEqual(manifest["question_answer_log_refs"], [])
        self.assertEqual(manifest["unresolved_requirements"], [])

    def test_run_manifest_schema_rejects_missing_audit_fields(self):
        manifest = maybe_await(self.workflow.buildRunManifest(self.valid_manifest_run_state()))
        for field_name in ["question_answer_log_refs", "unresolved_requirements"]:
            with self.subTest(field_name=field_name):
                invalid_manifest = dict(manifest)
                invalid_manifest.pop(field_name)
                with self.assertRaises(self.workflow.RunManifestValidationError) as raised:
                    self.workflow._validate_run_manifest(invalid_manifest)
                self.assertTrue(
                    any(
                        error.get("code") == "missing_field" and error.get("field_path") == field_name
                        for error in raised.exception.errors
                    ),
                    raised.exception.errors,
                )

    def test_run_manifest_versions_have_no_placeholders_and_match_real_sources(self):
        import career_store
        import resume_core
        from workflow.versions import CAREER_DB_VERSION_UNAVAILABLE

        run_state = self.valid_manifest_run_state()
        manifest = maybe_await(self.workflow.buildRunManifest(run_state))
        installed_version = importlib_metadata.version("resume-kit")
        self.assertFalse(contains_value(manifest, "0.0.0"))
        self.assertEqual(
            manifest["package_versions"],
            {
                "workflow": installed_version,
                "resume-core": installed_version,
                "career-store": installed_version,
            },
        )
        self.assertEqual(manifest["canonical_resume_schema_version"], resume_core.CANONICAL_RESUME_SCHEMA_VERSION)
        self.assertEqual(manifest["job_schema_version"], resume_core.JOB_MODEL_SCHEMA_VERSION)
        self.assertEqual(manifest["career_db_schema_version"], career_store.CAREER_STORE_SCHEMA_VERSION)
        self.assertEqual(manifest["change_operation_schema_version"], resume_core.RESUME_CHANGE_OPERATION_SCHEMA_VERSION)
        self.assertEqual(
            {
                "matching_algorithm_version": manifest["matching_algorithm_version"],
                "matching_config_version": manifest["matching_config_version"],
            },
            resume_core.matchingVersions(),
        )
        self.assertEqual(manifest["careerDbVersion"], CAREER_DB_VERSION_UNAVAILABLE)

    def test_run_manifest_validation_rejects_each_empty_identity_field(self):
        for field_name in ["base_resume_id", "base_resume_hash", "job_id", "renderer_template_version"]:
            with self.subTest(field_name=field_name):
                run_state = self.valid_manifest_run_state()
                run_state[field_name] = ""
                with self.assertRaises(self.workflow.RunManifestValidationError) as raised:
                    maybe_await(self.workflow.buildRunManifest(run_state))
                self.assertTrue(
                    any(
                        error.get("code") == "min_length" and error.get("field_path") == field_name
                        for error in raised.exception.errors
                    ),
                    raised.exception.errors,
                )

    def test_run_manifest_validation_rejects_placeholder_version_values(self):
        direct_run_state = self.valid_manifest_run_state()
        direct_run_state["renderer_template_version"] = "0.0.0"
        with self.assertRaises(self.workflow.RunManifestValidationError) as direct_error:
            maybe_await(self.workflow.buildRunManifest(direct_run_state))
        self.assertTrue(
            any(error.get("code") == "forbidden_value" and error.get("field_path") == "renderer_template_version" for error in direct_error.exception.errors),
            direct_error.exception.errors,
        )

        original_collect_versions = self.workflow.collectVersions
        cases = {
            "canonical_resume_schema_version": lambda versions: versions["schema_versions"].update({"canonical_resume": "0.0.0"}),
            "matching_algorithm_version": lambda versions: versions.update({"matching_algorithm_version": "0.0.0"}),
            "package_versions/workflow": lambda versions: versions["package_versions"].update({"workflow": "0.0.0"}),
        }
        for field_path, mutate_versions in cases.items():
            with self.subTest(field_path=field_path):
                def placeholder_versions(**kwargs):
                    versions = original_collect_versions(**kwargs)
                    versions["schema_versions"] = dict(versions["schema_versions"])
                    versions["package_versions"] = dict(versions["package_versions"])
                    mutate_versions(versions)
                    return versions

                with mock.patch.object(self.workflow, "collectVersions", side_effect=placeholder_versions):
                    with self.assertRaises(self.workflow.RunManifestValidationError) as raised:
                        maybe_await(self.workflow.buildRunManifest(self.valid_manifest_run_state()))
                self.assertTrue(
                    any(
                        error.get("code") == "forbidden_value" and error.get("field_path") == field_path
                        for error in raised.exception.errors
                    ),
                    raised.exception.errors,
                )

    def test_run_manifest_career_db_version_equals_store_state(self):
        import career_store

        career_db = self.workspace / "data" / "career.db"
        store = career_store.openCareerStore(str(career_db), clock=lambda: "2026-01-01T00:00:00Z")
        run_state = self.valid_manifest_run_state()
        manifest = maybe_await(self.workflow.buildRunManifest(run_state))
        self.assertEqual(manifest["careerDbVersion"], asdict(store.getMigrationState()))

    def test_recovered_resolve_gaps_excludes_previously_asked_question_ref_from_next_topic(self):
        run_state = self.enter_resolve_gaps_with_recorded_match(
            self.match_result(
                "resolve_gaps",
                [
                    self.requirement_result("req_aws", 8.0, classification="required"),
                    self.requirement_result("req_gcp", 7.0, classification="required"),
                ],
                unresolved=["req_aws", "req_gcp"],
            )
        )
        recorded = maybe_await(
            self.workflow.recordCheckpointResult(
                run_state,
                "RESOLVE_GAPS",
                {
                    "question_answers": [
                        {
                            "question_id": "q_aws",
                            "requirement_id": "req_aws",
                            "interaction_ref": "career-store/interactions/int_aws",
                        }
                    ]
                },
            )
        )
        self.assertEqual(recorded["status"], "ok")

        recovery = maybe_await(self.workflow.recoverRun(workspace=self.workspace, run_id=run_state["run_id"]))
        resumed = {"workspace": str(self.workspace), "run_id": run_state["run_id"], "current_checkpoint": "RESOLVE_GAPS"}
        decision = maybe_await(self.workflow.getNextCheckpoint(resumed))

        self.assertIn("q_aws", recovery["already_asked_questions"])
        self.assertEqual(decision["resolution_loop"]["next_topic"]["requirement_id"], "req_gcp")
        self.assertNotEqual(decision["resolution_loop"]["next_topic"]["requirement_id"], "req_aws")

    def test_recovered_fact_rewrite_is_typed_duplicate_and_registry_unchanged(self):
        run_state = self.create_run()
        run_state["current_checkpoint"] = "RESOLVE_GAPS"
        first = maybe_await(self.workflow.recordCheckpointResult(run_state, "RESOLVE_GAPS", {"facts_verified": ["fact_aws"]}))
        self.assertEqual(first["status"], "ok")
        maybe_await(self.workflow.recoverRun(workspace=self.workspace, run_id=run_state["run_id"]))
        before = self.persisted_run_state(run_state)["already_written_facts"]

        duplicate = maybe_await(self.workflow.recordCheckpointResult(run_state, "RESOLVE_GAPS", {"facts_verified": ["fact_aws"]}))

        self.assertEqual(duplicate["status"], "ok")
        self.assertEqual(duplicate["fact_results"], [{"status": "duplicate", "reason": "already_written_fact", "fact_id": "fact_aws"}])
        self.assertEqual(run_state["facts_verified"], ["fact_aws"])
        self.assertEqual(self.persisted_run_state(run_state)["already_written_facts"], before)

    def test_recovered_operation_reapplication_is_typed_duplicate_and_not_logged_again(self):
        run_state = self.create_run()
        run_state["current_checkpoint"] = "APPLY_CHANGES"
        first = maybe_await(self.workflow.recordCheckpointResult(run_state, "VALIDATE_CHANGES", {"operations_applied": ["op_1"]}))
        self.assertEqual(first["status"], "ok")
        maybe_await(self.workflow.recoverRun(workspace=self.workspace, run_id=run_state["run_id"]))
        operation_log = self.workspace / ".workflow" / "runs" / run_state["run_id"] / "operations.jsonl"
        before_lines = operation_log.read_text(encoding="utf-8").splitlines()

        duplicate = maybe_await(self.workflow.recordCheckpointResult(run_state, "APPLY_CHANGES", {"operations_applied": ["op_1"]}))

        self.assertEqual(duplicate["status"], "ok")
        self.assertEqual(duplicate["operation_results"], [{"status": "duplicate", "reason": "already_applied_operation", "operation_id": "op_1"}])
        self.assertEqual(duplicate["operation_log_refs"], [])
        self.assertEqual(run_state["operations_applied"], ["op_1"])
        self.assertEqual(operation_log.read_text(encoding="utf-8").splitlines(), before_lines)

    def test_recovered_render_overflow_iteration_count_preserves_remaining_budget(self):
        self.config = {
            "schemaVersion": "1.0",
            "matching": {"requireHardRequirementsResolved": True},
            "workflow": {"maxRenderOverflowIterations": 1},
        }
        run_state = self.enter_resolve_gaps_with_recorded_match(self.match_result("continue"))
        self.advance_tail_to_render_checkpoint(run_state)
        first_layout = self.overflow_layout_payload()
        self.advance_ok(
            run_state,
            "RENDER",
            {
                "render_output": self.artifact_ref("render/recovered-overflow-first.md", {"status": "rendered"}),
                "measure_layout": self.artifact_ref("render/recovered-overflow-first-layout.json", first_layout),
            },
        )
        first_recorded = maybe_await(self.workflow.recordCheckpointResult(run_state, "RENDER", first_layout))
        self.assertEqual(first_recorded["status"], "ok")

        recovery = maybe_await(self.workflow.recoverRun(workspace=self.workspace, run_id=run_state["run_id"]))
        self.assertEqual(recovery["render_overflow_state"]["iteration_count"], 1)
        second_layout = self.overflow_layout_payload()
        second_recorded = maybe_await(self.workflow.recordCheckpointResult(run_state, "RENDER", second_layout))

        self.assertEqual(second_recorded["status"], "blocked")
        self.assertEqual(second_recorded["render_overflow"]["iteration"], 2)
        self.assertIn("render_overflow_bound_exhausted", second_recorded["blocking_reasons"])

    def test_recovery_record_cycles_merge_registries_monotonically(self):
        run_state = self.create_run()
        run_state["current_checkpoint"] = "RESOLVE_GAPS"
        first = maybe_await(
            self.workflow.recordCheckpointResult(
                run_state,
                "RESOLVE_GAPS",
                {
                    "facts_verified": ["fact_aws"],
                    "question_answers": [{"question_id": "q_aws", "requirement_id": "req_aws", "interaction_ref": "int_aws"}],
                    "operations_applied": ["op_1"],
                },
            )
        )
        self.assertEqual(first["status"], "ok")
        maybe_await(self.workflow.recoverRun(workspace=self.workspace, run_id=run_state["run_id"]))
        stale_resumed = {
            "workspace": str(self.workspace),
            "run_id": run_state["run_id"],
            "current_checkpoint": "RESOLVE_GAPS",
            "already_applied_operations": [],
            "already_asked_questions": [],
            "already_written_facts": [],
        }

        second = maybe_await(
            self.workflow.recordCheckpointResult(
                stale_resumed,
                "RESOLVE_GAPS",
                {
                    "facts_verified": ["fact_gcp"],
                    "question_answers": [{"question_id": "q_gcp", "requirement_id": "req_gcp", "interaction_ref": "int_gcp"}],
                    "operations_applied": ["op_2"],
                },
            )
        )
        persisted = self.persisted_run_state(run_state)

        self.assertEqual(second["status"], "ok")
        self.assertEqual(persisted["already_written_facts"], ["fact_aws", "fact_gcp"])
        self.assertEqual(persisted["already_asked_questions"], ["q_aws", "q_gcp"])
        self.assertEqual(persisted["already_applied_operations"], ["op_1", "op_2"])

    def passing_completion_gate_state(self):
        return {
            "current_checkpoint": "RENDER_VALIDATION",
            "match_report_ref": self.artifact_ref("reports/final-match-gate.json", {"status": "passed"}),
            "grounding_audit_ref": self.artifact_ref("reports/grounding-gate.json", {"status": "passed"}),
            "ats_report_ref": self.artifact_ref("reports/ats-gate.json", {"status": "passed"}),
            "render_validation_report_ref": self.artifact_ref("reports/render-validation-gate.json", {"status": "pass"}),
            "audit_ref": self.artifact_ref("reports/audit-gate.json", {"status": "passed"}),
        }

    def hallucination_rejection_validation(self):
        return {
            "status": "rejected",
            "operation_id": "op_hallucinated_scale",
            "validation_state": "rejected",
            "errors": [
                {
                    "code": "unsupported_guarded_claim",
                    "message": "Guarded claims require exact supplied verified fact DTO support.",
                    "field_path": "after",
                }
            ],
            "grounding": {
                "supported": False,
                "supporting_fact_ids": [],
                "supporting_requirement_ids": ["req_scale"],
                "guarded_claims": ["scale:20m users"],
            },
        }


# Bridge the new five-point recovery matrix into the current static PR/future
# gate module list until tools/run_tests.py is approved to include it directly.
from tests.contract.test_workflow_recovery_matrix import WorkflowRecoveryMatrixContractTests  # noqa: E402,F401


if __name__ == "__main__":
    unittest.main()
