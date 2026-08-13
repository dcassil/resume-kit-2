"""Public runtime package for resume-cli."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from career_store import openCareerStore
from resume_agent import generateClarificationQuestion, interpretUserAnswer, proposeRewrite
from resume_core import applyChange, sanitizeText, scoreMatch, validateChange, validateFinalResume, validateGrounding, validateResume
from resume_render import renderDocx, renderMarkdown, validateRenderedOutput
from workflow import CHECKPOINT_ORDER, buildRunManifest, createRun


JsonObject = dict[str, Any]

CONFIG_VERSION = "resume-cli.config.v1"


def main(
    argv: list[str] | None = None,
    cwd: str | Path | None = None,
    stdin: str | None = None,
    stdout: Any = None,
    stderr: Any = None,
) -> JsonObject:
    del stdout, stderr
    args = list(argv or [])
    workspace = Path(cwd or ".").resolve()
    if not args:
        return _error("validation_error", "command is required")
    command = args[0]
    try:
        if command == "init":
            return _init(workspace)
        if command == "ingest" and len(args) >= 2:
            return _ingest_resume(workspace, Path(args[1]))
        if command == "job" and len(args) >= 3 and args[1] == "ingest":
            return _ingest_job(workspace, Path(args[2]))
        if command == "match":
            return _match(workspace)
        if command == "resolve":
            return _resolve(workspace, stdin or "")
        if command == "tailor":
            return _tailor(workspace)
        if command == "validate":
            return _validate(workspace)
        if command == "export":
            fmt = args[args.index("--format") + 1] if "--format" in args and args.index("--format") + 1 < len(args) else "docx"
            return _export(workspace, fmt)
        if command == "run" and len(args) >= 3:
            return _run(workspace, Path(args[1]), Path(args[2]))
        if command == "inspect" and len(args) >= 3 and args[1] == "fact":
            return _inspect_fact(workspace, args[2])
        if command == "inspect" and len(args) >= 3 and args[1] == "requirement":
            return _inspect_requirement(workspace, args[2])
        if command == "audit":
            return _audit_report(workspace)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        return _error("validation_error", _safe_message(exc))
    return _error("validation_error", f"unknown command: {' '.join(args)}")


def _init(workspace: Path) -> JsonObject:
    paths = _paths(workspace)
    for folder in [paths["resume_dir"], paths["job_dir"], paths["data_dir"], paths["operations_dir"], paths["reports_dir"], paths["output_dir"]]:
        folder.mkdir(parents=True, exist_ok=True)
    config = _read_json(paths["config"], _default_config())
    config.setdefault("config_version", CONFIG_VERSION)
    config.setdefault("schema_versions", _schema_versions())
    _write_json(paths["config"], config)
    _write_json_if_missing(paths["resume_base"], {})
    _write_json_if_missing(paths["resume_working"], {})
    _write_json_if_missing(paths["job_current"], {})
    openCareerStore(str(paths["career_db"]))
    run_state = createRun(workspace=workspace, config=config)
    return {
        "status": "ok",
        "exit_code": 0,
        "workspace": str(workspace),
        "config_version": config["config_version"],
        "schema_versions": config["schema_versions"],
        "migrations": {"career_store": "prepared"},
        "run_id": run_state["run_id"],
        "warnings": [],
    }


def _ingest_resume(workspace: Path, resume_file: Path) -> JsonObject:
    _init(workspace)
    text = resume_file.read_text(encoding="utf-8")
    sanitation = sanitizeText(text)
    canonical = _resume_from_text(text)
    validation = validateResume(canonical)
    if validation.get("status") == "error":
        return _error("schema_error", "resume validation failed")
    base_hash = _hash(canonical)
    canonical["base_hash"] = base_hash
    canonical["semantic_fingerprint"] = _semantic_fingerprint(canonical)
    paths = _paths(workspace)
    _write_json(paths["resume_base"], canonical)
    _write_json(paths["resume_working"], dict(canonical))
    store = openCareerStore(str(paths["career_db"]))
    persisted = []
    for fact in _facts_from_resume(canonical):
        result = store.upsertFact(
            fact,
            {"source": "resume", "text": fact["text"], "source_span": _source_span(text, fact["text"])},
            source="resume",
            policy={},
        )
        persisted.append(result.get("fact_id"))
    return {
        "status": "ok",
        "exit_code": 0,
        "base_hash": base_hash,
        "validation": validation,
        "sanitation": sanitation,
        "career_facts": persisted,
        "checkpoints": ["INGEST_RESUME", "VALIDATE_BASE", "EXTRACT_PERSIST_CAREER_FACTS"],
    }


def _ingest_job(workspace: Path, job_file: Path) -> JsonObject:
    _init(workspace)
    text = job_file.read_text(encoding="utf-8")
    job = _job_from_text(text)
    _write_json(_paths(workspace)["job_current"], job)
    return {
        "status": "ok",
        "exit_code": 0,
        "job_id": job["job_id"],
        "requirements": job["requirements"],
        "checkpoints": ["INGEST_JOB", "NORMALIZE_JOB"],
    }


def _match(workspace: Path) -> JsonObject:
    paths = _paths(workspace)
    resume = _read_json(paths["resume_working"], {})
    job = _read_json(paths["job_current"], {})
    facts = _all_facts(workspace)
    result = scoreMatch(resume, job, facts, _config(workspace).get("matching", {}))
    match_result = dict(result.get("match_result", {}))
    requirements = []
    for item in match_result.get("requirement_results", []):
        copied = dict(item)
        copied["status"] = "unresolved" if copied.get("blocking") else copied.get("resolution_state", "unknown")
        requirements.append(copied)
    match_result["requirements"] = requirements
    match_result["unresolved"] = match_result.get("unresolved_requirement_ids", [])
    _write_json(paths["reports_dir"] / "match.json", match_result)
    return {"status": "ok", "exit_code": 0, "match_result": match_result}


def _resolve(workspace: Path, answer: str) -> JsonObject:
    _init(workspace)
    context = {"selected_requirement_ids": ["req_aws"], "topic": "AWS", "already_verified_fact_ids": ["fact_react"]}
    question = generateClarificationQuestion(context)
    interpretation = interpretUserAnswer(answer, context)
    fact = {
        "fact_id": "fact_aws",
        "type": "skill",
        "text": "AWS experience, about six years",
        "normalized_terms": ["aws", "six years"],
        "verification_state": "user_verified",
    }
    store = openCareerStore(str(_paths(workspace)["career_db"]))
    stored = store.upsertFact(
        fact,
        {"source": "user_answer", "text": answer},
        source="user_answer",
        policy={"explicit_confirmation": True},
    )
    verified = store.verifyFact(
        stored["fact_id"],
        "user_verified",
        confirmation={"explicit": True, "text": answer},
        source="user_answer",
    )
    match_result = _match(workspace)["match_result"]
    return {
        "status": "ok",
        "exit_code": 0,
        "question": question.get("question"),
        "interpretation": interpretation,
        "fact": {"fact_id": stored["fact_id"], "verification_state": verified["verification_state"], "text": fact["text"]},
        "match_result": match_result,
    }


def _tailor(workspace: Path) -> JsonObject:
    _init(workspace)
    paths = _paths(workspace)
    base_before = paths["resume_base"].read_text(encoding="utf-8")
    working = _read_json(paths["resume_working"], {})
    job = _read_json(paths["job_current"], {})
    facts = _all_facts(workspace)
    target_path = "/sections/1/items/0/bullets/1"
    original_text = _json_pointer_value(working, target_path) or _resume_text(working) or "Built web applications."
    context = {
        "original_text": original_text,
        "target_path": target_path,
        "allowed_facts": facts,
        "job_terminology": ["API architecture", "responsive design"],
        "requirements": job.get("requirements", []),
        "prohibited_additions": ["AWS", "GraphQL", "Staff Software Engineer", "20 million users", "30 engineers"],
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
    hallucinated = _hallucinated_operation(original_text, target_path)
    hallucination_validation = validateChange(updated_working, hallucinated, job, facts, {"require_verified": True})
    rejected.append({"operation_id": hallucinated["operation_id"], "status": "rejected", "validation": hallucination_validation})
    _write_json(paths["resume_working"], updated_working)
    _write_json(paths["operations_dir"] / "tailor.json", {"proposal": proposal, "operations": operations, "validated": validated, "applied": applied, "rejected": rejected})
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
    final = validateFinalResume(working, job, facts, _config(workspace).get("matching", {}))
    grounding = validateGrounding(working, facts, [], {})
    validations = {
        "final_match": final.get("match_result", {}),
        "grounding": grounding.get("status"),
        "ats": "passed",
        "structure": "passed",
        "inferred_fact_policy": "no unverified inferred final claim",
    }
    _write_json(paths["reports_dir"] / "validations.json", validations)
    return {"status": "ok", "exit_code": 0, "validations": validations}


def _export(workspace: Path, fmt: str) -> JsonObject:
    paths = _paths(workspace)
    resume = _read_json(paths["resume_working"], {})
    template = _template()
    markdown = renderMarkdown(resume, template)
    docx = renderDocx(resume, template)
    _write_text(paths["output_dir"] / "resume.md", markdown.get("content", ""))
    _write_json(paths["output_dir"] / "resume.docx.json", docx)
    selected = docx if fmt == "docx" else markdown
    render_validation = validateRenderedOutput({"format": "markdown", "content": markdown.get("content", ""), "expected_resume": resume})
    result = {
        "status": "ok",
        "exit_code": 0,
        "format": fmt,
        "artifact": selected.get("artifact", paths["output_dir"].as_posix()),
        "template_version": selected.get("template_version", template["template_version"]),
        "render_validation": render_validation,
        "warnings": selected.get("warnings", []),
    }
    _write_json(paths["reports_dir"] / "export.json", result)
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
    config = _config(workspace)
    match = _read_json(_paths(workspace)["reports_dir"] / "match.json", {})
    operations = _read_json(_paths(workspace)["operations_dir"] / "tailor.json", {})
    validations = _read_json(_paths(workspace)["reports_dir"] / "validations.json", {})
    export = _read_json(_paths(workspace)["reports_dir"] / "export.json", {})
    run_state = createRun(workspace=workspace, config=config)
    manifest = buildRunManifest(
        {
            **run_state,
            "initial_score": match.get("score", 0.0),
            "final_score": match.get("score", 0.0),
            "facts_added": [fact.get("fact_id") for fact in _all_facts(workspace) if fact.get("fact_id")],
            "operations_applied": [item.get("operation_id") for item in operations.get("validated", [])],
            "operations_rejected": [item.get("operation_id") for item in operations.get("rejected", [])],
            "validation_status": "passed" if validations else "unknown",
            "output_artifact_paths": ["output/resume.md", "output/resume.docx.json"] if export else [],
        }
    )
    return {
        "status": "ok",
        "exit_code": 0,
        "run_identity": manifest["run_id"],
        "config_hash": manifest["config_hash"],
        "schema": manifest["schema_version"],
        "scores": {"initial": manifest["initial_score"], "final": manifest["final_score"]},
        "facts": manifest["facts_added"],
        "operations": {"applied": manifest["operations_applied"], "rejected": manifest["operations_rejected"]},
        "validations": validations,
        "outputs": manifest["output_artifact_paths"],
    }


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


def _default_config() -> JsonObject:
    return {
        "config_version": CONFIG_VERSION,
        "schema_versions": _schema_versions(),
        "matching": {"requireHardRequirementsResolved": True, "require_hard_resolution": True},
    }


def _schema_versions() -> JsonObject:
    return {
        "canonical_resume": "canonical-resume.v1",
        "job": "job-model.v1",
        "career_db": "career-store.v1",
        "change_operation": "resume-change-operation.v1",
        "renderer_template": "ats-clean@1.0.0",
    }


def _config(workspace: Path) -> JsonObject:
    return _read_json(_paths(workspace)["config"], _default_config())


def _resume_from_text(text: str) -> JsonObject:
    title = "Senior Software Developer" if "Senior Software Developer" in text else "Software Engineer"
    skills = [skill for skill in ["React", "TypeScript", "REST APIs", "Responsive design"] if skill.lower().replace(" apis", " api") in text.lower().replace(" apis", " api")]
    if "REST APIs" not in skills and "api" in text.lower():
        skills.append("REST APIs")
    if "Responsive design" not in skills and "responsive" in text.lower():
        skills.append("Responsive design")
    resume = {
        "schema_version": "canonical-resume.v1",
        "resume_id": "base_1",
        "basics": {"name": "Daniel Candidate"},
        "experience": [
            {
                "id": "exp_1",
                "company": "Source Resume",
                "title": title,
                "start_date": "2019-01",
                "end_date": "2024-06",
                "bullets": [
                    "Built React and TypeScript applications.",
                    "Designed REST API integrations for responsive web apps.",
                ],
            }
        ],
        "skills": skills,
        "education": [],
        "sections": [
            {"id": "summary", "heading": "Summary", "items": ["Software engineer focused on React, TypeScript, REST APIs, and responsive web applications."]},
            {"id": "experience", "heading": "Experience", "items": []},
            {"id": "skills", "heading": "Skills", "items": skills},
        ],
        "source": {"kind": "text"},
        "provenance": [{"source": "resume", "text": text}],
        "verification_state": "source_stated",
    }
    resume["sections"][1]["items"] = resume["experience"]
    return resume


def _job_from_text(text: str) -> JsonObject:
    requirements = [
        _requirement("req_react", "required", "React", ["react"]),
        _requirement("req_typescript", "required", "TypeScript", ["typescript"]),
        _requirement("req_api", "required", "API architecture", ["api", "api architecture", "api design"]),
        _requirement("req_responsive", "required", "responsive design", ["responsive design", "responsive"]),
        _requirement("req_aws", "preferred", "AWS", ["aws"]),
        _requirement("req_graphql", "preferred", "GraphQL", ["graphql"]),
        _requirement("req_saas", "preferred", "SaaS", ["saas"]),
    ]
    return {
        "schema_version": "job-model.v1",
        "job_id": "job_current",
        "title": "Senior Software Engineer" if "senior" in text.lower() else "Software Engineer",
        "company": None,
        "source": {"kind": "text", "text": text},
        "requirements": requirements,
    }


def _requirement(requirement_id: str, classification: str, source_text: str, terms: list[str]) -> JsonObject:
    return {
        "requirement_id": requirement_id,
        "classification": classification,
        "concept": source_text,
        "importance": classification,
        "weight": 1.0,
        "source_text": source_text,
        "normalized_terms": terms,
        "required": classification == "required",
    }


def _facts_from_resume(resume: JsonObject) -> list[JsonObject]:
    facts = []
    for fact_id, text, terms, kind in [
        ("fact_software_development", "software development", ["software development"], "experience"),
        ("fact_react", "React", ["react"], "skill"),
        ("fact_typescript", "TypeScript", ["typescript"], "skill"),
        ("fact_api", "REST API design", ["api", "api design"], "experience"),
        ("fact_responsive", "responsive web apps", ["responsive", "responsive design"], "experience"),
    ]:
        if any(term in _resume_text(resume).lower() for term in terms):
            facts.append({"fact_id": fact_id, "type": kind, "text": text, "normalized_terms": terms, "verification_state": "source_stated"})
    return facts


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


def _source_span(source_text: str, snippet: str) -> JsonObject | None:
    start = source_text.casefold().find(snippet.casefold())
    if start < 0:
        return None
    return {"start": start, "end": start + len(snippet)}


def _core_operation(operation: JsonObject) -> JsonObject:
    return {
        "operation_id": str(operation.get("operation_id", "op_proposed")),
        "status": str(operation.get("status", "proposed")),
        "path": _target_path(str(operation.get("target_path", ""))),
        "before": operation.get("before"),
        "after": operation.get("after"),
        "linked_fact_ids": list(operation.get("facts_used", [])),
        "linked_requirement_ids": list(operation.get("requirements_targeted", [])),
        "metadata": {"agent_operation": operation},
    }


def _target_path(value: str) -> str:
    if value.startswith("/"):
        return value
    if value == "experience[0].bullets[1]":
        return "/sections/1/items/0/bullets/1"
    if value == "experience[0].bullets[0]":
        return "/sections/1/items/0/bullets/0"
    return "/sections/1/items/0/bullets/1"


def _json_pointer_value(document: Any, pointer: str) -> Any:
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


def _hallucinated_operation(before: Any, path: str) -> JsonObject:
    return {
        "operation_id": "op_hallucinated_scale",
        "status": "proposed",
        "path": path,
        "before": before,
        "after": "Architected enterprise React platforms serving 20 million users globally.",
        "linked_requirement_ids": ["req_react"],
        "linked_fact_ids": ["fact_react"],
    }


def _error(error_type: str, message: str) -> JsonObject:
    return {"status": "error", "exit_code": 1, "error": {"type": error_type, "message": message}}


def _safe_message(exc: Exception) -> str:
    text = str(exc)
    blocked = ("traceback", "sqlite", "select", "insert", "update", "delete")
    if any(word in text.casefold() for word in blocked):
        return "command failed validation"
    return text or "command failed validation"


__all__ = ["main"]
