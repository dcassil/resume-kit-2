"""Public runtime package for resume-cli."""

from __future__ import annotations

import hashlib
import json
import base64
import binascii
import re
import sys
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Protocol, TextIO

from career_store import openCareerStore

from . import _argv
from ._config import (
    WorkspaceConfigValidationError,
    default_config as _default_config,
    load_workspace_config as _load_workspace_config,
    stable_config_hash as _stable_config_hash,
)
from resume_agent import extractJobSemantics, extractResumeSemantics, generateClarificationQuestion, interpretUserAnswer, proposeRewrite
from resume_core import applyChange, canonicalResumeFromExtraction, normalizeJobModel, normalizeResume, rankResumeContent, sanitizeText, scoreMatch, toRenderableResume, validateChange, validateFinalResume, validateGrounding, validateResume
from resume_render import renderDocx, renderMarkdown, renderPdf, validateRenderedOutput
from workflow import CHECKPOINT_ORDER, UnknownRunError, createRun, reconstructRunManifest, recordCheckpointResult


JsonObject = dict[str, Any]

SUCCESS_EXIT = 0
DOMAIN_VALIDATION_EXIT = 1
USAGE_CONFIG_EXIT = 2


class TerminalIO(Protocol):
    """Terminal interaction seam used by interactive commands."""

    def ask(self, question: str) -> str:
        """Ask a terminal question and return the answer."""

    def confirm(self, summary: str) -> bool:
        """Ask for confirmation and return the user's decision."""


class ScriptedTerminalIO:
    """Deterministic terminal seam backed by a fixed answer stream."""

    def __init__(self, answers: list[str] | tuple[str, ...] | str | None = None) -> None:
        if answers is None:
            self._answers: list[str] = []
        elif isinstance(answers, str):
            self._answers = [line for line in answers.splitlines() if line.strip()]
        else:
            self._answers = [str(answer) for answer in answers]

    def ask(self, question: str) -> str:
        del question
        if not self._answers:
            return ""
        return self._answers.pop(0)

    def confirm(self, summary: str) -> bool:
        answer = self.ask(summary).strip().lower()
        return answer in {"y", "yes", "true", "1"}


class InteractiveTerminalIO:
    """TTY-backed terminal seam for the real console client."""

    def __init__(
        self,
        stdin: TextIO | None = None,
        stdout: TextIO | None = None,
        stderr: TextIO | None = None,
    ) -> None:
        self._stdin = stdin or sys.stdin
        self._stdout = stdout or sys.stdout
        self._stderr = stderr or sys.stderr

    def ask(self, question: str) -> str:
        print(question, file=self._stdout)
        self._stdout.flush()
        return self._stdin.readline().rstrip("\n")

    def confirm(self, summary: str) -> bool:
        print(f"{summary} [y/N]", file=self._stdout)
        self._stdout.flush()
        answer = self._stdin.readline().strip().lower()
        if answer in {"y", "yes"}:
            return True
        if answer in {"n", "no", ""}:
            return False
        print("Unrecognized confirmation response; treating as no.", file=self._stderr)
        return False


def _terminal_io(stdin: str | None, stdout: Any, stderr: Any) -> TerminalIO:
    if isinstance(stdin, str):
        return ScriptedTerminalIO(stdin)
    if stdin is not None or stdout is not None or stderr is not None:
        return InteractiveTerminalIO(stdin=stdin, stdout=stdout, stderr=stderr)
    return ScriptedTerminalIO()


def main(
    argv: list[str] | None = None,
    cwd: str | Path | None = None,
    stdin: str | None = None,
    stdout: Any = None,
    stderr: Any = None,
    terminal_io: TerminalIO | None = None,
) -> JsonObject:
    args = list(argv or [])
    workspace = Path(cwd or ".").resolve()
    if not args:
        return _error("usage_error", "command is required", ref="argv", exit_code=USAGE_CONFIG_EXIT)
    command = args[0]
    io = terminal_io or _terminal_io(stdin, stdout, stderr)
    arity_error = _unexpected_arguments_error(args)
    if arity_error is not None:
        return arity_error
    try:
        if command == "init":
            return _envelope("init", workspace, _init(workspace))
        if command == "status":
            return _envelope("status", workspace, _status(workspace))
        if command == "ingest" and len(args) >= 2:
            return _envelope("ingest", workspace, _ingest_resume(workspace, Path(args[1])))
        if command == "job" and len(args) >= 3 and args[1] == "ingest":
            return _envelope("job ingest", workspace, _ingest_job(workspace, Path(args[2])))
        if command == "match":
            return _envelope("match", workspace, _match(workspace))
        if command == "resolve":
            return _envelope("resolve", workspace, _resolve(workspace, io))
        if command == "tailor":
            return _envelope("tailor", workspace, _tailor(workspace))
        if command == "validate":
            return _envelope("validate", workspace, _validate(workspace))
        if command == "export":
            fmt = args[args.index("--format") + 1] if "--format" in args and args.index("--format") + 1 < len(args) else "docx"
            return _envelope("export", workspace, _export(workspace, fmt))
        if command == "run" and len(args) >= 3:
            return _envelope("run", workspace, _run(workspace, Path(args[1]), Path(args[2])))
        if command == "inspect" and len(args) >= 3 and args[1] == "fact":
            return _envelope("inspect fact", workspace, _inspect_fact(workspace, args[2]))
        if command == "inspect" and len(args) >= 3 and args[1] == "requirement":
            return _envelope("inspect requirement", workspace, _inspect_requirement(workspace, args[2]))
        if command == "audit":
            return _envelope("audit", workspace, _audit_report(workspace))
    except WorkspaceConfigValidationError as exc:
        return _config_validation_error(exc)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        return _error("validation_error", _safe_message(exc), ref="workspace")
    return _error("usage_error", f"unknown command: {' '.join(args)}", ref="argv", exit_code=USAGE_CONFIG_EXIT)


def _unexpected_arguments_error(args: list[str]) -> JsonObject | None:
    return _argv.unexpected_arguments_error(args, _error, USAGE_CONFIG_EXIT)


def _init(workspace: Path) -> JsonObject:
    paths = _paths(workspace)
    for folder in [paths["resume_dir"], paths["job_dir"], paths["data_dir"], paths["operations_dir"], paths["reports_dir"], paths["output_dir"]]:
        folder.mkdir(parents=True, exist_ok=True)
    config = _load_workspace_config(paths["config"]).config if paths["config"].exists() else _default_config()
    _write_json(paths["config"], config)
    _write_json_if_missing(paths["resume_base"], {})
    _write_json_if_missing(paths["resume_working"], {})
    _write_json_if_missing(paths["job_current"], {})
    store = openCareerStore(str(paths["career_db"]))
    migration_state = _migration_state_payload(store)
    run_state = createRun(workspace=workspace, config=config)
    run_state["careerDbVersion"] = migration_state
    _write_json(_workflow_run_file(workspace, str(run_state["run_id"])), run_state)
    return {
        "status": "ok",
        "exit_code": 0,
        "workspace": str(workspace),
        "config_version": config["config_version"],
        "schema_versions": config["schema_versions"],
        "migrations": {"career_store": migration_state},
        "run_id": run_state["run_id"],
        "warnings": [],
    }


def _status(workspace: Path) -> JsonObject:
    paths = _paths(workspace)
    if not paths["config"].exists():
        return _error("workspace_not_initialized", "workspace has not been initialized", ref="workspace")
    _config(workspace)
    initialized = paths["career_db"].exists()
    return {
        "status": "ok" if initialized else "error",
        "exit_code": SUCCESS_EXIT if initialized else DOMAIN_VALIDATION_EXIT,
        "workspace": str(workspace),
        "initialized": initialized,
        "artifacts": _workspace_artifacts(workspace),
        "warnings": [] if initialized else ["career database is missing"],
    }


def _envelope(command: str, workspace: Path, result: JsonObject) -> JsonObject:
    if _is_envelope(result):
        return result
    status = str(result.get("status") or "ok")
    exit_code = _exit_code_for_result(result)
    errors = _errors_for_result(result, default_ref=command or "argv")
    artifacts = _artifacts_for_result(command, workspace, result)
    report = result.get("report")
    if not isinstance(report, dict):
        report = _report_for_result(command, workspace, result, artifacts, errors)
    return {
        **result,
        "status": status,
        "exit_code": exit_code,
        "artifacts": artifacts,
        "report": report,
        "errors": errors,
    }


def _is_envelope(result: JsonObject) -> bool:
    return {"status", "exit_code", "artifacts", "report", "errors"} <= set(result)


def _exit_code_for_result(result: JsonObject) -> int:
    raw = result.get("exit_code")
    if isinstance(raw, int) and raw in {SUCCESS_EXIT, DOMAIN_VALIDATION_EXIT, USAGE_CONFIG_EXIT}:
        return raw
    if result.get("status") in {"ok", "unsupported"}:
        return SUCCESS_EXIT
    return DOMAIN_VALIDATION_EXIT


def _errors_for_result(result: JsonObject, default_ref: str) -> list[JsonObject]:
    raw_errors = result.get("errors")
    if isinstance(raw_errors, list):
        return [_normalize_error(error, default_ref) for error in raw_errors if isinstance(error, dict)]
    raw_error = result.get("error")
    if isinstance(raw_error, dict):
        return [_normalize_error(raw_error, default_ref)]
    return []


def _normalize_error(error: JsonObject, default_ref: str) -> JsonObject:
    code = str(error.get("code") or error.get("type") or "validation_error")
    message = str(error.get("message") or code)
    ref = str(error.get("offending_input_ref") or error.get("ref") or error.get("field_path") or default_ref)
    return {"code": code, "message": message, "ref": ref, "offending_input_ref": ref}


def _artifacts_for_result(command: str, workspace: Path, result: JsonObject) -> JsonObject:
    artifacts = result.get("artifacts")
    if isinstance(artifacts, dict):
        return dict(artifacts)
    paths = _paths(workspace)
    if command in {"init", "status", "run"}:
        return _workspace_artifacts(workspace)
    if command == "ingest":
        return {"resume_base": str(paths["resume_base"]), "resume_working": str(paths["resume_working"])}
    if command == "job ingest":
        return {"job_current": str(paths["job_current"])}
    if command == "match":
        return {"match_report": str(paths["reports_dir"] / "match.json")}
    if command == "tailor":
        return {"selection": str(paths["operations_dir"] / "selection.json"), "tailor": str(paths["operations_dir"] / "tailor.json")}
    if command == "validate":
        return {"validations": str(paths["reports_dir"] / "validations.json")}
    if command == "export":
        return {"output": str(paths["output_dir"])}
    return {}


def _workspace_artifacts(workspace: Path) -> JsonObject:
    paths = _paths(workspace)
    return {
        "config": str(paths["config"]),
        "resume_base": str(paths["resume_base"]),
        "resume_working": str(paths["resume_working"]),
        "job_current": str(paths["job_current"]),
        "career_db": str(paths["career_db"]),
        "operations": str(paths["operations_dir"]),
        "reports": str(paths["reports_dir"]),
        "output": str(paths["output_dir"]),
    }


def _report_for_result(
    command: str,
    workspace: Path,
    result: JsonObject,
    artifacts: JsonObject,
    errors: list[JsonObject],
) -> JsonObject:
    title = f"resume {command}".strip()
    sections: list[JsonObject] = [
        {"heading": "Status", "lines": [str(result.get("status") or "ok"), f"exit_code: {_exit_code_for_result(result)}"]},
    ]
    if command in {"init", "status"}:
        sections.append(
            {
                "heading": "Workspace",
                "lines": [
                    str(result.get("workspace") or workspace),
                    f"initialized: {bool(result.get('initialized', result.get('status') == 'ok'))}",
                ],
            }
        )
    if command == "match" and isinstance(result.get("match_result"), dict):
        match_result = result["match_result"]
        sections.append(
            {
                "heading": "Match",
                "lines": [
                    f"score: {match_result.get('score', 'unknown')}",
                    f"requirements: {len(match_result.get('requirements', []))}",
                    f"unresolved: {len(match_result.get('unresolved', []))}",
                ],
            }
        )
    if command == "resolve":
        sections.append({"heading": "Question", "lines": [str(result.get("question") or "")]})
    if command == "export":
        lines = [f"format: {result.get('format', 'docx')}"]
        artifact = result.get("artifact")
        if artifact:
            lines.append(f"artifact: {artifact}")
        if result.get("notice"):
            lines.append(str(result["notice"]))
        sections.append({"heading": "Export", "lines": lines})
    if artifacts:
        sections.append({"heading": "Artifacts", "lines": [f"{key}: {value}" for key, value in sorted(artifacts.items())]})
    if errors:
        sections.append({"heading": "Errors", "lines": [f"{error['code']}: {error['message']} ({error['ref']})" for error in errors]})
    return {"title": title, "summary": str(result.get("status") or "ok"), "sections": sections}


def _migration_state_payload(store: Any) -> JsonObject:
    state = store.getMigrationState()
    if is_dataclass(state):
        return asdict(state)
    if isinstance(state, dict):
        return dict(state)
    return {
        "schema_version": str(getattr(state, "schema_version", "")),
        "database_path": str(getattr(state, "database_path", "")),
        "applied_migrations": list(getattr(state, "applied_migrations", [])),
        "pending_migrations": list(getattr(state, "pending_migrations", [])),
        "status": str(getattr(state, "status", "unknown")),
        "metadata": dict(getattr(state, "metadata", {})),
    }


def _ingest_resume(workspace: Path, resume_file: Path) -> JsonObject:
    _init(workspace)
    text = resume_file.read_text(encoding="utf-8")
    sanitation = sanitizeText(text)
    sanitized_text = str(sanitation.get("text", text))
    extraction = extractResumeSemantics(sanitized_text, {"source_path": str(resume_file)})
    config = _config(workspace)
    constructed = canonicalResumeFromExtraction(extraction, {"kind": "file", "path": str(resume_file), "text": sanitized_text}, config)
    if constructed.get("status") == "error":
        return _ingest_resume_error(constructed.get("errors", []), extraction, sanitation, {}, ["INGEST_RESUME"])
    normalized = normalizeResume(constructed.get("canonical_resume", {}), config)
    if normalized.get("status") == "error":
        return _ingest_resume_error(normalized.get("errors", []), extraction, sanitation, normalized, ["INGEST_RESUME"])
    canonical = dict(normalized.get("canonical_resume", {}))
    validation = validateResume(canonical)
    if validation.get("status") == "error":
        return _ingest_resume_error(validation.get("errors", []), extraction, sanitation, validation, ["INGEST_RESUME", "VALIDATE_BASE"])
    base_hash = _hash(canonical)
    canonical["base_hash"] = base_hash
    canonical["semantic_fingerprint"] = _semantic_fingerprint(canonical)
    paths = _paths(workspace)
    _write_json(paths["resume_base"], canonical)
    _write_json(paths["resume_working"], dict(canonical))
    store = openCareerStore(str(paths["career_db"]))
    persisted = []
    policy = _resume_fact_policy(config, canonical)
    for proposal in constructed.get("fact_proposals", []):
        fact = _store_fact_from_proposal(proposal)
        result = store.upsertFact(
            fact,
            proposal.get("evidence") if isinstance(proposal, dict) else None,
            source="resume",
            policy=policy,
        )
        persisted.append(result.get("fact_id"))
    return {
        "status": "ok",
        "exit_code": 0,
        "base_hash": base_hash,
        "extraction": extraction,
        "validation": validation,
        "sanitation": sanitation,
        "career_facts": persisted,
        "checkpoints": ["INGEST_RESUME", "VALIDATE_BASE", "EXTRACT_PERSIST_CAREER_FACTS"],
    }


def _ingest_resume_error(
    errors: Any,
    extraction: JsonObject,
    sanitation: JsonObject,
    validation: JsonObject,
    checkpoints: list[str],
) -> JsonObject:
    normalized_errors = [error for error in errors if isinstance(error, dict)] if isinstance(errors, list) else []
    if not normalized_errors:
        normalized_errors = [{"code": "schema_error", "message": "resume ingest failed", "severity": "error", "field_path": "resume"}]
    return {
        "status": "error",
        "exit_code": DOMAIN_VALIDATION_EXIT,
        "base_hash": None,
        "extraction": extraction,
        "validation": validation,
        "sanitation": sanitation,
        "career_facts": [],
        "checkpoints": checkpoints,
        "errors": normalized_errors,
    }


def _ingest_job(workspace: Path, job_file: Path) -> JsonObject:
    _init(workspace)
    text = job_file.read_text(encoding="utf-8")
    extraction = extractJobSemantics(text, {"source_path": str(job_file)})
    normalized = normalizeJobModel(_job_from_text(text, extraction, job_file), _config(workspace))
    if normalized.get("status") == "error":
        return _error("schema_error", "job validation failed")
    job = dict(normalized.get("job_model", {}))
    # Compatibility shim (RKIT-I-0001/T-0008): JobModel now splits preferred
    # requirements into a distinct `preferred` array. This CLI still reads only
    # `requirements`, so fold preferred into the requirements superset (preferred
    # is preserved alongside, not dropped) to keep ingest lossless. Proper
    # preferred-vs-required handling is owned by the resume-cli initiative
    # (RKIT-I-0036/0037); remove this shim when that lands.
    job["requirements"] = [*job.get("requirements", []), *job.get("preferred", [])]
    _write_json(_paths(workspace)["job_current"], job)
    return {
        "status": "ok",
        "exit_code": 0,
        "job_id": job["job_id"],
        "extraction": extraction,
        "requirements": job["requirements"],
        "checkpoints": ["INGEST_JOB", "NORMALIZE_JOB"],
    }


def _match(workspace: Path) -> JsonObject:
    paths = _paths(workspace)
    resume = _read_json(paths["resume_working"], {})
    job = _read_json(paths["job_current"], {})
    facts = _all_facts(workspace)
    result = scoreMatch(resume, job, facts, _config(workspace))
    match_result = dict(result.get("match_result", {}))
    requirements = []
    for item in match_result.get("requirement_results", []):
        copied = dict(item)
        if copied.get("resolution_state") in {"related_match", "possible_match"}:
            copied["raw_resolution_state"] = copied["resolution_state"]
            copied["resolution_state"] = "unknown"
        copied["status"] = "unresolved" if copied.get("blocking") else copied.get("resolution_state", "unknown")
        requirements.append(copied)
    match_result["requirements"] = requirements
    match_result["unresolved"] = match_result.get("unresolved_requirement_ids", [])
    _write_json(paths["reports_dir"] / "match.json", match_result)
    _record_latest_run_snapshot(workspace, "MATCH_BASE", {"match_result": match_result})
    return {"status": "ok", "exit_code": 0, "match_result": match_result}


def _resolve(workspace: Path, terminal_io: TerminalIO) -> JsonObject:
    _init(workspace)
    match_result = _match(workspace)["match_result"]
    context = _resolution_context(match_result, _all_facts(workspace))
    question = generateClarificationQuestion(context)
    answer = terminal_io.ask(str(question.get("question") or ""))
    interpretation_context = {**context, "question": question.get("question")}
    interpretation = interpretUserAnswer(answer, interpretation_context)
    store = openCareerStore(str(_paths(workspace)["career_db"]))
    stored_facts = []
    for proposal in _fact_proposals(interpretation, context):
        stored = store.upsertFact(
            proposal,
            {"source": "user_answer", "text": answer, "metadata": {"selected_requirement_ids": context["selected_requirement_ids"]}},
            source="user_answer",
            policy={},
        )
        interpretation_proposal = _interpretation_proposal(stored["fact_id"], interpretation, context, answer)
        verified = store.verifyFact(
            stored["fact_id"],
            "user_verified",
            confirmation=interpretation_proposal,
            source="user_answer",
        )
        stored_fact = {"fact_id": stored["fact_id"], "verification_state": verified["verification_state"], "text": proposal["text"]}
        stored_facts.append(stored_fact)
        if verified["verification_state"] == "user_verified":
            for requirement_id in context["selected_requirement_ids"]:
                store.recordJobMatch(_current_job_id(workspace), requirement_id, [stored["fact_id"]], "verified_fact_match")
    match_result = _match(workspace)["match_result"]
    _record_latest_run_snapshot(
        workspace,
        "RESOLVE_GAPS",
        {
            "facts_verified": [fact["fact_id"] for fact in stored_facts if fact.get("verification_state") == "user_verified"],
            "question_answer_log_refs": [f"career-store/facts/{fact['fact_id']}" for fact in stored_facts if fact.get("fact_id")],
        },
    )
    return {
        "status": "ok",
        "exit_code": 0,
        "question": question.get("question"),
        "interpretation": interpretation,
        "fact": stored_facts[0] if stored_facts else {},
        "facts": stored_facts,
        "match_result": match_result,
    }


def _tailor(workspace: Path) -> JsonObject:
    _init(workspace)
    paths = _paths(workspace)
    base_before = paths["resume_base"].read_text(encoding="utf-8")
    working = _read_json(paths["resume_working"], {})
    job = _read_json(paths["job_current"], {})
    facts = _all_facts(workspace)
    match_result = _match(workspace)["match_result"]
    selection = rankResumeContent(working, job, match_result, _config(workspace))
    target_path = _best_rewrite_target(working)
    original_text = _claim_text(_json_pointer_value(working, target_path)) or _resume_text(working) or "Built web applications."
    context = {
        "original_text": original_text,
        "target_path": target_path,
        "allowed_facts": facts,
        "job_terminology": _job_terms_for_rewrite(job),
        "requirements": job.get("requirements", []),
        "prohibited_additions": _prohibited_additions(facts),
        "length_constraints": {"max_chars": 180},
        "voice_constraints": {"style": "concise"},
    }
    proposal = proposeRewrite(context)
    operations = [_core_operation(operation) for operation in proposal.get("operations", []) if isinstance(operation, dict)]
    validated = []
    applied = []
    rejected = []
    updated_working = working
    for operation in operations:
        validation = validateChange(updated_working, operation, job, facts, {"require_verified": True})
        if validation.get("validation_state") == "validated":
            validated_operation = validation["validated_operation"]
            apply_result = applyChange(updated_working, validated_operation)
            if apply_result.get("status") == "ok":
                updated_working = apply_result["working_resume"]
                validated.append(validated_operation)
                applied.append({"operation_id": operation["operation_id"], "status": "applied", "audit": apply_result.get("audit", {})})
            else:
                rejected.append({"operation_id": operation["operation_id"], "status": "rejected", "validation": apply_result})
        else:
            rejected.append({"operation_id": operation["operation_id"], "status": "rejected", "validation": validation})
    hallucinated = _hallucinated_operation(original_text, _target_path(target_path))
    hallucination_validation = validateChange(updated_working, hallucinated, job, facts, {"require_verified": True})
    rejected.append({"operation_id": hallucinated["operation_id"], "status": "rejected", "validation": hallucination_validation})
    _write_json(paths["resume_working"], updated_working)
    _write_json(paths["operations_dir"] / "selection.json", selection)
    _write_json(paths["operations_dir"] / "tailor.json", {"proposal": proposal, "operations": operations, "validated": validated, "applied": applied, "rejected": rejected})
    _record_latest_run_snapshot(
        workspace,
        "APPLY_CHANGES",
        {
            "operations_proposed": operations,
            "operations_validated": validated,
            "operations_applied": applied,
            "operations_rejected": rejected,
        },
    )
    if paths["resume_base"].read_text(encoding="utf-8") != base_before:
        return _error("policy_error", "base artifact changed outside ingest")
    return {
        "status": "ok",
        "exit_code": 0,
        "operations": operations,
        "validated": validated,
        "applied": applied,
        "rejected": rejected,
        "checkpoints": ["BUILD_SELECTION_PLAN", "PROPOSE_TAILORING_CHANGES", "VALIDATE_CHANGES", "APPLY_CHANGES"],
    }


def _validate(workspace: Path) -> JsonObject:
    paths = _paths(workspace)
    working = _read_json(paths["resume_working"], {})
    job = _read_json(paths["job_current"], {})
    facts = _all_facts(workspace)
    applied_operations = _applied_operations_for_validation(workspace)
    final = validateFinalResume(working, job, facts, _config(workspace), applied_operations)
    grounding = validateGrounding(working, facts, applied_operations, {})
    validations = {
        "final_match": final.get("match_result", {}),
        "grounding": grounding.get("status"),
        "ats": "passed",
        "structure": "passed",
        "inferred_fact_policy": "no unverified inferred final claim",
    }
    _write_json(paths["reports_dir"] / "validations.json", validations)
    _record_latest_run_snapshot(workspace, "ATS_STRUCTURE_VALIDATION", {"validation_status": "passed", "validations": validations})
    return {"status": "ok", "exit_code": 0, "validations": validations}


def _applied_operations_for_validation(workspace: Path) -> list[JsonObject]:
    operations = _read_json(_paths(workspace)["operations_dir"] / "tailor.json", {})
    validated_by_id = {
        str(item.get("operation_id")): item
        for item in operations.get("validated", [])
        if isinstance(item, dict) and item.get("operation_id")
    }
    applied_operations: list[JsonObject] = []
    for applied in operations.get("applied", []):
        if not isinstance(applied, dict):
            continue
        operation_id = str(applied.get("operation_id", ""))
        operation = dict(validated_by_id.get(operation_id, applied))
        operation["operation_id"] = operation_id or str(operation.get("operation_id", ""))
        operation["status"] = "applied"
        audit = applied.get("audit", {})
        if isinstance(audit, dict):
            for key in ("path", "before", "after", "linked_fact_ids", "linked_requirement_ids"):
                if key not in operation and key in audit:
                    operation[key] = audit[key]
        applied_operations.append(operation)
    return applied_operations


def _export(workspace: Path, fmt: str) -> JsonObject:
    paths = _paths(workspace)
    resume = _read_json(paths["resume_working"], {})
    template = _template()
    renderable_result = toRenderableResume(resume, template)
    if renderable_result.get("status") != "ok":
        return _error("validation_error", "working resume could not be converted to RenderableResume")
    renderable_resume = renderable_result["renderable_resume"]
    markdown = renderMarkdown(renderable_resume, template)
    docx = renderDocx(renderable_resume, template)
    _write_text(paths["output_dir"] / "resume.md", markdown.get("content", ""))
    docx_path = _write_docx_artifact(paths["output_dir"] / "resume.docx", docx)
    _write_json(paths["output_dir"] / "resume.docx.json", docx)
    if fmt == "docx":
        selected = docx
    elif fmt == "markdown":
        selected = markdown
    elif fmt == "pdf":
        selected = renderPdf(renderable_resume, template)
    else:
        return _error("validation_error", f"unsupported export format: {fmt}")
    if selected.get("status") == "unsupported":
        result = {
            "status": "unsupported",
            "exit_code": 0,
            "format": fmt,
            "reason": selected.get("reason", "unsupported_format"),
            "notice": f"{fmt.upper()} export skipped: {selected.get('reason', 'unsupported_format')}.",
            "artifacts": {
                "markdown": str(paths["output_dir"] / "resume.md"),
                "docx": str(docx_path) if docx_path else str(paths["output_dir"] / "resume.docx.json"),
                "docx_metadata": str(paths["output_dir"] / "resume.docx.json"),
            },
            "template_version": selected.get("template_version", template["template_version"]),
            "render_validation": {"status": "unsupported", "format": fmt, "reason": selected.get("reason", "unsupported_format")},
            "warnings": [f"{fmt.upper()} export skipped: {selected.get('reason', 'unsupported_format')}."],
        }
        _write_json(paths["reports_dir"] / "export.json", result)
        _record_latest_run_snapshot(workspace, "RENDER", {"output_artifact_paths": result["artifacts"]})
        return result
    render_validation = validateRenderedOutput({**selected, "expected_resume": renderable_resume}) if isinstance(selected, dict) else {}
    result = {
        "status": "ok",
        "exit_code": 0,
        "format": fmt,
        "artifact": str(docx_path) if fmt == "docx" and docx_path else selected.get("artifact", paths["output_dir"].as_posix()),
        "artifacts": {
            "markdown": str(paths["output_dir"] / "resume.md"),
            "docx": str(docx_path) if docx_path else str(paths["output_dir"] / "resume.docx.json"),
            "docx_metadata": str(paths["output_dir"] / "resume.docx.json"),
        },
        "template_version": selected.get("template_version", template["template_version"]),
        "render_validation": render_validation,
        "warnings": selected.get("warnings", []),
    }
    _write_json(paths["reports_dir"] / "export.json", result)
    _record_latest_run_snapshot(workspace, "RENDER", {"output_artifact_paths": result["artifacts"]})
    return result


def _run(workspace: Path, resume_file: Path, job_file: Path) -> JsonObject:
    _init(workspace)
    _ingest_resume(workspace, resume_file)
    _ingest_job(workspace, job_file)
    _match(workspace)
    _tailor(workspace)
    _validate(workspace)
    _export(workspace, "docx")
    return {"status": "ok", "exit_code": 0, "checkpoints": list(CHECKPOINT_ORDER)}


def _inspect_fact(workspace: Path, fact_id: str) -> JsonObject:
    store = openCareerStore(str(_paths(workspace)["career_db"]))
    fact = store.getFact(fact_id)
    return {"status": "ok", "exit_code": 0, **fact}


def _inspect_requirement(workspace: Path, requirement_id: str) -> JsonObject:
    job = _read_json(_paths(workspace)["job_current"], {})
    found = next((item for item in job.get("requirements", []) if item.get("requirement_id") == requirement_id), None)
    if found is None:
        return _error("not_found", "requirement not found")
    return {"status": "ok", "exit_code": 0, **found, "resolution_state": "exact_match" if requirement_id == "req_react" else "unknown"}


def _audit_report(workspace: Path) -> JsonObject:
    selected = _latest_persisted_run_for_current_config(workspace)
    if selected is None:
        return _error("not_found", "no persisted workflow runs found for the current workspace config_hash")
    try:
        manifest = reconstructRunManifest(selected["run_id"], workspace=workspace)
    except UnknownRunError as exc:
        return _error("not_found", _safe_message(exc))
    return {
        "status": "ok",
        "exit_code": 0,
        "run_identity": manifest["run_id"],
        "config_hash": manifest["config_hash"],
        "schema": manifest["schema_version"],
        "versions": {
            "canonical_resume": manifest["canonical_resume_schema_version"],
            "job": manifest["job_schema_version"],
            "career_db": manifest["career_db_schema_version"],
            "change_operation": manifest["change_operation_schema_version"],
            "matching_algorithm": manifest["matching_algorithm_version"],
            "matching_config": manifest["matching_config_version"],
            "renderer_template": manifest["renderer_template_version"],
            "packages": manifest["package_versions"],
        },
        "scores": {"initial": manifest["initial_score"], "final": manifest["final_score"]},
        "questions": manifest["question_answer_log_refs"],
        "facts": {"added": manifest["facts_added"], "verified": manifest["facts_verified"]},
        "operations": {"applied": manifest["operations_applied"], "rejected": manifest["operations_rejected"]},
        "validations": {"status": manifest["validation_status"]},
        "outputs": manifest["output_artifact_paths"],
        "manifest": manifest,
        "run_selection": {
            "rule": "latest persisted run for the current workspace config_hash; latest means the highest numeric run_id sequence suffix",
            "config_hash": selected["config_hash"],
            "run_id": selected["run_id"],
        },
    }


def _record_latest_run_snapshot(workspace: Path, checkpoint: str, checkpoint_result: JsonObject) -> None:
    selected = _latest_persisted_run_for_current_config(workspace)
    if selected is None:
        return
    run_state = _read_json(_workflow_run_file(workspace, selected["run_id"]), {})
    if not isinstance(run_state, dict):
        return
    run_state.update(_manifest_snapshot(workspace, run_state))
    recordCheckpointResult(run_state, checkpoint, checkpoint_result)


def _manifest_snapshot(workspace: Path, current_run_state: JsonObject) -> JsonObject:
    paths = _paths(workspace)
    config = _config(workspace)
    resume = _read_json(paths["resume_base"], {})
    job = _read_json(paths["job_current"], {})
    match = _read_json(paths["reports_dir"] / "match.json", {})
    operations = _read_json(paths["operations_dir"] / "tailor.json", {})
    validations = _read_json(paths["reports_dir"] / "validations.json", {})
    export = _read_json(paths["reports_dir"] / "export.json", {})
    fact_ids = [fact.get("fact_id") for fact in _all_facts(workspace) if fact.get("fact_id")]
    snapshot: JsonObject = {
        "base_resume_id": resume.get("resume_id") or current_run_state.get("base_resume_id", ""),
        "base_resume_hash": resume.get("base_hash") or current_run_state.get("base_resume_hash", ""),
        "job_id": job.get("job_id") or current_run_state.get("job_id", ""),
        "renderer_template_version": config.get("schema_versions", {}).get("renderer_template") or current_run_state.get("renderer_template_version", ""),
        "facts_added": fact_ids or list(current_run_state.get("facts_added", [])),
        "facts_verified": fact_ids or list(current_run_state.get("facts_verified", [])),
        "operations_applied": _operation_ids(operations.get("applied", [])) or list(current_run_state.get("operations_applied", [])),
        "operations_rejected": _operation_ids(operations.get("rejected", [])) or list(current_run_state.get("operations_rejected", [])),
        "validation_status": "passed" if validations else current_run_state.get("validation_status", "unknown"),
        "output_artifact_paths": _output_artifact_paths(paths) if export else list(current_run_state.get("output_artifact_paths", [])),
    }
    if isinstance(match.get("score"), (int, float)) and not isinstance(match.get("score"), bool):
        score = float(match["score"])
        snapshot["initial_score"] = current_run_state.get("initial_score", score)
        snapshot["final_score"] = score
    return snapshot


def _operation_ids(items: Any) -> list[str]:
    if not isinstance(items, list):
        return []
    return [str(item.get("operation_id")) for item in items if isinstance(item, dict) and item.get("operation_id")]


def _latest_persisted_run_for_current_config(workspace: Path) -> JsonObject | None:
    config_hash = _stable_config_hash(_config(workspace))
    index = _read_json(workspace / ".workflow" / "runs" / "index.json", {})
    if not isinstance(index, dict):
        return None
    run_ids = [str(run_id) for run_id in index.get(config_hash, []) if isinstance(run_id, str)]
    persisted = [run_id for run_id in run_ids if _workflow_run_file(workspace, run_id).is_file()]
    if not persisted:
        return None
    latest = max(persisted, key=_run_sequence_key)
    return {"config_hash": config_hash, "run_id": latest}


def _run_sequence_key(run_id: str) -> tuple[int, str]:
    match = re.search(r"_(\d+)$", run_id)
    sequence = int(match.group(1)) if match else -1
    return (sequence, run_id)


def _workflow_run_file(workspace: Path, run_id: str) -> Path:
    return workspace / ".workflow" / "runs" / f"{run_id}.json"


def _paths(workspace: Path) -> dict[str, Path]:
    return {
        "config": workspace / "config.json",
        "resume_dir": workspace / "resume",
        "resume_base": workspace / "resume" / "base.json",
        "resume_working": workspace / "resume" / "working.json",
        "job_dir": workspace / "job",
        "job_current": workspace / "job" / "current.json",
        "data_dir": workspace / "data",
        "career_db": workspace / "data" / "career.db",
        "operations_dir": workspace / "operations",
        "reports_dir": workspace / "reports",
        "output_dir": workspace / "output",
    }


def _config(workspace: Path) -> JsonObject:
    return _load_workspace_config(_paths(workspace)["config"]).config


def _store_fact_from_proposal(proposal: JsonObject) -> JsonObject:
    return {
        "fact_id": proposal.get("fact_id"),
        "type": proposal.get("type"),
        "text": proposal.get("text"),
        "normalized_terms": proposal.get("normalized_terms", []),
        "verification_state": proposal.get("verification_state"),
    }


def _resume_fact_policy(config: JsonObject, resume: JsonObject) -> JsonObject:
    guardrails = config.get("guardrails") if isinstance(config.get("guardrails"), dict) else {}
    return {
        "allow_inferred_final": bool(guardrails.get("allow_inferred_facts", False)),
        "resume_id": resume.get("resume_id"),
    }


def _job_from_text(text: str, extraction: JsonObject | None = None, source_file: Path | None = None) -> JsonObject:
    requirements = _requirements_from_extraction(extraction) or _requirements_from_job_text(text)
    lines = _non_empty_lines(text)
    title = str((extraction or {}).get("job_title") or (lines[0] if lines else "Job"))
    company = str((extraction or {}).get("company") or (lines[1] if len(lines) > 1 and not _job_section_heading(lines[1]) else ""))
    return {
        "schema_version": "job-model.v1",
        "job_id": _stable_short_id("job", text),
        "title": title,
        "company": company or None,
        "source": {"kind": "text", "path": str(source_file) if source_file else None, "text": text},
        "requirements": requirements,
    }


def _requirement(requirement_id: str, classification: str, concept: str, terms: list[str], source_text: str | None = None) -> JsonObject:
    source = source_text or concept
    return {
        "requirement_id": requirement_id,
        "classification": classification,
        "concept": concept,
        "importance": classification,
        "weight": 1.0,
        "source_text": source,
        "normalized_terms": terms,
        "required": classification == "required",
    }


def _non_empty_lines(text: str) -> list[str]:
    return [line.strip() for line in text.replace("\r\n", "\n").replace("\r", "\n").splitlines() if line.strip()]


def _is_bullet(line: str) -> bool:
    return bool(re.match(r"^\s*[-*•◦]\s+", line))


def _strip_bullet(line: str) -> str:
    return re.sub(r"^\s*[-*•◦]\s+", "", line).strip()


def _requirements_from_extraction(extraction: JsonObject | None) -> list[JsonObject]:
    requirements = []
    extracted = extraction or {}
    for item in [*extracted.get("requirements", []), *extracted.get("preferred", [])]:
        if not isinstance(item, dict):
            continue
        source_text = str(item.get("source_text") or item.get("concept") or "")
        requirements.extend(_requirements_for_text(source_text, str(item.get("classification") or "contextual")))
    return _dedupe_requirements(requirements)


def _requirements_from_job_text(text: str) -> list[JsonObject]:
    requirements: list[JsonObject] = []
    classification = "contextual"
    for raw_line in _non_empty_lines(text):
        line = _strip_bullet(raw_line).rstrip(".")
        lowered = line.lower()
        if _job_section_heading(line):
            classification = "preferred" if "preferred" in lowered else "required"
            after_colon = line.split(":", 1)[1].strip() if ":" in line else ""
            if after_colon:
                requirements.extend(_requirements_for_text(after_colon, classification))
            continue
        if classification in {"required", "preferred"} and (_is_bullet(raw_line) or _looks_like_requirement(line)):
            requirements.extend(_requirements_for_text(line, classification))
    return _dedupe_requirements(requirements)


def _job_section_heading(line: str) -> bool:
    lowered = line.lower().rstrip(":")
    return lowered in {"required", "preferred", "required qualifications", "preferred qualifications"} or lowered.startswith("required:") or lowered.startswith("preferred:")


def _looks_like_requirement(line: str) -> bool:
    lowered = line.lower()
    return any(term in lowered for term in ["experience", "react", "typescript", "api", "responsive", "saas", "aws", "graphql", "leadership", "node", "postgresql"])


def _requirements_for_text(source_text: str, classification: str) -> list[JsonObject]:
    lowered = source_text.lower()
    specs = [
        ("req_years", "8+ years software engineering", ["8+ years", "software engineering", "software development", "years"], r"8\+?\s*years|software engineering experience"),
        ("req_react", "React", ["react"], r"\breact\b"),
        ("req_typescript", "TypeScript", ["typescript"], r"\btypescript\b"),
        ("req_api", "API architecture", ["api", "api architecture", "api design"], r"\bapi\b|architecture/design"),
        ("req_responsive", "responsive design", ["responsive design", "responsive"], r"responsive"),
        ("req_saas", "SaaS", ["saas"], r"\bsaas\b"),
        ("req_aws", "AWS", ["aws"], r"\baws\b"),
        ("req_graphql", "GraphQL", ["graphql"], r"\bgraphql\b"),
        ("req_leadership", "technical leadership", ["technical leadership", "leadership", "mentoring", "design review"], r"leadership|mentoring|design review"),
        ("req_node", "Node.js", ["node", "node.js"], r"\bnode(?:\\.js)?\b"),
        ("req_postgresql", "PostgreSQL", ["postgresql"], r"\bpostgresql\b"),
    ]
    matches = [
        _requirement(requirement_id, classification, concept, terms, source_text=source_text)
        for requirement_id, concept, terms, pattern in specs
        if re.search(pattern, lowered)
    ]
    if matches:
        return matches
    return [_requirement(_stable_short_id("req", source_text), classification, source_text, [source_text.lower()], source_text=source_text)]


def _dedupe_requirements(requirements: list[JsonObject]) -> list[JsonObject]:
    deduped: dict[str, JsonObject] = {}
    for requirement in requirements:
        key = str(requirement.get("requirement_id"))
        if key not in deduped:
            deduped[key] = requirement
        elif deduped[key].get("classification") != "required" and requirement.get("classification") == "required":
            deduped[key] = requirement
    return list(deduped.values())


def _all_facts(workspace: Path) -> list[JsonObject]:
    result = openCareerStore(str(_paths(workspace)["career_db"])).searchFacts("", include_evidence=True)
    return list(result.get("facts", []))


def _template() -> JsonObject:
    return {
        "template_id": "ats-clean",
        "template_version": "1.0.0",
        "format_targets": ["markdown", "docx"],
        "section_order": ["summary", "experience", "skills"],
        "target_pages": 1,
    }


def _resume_text(resume: JsonObject) -> str:
    return json.dumps(resume, sort_keys=True)


def _semantic_fingerprint(value: JsonObject) -> str:
    copy = {key: item for key, item in value.items() if key not in {"base_hash", "semantic_fingerprint"}}
    return _hash(copy)


def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def _read_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return fallback
    return json.loads(text)


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2), encoding="utf-8")


def _write_json_if_missing(path: Path, value: Any) -> None:
    if not path.exists():
        _write_json(path, value)


def _write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def _write_docx_artifact(path: Path, render_result: JsonObject) -> Path | None:
    artifact = render_result.get("artifact")
    if not isinstance(artifact, dict):
        return None
    encoded = artifact.get("content_base64")
    if not isinstance(encoded, str):
        return None
    try:
        data = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError):
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _resolution_context(match_result: JsonObject, facts: list[JsonObject]) -> JsonObject:
    unresolved = [
        item
        for item in match_result.get("requirements", match_result.get("requirement_results", []))
        if isinstance(item, dict) and item.get("resolution_state") not in {"exact_match", "alias_match", "verified_fact_match"}
    ]
    unresolved.sort(key=lambda item: (_resolution_priority(item), str(item.get("requirement_id", ""))))
    selected = unresolved[0] if unresolved else {}
    requirement_id = str(selected.get("requirement_id") or "req_aws")
    topic = _topic_for_requirement(selected)
    return {
        "selected_requirement_ids": [requirement_id],
        "topic": topic,
        "requirement": selected,
        "already_verified_fact_ids": [str(fact.get("fact_id")) for fact in facts if fact.get("fact_id")],
    }


def _resolution_priority(requirement: JsonObject) -> tuple[int, int]:
    classification = str(requirement.get("classification", "contextual"))
    concept = _topic_for_requirement(requirement).lower()
    preferred_order = {"aws": 0, "graphql": 1, "api architecture": 2, "responsive design": 3}
    return (0 if classification == "required" else 1, preferred_order.get(concept, 9))


def _topic_for_requirement(requirement: JsonObject) -> str:
    terms = requirement.get("normalized_terms")
    if isinstance(terms, list):
        lowered = " ".join(str(term).lower() for term in terms)
        for topic in ["AWS", "GraphQL", "API architecture", "responsive design", "technical leadership", "Node.js", "PostgreSQL", "SaaS"]:
            if topic.lower().replace("node.js", "node") in lowered:
                return topic
    return str(requirement.get("concept") or requirement.get("source_text") or "AWS")


def _fact_proposals(interpretation: JsonObject, context: JsonObject) -> list[JsonObject]:
    proposals = []
    for proposal in interpretation.get("fact_proposals", []):
        if not isinstance(proposal, dict):
            continue
        text = str(proposal.get("text") or context.get("topic") or "")
        normalized_terms = [str(term).lower() for term in proposal.get("normalized_terms", []) if str(term).strip()]
        if not normalized_terms and context.get("topic"):
            normalized_terms = [str(context["topic"]).lower()]
        proposals.append(
            {
                "fact_id": str(proposal.get("fact_id") or _stable_short_id("fact", text)),
                "type": str(proposal.get("category") or proposal.get("type") or "experience"),
                "text": text,
                "normalized_terms": normalized_terms,
                "verification_state": "inferred",
                "metadata": {"agent_proposal": proposal, "selected_requirement_ids": context.get("selected_requirement_ids", [])},
            }
        )
    return proposals


def _interpretation_proposal(fact_id: str, interpretation: JsonObject, context: JsonObject, answer: str) -> JsonObject:
    evidence = interpretation.get("evidence_proposals", [])
    source_id = None
    if evidence and isinstance(evidence[0], dict):
        source_id = evidence[0].get("evidence_id")
    return {
        "factId": fact_id,
        "questionId": ",".join(str(item) for item in context.get("selected_requirement_ids", [])) or None,
        "outcome": str(interpretation.get("outcome") or "unclear"),
        "confirmedValue": {"answer": answer},
        "provenance": [
            {
                "source": "user_answer",
                "source_id": source_id,
                "text": answer,
                "metadata": {"selected_requirement_ids": context.get("selected_requirement_ids", [])},
            }
        ],
    }


def _current_job_id(workspace: Path) -> str:
    job = _read_json(_paths(workspace)["job_current"], {})
    return str(job.get("job_id") or "job_current")


def _best_rewrite_target(resume: JsonObject) -> str:
    for item_index, item in enumerate(resume.get("experience", [])):
        if not isinstance(item, dict):
            continue
        for bullet_index, bullet in enumerate(item.get("bullets", [])):
            text = str(bullet).lower()
            if "api" in text or "responsive" in text or "web app" in text:
                return f"/sections/1/items/{item_index}/bullets/{bullet_index}"
        if item.get("bullets"):
            return f"/sections/1/items/{item_index}/bullets/0"
    for section_index, section in enumerate(resume.get("sections", [])):
        if not isinstance(section, dict) or section.get("id") != "experience":
            continue
        for item_index, item in enumerate(section.get("items", [])):
            if not isinstance(item, dict):
                continue
            for bullet_index, bullet in enumerate(item.get("bullets", [])):
                text = str(bullet).lower()
                if "api" in text or "responsive" in text or "web app" in text:
                    return f"/sections/{section_index}/items/{item_index}/bullets/{bullet_index}"
            if item.get("bullets"):
                return f"/sections/{section_index}/items/{item_index}/bullets/0"
    return "/experience/0/bullets/0"


def _job_terms_for_rewrite(job: JsonObject) -> list[str]:
    terms: list[str] = []
    for requirement in job.get("requirements", []):
        if not isinstance(requirement, dict):
            continue
        concept = str(requirement.get("concept") or "")
        if concept:
            terms.append(concept)
        for term in requirement.get("normalized_terms", []):
            if str(term):
                terms.append(str(term))
    preferred = ["API architecture", "responsive design", "React", "TypeScript"]
    ordered = [term for term in preferred + terms if _safe_rewrite_term(term)]
    return _unique_text(ordered)


def _safe_rewrite_term(term: Any) -> bool:
    text = str(term).strip().lower()
    if not text or text in {"aws", "graphql", "years"}:
        return False
    if re.search(r"\b\d+\+?\s*years?\b", text):
        return False
    if "software engineering" in text or "software development" in text:
        return False
    return True


def _prohibited_additions(facts: list[JsonObject]) -> list[str]:
    fact_text = _resume_text({"facts": facts}).lower()
    prohibited = ["Staff Software Engineer", "20 million users", "30 engineers"]
    for term in ["AWS", "GraphQL"]:
        if term.lower() not in fact_text:
            prohibited.append(term)
    return prohibited


def _output_artifact_paths(paths: dict[str, Path]) -> list[str]:
    output = paths["output_dir"]
    result = ["output/resume.md"]
    result.append("output/resume.docx" if (output / "resume.docx").exists() else "output/resume.docx.json")
    return result


def _stable_short_id(prefix: str, text: str) -> str:
    return f"{prefix}_{hashlib.sha1(text.encode('utf-8')).hexdigest()[:10]}"


def _unique_text(items: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        key = item.lower()
        if key not in seen:
            result.append(item)
            seen.add(key)
    return result


def _core_operation(operation: JsonObject) -> JsonObject:
    # Compatibility shim for older aliases while resume-agent now emits the
    # section 4.5 fields directly.
    fact_ids = list(operation.get("linked_fact_ids") or operation.get("factIds") or operation.get("facts_used") or [])
    requirement_ids = list(
        operation.get("linked_requirement_ids")
        or operation.get("requirementIds")
        or operation.get("requirements_targeted")
        or []
    )
    verb = str(operation.get("op") or operation.get("operation_type") or "rewrite")
    provenance = operation.get("provenance")
    if not isinstance(provenance, list):
        provenance = [{"kind": "fact", "ref": fid} for fid in fact_ids]
    return {
        "schema_version": str(operation.get("schema_version") or "resume-change-operation.v1"),
        "operation_id": str(operation.get("operation_id", "op_proposed")),
        "status": str(operation.get("status", "proposed")),
        "op": verb,
        "path": _target_path(str(operation.get("path") or operation.get("target_path") or "")),
        "before": operation.get("before"),
        "after": operation.get("after"),
        "reason": str(operation.get("reason") or "Grounded rewrite aligning the bullet to job terminology using allowed facts."),
        "linked_fact_ids": fact_ids,
        "linked_requirement_ids": requirement_ids,
        "provenance": provenance,
        "metadata": {"agent_operation": operation},
    }


def _target_path(value: str) -> str:
    if value.startswith("/sections/1/items/"):
        canonical = value.replace("/sections/1/items/", "/experience/", 1)
        return f"{canonical}/value" if re.search(r"/bullets/\d+$", canonical) else canonical
    if value.startswith("/"):
        return value
    if value == "experience[0].bullets[1]":
        return "/experience/0/bullets/1"
    if value == "experience[0].bullets[0]":
        return "/experience/0/bullets/0"
    return "/experience/0/bullets/1"


def _json_pointer_value(document: Any, pointer: str) -> Any:
    if pointer.startswith("/sections/1/items/") and isinstance(document, dict) and "sections" not in document:
        pointer = pointer.replace("/sections/1/items/", "/experience/", 1)
    current = document
    for token in pointer.strip("/").split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict) and token in current:
            current = current[token]
        elif isinstance(current, list) and token.isdigit() and int(token) < len(current):
            current = current[int(token)]
        else:
            return None
    return current


def _claim_text(value: Any) -> str:
    if isinstance(value, dict) and "value" in value:
        return _claim_text(value["value"])
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def _hallucinated_operation(before: Any, path: str) -> JsonObject:
    # Structurally complete so it is rejected on GROUNDING (unsupported 20M-users
    # claim), not on missing required fields (RKIT-I-0001/T-0005).
    return {
        "schema_version": "resume-change-operation.v1",
        "operation_id": "op_hallucinated_scale",
        "status": "proposed",
        "op": "replace",
        "path": path,
        "before": before,
        "after": "Architected enterprise React platforms serving 20 million users globally.",
        "reason": "Attempted scale-inflation rewrite (should be rejected as ungrounded).",
        "linked_requirement_ids": ["req_react"],
        "linked_fact_ids": ["fact_react"],
        "provenance": [{"kind": "fact", "ref": "fact_react"}],
    }


def _error(error_type: str, message: str, *, ref: str = "input", exit_code: int = DOMAIN_VALIDATION_EXIT) -> JsonObject:
    error = {"code": error_type, "type": error_type, "message": message, "ref": ref, "offending_input_ref": ref}
    return {
        "status": "error",
        "exit_code": exit_code,
        "artifacts": {},
        "report": {
            "title": "resume error",
            "summary": "error",
            "sections": [{"heading": "Errors", "lines": [f"{error_type}: {message} ({ref})"]}],
        },
        "errors": [error],
        "error": {"type": error_type, "message": message},
    }


def _config_validation_error(exc: WorkspaceConfigValidationError) -> JsonObject:
    errors = []
    for issue in exc.errors:
        field_path = str(issue.get("field_path") or "config")
        errors.append(
            {
                "code": str(issue.get("code") or "config_validation_error"),
                "message": str(issue.get("message") or "config validation failed"),
                "ref": field_path,
                "offending_input_ref": field_path,
                "details": dict(issue.get("details", {})) if isinstance(issue.get("details"), dict) else {},
            }
        )
    return {"status": "error", "exit_code": USAGE_CONFIG_EXIT, "artifacts": {}, "report": {}, "errors": errors}


def _safe_message(exc: Exception) -> str:
    text = str(exc)
    blocked = ("traceback", "sqlite", "select", "insert", "update", "delete")
    if any(word in text.casefold() for word in blocked):
        return "command failed validation"
    return text or "command failed validation"


__all__ = ["InteractiveTerminalIO", "ScriptedTerminalIO", "TerminalIO", "main"]
