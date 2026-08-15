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


if __name__ == "__main__":
    unittest.main()
