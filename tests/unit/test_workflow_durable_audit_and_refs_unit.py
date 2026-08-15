"""Unit coverage for durable workflow audit events and grounded checkpoint refs."""

from __future__ import annotations

import hashlib
import importlib
import json
import tempfile
import unittest
from pathlib import Path

import workflow


FIXED_TIME = "2026-01-01T00:00:00Z"


class WorkflowDurableAuditAndRefsTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tempdir.name)
        self.run_state = workflow.createRun(
            workspace=self.workspace,
            config={"schemaVersion": "1.0", "matching": {"requireHardRequirementsResolved": True}},
        )

    def tearDown(self):
        self.tempdir.cleanup()

    def persisted_state(self):
        path = self.workspace / ".workflow" / "runs" / f"{self.run_state['run_id']}.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def artifact_ref(self, relative_path, payload):
        path = self.workspace / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        return {"kind": "artifact", "path": relative_path, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

    def dto_ref(self, schema_id, payload=None):
        return {"kind": "dto", "schema_id": schema_id, "payload": payload or {"status": "passed"}}

    def assert_resolves_and_hash_matches(self, ref):
        self.assertEqual(ref.get("kind"), "artifact")
        path = Path(ref["path"])
        if not path.is_absolute():
            path = self.workspace / path
        self.assertTrue(path.is_file(), ref)
        self.assertEqual(ref["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())

    def log_lines(self, name):
        path = self.workspace / ".workflow" / "runs" / self.run_state["run_id"] / name
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def test_blocked_advance_persists_exactly_one_audit_event_and_survives_fresh_read(self):
        blocked = workflow.advanceCheckpoint(self.run_state, "INGEST_RESUME", {}, clock=lambda: FIXED_TIME)

        self.assertEqual(blocked["status"], "blocked")
        self.assertEqual(blocked["blocking_reasons"], ["config_validated"])

        persisted = self.persisted_state()
        self.assertEqual(len(persisted["audit_events"]), 1)
        event = persisted["audit_events"][0]
        self.assertEqual(
            event,
            {
                "event_id": f"{self.run_state['run_id']}_audit_0001",
                "run_id": self.run_state["run_id"],
                "checkpoint": "INGEST_RESUME",
                "decision": "blocked",
                "blocking_reasons": ["config_validated"],
                "evidence_refs": {},
                "timestamp": FIXED_TIME,
            },
        )
        self.assertEqual(blocked["audit_event"], event)

        reloaded_workflow = importlib.reload(workflow)
        run_path = self.workspace / ".workflow" / "runs" / f"{self.run_state['run_id']}.json"
        fresh = json.loads(run_path.read_text(encoding="utf-8"))
        recovered = reloaded_workflow.recoverRun(self.workspace, self.run_state["run_id"])
        self.assertEqual(fresh["audit_events"], [event])
        self.assertEqual(recovered["resume_from_checkpoint"], "INIT")

    def test_allowed_and_blocked_advances_append_sequence_audit_events(self):
        evidence = {"config_validated": self.dto_ref("WorkflowStatusEvidence")}

        advanced = workflow.advanceCheckpoint(self.run_state, "INGEST_RESUME", evidence, clock=lambda: "2026-01-01T00:00:00Z")
        blocked = workflow.advanceCheckpoint(self.run_state, "VALIDATE_BASE", {}, clock=lambda: "2026-01-01T00:01:00Z")

        self.assertEqual(advanced["status"], "ok")
        self.assertEqual(blocked["status"], "blocked")
        persisted = self.persisted_state()
        self.assertEqual([event["event_id"] for event in persisted["audit_events"]], [f"{self.run_state['run_id']}_audit_0001", f"{self.run_state['run_id']}_audit_0002"])
        self.assertEqual([event["decision"] for event in persisted["audit_events"]], ["advanced", "blocked"])
        self.assertEqual(persisted["audit_events"][0]["evidence_refs"], evidence)
        self.assertEqual(persisted["audit_events"][1]["blocking_reasons"], ["canonical_resume_exists"])

    def test_record_checkpoint_result_writes_payload_and_returns_only_hash_matched_artifact_refs(self):
        output_ref = self.artifact_ref("output/resume.md", {"status": "rendered"})
        validation_ref = self.artifact_ref("reports/validation.json", {"status": "passed"})
        render_ref = self.artifact_ref("reports/render.json", {"status": "passed"})
        payload = {
            "operations_applied": ["op_1"],
            "artifact_refs": [output_ref],
            "validation_refs": [validation_ref],
            "render_refs": [render_ref],
        }

        recorded = workflow.recordCheckpointResult(self.run_state, "APPLY_CHANGES", payload, clock=lambda: FIXED_TIME)

        self.assertEqual(recorded["status"], "ok")
        for ref in recorded["artifact_refs"]:
            self.assert_resolves_and_hash_matches(ref)
        self.assertEqual(recorded["artifact_refs"][1:], [output_ref])
        self.assertEqual(recorded["validation_refs"], [validation_ref])
        self.assertEqual(recorded["render_refs"], [render_ref])
        self.assert_resolves_and_hash_matches(recorded["validation_refs"][0])
        self.assert_resolves_and_hash_matches(recorded["render_refs"][0])

        checkpoint_ref = recorded["artifact_refs"][0]
        checkpoint_path = self.workspace / checkpoint_ref["path"]
        self.assertEqual(json.loads(checkpoint_path.read_text(encoding="utf-8")), payload)

    def test_unrelated_validation_and_render_words_do_not_create_validation_or_render_refs(self):
        recorded = workflow.recordCheckpointResult(
            self.run_state,
            "MATCH_BASE",
            {
                "notes": "This unrelated prose mentions validation and render but supplies no typed refs.",
                "match_result": {"score": 7.4},
            },
            clock=lambda: FIXED_TIME,
        )

        self.assertEqual(recorded["validation_refs"], [])
        self.assertEqual(recorded["render_refs"], [])
        self.assertEqual(len(recorded["artifact_refs"]), 1)
        self.assert_resolves_and_hash_matches(recorded["artifact_refs"][0])

    def test_record_checkpoint_result_appends_operation_and_question_logs_on_disk(self):
        first = workflow.recordCheckpointResult(
            self.run_state,
            "RESOLVE_GAPS",
            {
                "operation_statuses": [{"operation_id": "op_1", "status": "proposed"}],
                "question_answers": [
                    {
                        "question_id": "q_1",
                        "question_ref": "career-store/interactions/int_q_1",
                        "answer_ref": "career-store/interactions/int_a_1",
                        "question_text": "Do you have Kubernetes experience?",
                        "answer_text": "No.",
                        "fact_refs": ["fact_aws"],
                        "career_store_interaction_id": "int_a_1",
                        "unresolved_requirements": [
                            {
                                "requirement_id": "req_k8s",
                                "resolution_state": "unresolved",
                                "reason": "User did not confirm this requirement.",
                            }
                        ],
                    }
                ],
            },
            clock=lambda: "2026-01-01T00:00:00Z",
        )
        second = workflow.recordCheckpointResult(
            self.run_state,
            "APPLY_CHANGES",
            {"operations_applied": ["op_1"], "question_answer_log_refs": ["career-store/interactions/int_followup"]},
            clock=lambda: "2026-01-01T00:01:00Z",
        )

        self.assertEqual(first["operation_log_refs"], [f".workflow/runs/{self.run_state['run_id']}/operations.jsonl#L1"])
        self.assertEqual(second["operation_log_refs"], [f".workflow/runs/{self.run_state['run_id']}/operations.jsonl#L2"])
        self.assertEqual(first["question_answer_log_refs"], [f".workflow/runs/{self.run_state['run_id']}/questions.jsonl#L1"])
        self.assertEqual(second["question_answer_log_refs"], [f".workflow/runs/{self.run_state['run_id']}/questions.jsonl#L2"])

        operations = self.log_lines("operations.jsonl")
        questions = self.log_lines("questions.jsonl")
        self.assertEqual([record["status"] for record in operations], ["proposed", "applied"])
        self.assertEqual([record["operation_id"] for record in operations], ["op_1", "op_1"])
        self.assertEqual(questions[0]["question_ref"], "career-store/interactions/int_q_1")
        self.assertEqual(questions[0]["answer_ref"], "career-store/interactions/int_a_1")
        self.assertEqual(questions[0]["fact_refs"], ["fact_aws"])
        self.assertEqual(questions[0]["career_store_interaction_id"], "int_a_1")
        self.assertNotIn("question_text", questions[0])
        self.assertNotIn("answer_text", questions[0])

        manifest_state = {
            **self.run_state,
            "base_resume_id": "base_1",
            "base_resume_hash": "hash_base",
            "job_id": "job_1",
            "renderer_template_version": "ats-clean@1",
        }
        manifest = workflow.buildRunManifest(manifest_state)
        self.assertEqual(manifest["operations_applied"], ["op_1"])
        self.assertEqual(
            manifest["question_answer_log_refs"],
            [
                f".workflow/runs/{self.run_state['run_id']}/questions.jsonl#L1",
                f".workflow/runs/{self.run_state['run_id']}/questions.jsonl#L2",
            ],
        )
        self.assertEqual(
            manifest["unresolved_requirements"],
            [
                {
                    "requirement_id": "req_k8s",
                    "resolution_state": "unresolved",
                    "reason": "User did not confirm this requirement.",
                }
            ],
        )

    def test_reconstruct_run_manifest_matches_built_manifest_for_recorded_run(self):
        self.run_state.update(
            {
                "base_resume_id": "base_1",
                "base_resume_hash": "hash_base",
                "job_id": "job_1",
                "renderer_template_version": "ats-clean@1",
                "agent_model_config": {"model": "fixed-test"},
                "initial_score": 6.4,
                "final_score": 8.2,
                "facts_added": ["fact_aws"],
                "facts_verified": ["fact_aws"],
                "validation_status": "passed",
                "output_artifact_paths": ["output/resume.docx"],
                "unresolved_requirements": [
                    {
                        "requirement_id": "req_k8s",
                        "resolution_state": "unresolved",
                        "reason": "Awaiting user confirmation.",
                    }
                ],
            }
        )
        workflow.recordCheckpointResult(
            self.run_state,
            "APPLY_CHANGES",
            {
                "operations_applied": ["op_1"],
                "operations_rejected": ["op_bad"],
                "question_answer_log_refs": ["career-store/interactions/int_1"],
            },
            clock=lambda: FIXED_TIME,
        )

        built = workflow.buildRunManifest(self.run_state)
        reconstructed = workflow.reconstructRunManifest(self.run_state["run_id"], workspace=self.workspace)

        self.assertEqual(reconstructed, built)

    def test_reconstruct_run_manifest_unknown_run_id_raises_typed_error(self):
        with self.assertRaises(workflow.UnknownRunError) as raised:
            workflow.reconstructRunManifest("run_missing", workspace=self.workspace)
        self.assertEqual(raised.exception.run_id, "run_missing")

    def test_reconstruct_pre_initiative_run_uses_not_recorded_markers(self):
        run_id = "run_legacy"
        path = self.workspace / ".workflow" / "runs" / f"{run_id}.json"
        path.write_text(
            json.dumps({"run_id": run_id, "workspace": str(self.workspace), "current_checkpoint": "INIT"}, sort_keys=True),
            encoding="utf-8",
        )

        manifest = workflow.reconstructRunManifest(run_id, workspace=self.workspace)

        self.assertEqual(manifest["base_resume_id"], "not recorded")
        self.assertEqual(manifest["renderer_template_version"], "not recorded")
        self.assertEqual(manifest["matching_algorithm_version"], "not recorded")
        self.assertIn("not_recorded_fields", manifest["metadata"])
        self.assertIn("base_resume_id", manifest["metadata"]["not_recorded_fields"])
        self.assertEqual(manifest["question_answer_log_refs"], [])


if __name__ == "__main__":
    unittest.main()
