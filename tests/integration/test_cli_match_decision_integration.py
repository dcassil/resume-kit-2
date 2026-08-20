"""Integration coverage for resume match passthrough and decision enforcement."""

from __future__ import annotations

import contextlib
import importlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


@contextlib.contextmanager
def chdir(path: Path):
    previous = Path.cwd()
    try:
        import os

        os.chdir(path)
        yield
    finally:
        os.chdir(previous)


def load_cli():
    return importlib.import_module("resume_cli")


def run_cli(module, argv: list[str], cwd: Path):
    return module.main(argv=argv, cwd=cwd)


def write_match_artifacts(workspace: Path, *, resume_text: str = "Built React applications.") -> None:
    (workspace / "resume" / "working.json").write_text(
        json.dumps({"schema_version": "canonical-resume.v1", "resume_id": "resume_test", "summary": resume_text}),
        encoding="utf-8",
    )
    (workspace / "job" / "current.json").write_text(
        json.dumps(
            {
                "schema_version": "job-model.v1",
                "job_id": "job_test",
                "title": "Platform Engineer",
                "requirements": [
                    {
                        "requirement_id": "req_kubernetes",
                        "classification": "required",
                        "concept": "Kubernetes",
                        "source_text": "Kubernetes",
                        "normalized_terms": ["kubernetes"],
                        "weight": 1.0,
                    }
                ],
                "preferred": [],
                "terminology": [],
            }
        ),
        encoding="utf-8",
    )


class ResumeCliMatchDecisionIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cli = load_cli()
        self.console = importlib.import_module("resume_cli.cli")
        self.tempdir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tempdir.name)
        run_cli(self.cli, ["init"], self.workspace)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_match_report_and_persisted_json_pass_resolution_states_verbatim(self) -> None:
        write_match_artifacts(self.workspace)
        fake_match = {
            "schema_version": "match-result.v1",
            "match_id": "match_passthrough",
            "job_id": "job_test",
            "resume_id": "resume_test",
            "score": 1.0,
            "max_score": 4.0,
            "score_percent": 25.0,
            "threshold": 0.7,
            "hardRequirementsResolved": True,
            "decision": "continue",
            "dimensions": [{"name": "requiredSkills", "score": 1.0, "max_score": 4.0}],
            "requirement_results": [
                {"requirement_id": "req_related", "classification": "required", "resolution_state": "related_match", "blocking": False},
                {"requirement_id": "req_possible", "classification": "preferred", "resolution_state": "possible_match", "blocking": False},
                {"requirement_id": "req_na", "classification": "contextual", "resolution_state": "not_applicable", "blocking": False},
            ],
            "unresolved_requirement_ids": [],
            "preferred_unresolved_requirement_ids": [],
            "can_continue": True,
            "algorithm_version": "test",
        }
        stdout = io.StringIO()
        stderr = io.StringIO()

        with mock.patch.object(self.cli, "scoreMatch", return_value={"status": "ok", "match_result": fake_match}):
            with chdir(self.workspace):
                exit_code = self.console.main(argv=["match"], stdin=io.StringIO(""), stdout=stdout, stderr=stderr)

        self.assertEqual(exit_code, 0, stderr.getvalue())
        persisted = json.loads((self.workspace / "reports" / "match.json").read_text(encoding="utf-8"))
        self.assertEqual(
            [item["resolution_state"] for item in persisted["requirement_results"]],
            ["related_match", "possible_match", "not_applicable"],
        )
        self.assertEqual(persisted["requirements"], persisted["requirement_results"])
        self.assertEqual(persisted["unresolved"], persisted["unresolved_requirement_ids"])
        self.assertTrue({"score", "threshold", "hardRequirementsResolved", "dimensions", "requirement_results", "decision"} <= set(persisted))
        self.assertFalse(any("status" in item for item in persisted["requirement_results"]))
        self.assertNotIn("raw_resolution_state", json.dumps(persisted, sort_keys=True))
        report = stdout.getvalue()
        for state in ["related_match", "possible_match", "not_applicable"]:
            self.assertIn(state, report)

    def test_resolve_gaps_exits_zero_and_uses_core_selected_requirement_for_hint(self) -> None:
        write_match_artifacts(self.workspace)
        fake_match = {
            "schema_version": "match-result.v1",
            "match_id": "match_route",
            "job_id": "job_test",
            "resume_id": "resume_test",
            "score": 0.2,
            "max_score": 1.0,
            "score_percent": 20.0,
            "threshold": 0.7,
            "hardRequirementsResolved": False,
            "decision": "resolve_gaps",
            "dimensions": [],
            "requirement_results": [
                {"requirement_id": "req_cli_first", "classification": "required", "resolution_state": "unknown", "blocking": True},
                {"requirement_id": "req_core_selected", "classification": "preferred", "resolution_state": "unknown", "blocking": False},
            ],
            "unresolved_requirement_ids": ["req_cli_first"],
            "preferred_unresolved_requirement_ids": ["req_core_selected"],
            "can_continue": False,
            "algorithm_version": "test",
        }
        selection = {
            "status": "ok",
            "selected_requirement": {"requirement_id": "req_core_selected", "resolution_state": "unknown", "blocking": False},
            "blocking_requirements": [{"requirement_id": "req_cli_first"}],
            "can_continue": True,
        }

        with mock.patch.object(self.cli, "scoreMatch", return_value={"status": "ok", "match_result": fake_match}):
            with mock.patch.object(self.cli, "getUnresolvedRequirements", return_value=selection) as unresolved:
                result = run_cli(self.cli, ["match"], self.workspace)

        self.assertEqual(result["status"], "ok", result)
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(result["routing_hint"]["requirement_id"], "req_core_selected")
        unresolved.assert_called_once()

    def test_required_unresolved_requirement_blocks_when_policy_requires_resolution(self) -> None:
        write_match_artifacts(self.workspace)
        config_path = self.workspace / "config.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["matching"]["requireHardRequirementsResolved"] = True
        config_path.write_text(json.dumps(config), encoding="utf-8")

        result = run_cli(self.cli, ["match"], self.workspace)

        self.assertEqual(result["status"], "error", result)
        self.assertEqual(result["exit_code"], 1)
        self.assertEqual(result["match_result"]["decision"], "blocked")
        self.assertIn("req_kubernetes", result["blocking_requirement_ids"])
        self.assertIn("req_kubernetes", result["errors"][0]["message"])

    def test_empty_workspace_match_is_typed_failure_naming_missing_artifacts(self) -> None:
        result = run_cli(self.cli, ["match"], self.workspace)

        self.assertEqual(result["status"], "error", result)
        self.assertEqual(result["exit_code"], 1)
        self.assertEqual([error["code"] for error in result["errors"]], ["missing_match_artifact", "missing_match_artifact"])
        self.assertEqual({error["ref"] for error in result["errors"]}, {"resume/working.json", "job/current.json"})
        messages = " ".join(error["message"] for error in result["errors"])
        self.assertIn("resume artifact", messages)
        self.assertIn("job artifact", messages)


if __name__ == "__main__":
    unittest.main()
