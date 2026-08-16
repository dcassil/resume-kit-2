"""Five-point workflow recovery interruption matrix contract tests."""

from __future__ import annotations

import asyncio
import hashlib
import importlib
import inspect
import json
import tempfile
import unittest
from pathlib import Path


def maybe_await(value):
    if inspect.isawaitable(value):
        return asyncio.run(value)
    return value


class CareerStoreDouble:
    def __init__(self, state):
        self.state = dict(state)
        self.calls = 0
        self.getMigrationState = self.read_state

    def read_state(self):
        self.calls += 1
        return dict(self.state)


class WorkflowRecoveryMatrixContractTests(unittest.TestCase):
    def setUp(self):
        self.workflow = importlib.import_module("workflow")
        self.tempdir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tempdir.name)
        self.config = {"schemaVersion": "1.0", "matching": {"requireHardRequirementsResolved": True}}

    def tearDown(self):
        self.tempdir.cleanup()

    def test_recovery_matrix_job_ingest_interruption(self):
        run_state = self.drive_to_job_ingest()

        recovery = self.recover_and_assert_matrix_point(run_state, "INGEST_JOB", [])

        self.assertEqual(recovery["already_asked_questions"], [])
        self.assertEqual(recovery["already_written_facts"], [])
        self.assertEqual(recovery["already_applied_operations"], [])
        self.assertEqual(recovery["integrity"]["rejected_operations"]["reason"], "no_operations_recorded")

    def test_recovery_matrix_user_verification_interruption(self):
        run_state = self.drive_to_user_verification()

        recovery = self.recover_and_assert_matrix_point(run_state, "RESOLVE_GAPS", [])

        self.assert_question_resume_does_not_reask_first_topic(recovery, run_state)
        self.assert_fact_rewrite_is_typed_duplicate(run_state, "fact_aws")
        self.assertEqual(recovery["already_applied_operations"], [])

    def test_recovery_matrix_proposed_operations_interruption(self):
        run_state = self.drive_to_proposed_operations()

        recovery = self.recover_and_assert_matrix_point(run_state, "PROPOSE_TAILORING_CHANGES", [])

        self.assert_question_and_fact_registries_remain_monotone(recovery, run_state)
        self.assert_fact_rewrite_is_typed_duplicate(run_state, "fact_aws")
        self.assertEqual(recovery["already_applied_operations"], [])

    def test_recovery_matrix_partially_applied_operation_sequence_interruption(self):
        run_state = self.drive_to_partially_applied_operation_sequence()

        recovery = self.recover_and_assert_matrix_point(run_state, "APPLY_CHANGES", ["GROUNDING_AUDIT", "FINAL_MATCH"])

        self.assert_question_and_fact_registries_remain_monotone(recovery, run_state)
        self.assert_fact_rewrite_is_typed_duplicate(run_state, "fact_aws")
        self.assert_operation_reapplication_is_typed_duplicate(run_state, "op_1")
        self.assert_completion_blocked_until_required_reruns(run_state, ["GROUNDING_AUDIT", "FINAL_MATCH"])

    def test_recovery_matrix_render_overflow_interruption(self):
        run_state = self.drive_to_render_overflow()

        recovery = self.recover_and_assert_matrix_point(run_state, "RENDER", ["RENDER", "RENDER_VALIDATION"])

        self.assert_question_and_fact_registries_remain_monotone(recovery, run_state)
        self.assert_fact_rewrite_is_typed_duplicate(run_state, "fact_aws")
        self.assert_operation_reapplication_is_typed_duplicate(run_state, "op_1")
        self.assertEqual(recovery["render_overflow_state"]["status"], "pending")
        self.assert_completion_blocked_until_required_reruns(run_state, ["RENDER", "RENDER_VALIDATION"])

    def recover_and_assert_matrix_point(self, run_state, checkpoint, expected_reruns):
        persisted_before = self.persisted_run_state(run_state)
        self.assertEqual(persisted_before["current_checkpoint"], checkpoint)

        store = CareerStoreDouble(self.store_state())
        recovery = maybe_await(self.workflow.recoverRun(workspace=self.workspace, run_id=run_state["run_id"], career_store=store))

        self.assertEqual(store.calls, 1)
        self.assertEqual(recovery["status"], "ok")
        self.assertEqual(recovery["run_id"], run_state["run_id"])
        self.assertEqual(recovery["resume_from_checkpoint"], checkpoint)
        self.assertEqual(recovery["required_reruns"], expected_reruns)
        self.assertTrue(recovery["resumable"], recovery["integrity"])
        self.assert_integrity_verified_with_evidence(recovery)

        persisted_after = self.persisted_run_state(run_state)
        self.assertEqual(
            persisted_after["recovery_events"][-1],
            {
                "recovered_at_checkpoint": checkpoint,
                "required_reruns": expected_reruns,
                "recovery_sequence": 1,
            },
        )
        self.assertEqual(persisted_after["current_checkpoint"], checkpoint)
        return recovery

    def assert_integrity_verified_with_evidence(self, recovery):
        self.assertEqual(set(recovery["integrity"]), {"career_db", "base_resume", "rejected_operations"})
        for name, check in recovery["integrity"].items():
            with self.subTest(integrity=name):
                self.assertEqual(check["status"], "verified")
                self.assertIsInstance(check["evidence_ref"], dict)
                self.assertTrue(check["reason"])
        self.assertEqual(recovery["integrity"]["career_db"]["evidence_ref"]["state"]["schema_version"], self.store_state()["schema_version"])
        self.assertEqual(recovery["integrity"]["base_resume"]["evidence_ref"]["path"], "resume/base.json")
        self.assertEqual(recovery["integrity"]["base_resume"]["reason"], "base_resume_hash_matches_recorded_hash")
        self.assertEqual(recovery["integrity"]["rejected_operations"]["evidence_ref"]["kind"], "operations_log_scan")

    def assert_question_resume_does_not_reask_first_topic(self, recovery, run_state):
        self.assertIn("q_aws", recovery["already_asked_questions"])
        decision = maybe_await(
            self.workflow.getNextCheckpoint(
                {"workspace": str(self.workspace), "run_id": run_state["run_id"], "current_checkpoint": "RESOLVE_GAPS"}
            )
        )
        next_topic = decision["resolution_loop"]["next_topic"]
        if next_topic is not None:
            self.assertNotEqual(next_topic["requirement_id"], "req_aws")

    def assert_question_and_fact_registries_remain_monotone(self, recovery, run_state):
        self.assertIn("q_aws", recovery["already_asked_questions"])
        self.assertIn("fact_aws", recovery["already_written_facts"])
        persisted = self.persisted_run_state(run_state)
        self.assertEqual(persisted["already_asked_questions"].count("q_aws"), 1)
        self.assertEqual(persisted["already_written_facts"].count("fact_aws"), 1)

    def assert_fact_rewrite_is_typed_duplicate(self, run_state, fact_id):
        before = self.persisted_run_state(run_state)["already_written_facts"]
        duplicate = maybe_await(
            self.workflow.recordCheckpointResult(
                {"workspace": str(self.workspace), "run_id": run_state["run_id"], "current_checkpoint": "RESOLVE_GAPS"},
                "RESOLVE_GAPS",
                {"facts_verified": [fact_id]},
            )
        )

        self.assertEqual(duplicate["status"], "ok")
        self.assertEqual(duplicate["fact_results"], [{"status": "duplicate", "reason": "already_written_fact", "fact_id": fact_id}])
        self.assertEqual(self.persisted_run_state(run_state)["already_written_facts"], before)

    def assert_operation_reapplication_is_typed_duplicate(self, run_state, operation_id):
        operation_log = self.workspace / ".workflow" / "runs" / run_state["run_id"] / "operations.jsonl"
        before_lines = operation_log.read_text(encoding="utf-8").splitlines()

        duplicate = maybe_await(
            self.workflow.recordCheckpointResult(
                {"workspace": str(self.workspace), "run_id": run_state["run_id"], "current_checkpoint": "APPLY_CHANGES"},
                "APPLY_CHANGES",
                {"operations_applied": [operation_id]},
            )
        )

        self.assertEqual(duplicate["status"], "ok")
        self.assertEqual(
            duplicate["operation_results"],
            [{"status": "duplicate", "reason": "already_applied_operation", "operation_id": operation_id}],
        )
        self.assertEqual(duplicate["operation_log_refs"], [])
        self.assertEqual(operation_log.read_text(encoding="utf-8").splitlines(), before_lines)

    def assert_completion_blocked_until_required_reruns(self, run_state, required_reruns):
        completion_state = self.passing_completion_gate_state(run_state)
        blocked = maybe_await(self.workflow.assertCanComplete(completion_state))

        self.assertFalse(blocked["can_complete"])
        self.assertIn("recovery_reruns", blocked["failed_gates"])
        self.assertEqual(blocked["failed_gate_reasons"]["recovery_reruns"]["missing_or_stale_checkpoints"], required_reruns)

        for index, checkpoint in enumerate(required_reruns):
            maybe_await(self.workflow.recordCheckpointResult(completion_state, checkpoint, self.rerun_result(checkpoint)))
            decision = maybe_await(self.workflow.assertCanComplete(completion_state))
            missing = required_reruns[index + 1 :]
            if missing:
                self.assertFalse(decision["can_complete"])
                self.assertEqual(decision["failed_gate_reasons"]["recovery_reruns"]["missing_or_stale_checkpoints"], missing)
            else:
                self.assertTrue(decision["can_complete"], decision)

    def drive_to_job_ingest(self):
        run_state = self.create_verified_run()
        self.advance_ok(run_state, "INGEST_RESUME", {"config_validated": self.dto_ref("WorkflowStatusEvidence")})
        self.advance_ok(run_state, "VALIDATE_BASE", {"canonical_resume_exists": self.base_ref})
        self.advance_ok(run_state, "EXTRACT_PERSIST_CAREER_FACTS", {"base_validation": self.dto_ref("WorkflowStatusEvidence")})
        self.advance_ok(run_state, "INGEST_JOB", {"career_facts_persisted": self.artifact_ref("data/career.db", {"status": "persisted"})})
        return run_state

    def drive_to_user_verification(self):
        run_state = self.drive_to_job_ingest()
        self.advance_ok(run_state, "NORMALIZE_JOB", {"job_ingested": self.artifact_ref("job/current.json", {"job_id": "job_1"})})
        self.advance_ok(run_state, "MATCH_BASE", {"job_normalized": self.dto_ref("WorkflowStatusEvidence")})
        recorded = maybe_await(self.workflow.recordCheckpointResult(run_state, "MATCH_BASE", {"match_result": self.match_result("resolve_gaps")}))
        self.assertEqual(recorded["status"], "ok")
        self.advance_ok(
            run_state,
            "RESOLVE_GAPS",
            {"match_result": self.dto_ref("MatchResultEvidence", {"status": "ok", "match_result": self.match_result("resolve_gaps")})},
        )
        recorded = maybe_await(
            self.workflow.recordCheckpointResult(
                run_state,
                "RESOLVE_GAPS",
                {
                    "facts_verified": ["fact_aws"],
                    "question_answers": [{"question_id": "q_aws", "requirement_id": "req_aws", "interaction_ref": "career-store/int_aws"}],
                },
            )
        )
        self.assertEqual(recorded["status"], "ok")
        return run_state

    def drive_past_user_verification(self):
        run_state = self.drive_to_user_verification()
        self.advance_ok(run_state, "MATCH_BASE", {"job_normalized": self.dto_ref("WorkflowStatusEvidence")})
        recorded = maybe_await(self.workflow.recordCheckpointResult(run_state, "MATCH_BASE", {"match_result": self.match_result("continue")}))
        self.assertEqual(recorded["status"], "ok")
        self.advance_ok(
            run_state,
            "RESOLVE_GAPS",
            {"match_result": self.dto_ref("MatchResultEvidence", {"status": "ok", "match_result": self.match_result("continue")})},
        )
        return run_state

    def drive_to_proposed_operations(self):
        run_state = self.drive_past_user_verification()
        self.advance_ok(run_state, "BUILD_SELECTION_PLAN", {"selection_plan": self.artifact_ref("plans/selection-plan.json", {"status": "ok"})})
        recorded = maybe_await(self.workflow.recordCheckpointResult(run_state, "BUILD_SELECTION_PLAN", {"operations_proposed": ["op_1"]}))
        self.assertEqual(recorded["status"], "ok")
        self.advance_ok(run_state, "PROPOSE_TAILORING_CHANGES", {"proposed_operations": self.operation_state_ref("op_1")})
        return run_state

    def drive_to_partially_applied_operation_sequence(self):
        run_state = self.drive_to_proposed_operations()
        recorded = maybe_await(self.workflow.recordCheckpointResult(run_state, "PROPOSE_TAILORING_CHANGES", {"operations_validated": ["op_1"]}))
        self.assertEqual(recorded["status"], "ok")
        self.advance_ok(run_state, "VALIDATE_CHANGES", {"validated_operations": self.operation_state_ref("op_1")})
        recorded = maybe_await(self.workflow.recordCheckpointResult(run_state, "VALIDATE_CHANGES", {"operations_applied": ["op_1"]}))
        self.assertEqual(recorded["status"], "ok")
        self.advance_ok(run_state, "APPLY_CHANGES", {"applied_operations": self.operation_state_ref("op_1")})
        return run_state

    def drive_to_render_overflow(self):
        run_state = self.drive_to_partially_applied_operation_sequence()
        self.advance_ok(run_state, "FINAL_MATCH", {"match_report": self.artifact_ref("reports/final-match.json", {"status": "passed"})})
        self.advance_ok(run_state, "GROUNDING_AUDIT", {"grounding_audit": self.artifact_ref("reports/grounding-audit.json", {"status": "passed"})})
        self.advance_ok(run_state, "ATS_STRUCTURE_VALIDATION", {"ats_report": self.artifact_ref("reports/ats.json", {"status": "passed"})})
        self.advance_ok(
            run_state,
            "RENDER",
            {
                "render_output": self.artifact_ref("render/resume.md", {"status": "rendered"}),
                "measure_layout": self.artifact_ref("render/measure-layout.json", {"status": "overflow", "requiredReduction": 12}),
            },
        )
        recorded = maybe_await(
            self.workflow.recordCheckpointResult(
                run_state,
                "RENDER",
                {"status": "overflow", "requiredReduction": 12, "offending_sections": ["experience"]},
            )
        )
        self.assertEqual(recorded["status"], "ok")
        self.assertEqual(recorded["render_overflow"]["status"], "pending")
        return run_state

    def create_verified_run(self):
        import career_store

        run_state = maybe_await(self.workflow.createRun(workspace=self.workspace, config=self.config))
        self.base_ref = self.artifact_ref("resume/base.json", {"resume_id": "base_1", "summary": "Built React systems."})
        store_state = self.store_state(schema_version=career_store.CAREER_STORE_SCHEMA_VERSION)
        run_state.update(
            {
                "base_resume_id": "base_1",
                "base_resume_hash": self.base_ref["sha256"],
                "careerDbVersion": dict(store_state),
                "stage_state": {
                    **run_state.get("stage_state", {}),
                    "VALIDATE_BASE": {"canonical_resume_exists": dict(self.base_ref)},
                },
                "verified_evidence": {
                    **run_state.get("verified_evidence", {}),
                    "VALIDATE_BASE": {"canonical_resume_exists": dict(self.base_ref)},
                },
            }
        )
        self.persist_run_state(run_state)
        return run_state

    def passing_completion_gate_state(self, run_state):
        return {
            "workspace": str(self.workspace),
            "run_id": run_state["run_id"],
            "current_checkpoint": "RENDER_VALIDATION",
            "match_report_ref": self.artifact_ref("reports/final-match-gate.json", {"status": "passed"}),
            "grounding_audit_ref": self.artifact_ref("reports/grounding-gate.json", {"status": "passed"}),
            "ats_report_ref": self.artifact_ref("reports/ats-gate.json", {"status": "passed"}),
            "render_validation_report_ref": self.artifact_ref("reports/render-validation-gate.json", {"status": "pass"}),
            "audit_ref": self.artifact_ref("reports/audit-gate.json", {"status": "passed"}),
        }

    def rerun_result(self, checkpoint):
        if checkpoint == "RENDER":
            return {"status": "fits", "requiredReduction": 0}
        return {"status": "passed"}

    def match_result(self, decision):
        unresolved = ["req_aws", "req_gcp"] if decision == "resolve_gaps" else []
        return {
            "schema_version": "match-result.v1",
            "score": 7.0,
            "threshold": 7.5,
            "hardRequirementsResolved": True,
            "decision": decision,
            "can_continue": decision == "continue",
            "requirement_results": [
                {"requirement_id": "req_aws", "classification": "required", "impact_rank": 8.0, "resolution_state": "unknown", "unresolved": "req_aws" in unresolved},
                {"requirement_id": "req_gcp", "classification": "required", "impact_rank": 7.0, "resolution_state": "unknown", "unresolved": "req_gcp" in unresolved},
            ],
            "unresolved_requirement_ids": unresolved,
            "preferred_unresolved_requirement_ids": [],
            "explanations": [],
        }

    def store_state(self, *, schema_version=None):
        import career_store

        return {
            "schema_version": schema_version or career_store.CAREER_STORE_SCHEMA_VERSION,
            "database_path": str(self.workspace / "data" / "career.db"),
            "applied_migrations": ["001_initial"],
            "pending_migrations": [],
            "status": "ok",
            "metadata": {"source": "test-double"},
        }

    def dto_ref(self, schema_id, payload=None):
        return {"kind": "dto", "schema_id": schema_id, "payload": payload or {"status": "passed"}}

    def artifact_ref(self, relative_path, payload):
        path = self.workspace / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        return {"kind": "artifact", "path": relative_path, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

    def operation_state_ref(self, *operation_ids):
        return {"kind": "run_state", "key": "operation_statuses", "operation_ids": list(operation_ids)}

    def advance_ok(self, run_state, target, evidence):
        advanced = maybe_await(self.workflow.advanceCheckpoint(run_state, target, evidence))
        self.assertEqual(advanced["status"], "ok", advanced.get("blocking_reasons"))
        return advanced

    def persist_run_state(self, run_state):
        path = self.workspace / ".workflow" / "runs" / f"{run_state['run_id']}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(run_state, sort_keys=True, indent=2), encoding="utf-8")

    def persisted_run_state(self, run_state):
        path = self.workspace / ".workflow" / "runs" / f"{run_state['run_id']}.json"
        return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
