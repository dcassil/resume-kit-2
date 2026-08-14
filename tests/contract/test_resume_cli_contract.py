"""Contract-first tests for the future resume_cli package."""

from __future__ import annotations

import asyncio
import importlib
import inspect
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SURFACE = json.loads((ROOT / "resume-cli" / "cli_surface.json").read_text(encoding="utf-8"))
REQUIRED_COMMANDS = tuple(SURFACE["required_commands"])
EXPECTED_WORKSPACE = tuple(SURFACE["expected_workspace"])
CHECKPOINTS = tuple(SURFACE["canonical_checkpoints"])


RESUME_FIXTURE_TEXT = """
Daniel Candidate
Software Engineer
Built React and TypeScript applications, REST APIs, and responsive web apps.
"""

JOB_FIXTURE_TEXT = """
Senior Software Engineer
Required: React, TypeScript, API architecture, responsive design.
Preferred: AWS, GraphQL, SaaS.
"""


def maybe_await(value):
    if inspect.isawaitable(value):
        return asyncio.run(value)
    return value


def load_cli_module(test_case: unittest.TestCase):
    try:
        module = importlib.import_module("resume_cli")
    except ModuleNotFoundError as exc:
        test_case.fail(
            "Expected importable package 'resume_cli'. Implement resume_cli.main(argv=None, cwd=None, "
            "stdin=None, stdout=None, stderr=None) and the command surface from resume-cli/TEST_SPEC.md."
        )
        raise exc
    test_case.assertTrue(callable(getattr(module, "main", None)), "resume_cli must expose main(...).")
    signature = inspect.signature(module.main)
    test_case.assertIn("argv", signature.parameters, "main must accept argv for deterministic command tests.")
    return module


def run_cli(module, argv: list[str], cwd: Path, stdin: str | None = None):
    return maybe_await(module.main(argv=argv, cwd=cwd, stdin=stdin))


def normalize_result(result):
    if isinstance(result, int):
        return {"exit_code": result}
    return result


class ResumeCliSurfaceManifestTests(unittest.TestCase):
    def test_manifest_declares_exact_command_surface(self):
        self.assertEqual(set(REQUIRED_COMMANDS), {
            "resume init",
            "resume ingest <file>",
            "resume job ingest <file-or-url-text>",
            "resume match",
            "resume resolve",
            "resume tailor",
            "resume validate",
            "resume export --format docx",
            "resume run <resume> <job>",
            "resume inspect fact <id>",
            "resume inspect requirement <id>",
            "resume audit",
        })

    def test_manifest_declares_workspace_and_checkpoint_contracts(self):
        self.assertEqual(set(EXPECTED_WORKSPACE), {
            "config.json",
            "resume/base.json",
            "resume/working.json",
            "job/current.json",
            "data/career.db",
            "operations/",
            "reports/",
            "output/",
        })
        self.assertIn("VALIDATE_CHANGES", CHECKPOINTS)
        self.assertIn("RENDER_VALIDATION", CHECKPOINTS)
        self.assertEqual(CHECKPOINTS[-1], "COMPLETE")


class ResumeCliCommandContractTests(unittest.TestCase):
    def setUp(self):
        self.cli = load_cli_module(self)
        self.tempdir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tempdir.name)
        self.resume_file = self.workspace / "resume.txt"
        self.job_file = self.workspace / "job.txt"
        self.resume_file.write_text(RESUME_FIXTURE_TEXT, encoding="utf-8")
        self.job_file.write_text(JOB_FIXTURE_TEXT, encoding="utf-8")

    def tearDown(self):
        self.tempdir.cleanup()

    def test_init_creates_expected_workspace_and_is_idempotent(self):
        first = normalize_result(run_cli(self.cli, ["init"], self.workspace))
        self.assertIn(first.get("exit_code", 0), {0, None})
        for path in EXPECTED_WORKSPACE:
            target = self.workspace / path.rstrip("/")
            self.assertTrue(target.exists(), f"init must create or prepare {path}")
        config = json.loads((self.workspace / "config.json").read_text(encoding="utf-8"))
        self.assertIn("config_version", config)
        self.assertIn("schema_versions", config)

        career_db_before = (self.workspace / "data" / "career.db").stat().st_mtime_ns
        second = normalize_result(run_cli(self.cli, ["init"], self.workspace))
        self.assertIn(second.get("exit_code", 0), {0, None})
        self.assertTrue((self.workspace / "data" / "career.db").exists())
        self.assertGreaterEqual((self.workspace / "data" / "career.db").stat().st_mtime_ns, career_db_before)

    def test_ingest_resume_creates_base_working_hash_and_career_fact_summary(self):
        run_cli(self.cli, ["init"], self.workspace)
        result = normalize_result(run_cli(self.cli, ["ingest", str(self.resume_file)], self.workspace))
        self.assertIn(result.get("exit_code", 0), {0, None})
        base = json.loads((self.workspace / "resume" / "base.json").read_text(encoding="utf-8"))
        working = json.loads((self.workspace / "resume" / "working.json").read_text(encoding="utf-8"))
        self.assertEqual(base.get("semantic_fingerprint"), working.get("semantic_fingerprint"))
        self.assertIn("base_hash", result)
        serialized = json.dumps(base, sort_keys=True).lower()
        self.assertIn("react", serialized)
        self.assertNotIn("aws", serialized)
        self.assertNotIn("graphql", serialized)
        self.assertNotIn("staff software engineer", serialized)

    def test_job_ingest_persists_source_text_and_requirement_classification(self):
        run_cli(self.cli, ["init"], self.workspace)
        result = normalize_result(run_cli(self.cli, ["job", "ingest", str(self.job_file)], self.workspace))
        self.assertIn(result.get("exit_code", 0), {0, None})
        job = json.loads((self.workspace / "job" / "current.json").read_text(encoding="utf-8"))
        requirements = job.get("requirements", [])
        self.assertTrue(requirements)
        self.assertTrue(all("source_text" in requirement for requirement in requirements))
        self.assertTrue({"required", "preferred"} <= {requirement.get("classification") for requirement in requirements})

    def test_match_is_deterministic_and_reports_requirement_reasoning(self):
        run_cli(self.cli, ["init"], self.workspace)
        run_cli(self.cli, ["ingest", str(self.resume_file)], self.workspace)
        run_cli(self.cli, ["job", "ingest", str(self.job_file)], self.workspace)
        first = normalize_result(run_cli(self.cli, ["match"], self.workspace))
        second = normalize_result(run_cli(self.cli, ["match"], self.workspace))
        self.assertEqual(first, second)
        self.assertIn("match_result", first)
        self.assertIn("requirements", first["match_result"])
        serialized = json.dumps(first, sort_keys=True).lower()
        self.assertIn("unresolved", serialized)
        self.assertNotIn("related_match_as_exact", serialized)

    def test_resolve_uses_agent_for_phrasing_and_persists_after_confirmation(self):
        run_cli(self.cli, ["init"], self.workspace)
        run_cli(self.cli, ["ingest", str(self.resume_file)], self.workspace)
        run_cli(self.cli, ["job", "ingest", str(self.job_file)], self.workspace)
        answer = "Yes. I have about six years of AWS experience, mainly EC2, S3, Lambda, RDS, and IAM.\n"
        result = normalize_result(run_cli(self.cli, ["resolve"], self.workspace, stdin=answer))
        self.assertIn(result.get("exit_code", 0), {0, None})
        serialized = json.dumps(result, sort_keys=True).lower()
        self.assertIn("question", serialized)
        self.assertIn("fact", serialized)
        self.assertIn("user_verified", serialized)
        self.assertRegex(serialized, r"\bsix\b|\b6\b")
        self.assertIn("match_result", serialized)

    def test_tailor_keeps_base_immutable_and_audits_operations(self):
        run_cli(self.cli, ["init"], self.workspace)
        run_cli(self.cli, ["ingest", str(self.resume_file)], self.workspace)
        base_before = (self.workspace / "resume" / "base.json").read_text(encoding="utf-8")
        run_cli(self.cli, ["job", "ingest", str(self.job_file)], self.workspace)
        result = normalize_result(run_cli(self.cli, ["tailor"], self.workspace))
        self.assertIn(result.get("exit_code", 0), {0, None})
        self.assertEqual((self.workspace / "resume" / "base.json").read_text(encoding="utf-8"), base_before)
        self.assertTrue((self.workspace / "operations").exists())
        serialized = json.dumps(result, sort_keys=True).lower()
        self.assertIn("validated", serialized)
        self.assertIn("rejected", serialized)
        validation = normalize_result(run_cli(self.cli, ["validate"], self.workspace))
        self.assertEqual(validation.get("validations", {}).get("grounding"), "pass", validation)

    def test_validate_runs_final_gates_and_rejects_unverified_inferred_claims(self):
        run_cli(self.cli, ["init"], self.workspace)
        run_cli(self.cli, ["ingest", str(self.resume_file)], self.workspace)
        run_cli(self.cli, ["job", "ingest", str(self.job_file)], self.workspace)
        result = normalize_result(run_cli(self.cli, ["validate"], self.workspace))
        self.assertIn(result.get("exit_code", 0), {0, None})
        validations = json.dumps(result.get("validations", result), sort_keys=True).lower()
        for expected in ["final_match", "grounding", "ats", "structure"]:
            self.assertIn(expected, validations)
        self.assertNotIn("unverified inferred fact accepted", validations)

    def test_export_invokes_renderer_records_template_and_validation(self):
        run_cli(self.cli, ["init"], self.workspace)
        run_cli(self.cli, ["ingest", str(self.resume_file)], self.workspace)
        result = normalize_result(run_cli(self.cli, ["export", "--format", "docx"], self.workspace))
        self.assertIn(result.get("exit_code", 0), {0, None})
        self.assertTrue((self.workspace / "output").exists())
        serialized = json.dumps(result, sort_keys=True).lower()
        self.assertIn("template_version", serialized)
        self.assertIn("render_validation", serialized)
        self.assertNotIn("truncated", serialized)

    def test_run_uses_same_checkpoint_contract_and_outputs_as_sequence(self):
        sequence_workspace = self.workspace / "sequence"
        run_workspace = self.workspace / "run"
        sequence_workspace.mkdir()
        run_workspace.mkdir()
        seq_resume = sequence_workspace / "resume.txt"
        seq_job = sequence_workspace / "job.txt"
        run_resume = run_workspace / "resume.txt"
        run_job = run_workspace / "job.txt"
        for path, text in [(seq_resume, RESUME_FIXTURE_TEXT), (seq_job, JOB_FIXTURE_TEXT), (run_resume, RESUME_FIXTURE_TEXT), (run_job, JOB_FIXTURE_TEXT)]:
            path.write_text(text, encoding="utf-8")

        for argv in [["init"], ["ingest", str(seq_resume)], ["job", "ingest", str(seq_job)], ["match"], ["tailor"], ["validate"], ["export", "--format", "docx"]]:
            run_cli(self.cli, argv, sequence_workspace)
        run_result = normalize_result(run_cli(self.cli, ["run", str(run_resume), str(run_job)], run_workspace))
        self.assertIn(run_result.get("exit_code", 0), {0, None})
        self.assertEqual(run_result.get("checkpoints"), list(CHECKPOINTS))
        self.assertTrue((run_workspace / "reports").exists())
        self.assertTrue((run_workspace / "output").exists())

    def test_inspect_and_audit_return_traceable_facts_requirements_and_run_identity(self):
        run_cli(self.cli, ["init"], self.workspace)
        run_cli(self.cli, ["ingest", str(self.resume_file)], self.workspace)
        run_cli(self.cli, ["job", "ingest", str(self.job_file)], self.workspace)
        fact = normalize_result(run_cli(self.cli, ["inspect", "fact", "fact_react"], self.workspace))
        self.assertIn("verification_state", json.dumps(fact, sort_keys=True))
        self.assertIn("evidence", json.dumps(fact, sort_keys=True))

        requirement = normalize_result(run_cli(self.cli, ["inspect", "requirement", "req_react"], self.workspace))
        serialized_requirement = json.dumps(requirement, sort_keys=True).lower()
        self.assertIn("source_text", serialized_requirement)
        self.assertIn("resolution_state", serialized_requirement)

        audit = normalize_result(run_cli(self.cli, ["audit"], self.workspace))
        serialized_audit = json.dumps(audit, sort_keys=True).lower()
        for expected in ["config_hash", "schema", "scores", "facts", "operations", "validations", "outputs"]:
            self.assertIn(expected, serialized_audit)


if __name__ == "__main__":
    unittest.main()
