"""Unit coverage for resume-cli audit reconstruction."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import resume_cli


class ResumeCliAuditReconstructionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tempdir.name)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def init_workspace(self) -> str:
        result = resume_cli.main(["init"], cwd=self.workspace)
        self.assertEqual(result["status"], "ok", result)
        return str(result["run_id"])

    def run_file(self, run_id: str) -> Path:
        return self.workspace / ".workflow" / "runs" / f"{run_id}.json"

    def read_run(self, run_id: str) -> dict:
        return json.loads(self.run_file(run_id).read_text(encoding="utf-8"))

    def write_run(self, run_id: str, values: dict) -> None:
        state = self.read_run(run_id)
        state.update(values)
        self.run_file(run_id).write_text(json.dumps(state, sort_keys=True, indent=2), encoding="utf-8")

    def run_files(self) -> list[str]:
        return sorted(path.name for path in (self.workspace / ".workflow" / "runs").glob("run_*.json"))

    def index_text(self) -> str:
        return (self.workspace / ".workflow" / "runs" / "index.json").read_text(encoding="utf-8")

    def test_audit_reconstructs_latest_run_without_creating_a_run(self) -> None:
        run_id = self.init_workspace()
        self.write_run(
            run_id,
            {
                "base_resume_id": "resume_1",
                "base_resume_hash": "hash_1",
                "job_id": "job_1",
                "renderer_template_version": "ats-clean@1.0.0",
                "initial_score": 6.5,
                "final_score": 8.25,
                "facts_added": ["fact_react"],
                "facts_verified": ["fact_react"],
                "operations_applied": ["op_grounded"],
                "operations_rejected": ["op_hallucinated_scale"],
                "validation_status": "passed",
                "output_artifact_paths": ["output/resume.docx"],
            },
        )
        files_before = self.run_files()
        index_before = self.index_text()

        with mock.patch.object(resume_cli, "createRun", side_effect=AssertionError("audit called createRun")):
            audit = resume_cli.main(["audit"], cwd=self.workspace)

        self.assertEqual(audit["status"], "ok", audit)
        self.assertEqual(audit["run_identity"], run_id)
        self.assertEqual(audit["scores"], {"initial": 6.5, "final": 8.25})
        self.assertEqual(audit["facts"], {"added": ["fact_react"], "verified": ["fact_react"]})
        self.assertEqual(audit["operations"]["applied"], ["op_grounded"])
        self.assertEqual(audit["operations"]["rejected"], ["op_hallucinated_scale"])
        self.assertEqual(audit["validations"], {"status": "passed"})
        self.assertEqual(audit["outputs"], ["output/resume.docx"])
        self.assertEqual(audit["run_selection"]["rule"], "latest persisted run for the current workspace config_hash; latest means the highest numeric run_id sequence suffix")
        self.assertEqual(self.run_files(), files_before)
        self.assertEqual(self.index_text(), index_before)

    def test_audit_selects_highest_sequence_for_current_config_hash(self) -> None:
        older_run_id = self.init_workspace()
        latest_run_id = self.init_workspace()
        self.write_run(
            older_run_id,
            {
                "renderer_template_version": "ats-clean@1.0.0",
                "operations_rejected": ["op_old"],
            },
        )
        self.write_run(
            latest_run_id,
            {
                "renderer_template_version": "ats-clean@1.0.0",
                "operations_rejected": ["op_latest"],
            },
        )

        audit = resume_cli.main(["audit"], cwd=self.workspace)

        self.assertEqual(audit["status"], "ok", audit)
        self.assertEqual(audit["run_identity"], latest_run_id)
        self.assertEqual(audit["operations"]["rejected"], ["op_latest"])

    def test_audit_without_persisted_runs_returns_typed_error_and_creates_nothing(self) -> None:
        audit = resume_cli.main(["audit"], cwd=self.workspace)

        self.assertEqual(audit["status"], "error", audit)
        self.assertEqual(audit["error"]["type"], "not_found")
        self.assertIn("no persisted workflow runs", audit["error"]["message"])
        self.assertFalse((self.workspace / ".workflow").exists())

    def test_audit_surfaces_reconstruction_not_recorded_markers(self) -> None:
        run_id = self.init_workspace()
        state = self.read_run(run_id)
        legacy_state = {"run_id": state["run_id"], "workspace": state["workspace"], "current_checkpoint": "INIT"}
        self.run_file(run_id).write_text(json.dumps(legacy_state, sort_keys=True, indent=2), encoding="utf-8")

        audit = resume_cli.main(["audit"], cwd=self.workspace)

        self.assertEqual(audit["status"], "ok", audit)
        self.assertEqual(audit["config_hash"], "not recorded")
        self.assertEqual(audit["manifest"]["base_resume_id"], "not recorded")
        self.assertEqual(audit["versions"]["renderer_template"], "not recorded")
        self.assertEqual(audit["manifest"]["metadata"]["not_recorded_marker"], "not recorded")
        self.assertIn("base_resume_id", audit["manifest"]["metadata"]["not_recorded_fields"])


if __name__ == "__main__":
    unittest.main()
