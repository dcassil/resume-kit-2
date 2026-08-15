"""Unit coverage for workflow grounded transition recording."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import workflow


class WorkflowGroundedTransitionInvariantTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tempdir.name)
        self.run_state = workflow.createRun(
            workspace=self.workspace,
            config={"schemaVersion": "1.0", "matching": {"requireHardRequirementsResolved": True}},
        )

    def tearDown(self):
        self.tempdir.cleanup()

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

    def persisted_state(self):
        path = self.workspace / ".workflow" / "runs" / f"{self.run_state['run_id']}.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def advance(self, target, evidence):
        result = workflow.advanceCheckpoint(self.run_state, target, evidence)
        self.assertEqual(result["status"], "ok", result.get("blocking_reasons"))
        self.run_state = self.persisted_state()

    def record(self, checkpoint, result):
        recorded = workflow.recordCheckpointResult(self.run_state, checkpoint, result)
        self.assertEqual(recorded["status"], "ok")
        self.run_state = self.persisted_state()

    def assert_grounded_transition_invariant(self, run_state):
        accepted_transitions = [
            event
            for event in run_state.get("audit_events", [])
            if event.get("decision") == "advanced"
        ]
        self.assertTrue(accepted_transitions)
        self.assertEqual(accepted_transitions[-1]["checkpoint"], run_state["current_checkpoint"])

        verified_by_checkpoint = run_state.get("verified_evidence", {})
        stage_state = run_state.get("stage_state", {})
        latest_event_by_checkpoint = {}
        for event in accepted_transitions:
            checkpoint = event["checkpoint"]
            self.assertEqual(event["run_id"], run_state["run_id"])
            self.assertEqual(event["blocking_reasons"], [])
            self.assertIn("event_id", event)
            self.assertIn("timestamp", event)
            self.assertIsInstance(event["evidence_refs"], dict, checkpoint)
            self.assertTrue(event["evidence_refs"], checkpoint)
            for evidence_ref in event["evidence_refs"].values():
                self.assertIsInstance(evidence_ref, dict)
                self.assertIn(evidence_ref.get("kind"), {"artifact", "dto", "run_state"})
            latest_event_by_checkpoint[checkpoint] = event
        for checkpoint, event in latest_event_by_checkpoint.items():
            evidence = verified_by_checkpoint.get(checkpoint)
            self.assertEqual(event["evidence_refs"], evidence)
            self.assertEqual(stage_state.get(checkpoint), evidence)

    def test_reached_checkpoints_have_recorded_grounded_transitions(self):
        self.advance("INGEST_RESUME", {"config_validated": self.dto_ref("WorkflowStatusEvidence")})
        self.advance("VALIDATE_BASE", {"canonical_resume_exists": self.artifact_ref("resume/base.json", {"resume_id": "base_1"})})
        self.advance("EXTRACT_PERSIST_CAREER_FACTS", {"base_validation": self.dto_ref("WorkflowStatusEvidence")})
        self.advance("INGEST_JOB", {"career_facts_persisted": self.artifact_ref("data/career.db")})
        self.advance("NORMALIZE_JOB", {"job_ingested": self.artifact_ref("job/current.json", {"job_id": "job_1"})})
        self.advance("MATCH_BASE", {"job_normalized": self.dto_ref("WorkflowStatusEvidence")})
        self.record("MATCH_BASE", {"match_result": {"score": 7.4}})
        self.advance("RESOLVE_GAPS", {"match_result": self.dto_ref("MatchResultEvidence", {"status": "ok", "match_result": {"score": 7.4}})})
        self.record("RESOLVE_GAPS", {"facts_verified": ["fact_aws"], "question_answer_log_refs": ["qa_aws"]})
        self.advance("MATCH_BASE", {"job_normalized": self.dto_ref("WorkflowStatusEvidence")})
        self.record("MATCH_BASE", {"match_result": {"score": 8.1}})
        self.advance("RESOLVE_GAPS", {"match_result": self.dto_ref("MatchResultEvidence", {"status": "ok", "match_result": {"score": 8.1}})})
        self.advance("BUILD_SELECTION_PLAN", {"gaps_resolved": {"kind": "run_state", "key": "facts_verified"}})

        persisted = self.persisted_state()
        self.assert_grounded_transition_invariant(persisted)

        corrupted = dict(persisted)
        corrupted["verified_evidence"] = dict(persisted["verified_evidence"])
        corrupted["verified_evidence"].pop("BUILD_SELECTION_PLAN")
        with self.assertRaises(AssertionError):
            self.assert_grounded_transition_invariant(corrupted)
