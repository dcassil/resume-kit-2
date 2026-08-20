"""Contract-first tests for the future resume_cli package."""

from __future__ import annotations

import asyncio
import importlib
import inspect
import json
import os
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
SURFACE = json.loads((ROOT / "resume-cli" / "cli_surface.json").read_text(encoding="utf-8"))
ROOT_PYPROJECT = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
RESUME_CLI_PYPROJECT = tomllib.loads((ROOT / "resume-cli" / "pyproject.toml").read_text(encoding="utf-8"))
REQUIRED_COMMANDS = tuple(SURFACE["required_commands"])
EXPECTED_WORKSPACE = tuple(SURFACE["expected_workspace"])
CHECKPOINTS = tuple(SURFACE["canonical_checkpoints"])
SUBPROCESS_TIMEOUT_SECONDS = 10


RESUME_FIXTURE_TEXT = (ROOT / "fixtures" / "resumes" / "resume-main.txt").read_text(encoding="utf-8")

JOB_FIXTURE_TEXT = (ROOT / "fixtures" / "jobs" / "job-a-staff-software-engineer.txt").read_text(encoding="utf-8")


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


def subprocess_env() -> dict[str, str]:
    env = os.environ.copy()
    package_paths = [
        str(ROOT / "resume-cli"),
        str(ROOT / "resume-core"),
        str(ROOT / "career-store"),
        str(ROOT / "career-mcp"),
        str(ROOT / "resume-agent"),
        str(ROOT / "resume-render"),
        str(ROOT),
    ]
    if env.get("PYTHONPATH"):
        package_paths.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(package_paths)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def run_resume_subprocess(args: list[str], cwd: Path, stdin: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "resume_cli", *args],
        cwd=cwd,
        env=subprocess_env(),
        input=stdin,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=SUBPROCESS_TIMEOUT_SECONDS,
        check=False,
    )


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

    def test_pyproject_declares_resume_console_entrypoint(self):
        self.assertEqual(ROOT_PYPROJECT["project"]["scripts"]["resume"], "resume_cli.cli:main")
        self.assertEqual(RESUME_CLI_PYPROJECT["project"]["scripts"]["resume"], "resume_cli.cli:main")


class ResumeCliCommandContractTests(unittest.TestCase):
    def setUp(self):
        self.cli = load_cli_module(self)
        self.tempdir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tempdir.name)
        self.resume_file = self.workspace / "resume-main.txt"
        self.job_file = self.workspace / "job-a-staff-software-engineer.txt"
        self.resume_file.write_text(RESUME_FIXTURE_TEXT, encoding="utf-8")
        self.job_file.write_text(JOB_FIXTURE_TEXT, encoding="utf-8")

    def tearDown(self):
        self.tempdir.cleanup()

    def test_init_creates_expected_workspace_and_is_idempotent(self):
        first = normalize_result(run_cli(self.cli, ["init"], self.workspace))
        self.assertIn(first.get("exit_code", 0), {0, None})
        self.assertEqual({"status", "exit_code", "artifacts", "report", "errors"} & set(first), {"status", "exit_code", "artifacts", "report", "errors"})
        self.assertEqual(first["errors"], [])
        self.assertIn("config", first["artifacts"])
        for path in EXPECTED_WORKSPACE:
            target = self.workspace / path.rstrip("/")
            self.assertTrue(target.exists(), f"init must create or prepare {path}")
        config = json.loads((self.workspace / "config.json").read_text(encoding="utf-8"))
        self.assertIn("config_version", config)
        self.assertIn("schema_versions", config)
        self.assertEqual(set(config["matching"]), {"scoreAutoThreshold", "weights", "requireHardRequirementsResolved"})
        self.assertEqual(
            set(config["matching"]["weights"]),
            {"requiredSkills", "experience", "roleAlignment", "domainIndustry", "preferredSkills", "terminology"},
        )
        self.assertEqual(set(config["resume"]), {"targetPages", "skills", "experience", "bulletsPerRole", "sectionOrder"})
        for key in ["skills", "experience", "bulletsPerRole"]:
            self.assertEqual(set(config["resume"][key]), {"min", "max"})
        self.assertEqual(set(config["guardrails"]), {"allow_inferred_facts"})
        self.assertEqual(set(config["agent"]), {"model", "schema_mode", "timeout_ms", "max_retries", "cost_ceiling"})

        career_db_before = (self.workspace / "data" / "career.db").stat().st_mtime_ns
        second = normalize_result(run_cli(self.cli, ["init"], self.workspace))
        self.assertIn(second.get("exit_code", 0), {0, None})
        self.assertTrue((self.workspace / "data" / "career.db").exists())
        self.assertGreaterEqual((self.workspace / "data" / "career.db").stat().st_mtime_ns, career_db_before)

    def test_init_embeds_store_state_verbatim_in_result_and_run_artifact(self):
        expected_state = {
            "schema_version": "career-store.v1",
            "database_path": str(self.workspace / "data" / "career.db"),
            "applied_migrations": ["001_initial"],
            "pending_migrations": ["002_pending"],
            "status": "pending",
            "metadata": {"source": "double"},
        }
        store = type("CareerStoreStatusDouble", (), {})()
        setattr(store, "get" + "MigrationState", lambda: expected_state)

        with mock.patch.object(self.cli, "openCareerStore", return_value=store):
            result = normalize_result(run_cli(self.cli, ["init"], self.workspace))

        self.assertEqual(result["migrations"]["career_store"], expected_state)
        run_artifact = json.loads((self.workspace / ".workflow" / "runs" / f"{result['run_id']}.json").read_text(encoding="utf-8"))
        self.assertEqual(run_artifact["careerDbVersion"], expected_state)

    def test_init_surfaces_store_typed_version_error_without_rewriting_it(self):
        with mock.patch.object(self.cli, "openCareerStore", side_effect=ValueError("incompatible_schema_version: career-store.v999")):
            result = normalize_result(run_cli(self.cli, ["init"], self.workspace))

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["errors"][0]["code"], "validation_error")
        self.assertIn("incompatible_schema_version", result["errors"][0]["message"])

    def test_ingest_resume_creates_base_working_hash_and_career_fact_summary(self):
        run_cli(self.cli, ["init"], self.workspace)
        result = normalize_result(run_cli(self.cli, ["ingest", str(self.resume_file)], self.workspace))
        self.assertIn(result.get("exit_code", 0), {0, None})
        base = json.loads((self.workspace / "resume" / "base.json").read_text(encoding="utf-8"))
        working = json.loads((self.workspace / "resume" / "working.json").read_text(encoding="utf-8"))
        from resume_core import CANONICAL_RESUME_SCHEMA

        self.assertEqual(set(base) & set(CANONICAL_RESUME_SCHEMA["required"]), set(CANONICAL_RESUME_SCHEMA["required"]))
        self.assertEqual(base.get("semantic_fingerprint"), working.get("semantic_fingerprint"))
        self.assertIn("base_hash", result)
        serialized = json.dumps(base, sort_keys=True).lower()
        self.assertIn("react", serialized)
        self.assertNotIn("aws", serialized)
        self.assertNotIn("graphql", serialized)
        self.assertNotIn("staff software engineer", serialized)

    def test_ingest_resume_empty_extraction_returns_typed_failure_without_fallback_content(self):
        run_cli(self.cli, ["init"], self.workspace)
        with mock.patch.object(
            self.cli,
            "extractResumeSemantics",
            return_value={"schema_version": "resume-agent.proposal.v1", "proposal_type": "resume_semantic_extraction", "fact_proposals": [], "source_evidence": []},
        ):
            result = normalize_result(run_cli(self.cli, ["ingest", str(self.resume_file)], self.workspace))

        self.assertEqual(result.get("status"), "error")
        self.assertEqual(result.get("exit_code"), 1)
        self.assertEqual(result.get("base_hash"), None)
        self.assertEqual(result.get("career_facts"), [])
        self.assertEqual(result["errors"][0]["code"], "empty_resume_extraction")
        self.assertEqual(json.loads((self.workspace / "resume" / "base.json").read_text(encoding="utf-8")), {})

    def test_ingest_resume_no_title_or_experience_does_not_fabricate_defaults(self):
        run_cli(self.cli, ["init"], self.workspace)
        minimal_resume = self.workspace / "minimal-resume.txt"
        minimal_resume.write_text("Sam No Defaults\nSkills: Python\n", encoding="utf-8")
        extraction = {
            "schema_version": "resume-agent.proposal.v1",
            "proposal_type": "resume_semantic_extraction",
            "fact_proposals": [
                {
                    "fact_id": "fact_minimal_name",
                    "category": "name",
                    "text": "Sam No Defaults",
                    "normalized_terms": ["sam no defaults"],
                    "source_evidence_ids": ["ev_minimal_name"],
                    "verification_state": "inferred",
                    "confidence": 0.94,
                    "review_required": True,
                },
                {
                    "fact_id": "fact_minimal_python",
                    "category": "skill",
                    "text": "Python",
                    "normalized_terms": ["python"],
                    "source_evidence_ids": ["ev_minimal_skills"],
                    "verification_state": "inferred",
                    "confidence": 0.91,
                    "review_required": True,
                },
            ],
            "source_evidence": [
                {"evidence_id": "ev_minimal_name", "text": "Sam No Defaults", "span": {"start": 0, "end": 15}},
                {"evidence_id": "ev_minimal_skills", "text": "Skills: Python", "span": {"start": 16, "end": 30}},
            ],
        }

        with mock.patch.object(self.cli, "extractResumeSemantics", return_value=extraction):
            result = normalize_result(run_cli(self.cli, ["ingest", str(minimal_resume)], self.workspace))

        self.assertEqual(result.get("status"), "ok", result)
        base = json.loads((self.workspace / "resume" / "base.json").read_text(encoding="utf-8"))
        serialized = json.dumps(base, sort_keys=True)
        self.assertNotIn("title", base)
        self.assertEqual(base["experience"], [])
        self.assertNotIn("Software Engineer", serialized)
        self.assertNotIn("Source Resume", serialized)
        self.assertNotIn("Software Developer", serialized)

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
        run_cli(self.cli, ["resolve"], self.workspace, stdin="Yes. I have about six years of AWS experience, mainly EC2, S3, Lambda, RDS, and IAM.\n")
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

    def test_pdf_export_skips_with_notice_without_fabricated_artifact_or_pipeline_error(self):
        run_cli(self.cli, ["init"], self.workspace)
        run_cli(self.cli, ["ingest", str(self.resume_file)], self.workspace)
        result = normalize_result(run_cli(self.cli, ["export", "--format", "pdf"], self.workspace))
        self.assertEqual(result.get("status"), "unsupported")
        self.assertEqual(result.get("exit_code"), 0)
        self.assertEqual(result.get("reason"), "not_in_format_targets")
        self.assertNotIn("artifact", result)
        self.assertIn("skipped", result.get("notice", "").lower())
        self.assertEqual(result.get("render_validation", {}).get("status"), "unsupported")
        self.assertTrue((self.workspace / "output" / "resume.md").exists())
        self.assertTrue((self.workspace / "output" / "resume.docx.json").exists())

    def test_run_uses_same_checkpoint_contract_and_outputs_as_sequence(self):
        sequence_workspace = self.workspace / "sequence"
        run_workspace = self.workspace / "run"
        sequence_workspace.mkdir()
        run_workspace.mkdir()
        seq_resume = sequence_workspace / "resume-main.txt"
        seq_job = sequence_workspace / "job-a-staff-software-engineer.txt"
        run_resume = run_workspace / "resume-main.txt"
        run_job = run_workspace / "job-a-staff-software-engineer.txt"
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
        run_cli(self.cli, ["match"], self.workspace)
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

    def test_result_envelope_wraps_domain_error_with_stable_ref(self):
        result = normalize_result(run_cli(self.cli, ["inspect", "requirement", "missing"], self.workspace))
        self.assertEqual(result.get("status"), "no_data")
        self.assertEqual(result.get("exit_code"), 0)
        self.assertIn("artifacts", result)
        self.assertIn("report", result)
        self.assertEqual(result.get("reason"), "missing_match_report")
        self.assertEqual(result.get("errors"), [])

    def test_terminal_io_scripted_mode_is_deterministic(self):
        scripted = self.cli.ScriptedTerminalIO(["first answer", "yes", "unused"])
        self.assertEqual(scripted.ask("Question?"), "first answer")
        self.assertTrue(scripted.confirm("Confirm?"))
        self.assertEqual(scripted.ask("Next?"), "unused")
        self.assertEqual(scripted.ask("Exhausted?"), "")


class ResumeCliSubprocessContractTests(unittest.TestCase):
    def test_python_module_entrypoint_init_and_status_render_human_reports(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)

            init = run_resume_subprocess(["init"], workspace)
            self.assertEqual(init.returncode, 0, init.stderr)
            self.assertIn("resume init", init.stdout)
            self.assertIn("Workspace", init.stdout)
            self.assertEqual(init.stderr, "")

            status = run_resume_subprocess(["status"], workspace)
            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertIn("resume status", status.stdout)
            self.assertIn("initialized: True", status.stdout)
            self.assertEqual(status.stderr, "")

    def test_python_module_json_mode_emits_machine_envelope(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)

            completed = run_resume_subprocess(["--json", "init"], workspace)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            envelope = json.loads(completed.stdout)
            self.assertEqual(envelope["status"], "ok")
            self.assertEqual(envelope["exit_code"], 0)
            self.assertEqual(envelope["errors"], [])
            self.assertIn("artifacts", envelope)
            self.assertIn("report", envelope)

    def test_python_module_typed_stderr_errors_cover_domain_and_usage_exit_codes(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)

            domain = run_resume_subprocess(["status"], workspace)
            self.assertEqual(domain.returncode, 1)
            domain_error = json.loads(domain.stderr)
            self.assertEqual(domain_error["type"], "resume_cli.error")
            self.assertEqual(domain_error["code"], "workspace_not_initialized")
            self.assertEqual(domain_error["ref"], "workspace")

            usage = run_resume_subprocess(["bogus"], workspace)
            self.assertEqual(usage.returncode, 2)
            usage_error = json.loads(usage.stderr)
            self.assertEqual(usage_error["type"], "resume_cli.error")
            self.assertEqual(usage_error["code"], "usage_error")
            self.assertEqual(usage_error["ref"], "argv")

    def test_help_flag_prints_usage_and_never_executes_the_command(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            result = run_resume_subprocess(["init", "--help"], workspace)
            self.assertEqual(result.returncode, 0)
            self.assertIn("usage: resume", result.stdout)
            self.assertFalse((workspace / "config.json").exists(), "--help must not execute init")
            self.assertFalse((workspace / "data").exists(), "--help must not create workspace dirs")

    def test_unexpected_trailing_arguments_are_usage_errors_not_silently_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            result = run_resume_subprocess(["init", "extra-arg"], workspace)
            self.assertEqual(result.returncode, 2)
            error = json.loads(result.stderr)
            self.assertEqual(error["code"], "usage_error")
            self.assertIn("unexpected arguments", error["message"])
            self.assertFalse((workspace / "config.json").exists(), "arity errors must not execute the command")


if __name__ == "__main__":
    unittest.main()
