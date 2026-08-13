#!/usr/bin/env python3
"""Executable smoke harness for SMOKE_TEST.md."""

from __future__ import annotations

import argparse
import asyncio
import importlib
import importlib.metadata
import json
import os
import shutil
import subprocess
import sys
import tempfile
import venv
from pathlib import Path
from typing import Any


PACKAGE_IMPORTS = [
    "resume_core",
    "career_store",
    "career_mcp",
    "workflow",
    "resume_agent",
    "resume_render",
    "resume_cli",
    "resume_plugin",
]

WORKSPACE_PATHS = [
    "config.json",
    "resume/base.json",
    "resume/working.json",
    "job/current.json",
    "data/career.db",
    "operations",
    "reports",
    "output",
]

JsonObject = dict[str, Any]


class SmokeFailure(AssertionError):
    """A release-blocking smoke assertion failed."""


def venv_python(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def run_command(command: list[str], cwd: Path, env: dict[str, str]) -> int:
    print(f"$ {' '.join(command)}", flush=True)
    completed = subprocess.run(command, cwd=cwd, env=env, text=True, check=False)
    return completed.returncode


def run_in_clean_install(root: Path, workspace: Path | None, keep_workspace: bool) -> int:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    with tempfile.TemporaryDirectory(prefix="resume-kit-smoke-") as temp_name:
        temp = Path(temp_name)
        env_dir = temp / ".venv"
        smoke_workspace = workspace or temp / "smoke-workspace"
        venv.EnvBuilder(with_pip=True).create(env_dir)
        python = venv_python(env_dir)
        try:
            install_code = run_command([str(python), "-m", "pip", "install", "-e", str(root)], root, env)
            if install_code:
                return install_code
            command = [
                str(python),
                str(root / "tools" / "run_smoke.py"),
                "--root",
                str(root),
                "--workspace",
                str(smoke_workspace),
                "--installed-env",
            ]
            if keep_workspace:
                command.append("--keep-workspace")
            return run_command(command, root, env)
        finally:
            shutil.rmtree(root / "resume_kit.egg-info", ignore_errors=True)


def run_smoke(root: Path, workspace: Path, keep_workspace: bool) -> None:
    workspace.mkdir(parents=True, exist_ok=True)
    modules = load_public_packages()
    resume_core = modules["resume_core"]
    career_store = modules["career_store"]
    career_mcp = modules["career_mcp"]
    resume_cli = modules["resume_cli"]

    resume_file = root / "fixtures" / "resumes" / "resume-main.txt"
    job_file = root / "fixtures" / "jobs" / "job-a-staff-software-engineer.txt"
    answer_file = root / "fixtures" / "answers" / "aws.txt"
    for fixture in [resume_file, job_file, answer_file]:
        require(fixture.exists(), f"missing smoke fixture: {fixture}")

    resume_text = resume_file.read_text(encoding="utf-8")
    sanitized = resume_core.sanitizeText(resume_text)
    require(sanitized.get("status") in {"ok", "warning"}, "ATS sanitation must complete")
    require(sanitized.get("text") != resume_text, "smoke fixture must exercise ATS character sanitation")

    init = run_cli(resume_cli, ["init"], workspace)
    require_ok(init, "resume init")
    for rel_path in WORKSPACE_PATHS:
        require((workspace / rel_path).exists(), f"init did not create {rel_path}")
    require_json(workspace / "config.json", "config.json")
    require((workspace / "data" / "career.db").exists(), "career-store migration did not create database")

    ingest = run_cli(resume_cli, ["ingest", str(resume_file)], workspace)
    require_ok(ingest, "resume ingest")
    require(ingest.get("sanitation", {}).get("text") == sanitized.get("text"), "ingest must report core sanitation output")
    base = require_json(workspace / "resume" / "base.json", "resume/base.json")
    working = require_json(workspace / "resume" / "working.json", "resume/working.json")
    require(base == working, "working resume must equal base immediately after ingest")
    require(base.get("semantic_fingerprint") == working.get("semantic_fingerprint"), "base and working semantic fingerprints differ after ingest")
    base_before_tailor = (workspace / "resume" / "base.json").read_text(encoding="utf-8")
    serialized_base = json_text(base)
    for unsupported in ["aws", "graphql", "staff software engineer", "20 million"]:
        require(unsupported not in serialized_base, f"unsupported claim appeared in base resume: {unsupported}")
    require("senior software developer" in serialized_base, "source candidate title was not preserved")
    require(base.get("provenance"), "base resume must retain source provenance")

    store = career_store.openCareerStore(str(workspace / "data" / "career.db"))
    assert_store_fact(store, "software development")
    react_fact = assert_store_fact(store, "React")
    assert_store_fact(store, "api")

    adapter = career_mcp.create_career_mcp(store)
    tool_names = {tool.get("name") for tool in adapter.list_tools()}
    require("career.search_facts" in tool_names and "career.get_fact" in tool_names, "MCP search/detail tools must be exposed")
    require(not any("raw" in str(name).casefold() or "sql" in str(name).casefold() for name in tool_names), "MCP exposed raw SQL-style tool")
    mcp_search = asyncio.run(adapter.call_tool("career.search_facts", {"query": "React", "limit": 5}))
    require_ok(mcp_search, "career.search_facts")
    require(mcp_search.get("facts"), "MCP search did not return React")
    mcp_fact = asyncio.run(adapter.call_tool("career.get_fact", {"fact_id": react_fact["fact_id"]}))
    require_ok(mcp_fact, "career.get_fact")
    require(mcp_fact.get("evidence_summary"), "MCP fact detail did not include evidence summary")
    raw_attempt = asyncio.run(adapter.call_tool("career.raw_sql", {"query": "select * from facts"}))
    require(raw_attempt.get("status") == "error", "raw SQL-style MCP call must fail")
    require(raw_attempt.get("error", {}).get("type") in {"unknown_tool", "not_found", "validation_error"}, "raw SQL-style MCP failure used wrong error type")
    require("select" not in json_text(raw_attempt), "raw SQL-style MCP error leaked query details")

    job_ingest = run_cli(resume_cli, ["job", "ingest", str(job_file)], workspace)
    require_ok(job_ingest, "resume job ingest")
    job = require_json(workspace / "job" / "current.json", "job/current.json")
    requirement_ids = {item.get("requirement_id") for item in job.get("requirements", [])}
    for requirement_id in ["req_react", "req_api", "req_responsive", "req_aws", "req_saas"]:
        require(requirement_id in requirement_ids, f"job ingest missed {requirement_id}")

    initial_match = run_cli(resume_cli, ["match"], workspace)
    repeat_match = run_cli(resume_cli, ["match"], workspace)
    require_ok(initial_match, "resume match")
    require(initial_match == repeat_match, "match result is not deterministic")
    initial_result = initial_match["match_result"]
    require_requirement(initial_result, "req_react", {"exact_match", "verified_fact_match"})
    require_requirement(initial_result, "req_api", {"exact_match", "verified_fact_match"})
    require_requirement(initial_result, "req_responsive", {"exact_match", "verified_fact_match"})
    require_requirement(initial_result, "req_aws", {"unknown"})
    require(initial_result.get("explanations"), "match result must include explanations")

    answer = answer_file.read_text(encoding="utf-8")
    resolved = run_cli(resume_cli, ["resolve"], workspace, stdin=answer)
    require_ok(resolved, "resume resolve")
    require(resolved.get("fact", {}).get("verification_state") == "user_verified", "confirmed AWS fact was not user_verified")
    aws_fact = store.getFact(resolved["fact"]["fact_id"])
    require(aws_fact.get("fact", {}).get("verification_state") == "user_verified", "career-store did not persist verified AWS fact")
    require(aws_fact.get("evidence"), "confirmed AWS fact must retain evidence")
    post_resolution_match = resolved["match_result"]
    require(post_resolution_match.get("score", 0) >= initial_result.get("score", 0), "confirmed fact reduced match score")
    require_requirement(post_resolution_match, "req_aws", {"verified_fact_match", "exact_match"})

    tailor = run_cli(resume_cli, ["tailor"], workspace)
    require_ok(tailor, "resume tailor")
    require(tailor.get("operations"), "tailor must produce proposal operations")
    require(tailor.get("validated"), "tailor must validate a grounded operation")
    require(tailor.get("applied"), "tailor must apply a validated operation")
    require(any(item.get("operation_id") == "op_hallucinated_scale" for item in tailor.get("rejected", [])), "hallucinated operation rejection was not recorded")
    require((workspace / "resume" / "base.json").read_text(encoding="utf-8") == base_before_tailor, "base resume changed after tailoring")
    tailored_working = require_json(workspace / "resume" / "working.json", "resume/working.json")
    require(tailored_working != base, "working resume did not change after applying valid operation")
    require("responsive design" in json_text(tailored_working), "valid terminology rewrite was not reflected in working resume")

    bad_operation = {
        "operation_id": "op_smoke_invalid_scale",
        "status": "proposed",
        "path": "/sections/1/items/0/bullets/1",
        "before": "Built API architecture, responsive design, React, TypeScript, software development.",
        "after": "Architected enterprise React platforms serving 20 million users globally.",
        "linked_requirement_ids": ["req_react"],
        "linked_fact_ids": ["fact_react"],
    }
    invalid = resume_core.validateChange(tailored_working, bad_operation, job, store.searchFacts("", include_evidence=True).get("facts", []), {"require_verified": True})
    require(invalid.get("validation_state") == "rejected", "hallucinated rewrite must be rejected")
    require_json(workspace / "resume" / "working.json", "resume/working.json")

    validation = run_cli(resume_cli, ["validate"], workspace)
    require_ok(validation, "resume validate")
    validations = validation.get("validations", {})
    require(validations.get("grounding") == "pass", "final grounding audit did not pass")
    require(validations.get("ats") == "passed", "ATS validation did not pass")
    require(validations.get("structure") == "passed", "structure validation did not pass")

    final_match = run_cli(resume_cli, ["match", "--working"], workspace)
    repeat_final_match = run_cli(resume_cli, ["match", "--working"], workspace)
    require_ok(final_match, "resume match --working")
    require(final_match == repeat_final_match, "final match result is not deterministic")
    require(final_match["match_result"].get("score", 0) >= initial_result.get("score", 0), "final score regressed below initial score")

    markdown = run_cli(resume_cli, ["export", "--format", "markdown"], workspace)
    docx = run_cli(resume_cli, ["export", "--format", "docx"], workspace)
    require_ok(markdown, "resume export --format markdown")
    require_ok(docx, "resume export --format docx")
    require((workspace / "output" / "resume.md").exists(), "Markdown export was not created")
    require((workspace / "output" / "resume.docx.json").exists(), "DOCX export artifact was not created")
    require(markdown.get("render_validation", {}).get("status") == "pass", "Markdown render validation did not pass")
    require(docx.get("render_validation", {}).get("status") == "pass", "DOCX render validation did not pass")

    audit = run_cli(resume_cli, ["audit"], workspace)
    require_ok(audit, "resume audit")
    audit_text = json_text(audit)
    for expected in ["scores", "facts", "operations", "validations", "outputs", "config_hash"]:
        require(expected in audit_text, f"audit report missed {expected}")
    require("op_hallucinated_scale" in audit_text, "audit report missed rejected hallucinated change")

    if keep_workspace:
        print(f"Smoke workspace: {workspace}", flush=True)
    print("smoke passed: installed packages, workspace flow, honesty guardrails, rendering, and audit are operational.", flush=True)


def load_public_packages() -> dict[str, Any]:
    require(importlib.metadata.version("resume-kit") == "0.0.0", "resume-kit package metadata is unavailable or wrong")
    modules: dict[str, Any] = {}
    for name in PACKAGE_IMPORTS:
        modules[name] = importlib.import_module(name)
    return modules


def run_cli(module: Any, argv: list[str], workspace: Path, stdin: str | None = None) -> JsonObject:
    result = module.main(argv=argv, cwd=workspace, stdin=stdin)
    if isinstance(result, int):
        return {"exit_code": result, "status": "ok" if result == 0 else "error"}
    if not isinstance(result, dict):
        raise SmokeFailure(f"CLI returned unsupported result for {' '.join(argv)}: {type(result).__name__}")
    return result


def assert_store_fact(store: Any, query: str) -> JsonObject:
    result = store.searchFacts(query, include_evidence=True)
    require_ok(result, f"career-store search {query}")
    facts = result.get("facts", [])
    require(facts, f"career-store did not persist {query}")
    fact = facts[0]
    require(fact.get("verification_state") == "source_stated", f"{query} fact should be source_stated")
    require(fact.get("evidence"), f"{query} fact must include evidence")
    return fact


def require_requirement(match_result: JsonObject, requirement_id: str, allowed_states: set[str]) -> JsonObject:
    for item in match_result.get("requirements", []):
        if item.get("requirement_id") == requirement_id:
            state = item.get("resolution_state")
            require(state in allowed_states, f"{requirement_id} state {state!r} not in {sorted(allowed_states)}")
            require("evidence" in item or item.get("status") == "unresolved", f"{requirement_id} missed requirement-level evidence")
            return item
    raise SmokeFailure(f"match result missed requirement {requirement_id}")


def require_json(path: Path, label: str) -> JsonObject:
    require(path.exists(), f"{label} does not exist")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"{label} must contain a JSON object")
    return value


def require_ok(result: JsonObject, label: str) -> None:
    require(result.get("status") == "ok" or result.get("exit_code") in {0, None}, f"{label} failed: {json.dumps(result, sort_keys=True)}")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SmokeFailure(message)


def json_text(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str).casefold()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Repository root. Defaults to current directory.")
    parser.add_argument("--workspace", help="Workspace directory to use for the smoke run.")
    parser.add_argument("--keep-workspace", action="store_true", help="Print and keep the smoke workspace when possible.")
    parser.add_argument("--installed-env", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    workspace = Path(args.workspace).resolve() if args.workspace else None
    if not args.installed_env:
        return run_in_clean_install(root, workspace, args.keep_workspace)

    smoke_workspace = workspace or Path(tempfile.mkdtemp(prefix="resume-kit-smoke-workspace-"))
    try:
        run_smoke(root, smoke_workspace, args.keep_workspace)
    except SmokeFailure as exc:
        print(f"smoke failed: {exc}", file=sys.stderr)
        if args.keep_workspace:
            print(f"Smoke workspace: {smoke_workspace}", file=sys.stderr)
        return 1
    finally:
        if workspace is None and not args.keep_workspace:
            shutil.rmtree(smoke_workspace, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
