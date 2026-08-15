"""Public runtime package for workflow."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .schemas import RUN_MANIFEST_SCHEMA, SCHEMAS, Checkpoint, RunManifest
from .versions import collectVersions


JsonObject = dict[str, Any]

CHECKPOINT_ORDER = [checkpoint.value for checkpoint in Checkpoint]

_ADVANCE_REQUIREMENTS: dict[str, tuple[str, ...]] = {
    "INGEST_RESUME": ("config_validated",),
    "VALIDATE_BASE": ("canonical_resume_exists",),
    "EXTRACT_PERSIST_CAREER_FACTS": ("base_validation",),
    "INGEST_JOB": ("career_facts_persisted",),
    "NORMALIZE_JOB": ("job_ingested",),
    "MATCH_BASE": ("job_normalized",),
    "RESOLVE_GAPS": ("match_result",),
    "BUILD_SELECTION_PLAN": ("gaps_resolved",),
    "PROPOSE_TAILORING_CHANGES": ("selection_plan",),
    "VALIDATE_CHANGES": ("proposed_operations",),
    "APPLY_CHANGES": ("change_validation",),
    "FINAL_MATCH": ("operations_applied",),
    "GROUNDING_AUDIT": ("final_match",),
    "ATS_STRUCTURE_VALIDATION": ("grounding_audit",),
    "RENDER": ("ats_structure_validation",),
    "RENDER_VALIDATION": ("render_result",),
    "COMPLETE": ("render_validation", "audit_manifest_ref"),
}


class RunManifestValidationError(ValueError):
    """Raised when an assembled run manifest violates the manifest schema."""

    def __init__(self, errors: list[JsonObject]) -> None:
        self.errors = errors
        summary = "; ".join(
            f"{error.get('field_path', '<root>')}: {error.get('message', error.get('code', 'invalid'))}"
            for error in errors[:3]
        )
        if len(errors) > 3:
            summary = f"{summary}; ... {len(errors) - 3} more"
        super().__init__(f"Run manifest validation failed: {summary}")


def createRun(workspace: str | Path, config: JsonObject) -> JsonObject:
    workspace_path = Path(workspace)
    config_hash = _stable_hash(config)
    run_id = _new_run_id(workspace_path, config_hash)
    versions = collectVersions(workspace=workspace_path, config=config)
    run_state = {
        "run_id": run_id,
        "workspace": str(workspace_path),
        "current_checkpoint": "INIT",
        "config_hash": config_hash,
        "schema_versions": dict(versions["schema_versions"]),
        "package_versions": dict(versions["package_versions"]),
        "careerDbVersion": dict(versions["careerDbVersion"]),
        "stage_state": {},
        "recovery_markers": [],
        "operation_log_refs": [],
        "question_answer_log_refs": [],
        "unresolved_requirements": [],
        "validation_refs": [],
        "render_refs": [],
        "audit_events": [],
        "already_applied_operations": [],
        "already_asked_questions": [],
        "already_written_facts": [],
    }
    _persist_run(run_state)
    _index_run(workspace_path, config_hash, run_id)
    return run_state


def getNextCheckpoint(run_state: JsonObject) -> JsonObject:
    current = str(run_state.get("current_checkpoint", "INIT"))
    if current == "RESOLVE_GAPS" and run_state.get("facts_verified"):
        next_checkpoint = "MATCH_BASE"
    elif current in CHECKPOINT_ORDER:
        index = CHECKPOINT_ORDER.index(current)
        next_checkpoint = CHECKPOINT_ORDER[min(index + 1, len(CHECKPOINT_ORDER) - 1)]
    else:
        next_checkpoint = "INIT"
    return {
        "status": "ok",
        "current_checkpoint": current,
        "next_checkpoint": next_checkpoint,
        "required_inputs": list(_ADVANCE_REQUIREMENTS.get(next_checkpoint, ())),
        "blocking_reasons": [],
        "determinism_key": _stable_hash({"current": current, "next": next_checkpoint, "policy": run_state.get("policy", {})}),
    }


def advanceCheckpoint(run_state: JsonObject, target_checkpoint: str, evidence: JsonObject) -> JsonObject:
    current = str(run_state.get("current_checkpoint", "INIT"))
    expected = getNextCheckpoint(run_state)["next_checkpoint"]
    blocking_reasons: list[str] = []
    if target_checkpoint != expected:
        blocking_reasons.append(f"expected {expected} after {current}")
    for required in _ADVANCE_REQUIREMENTS.get(target_checkpoint, ()):
        if not _evidence_present(evidence, required):
            blocking_reasons.append(f"missing evidence: {required}")
    if target_checkpoint == "EXTRACT_PERSIST_CAREER_FACTS" and evidence.get("base_validation") != "passed":
        blocking_reasons.append("base validation must pass")
    if target_checkpoint == "COMPLETE":
        complete = assertCanComplete({**run_state, **evidence})
        if not complete["can_complete"]:
            blocking_reasons.extend(complete["failed_gates"])
    if blocking_reasons:
        return {
            "status": "blocked",
            "previous_checkpoint": current,
            "current_checkpoint": current,
            "transition_evidence": dict(evidence),
            "audit_event": _audit("advanceCheckpoint", current, target_checkpoint, False),
            "blocking_reasons": sorted(set(blocking_reasons)),
        }
    updated = {
        **run_state,
        "current_checkpoint": target_checkpoint,
        "stage_state": {**run_state.get("stage_state", {}), target_checkpoint: dict(evidence)},
    }
    updated.setdefault("audit_events", []).append(_audit("advanceCheckpoint", current, target_checkpoint, True))
    _persist_run(updated)
    return {
        "status": "ok",
        "previous_checkpoint": current,
        "current_checkpoint": target_checkpoint,
        "transition_evidence": dict(evidence),
        "audit_event": updated["audit_events"][-1],
        "blocking_reasons": [],
    }


def recordCheckpointResult(run_state: JsonObject, checkpoint: str, result: JsonObject) -> JsonObject:
    checkpoint_result = dict(result)
    _extend_unique(run_state, "facts_verified", checkpoint_result.get("facts_verified", []))
    _extend_unique(run_state, "facts_added", checkpoint_result.get("facts_added", []))
    _extend_unique(run_state, "operations_applied", checkpoint_result.get("operations_applied", []))
    _extend_unique(run_state, "operations_rejected", checkpoint_result.get("operations_rejected", []))
    _extend_unique(run_state, "already_applied_operations", checkpoint_result.get("operations_applied", []))
    _extend_unique(run_state, "already_asked_questions", checkpoint_result.get("question_answer_log_refs", []))
    _extend_unique(run_state, "already_written_facts", checkpoint_result.get("facts_verified", []) + checkpoint_result.get("facts_added", []))
    operation_refs = [f"operations/{item}.json" for item in checkpoint_result.get("operations_applied", [])]
    question_refs = list(checkpoint_result.get("question_answer_log_refs", []))
    validation_refs = [f"validations/{checkpoint}.json"] if "validation" in json.dumps(checkpoint_result, sort_keys=True).casefold() else []
    render_refs = [f"render/{checkpoint}.json"] if "render" in json.dumps(checkpoint_result, sort_keys=True).casefold() else []
    _extend_unique(run_state, "operation_log_refs", operation_refs)
    _extend_unique(run_state, "question_answer_log_refs", question_refs)
    _extend_unique(run_state, "validation_refs", validation_refs)
    _extend_unique(run_state, "render_refs", render_refs)
    event = _audit("recordCheckpointResult", checkpoint, checkpoint, True)
    run_state.setdefault("audit_events", []).append(event)
    _persist_run(run_state)
    return {
        "status": "ok",
        "checkpoint": checkpoint,
        "artifact_refs": [f"workflow/{checkpoint}.json"],
        "operation_log_refs": operation_refs,
        "question_answer_log_refs": question_refs,
        "validation_refs": validation_refs,
        "render_refs": render_refs,
        "audit_event": event,
    }


def buildRunManifest(run_state: JsonObject) -> JsonObject:
    versions = collectVersions(workspace=run_state.get("workspace"), run_state=run_state)
    schema_versions = versions["schema_versions"]
    manifest = {
        "run_id": run_state.get("run_id", ""),
        "base_resume_id": run_state.get("base_resume_id", ""),
        "base_resume_hash": run_state.get("base_resume_hash", ""),
        "job_id": run_state.get("job_id", ""),
        "config_hash": run_state.get("config_hash", ""),
        "canonical_resume_schema_version": schema_versions["canonical_resume"],
        "job_schema_version": schema_versions["job"],
        "career_db_schema_version": schema_versions["career_db"],
        "careerDbVersion": dict(versions["careerDbVersion"]),
        "change_operation_schema_version": schema_versions["change_operation"],
        "matching_algorithm_version": versions["matching_algorithm_version"],
        "matching_config_version": versions["matching_config_version"],
        "renderer_template_version": run_state.get("renderer_template_version", ""),
        "agent_model_config": run_state.get("agent_model_config", {}),
        "initial_score": run_state.get("initial_score", 0.0),
        "final_score": run_state.get("final_score", 0.0),
        "facts_added": list(run_state.get("facts_added", [])),
        "facts_verified": list(run_state.get("facts_verified", [])),
        "operations_applied": list(run_state.get("operations_applied", [])),
        "operations_rejected": list(run_state.get("operations_rejected", [])),
        "validation_status": run_state.get("validation_status", "unknown"),
        "output_artifact_paths": list(run_state.get("output_artifact_paths", [])),
        "question_answer_log_refs": list(run_state.get("question_answer_log_refs", [])),
        "unresolved_requirements": [dict(requirement) for requirement in run_state.get("unresolved_requirements", [])],
        "schema_version": RUN_MANIFEST_SCHEMA["schema_version"],
        "package_versions": dict(versions["package_versions"]),
        "recovery_markers": list(run_state.get("recovery_markers", [])),
        "audit_refs": list(run_state.get("audit_refs", [])),
    }
    _validate_run_manifest(manifest)
    return manifest


def recoverRun(workspace: str | Path, run_id: str) -> JsonObject:
    saved = _run_path(Path(workspace), run_id)
    run_state = json.loads(saved.read_text(encoding="utf-8")) if saved.exists() else {"run_id": run_id, "current_checkpoint": "INIT"}
    current = str(run_state.get("current_checkpoint", "INIT"))
    required_reruns = ["FINAL_MATCH"] if current in {"APPLY_CHANGES", "FINAL_MATCH", "GROUNDING_AUDIT", "ATS_STRUCTURE_VALIDATION", "RENDER"} else []
    return {
        "status": "ok",
        "run_id": run_id,
        "resume_from_checkpoint": current,
        "already_applied_operations": _dedupe(run_state.get("already_applied_operations", run_state.get("operations_applied", []))),
        "already_asked_questions": _dedupe(run_state.get("already_asked_questions", [])),
        "already_written_facts": _dedupe(run_state.get("already_written_facts", run_state.get("facts_verified", []))),
        "required_reruns": required_reruns,
        "transactional_integrity": "valid",
    }


def assertCanComplete(run_state: JsonObject) -> JsonObject:
    required_gates = {
        "final_match": _status_is_passed(run_state.get("final_match")),
        "grounding_audit": _status_is_passed(run_state.get("grounding_audit")),
        "ats_structure_validation": _status_is_passed(run_state.get("ats_structure_validation")),
        "render_validation": _status_is_passed(run_state.get("render_validation")),
        "audit_manifest_ref": bool(run_state.get("audit_manifest_ref")),
    }
    if run_state.get("unresolved_hard_requirements") and run_state.get("policy", {}).get("requireHardRequirementsResolved", True):
        required_gates["unresolved_hard_requirements"] = False
    failed = [gate for gate, passed in required_gates.items() if not passed]
    return {
        "status": "ok" if not failed else "blocked",
        "can_complete": not failed,
        "required_gates": list(required_gates),
        "failed_gates": failed,
        "audit_manifest_ref": run_state.get("audit_manifest_ref"),
    }


def _run_path(workspace: Path, run_id: str) -> Path:
    return workspace / ".workflow" / "runs" / f"{run_id}.json"


def _new_run_id(workspace: Path, config_hash: str) -> str:
    # config_hash stays a manifest field; identity must be unique per createRun
    # so same-config runs persist side by side (RKIT-I-0022 requirement 1).
    prefix = f"run_{config_hash[:16]}"
    runs_dir = workspace / ".workflow" / "runs"
    existing = {path.stem for path in runs_dir.glob(f"{prefix}*.json")} if runs_dir.exists() else set()
    sequence = len(existing) + 1
    run_id = f"{prefix}_{sequence:04d}"
    while run_id in existing:
        sequence += 1
        run_id = f"{prefix}_{sequence:04d}"
    return run_id


def _index_run(workspace: Path, config_hash: str, run_id: str) -> None:
    index_path = workspace / ".workflow" / "runs" / "index.json"
    index: JsonObject = {}
    if index_path.exists():
        try:
            index = json.loads(index_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            index = {}
    if not isinstance(index, dict):
        index = {}
    run_ids = list(index.get(config_hash, []))
    if run_id not in run_ids:
        run_ids.append(run_id)
    index[config_hash] = run_ids
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(json.dumps(index, sort_keys=True, indent=2), encoding="utf-8")


def _persist_run(run_state: JsonObject) -> None:
    workspace = run_state.get("workspace")
    if not workspace:
        return
    path = _run_path(Path(workspace), str(run_state["run_id"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_jsonable(run_state), sort_keys=True, indent=2), encoding="utf-8")


def _stable_hash(value: Any) -> str:
    payload = json.dumps(_jsonable(value), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _validate_run_manifest(manifest: JsonObject) -> None:
    errors = _schema_errors(manifest, RUN_MANIFEST_SCHEMA, "")
    if errors:
        raise RunManifestValidationError(errors)


def _schema_errors(value: Any, schema: JsonObject, field_path: str) -> list[JsonObject]:
    errors: list[JsonObject] = []

    one_of = schema.get("oneOf")
    if isinstance(one_of, list):
        if any(not _schema_errors(value, subschema, field_path) for subschema in one_of if isinstance(subschema, dict)):
            return []
        return [_issue("one_of", "Value must match exactly one allowed schema.", field_path)]

    forbidden = schema.get("not")
    if isinstance(forbidden, dict) and not _schema_errors(value, forbidden, field_path):
        errors.append(_issue("forbidden_value", "Value must not use a placeholder value.", field_path, {"value": value}))

    enum_values = schema.get("enum")
    if isinstance(enum_values, list) and value not in enum_values:
        errors.append(_issue("invalid_enum", "Value is not one of the allowed values.", field_path, {"allowed": enum_values}))

    expected_type = schema.get("type")
    if isinstance(expected_type, str) and not _matches_type(value, expected_type):
        errors.append(_issue("invalid_type", f"Expected {expected_type}.", field_path, {"actual": type(value).__name__}))
        return errors

    min_length = schema.get("minLength")
    if isinstance(min_length, int) and isinstance(value, str) and len(value) < min_length:
        errors.append(_issue("min_length", f"Expected at least {min_length} character(s).", field_path))

    if expected_type == "object" and isinstance(value, dict):
        for field_name in schema.get("required", []):
            if isinstance(field_name, str) and field_name not in value:
                errors.append(_issue("missing_field", f"RunManifest requires {field_name}.", _join_path(field_path, field_name)))
        properties = schema.get("properties", {})
        if isinstance(properties, dict):
            for field_name, field_schema in properties.items():
                if field_name in value and isinstance(field_schema, dict):
                    errors.extend(_schema_errors(value[field_name], field_schema, _join_path(field_path, field_name)))
        additional_schema = schema.get("additionalProperties")
        if isinstance(additional_schema, dict):
            known = set(properties) if isinstance(properties, dict) else set()
            for field_name, item in value.items():
                if field_name not in known:
                    errors.extend(_schema_errors(item, additional_schema, _join_path(field_path, str(field_name))))

    if expected_type == "array" and isinstance(value, list):
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                errors.extend(_schema_errors(item, item_schema, _join_path(field_path, str(index))))

    return errors


def _matches_type(value: Any, expected_type: str) -> bool:
    if expected_type == "object":
        return isinstance(value, dict)
    if expected_type == "array":
        return isinstance(value, list)
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected_type == "boolean":
        return isinstance(value, bool)
    if expected_type == "null":
        return value is None
    return True


def _issue(code: str, message: str, field_path: str, details: JsonObject | None = None) -> JsonObject:
    issue: JsonObject = {"code": code, "message": message, "severity": "error"}
    if field_path:
        issue["field_path"] = field_path
    if details:
        issue["details"] = details
    return issue


def _join_path(parent: str, child: str) -> str:
    return f"{parent}/{child}" if parent else child


def _jsonable(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(item) for item in value]
    return value


def _evidence_present(evidence: JsonObject, key: str) -> bool:
    value = evidence.get(key)
    if key == "base_validation":
        return value == "passed"
    if isinstance(value, bool):
        return value
    return value not in (None, "", [], {})


def _extend_unique(target: JsonObject, key: str, values: list[str]) -> None:
    target[key] = _dedupe(list(target.get(key, [])) + list(values or []))


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value)
        if text not in seen:
            seen.add(text)
            result.append(text)
    return result


def _audit(operation: str, previous: str, current: str, accepted: bool) -> JsonObject:
    return {
        "operation": operation,
        "previous_checkpoint": previous,
        "current_checkpoint": current,
        "accepted": accepted,
    }


def _status_is_passed(value: Any) -> bool:
    return isinstance(value, dict) and value.get("status") == "passed"

__all__ = [
    "RUN_MANIFEST_SCHEMA",
    "SCHEMAS",
    "Checkpoint",
    "RunManifest",
    "RunManifestValidationError",
    "createRun",
    "getNextCheckpoint",
    "advanceCheckpoint",
    "recordCheckpointResult",
    "buildRunManifest",
    "recoverRun",
    "assertCanComplete",
]
