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

    def valid_manifest_run_state(self):
        run_state = self.create_run()
        run_state.update(
            {
                "base_resume_id": "base_1",
                "base_resume_hash": "hash_base",
                "job_id": "job_1",
                "renderer_template_version": "ats-clean@1",
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
        run_state["current_checkpoint"] = "APPLY_CHANGES"
        blocked = maybe_await(
            self.workflow.advanceCheckpoint(
                run_state,
                "FINAL_MATCH",
                {"operations_applied": {"kind": "run_state", "key": "operations_applied"}},
            )
        )
        self.assertEqual(blocked["status"], "blocked")
        self.assertIn("operations_applied", blocked["blocking_reasons"])

        record = maybe_await(self.workflow.recordCheckpointResult(run_state, "APPLY_CHANGES", {"operations_applied": ["op_1"]}))
        self.assertEqual(record["status"], "ok")
        advanced = maybe_await(
            self.workflow.advanceCheckpoint(
                run_state,
                "FINAL_MATCH",
                {"operations_applied": {"kind": "run_state", "key": "operations_applied"}},
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
        self.assertIn("gaps_resolved", decision["blocking_reasons"])

        advance("BUILD_SELECTION_PLAN", {"gaps_resolved": {"kind": "run_state", "key": "facts_verified"}})
        advance("PROPOSE_TAILORING_CHANGES", {"selection_plan": self.dto_ref("SelectionPlanEvidence", {"status": "ok", "selection_plan": {}})})
        advance("VALIDATE_CHANGES", {"proposed_operations": self.dto_ref("ProposedOperationsEvidence", {"status": "ok", "operations": []})})
        advance("APPLY_CHANGES", {"change_validation": self.dto_ref("ChangeValidationEvidence", {"status": "ok", "validation": {}})})
        apply_record = maybe_await(self.workflow.recordCheckpointResult(run_state, "APPLY_CHANGES", {"operations_applied": ["op_1"]}))
        self.assertEqual(apply_record["status"], "ok")
        advance("FINAL_MATCH", {"operations_applied": {"kind": "run_state", "key": "operations_applied"}})
        advance("GROUNDING_AUDIT", {"final_match": self.dto_ref("FinalMatchEvidence", {"status": "passed", "final_match": {}})})
        advance("ATS_STRUCTURE_VALIDATION", {"grounding_audit": self.dto_ref("WorkflowStatusEvidence")})
        advance("RENDER", {"ats_structure_validation": self.dto_ref("WorkflowStatusEvidence")})
        advance("RENDER_VALIDATION", {"render_result": self.artifact_ref("render/resume.md", {"status": "rendered"})})

        complete_decision = maybe_await(self.workflow.getNextCheckpoint(run_state))
        self.assertEqual(complete_decision["next_checkpoint"], "COMPLETE")
        self.assertIn("render_validation", complete_decision["blocking_reasons"])
        self.assertIn("audit_manifest_ref", complete_decision["blocking_reasons"])

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

    def test_completion_gate_requires_final_validation_render_validation_and_audit(self):
        run_state = self.create_run()
        run_state.update(
            {
                "current_checkpoint": "RENDER",
                "final_match": {"status": "passed"},
                "grounding_audit": {"status": "passed"},
                "ats_structure_validation": {"status": "passed"},
                "render_validation": None,
                "audit_manifest_ref": None,
            }
        )
        blocked = maybe_await(self.workflow.assertCanComplete(run_state))
        self.assertFalse(blocked["can_complete"])
        self.assertIn("render_validation", serialized(blocked))
        self.assertIn("audit", serialized(blocked))

        run_state["render_validation"] = {"status": "passed"}
        run_state["audit_manifest_ref"] = "reports/run-manifest.json"
        allowed = maybe_await(self.workflow.assertCanComplete(run_state))
        self.assertTrue(allowed["can_complete"])

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

    def test_recovery_does_not_duplicate_questions_facts_or_applied_operations(self):
        run_state = self.create_run()
        run_state.update(
            {
                "run_id": "run_recover",
                "current_checkpoint": "APPLY_CHANGES",
                "already_applied_operations": ["op_1"],
                "already_asked_questions": ["req_aws"],
                "already_written_facts": ["fact_aws"],
                "recovery_markers": [{"after": "partially_applied_operation_sequence"}],
            }
        )
        maybe_await(self.workflow.recordCheckpointResult(run_state, "APPLY_CHANGES", {"operations_applied": ["op_1"]}))
        recovery = maybe_await(self.workflow.recoverRun(workspace=self.workspace, run_id="run_recover"))
        self.assertEqual(recovery["status"], "ok")
        self.assertEqual(recovery["already_applied_operations"].count("op_1"), 1)
        self.assertEqual(recovery["already_asked_questions"].count("req_aws"), 1)
        self.assertEqual(recovery["already_written_facts"].count("fact_aws"), 1)
        self.assertIn("FINAL_MATCH", recovery["required_reruns"])

    def passing_completion_gate_state(self):
        return {
            "current_checkpoint": "RENDER",
            "final_match": {"status": "passed"},
            "grounding_audit": {"status": "passed"},
            "ats_structure_validation": {"status": "passed"},
            "render_validation": {"status": "passed"},
            "audit_manifest_ref": "reports/run-manifest.json",
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


if __name__ == "__main__":
    unittest.main()
