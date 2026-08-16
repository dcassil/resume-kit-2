"""Public runtime package for workflow."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Callable

from .config import resolve_workflow_config as _resolve_workflow_config
from .resolution_loop import (
    empty_resolution_loop_state as _empty_resolution_loop_state,
    normalize_resolution_loop_state as _normalize_resolution_loop_state,
    resolution_loop_decision as _resolution_loop_decision,
    resolution_loop_surface as _resolution_loop_surface,
    update_resolution_loop_state as _update_resolution_loop_state,
)
from .render_overflow import (
    empty_render_overflow_state as _empty_render_overflow_state,
    mark_render_overflow_consumed as _mark_render_overflow_consumed,
    normalize_render_overflow_state as _normalize_render_overflow_state,
    record_render_overflow_result as _record_render_overflow_result,
    render_overflow_completion_gate_passed as _render_overflow_completion_gate_passed,
    render_overflow_completion_reason as _render_overflow_completion_reason,
    render_overflow_decision as _render_overflow_decision,
)
from .recovery import recover_run as _recover_run
from .schemas import RUN_MANIFEST_SCHEMA, SCHEMAS, Checkpoint, RunManifest
from .versions import collectVersions


JsonObject = dict[str, Any]

CHECKPOINT_ORDER = [checkpoint.value for checkpoint in Checkpoint]

_ADVANCE_REQUIREMENTS: dict[str, tuple[JsonObject, ...]] = {
    "INGEST_RESUME": ({"name": "config_validated", "kind": "dto", "schema_id": "WorkflowStatusEvidence"},),
    "VALIDATE_BASE": ({"name": "canonical_resume_exists", "kind": "artifact"},),
    "EXTRACT_PERSIST_CAREER_FACTS": ({"name": "base_validation", "kind": "dto", "schema_id": "WorkflowStatusEvidence"},),
    "INGEST_JOB": ({"name": "career_facts_persisted", "kind": "artifact"},),
    "NORMALIZE_JOB": ({"name": "job_ingested", "kind": "artifact"},),
    "MATCH_BASE": ({"name": "job_normalized", "kind": "dto", "schema_id": "WorkflowStatusEvidence"},),
    "RESOLVE_GAPS": ({"name": "match_result", "kind": "dto", "schema_id": "MatchResultEvidence"},),
    "BUILD_SELECTION_PLAN": ({"name": "selection_plan", "kind": "artifact"},),
    "PROPOSE_TAILORING_CHANGES": (
        {"name": "proposed_operations", "kind": "run_state", "key": "operation_statuses", "statuses": ["proposed"]},
    ),
    "VALIDATE_CHANGES": (
        {"name": "validated_operations", "kind": "run_state", "key": "operation_statuses", "statuses": ["validated"]},
    ),
    "APPLY_CHANGES": (
        {"name": "applied_operations", "kind": "run_state", "key": "operation_statuses", "statuses": ["applied"]},
    ),
    "FINAL_MATCH": ({"name": "match_report", "kind": "artifact"},),
    "GROUNDING_AUDIT": ({"name": "grounding_audit", "kind": "artifact"},),
    "ATS_STRUCTURE_VALIDATION": ({"name": "ats_report", "kind": "artifact"},),
    "RENDER": (
        {"name": "render_output", "kind": "artifact"},
        {"name": "measure_layout", "kind": "artifact"},
    ),
    "RENDER_VALIDATION": ({"name": "render_validation_report", "kind": "artifact"},),
    "COMPLETE": ({"name": "audit_ref", "kind": "artifact"},),
}

_COMPLETION_ARTIFACT_GATES: dict[str, JsonObject] = {
    "final_match": {"checkpoint": "FINAL_MATCH", "name": "match_report", "state_keys": ["match_report_ref", "final_match_ref"]},
    "grounding": {"checkpoint": "GROUNDING_AUDIT", "name": "grounding_audit", "state_keys": ["grounding_audit_ref", "grounding_ref"]},
    "ats": {"checkpoint": "ATS_STRUCTURE_VALIDATION", "name": "ats_report", "state_keys": ["ats_report_ref", "ats_ref"]},
    "render_validation": {
        "checkpoint": "RENDER_VALIDATION",
        "name": "render_validation_report",
        "state_keys": ["render_validation_report_ref", "render_validation_ref"],
    },
    "audit_ref": {"checkpoint": "COMPLETE", "name": "audit_ref", "state_keys": ["audit_ref", "audit_manifest_ref"]},
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


class UnknownRunError(FileNotFoundError):
    """Raised when persisted state for a requested run id does not exist."""

    def __init__(self, run_id: str, workspace: str | Path) -> None:
        self.run_id = run_id
        self.workspace = str(workspace)
        super().__init__(f"Unknown workflow run_id {run_id!r} under workspace {self.workspace!r}.")


def createRun(workspace: str | Path, config: JsonObject) -> JsonObject:
    workspace_path = Path(workspace)
    config_hash = _stable_hash(config)
    run_id = _new_run_id(workspace_path, config_hash)
    versions = collectVersions(workspace=workspace_path, config=config)
    workflow_config = _resolve_workflow_config(config)
    run_state = {
        "run_id": run_id,
        "workspace": str(workspace_path),
        "current_checkpoint": "INIT",
        "config_hash": config_hash,
        "schema_versions": dict(versions["schema_versions"]),
        "package_versions": dict(versions["package_versions"]),
        "careerDbVersion": dict(versions["careerDbVersion"]),
        "matching_algorithm_version": versions["matching_algorithm_version"],
        "matching_config_version": versions["matching_config_version"],
        "stage_state": {},
        "recovery_markers": [],
        "operation_log_refs": [],
        "question_answer_log_refs": [],
        "unresolved_requirements": [],
        "validation_refs": [],
        "render_refs": [],
        "audit_events": [],
        "operation_statuses": [],
        "already_applied_operations": [],
        "already_asked_questions": [],
        "already_written_facts": [],
        "last_match_fact_watermark": [],
        "resolution_loop_state": _empty_resolution_loop_state(),
        "resolution_blocking_reasons": [],
        "workflow_config": workflow_config.config.to_dict(),
        "workflow_config_errors": list(workflow_config.errors),
        "workflow_config_warnings": list(workflow_config.warnings),
        "overflow_iteration": 0,
        "render_overflow_state": _empty_render_overflow_state(),
        "render_overflow_blocking_reasons": [],
    }
    _persist_run(run_state)
    _index_run(workspace_path, config_hash, run_id)
    return run_state


def getNextCheckpoint(run_state: JsonObject) -> JsonObject:
    working_state = _working_run_state(run_state)
    current = str(working_state.get("current_checkpoint", "INIT"))
    resolution_decision = _resolution_loop_decision(working_state) if current == "RESOLVE_GAPS" else _resolution_loop_surface(working_state)
    render_overflow_decision = _render_overflow_decision(working_state)
    if current == "RESOLVE_GAPS" and resolution_decision["predicate"]["action"] == "rerun_match":
        next_checkpoint = "MATCH_BASE"
    elif current == "RESOLVE_GAPS" and resolution_decision["predicate"]["action"] == "select_next_topic":
        next_checkpoint = "RESOLVE_GAPS"
    elif current == "RESOLVE_GAPS" and resolution_decision["predicate"]["action"] == "blocked":
        next_checkpoint = "RESOLVE_GAPS"
    elif current == "RENDER" and render_overflow_decision["predicate"]["action"] == "loop_back":
        next_checkpoint = "BUILD_SELECTION_PLAN"
    elif current == "RENDER" and render_overflow_decision["predicate"]["action"] == "blocked":
        next_checkpoint = "RENDER"
    elif current in CHECKPOINT_ORDER:
        index = CHECKPOINT_ORDER.index(current)
        next_checkpoint = CHECKPOINT_ORDER[min(index + 1, len(CHECKPOINT_ORDER) - 1)]
    else:
        next_checkpoint = "INIT"
    if current == next_checkpoint == "RESOLVE_GAPS":
        required_inputs = []
        blocking_reasons = list(resolution_decision["predicate"]["blocking_reasons"])
    elif current == next_checkpoint == "RENDER" and render_overflow_decision["predicate"]["action"] == "blocked":
        required_inputs = []
        blocking_reasons = list(render_overflow_decision["predicate"]["blocking_reasons"])
    else:
        required_inputs = _required_input_names(working_state, next_checkpoint)
        blocking_reasons = _blocking_reasons_for(working_state, next_checkpoint)
    status = "blocked" if resolution_decision["predicate"]["action"] == "blocked" or render_overflow_decision["predicate"]["action"] == "blocked" else "ok"
    return {
        "status": status,
        "current_checkpoint": current,
        "next_checkpoint": next_checkpoint,
        "required_inputs": required_inputs,
        "blocking_reasons": blocking_reasons,
        "resolution_loop": resolution_decision,
        "render_overflow": render_overflow_decision,
        "determinism_key": _stable_hash(
            {
                "current": current,
                "next": next_checkpoint,
                "policy": working_state.get("policy", {}),
                "resolution_loop": resolution_decision["predicate"],
                "render_overflow": render_overflow_decision["predicate"],
            }
        ),
    }


def advanceCheckpoint(run_state: JsonObject, target_checkpoint: str, evidence: JsonObject, clock: Callable[[], str] | None = None) -> JsonObject:
    working_state = _working_run_state(run_state)
    current = str(working_state.get("current_checkpoint", "INIT"))
    checkpoint_plan = getNextCheckpoint(working_state)
    expected = checkpoint_plan["next_checkpoint"]
    blocking_reasons: list[str] = []
    evidence_errors: list[JsonObject] = []
    verified_evidence: JsonObject = {}
    if target_checkpoint != expected:
        blocking_reasons.append(f"expected {expected} after {current}")
    if current == target_checkpoint == "RESOLVE_GAPS":
        blocking_reasons.append("resolution_loop_pending_topic")
    for requirement in _advance_requirements(working_state, target_checkpoint):
        required_name = str(requirement["name"])
        result = _verify_evidence_ref(working_state, requirement, evidence.get(required_name))
        if result.get("status") != "ok":
            blocking_reasons.append(required_name)
            evidence_errors.append(result)
        else:
            verified_evidence[required_name] = result["evidence_ref"]
    if target_checkpoint == "COMPLETE":
        complete = assertCanComplete(_completion_gate_state(working_state, verified_evidence))
        if not complete["can_complete"]:
            blocking_reasons.extend(complete["failed_gates"])
    if blocking_reasons:
        blocking_reasons = sorted(set(blocking_reasons))
        event = _append_advance_audit_event(
            working_state,
            checkpoint=target_checkpoint,
            decision="blocked",
            blocking_reasons=blocking_reasons,
            evidence_refs=verified_evidence,
            clock=clock,
        )
        run_state.update(working_state)
        return {
            "status": "blocked",
            "previous_checkpoint": current,
            "current_checkpoint": current,
            "transition_evidence": dict(evidence),
            "audit_event": event,
            "blocking_reasons": blocking_reasons,
            "evidence_errors": evidence_errors,
        }
    verified_by_checkpoint = {
        **working_state.get("verified_evidence", {}),
        target_checkpoint: verified_evidence,
    }
    updated = {
        **working_state,
        "current_checkpoint": target_checkpoint,
        "stage_state": {**working_state.get("stage_state", {}), target_checkpoint: dict(verified_evidence)},
        "verified_evidence": verified_by_checkpoint,
    }
    if current == "RESOLVE_GAPS" and target_checkpoint == "MATCH_BASE":
        updated["resolution_match_rerun_pending"] = True
    if current == "RESOLVE_GAPS" and target_checkpoint == "BUILD_SELECTION_PLAN":
        _record_resolution_loop_exit_unresolved(updated, checkpoint_plan)
    if current == "RENDER" and target_checkpoint == "BUILD_SELECTION_PLAN":
        _mark_render_overflow_consumed(updated)
    event = _append_advance_audit_event(
        updated,
        checkpoint=target_checkpoint,
        decision="advanced",
        blocking_reasons=[],
        evidence_refs=verified_evidence,
        clock=clock,
    )
    _persist_run(updated)
    run_state.update(updated)
    return {
        "status": "ok",
        "previous_checkpoint": current,
        "current_checkpoint": target_checkpoint,
        "transition_evidence": dict(evidence),
        "verified_evidence": dict(verified_evidence),
        "audit_event": event,
        "blocking_reasons": [],
    }


def recordCheckpointResult(run_state: JsonObject, checkpoint: str, result: JsonObject, clock: Callable[[], str] | None = None) -> JsonObject:
    working_state = _working_run_state(run_state)
    checkpoint_result = dict(result)
    timestamp = _timestamp(clock)
    operation_records = _operation_status_records(checkpoint_result)
    question_records = _question_log_records(checkpoint_result)
    _extend_unique(working_state, "facts_verified", checkpoint_result.get("facts_verified", []))
    _extend_unique(working_state, "facts_added", checkpoint_result.get("facts_added", []))
    _extend_unique(working_state, "operations_applied", checkpoint_result.get("operations_applied", []))
    _extend_unique(working_state, "operations_rejected", checkpoint_result.get("operations_rejected", []))
    _extend_requirement_unique(working_state, checkpoint_result.get("unresolved_requirements", []))
    _merge_operation_statuses(working_state, operation_records)
    _extend_unique(working_state, "already_applied_operations", checkpoint_result.get("operations_applied", []))
    _extend_unique(working_state, "already_asked_questions", _question_recovery_refs(question_records))
    _extend_unique(working_state, "already_written_facts", checkpoint_result.get("facts_verified", []) + checkpoint_result.get("facts_added", []))
    if checkpoint == "MATCH_BASE":
        working_state["last_match_fact_watermark"] = _dedupe(working_state.get("facts_verified", []))
    operation_refs = _append_operation_log(working_state, checkpoint, operation_records, timestamp)
    question_refs = _append_question_log(working_state, checkpoint, question_records, timestamp)
    checkpoint_ref = _write_checkpoint_result(working_state, checkpoint, checkpoint_result)
    artifact_refs = [checkpoint_ref] + _normalize_artifact_refs(working_state, checkpoint_result.get("artifact_refs", []), "artifact_refs")
    validation_refs = _normalize_artifact_refs(working_state, checkpoint_result.get("validation_refs", []), "validation_refs")
    render_refs = _normalize_artifact_refs(working_state, checkpoint_result.get("render_refs", []), "render_refs")
    render_overflow_result = _record_render_overflow_result(working_state, checkpoint, checkpoint_result)
    if render_overflow_result.get("constraint_ref"):
        artifact_refs.append(render_overflow_result["constraint_ref"])
        render_refs.append(render_overflow_result["constraint_ref"])
    _extend_unique(working_state, "operation_log_refs", operation_refs)
    _extend_unique(working_state, "question_answer_log_refs", question_refs)
    _extend_ref_unique(working_state, "validation_refs", validation_refs)
    _extend_ref_unique(working_state, "render_refs", render_refs)
    _extend_ref_unique(working_state, "checkpoint_result_refs", [checkpoint_ref])
    _extend_ref_unique(working_state, "artifact_refs", artifact_refs)
    _update_resolution_loop_state(working_state, checkpoint, checkpoint_result, question_records)
    if checkpoint == "MATCH_BASE":
        working_state.pop("resolution_match_rerun_pending", None)
    _persist_run(working_state)
    run_state.update(working_state)
    event = _record_audit("recordCheckpointResult", checkpoint, timestamp)
    status = "blocked" if render_overflow_result.get("status") == "blocked" else "ok"
    return {
        "status": status,
        "checkpoint": checkpoint,
        "artifact_refs": artifact_refs,
        "operation_log_refs": operation_refs,
        "question_answer_log_refs": question_refs,
        "validation_refs": validation_refs,
        "render_refs": render_refs,
        "audit_event": event,
        "render_overflow": render_overflow_result,
        "blocking_reasons": list(render_overflow_result.get("blocking_reasons", [])),
    }


def buildRunManifest(run_state: JsonObject) -> JsonObject:
    working_state = _working_run_state(run_state)
    versions = _manifest_versions(working_state, allow_not_recorded=False)
    schema_versions = versions["schema_versions"]
    manifest = {
        "run_id": working_state.get("run_id", ""),
        "base_resume_id": working_state.get("base_resume_id", ""),
        "base_resume_hash": working_state.get("base_resume_hash", ""),
        "job_id": working_state.get("job_id", ""),
        "config_hash": working_state.get("config_hash", ""),
        "canonical_resume_schema_version": schema_versions["canonical_resume"],
        "job_schema_version": schema_versions["job"],
        "career_db_schema_version": schema_versions["career_db"],
        "careerDbVersion": dict(versions["careerDbVersion"]),
        "change_operation_schema_version": schema_versions["change_operation"],
        "matching_algorithm_version": versions["matching_algorithm_version"],
        "matching_config_version": versions["matching_config_version"],
        "renderer_template_version": working_state.get("renderer_template_version", ""),
        "agent_model_config": working_state.get("agent_model_config", {}),
        "initial_score": working_state.get("initial_score", 0.0),
        "final_score": working_state.get("final_score", 0.0),
        "facts_added": list(working_state.get("facts_added", [])),
        "facts_verified": list(working_state.get("facts_verified", [])),
        "operations_applied": _manifest_operation_ids(working_state, "operations_applied", {"applied"}),
        "operations_rejected": _manifest_operation_ids(working_state, "operations_rejected", {"rejected"}),
        "validation_status": working_state.get("validation_status", "unknown"),
        "output_artifact_paths": list(working_state.get("output_artifact_paths", [])),
        "question_answer_log_refs": _manifest_question_answer_refs(working_state),
        "unresolved_requirements": _manifest_unresolved_requirements(working_state),
        "schema_version": RUN_MANIFEST_SCHEMA["schema_version"],
        "package_versions": dict(versions["package_versions"]),
        "recovery_markers": list(working_state.get("recovery_markers", [])),
        "audit_refs": list(working_state.get("audit_refs", [])),
        "metadata": {"field_sources": _manifest_field_sources()},
    }
    _validate_run_manifest(manifest)
    return manifest


def reconstructRunManifest(run_id: str, workspace: str | Path = ".") -> JsonObject:
    workspace_path = Path(workspace)
    path = _run_path(workspace_path, run_id)
    if not path.exists():
        raise UnknownRunError(run_id, workspace_path)
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise RunManifestValidationError([_issue("invalid_run_state", "Persisted run state must be an object.", "")])
    run_state = dict(loaded)
    run_state.setdefault("workspace", str(workspace_path))
    manifest = _reconstructed_manifest_from_state(run_state)
    _validate_run_manifest(manifest)
    return manifest


def recoverRun(workspace: str | Path, run_id: str, career_store: Any | None = None) -> JsonObject:
    return _recover_run(
        workspace,
        run_id,
        _run_path,
        UnknownRunError,
        RunManifestValidationError,
        _issue,
        _dedupe,
        _normalize_resolution_loop_state,
        _normalize_render_overflow_state,
        career_store=career_store,
    )


def assertCanComplete(run_state: JsonObject) -> JsonObject:
    working_state = _working_run_state(run_state)
    required_gates: dict[str, bool] = {}
    failed_gate_reasons: JsonObject = {}
    gate_errors: list[JsonObject] = []
    for gate, declaration in _COMPLETION_ARTIFACT_GATES.items():
        result = _completion_artifact_gate_result(working_state, gate, declaration)
        required_gates[gate] = result["passed"]
        if not result["passed"]:
            failed_gate_reasons[gate] = result["reason"]
            if isinstance(result.get("error"), dict):
                gate_errors.append(result["error"])

    hallucination_passed = _hallucination_rejection_passed(working_state)
    required_gates["hallucination_rejection"] = hallucination_passed
    if not hallucination_passed:
        failed_gate_reasons["hallucination_rejection"] = "flagged_operation_not_rejected"

    hard_requirements_passed = _hard_requirements_gate_passed(working_state)
    required_gates["hard_requirements"] = hard_requirements_passed
    if not hard_requirements_passed:
        failed_gate_reasons["hard_requirements"] = "unresolved_hard_requirements"

    render_overflow_passed = _render_overflow_completion_gate_passed(working_state)
    required_gates["render_overflow"] = render_overflow_passed
    if not render_overflow_passed:
        failed_gate_reasons["render_overflow"] = _render_overflow_completion_reason(working_state)

    failed = [gate for gate, passed in required_gates.items() if not passed]
    return {
        "status": "ok" if not failed else "blocked",
        "can_complete": not failed,
        "required_gates": list(required_gates),
        "failed_gates": failed,
        "failed_gate_reasons": failed_gate_reasons,
        "gate_errors": gate_errors,
        "gate_refs": _completion_gate_refs(working_state),
        "audit_ref": _completion_gate_ref(working_state, _COMPLETION_ARTIFACT_GATES["audit_ref"]),
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


def _working_run_state(run_state: JsonObject) -> JsonObject:
    persisted = _load_persisted_run_state(run_state)
    if not isinstance(persisted, dict):
        working = dict(run_state)
        working["resolution_loop_state"] = _normalize_resolution_loop_state(working.get("resolution_loop_state", {}), working)
        working["render_overflow_state"] = _normalize_render_overflow_state(working.get("render_overflow_state", {}), working)
        working["overflow_iteration"] = int(working["render_overflow_state"].get("iteration_count", 0))
        return working
    merged = {**persisted, **run_state}
    merged["audit_events"] = _merge_dict_records(persisted.get("audit_events", []), run_state.get("audit_events", []), "event_id")
    merged["verified_evidence"] = _merge_dict_values(persisted.get("verified_evidence", {}), run_state.get("verified_evidence", {}))
    merged["stage_state"] = _merge_dict_values(persisted.get("stage_state", {}), run_state.get("stage_state", {}))
    merged["resolution_loop_state"] = _normalize_resolution_loop_state(merged.get("resolution_loop_state", {}), merged)
    merged["render_overflow_state"] = _normalize_render_overflow_state(merged.get("render_overflow_state", {}), merged)
    merged["overflow_iteration"] = int(merged["render_overflow_state"].get("iteration_count", 0))
    return merged


def _merge_dict_values(first: Any, second: Any) -> JsonObject:
    merged: JsonObject = {}
    if isinstance(first, dict):
        merged.update(first)
    if isinstance(second, dict):
        merged.update(second)
    return merged


def _merge_dict_records(first: Any, second: Any, identity_key: str) -> list[JsonObject]:
    records: list[JsonObject] = []
    seen: set[str] = set()
    for value in list(first or []) + list(second or []):
        if not isinstance(value, dict):
            continue
        identity = str(value.get(identity_key) or _stable_hash(value))
        if identity in seen:
            continue
        seen.add(identity)
        records.append(dict(value))
    return records


def _append_advance_audit_event(
    run_state: JsonObject,
    *,
    checkpoint: str,
    decision: str,
    blocking_reasons: list[str],
    evidence_refs: JsonObject,
    clock: Callable[[], str] | None,
) -> JsonObject:
    event = {
        "event_id": _next_audit_event_id(run_state),
        "run_id": str(run_state.get("run_id", "")),
        "checkpoint": checkpoint,
        "decision": decision,
        "blocking_reasons": list(blocking_reasons),
        "evidence_refs": dict(evidence_refs),
        "timestamp": _timestamp(clock),
    }
    run_state.setdefault("audit_events", []).append(event)
    _persist_run(run_state)
    return event


def _next_audit_event_id(run_state: JsonObject) -> str:
    run_id = str(run_state.get("run_id", "run"))
    sequence = 1
    for event in run_state.get("audit_events", []):
        if not isinstance(event, dict):
            continue
        event_id = str(event.get("event_id", ""))
        prefix = f"{run_id}_audit_"
        if not event_id.startswith(prefix):
            sequence += 1
            continue
        try:
            sequence = max(sequence, int(event_id.removeprefix(prefix)) + 1)
        except ValueError:
            sequence += 1
    return f"{run_id}_audit_{sequence:04d}"


def _write_checkpoint_result(run_state: JsonObject, checkpoint: str, checkpoint_result: JsonObject) -> JsonObject:
    workspace = run_state.get("workspace")
    run_id = run_state.get("run_id")
    if not workspace or not run_id:
        raise ValueError("Checkpoint result recording requires a run_state with workspace and run_id.")
    workspace_path = Path(str(workspace))
    checkpoint_path = workspace_path / ".workflow" / "runs" / str(run_id) / "checkpoints" / f"{checkpoint}.json"
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    checkpoint_path.write_text(json.dumps(_jsonable(checkpoint_result), sort_keys=True, indent=2), encoding="utf-8")
    return {
        "kind": "artifact",
        "path": str(checkpoint_path.relative_to(workspace_path)),
        "sha256": _file_sha256(checkpoint_path),
    }


def _normalize_artifact_refs(run_state: JsonObject, value: Any, field_name: str) -> list[JsonObject]:
    if value in (None, ""):
        return []
    if isinstance(value, dict):
        refs = [value]
    elif isinstance(value, list):
        refs = value
    else:
        raise ValueError(f"{field_name} must contain typed artifact refs.")
    normalized: list[JsonObject] = []
    for ref in refs:
        if not isinstance(ref, dict) or ref.get("kind") != "artifact":
            raise ValueError(f"{field_name} entries must be artifact EvidenceRef objects.")
        path_value = ref.get("path")
        sha256_value = ref.get("sha256")
        if not isinstance(path_value, str) or not path_value:
            raise ValueError(f"{field_name} entries require a non-empty path.")
        if not isinstance(sha256_value, str) or not sha256_value:
            raise ValueError(f"{field_name} entries require a sha256.")
        path = _resolve_artifact_path(run_state, path_value)
        if not path.exists() or not path.is_file():
            raise ValueError(f"{field_name} artifact does not exist: {path}")
        actual_sha256 = _file_sha256(path)
        if actual_sha256 != sha256_value:
            raise ValueError(f"{field_name} artifact sha256 mismatch for {path}.")
        normalized.append(dict(ref))
    return normalized


def _resolve_artifact_path(run_state: JsonObject, path_value: str) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    workspace = run_state.get("workspace")
    return Path(str(workspace)) / path if workspace else path


def _run_dir(run_state: JsonObject) -> Path:
    workspace = run_state.get("workspace")
    run_id = run_state.get("run_id")
    if not workspace or not run_id:
        raise ValueError("Workflow log recording requires a run_state with workspace and run_id.")
    return Path(str(workspace)) / ".workflow" / "runs" / str(run_id)


def _run_relative_log_ref(run_state: JsonObject, filename: str, line_number: int) -> str:
    return f".workflow/runs/{run_state['run_id']}/{filename}#L{line_number}"


def _append_operation_log(run_state: JsonObject, checkpoint: str, records: list[JsonObject], timestamp: str) -> list[str]:
    return _append_jsonl_records(
        run_state,
        "operations.jsonl",
        [
            {
                "run_id": str(run_state.get("run_id", "")),
                "checkpoint": checkpoint,
                "operation_id": str(record["operation_id"]),
                "status": str(record.get("status", "")),
                "timestamp": timestamp,
                "record": dict(record),
            }
            for record in records
        ],
    )


def _append_question_log(run_state: JsonObject, checkpoint: str, records: list[JsonObject], timestamp: str) -> list[str]:
    return _append_jsonl_records(
        run_state,
        "questions.jsonl",
        [
            {
                "run_id": str(run_state.get("run_id", "")),
                "checkpoint": checkpoint,
                "timestamp": timestamp,
                **dict(record),
            }
            for record in records
        ],
    )


def _append_jsonl_records(run_state: JsonObject, filename: str, records: list[JsonObject]) -> list[str]:
    if not records:
        return []
    path = _run_dir(run_state) / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    start_line = _jsonl_line_count(path) + 1
    refs: list[str] = []
    with path.open("a", encoding="utf-8") as handle:
        for offset, record in enumerate(records):
            handle.write(json.dumps(_jsonable(record), sort_keys=True, separators=(",", ":")) + "\n")
            refs.append(_run_relative_log_ref(run_state, filename, start_line + offset))
        handle.flush()
        os.fsync(handle.fileno())
    return refs


def _jsonl_line_count(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8") as handle:
        return sum(1 for line in handle if line.strip())


def _read_jsonl_records(path: Path) -> list[JsonObject]:
    if not path.exists():
        return []
    records: list[JsonObject] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        value = json.loads(line)
        if isinstance(value, dict):
            records.append(value)
    return records


def _manifest_question_answer_refs(run_state: JsonObject) -> list[str]:
    question_log = _log_path_if_recorded(run_state, "questions.jsonl")
    if question_log is None:
        return list(run_state.get("question_answer_log_refs", []))
    line_count = _jsonl_line_count(question_log)
    if line_count == 0:
        return list(run_state.get("question_answer_log_refs", []))
    return [_run_relative_log_ref(run_state, "questions.jsonl", line_number) for line_number in range(1, line_count + 1)]


def _manifest_unresolved_requirements(run_state: JsonObject) -> list[JsonObject]:
    unresolved: list[JsonObject] = []
    _append_unresolved_requirements(unresolved, run_state.get("unresolved_requirements", []))
    question_log = _log_path_if_recorded(run_state, "questions.jsonl")
    if question_log is not None:
        for record in _read_jsonl_records(question_log):
            _append_unresolved_requirements(unresolved, record.get("unresolved_requirements", []))
    return _dedupe_dicts(unresolved)


def _manifest_operation_ids(run_state: JsonObject, state_key: str, statuses: set[str]) -> list[str]:
    operation_ids = [str(value) for value in run_state.get(state_key, [])]
    operation_log = _log_path_if_recorded(run_state, "operations.jsonl")
    if operation_log is not None:
        for record in _read_jsonl_records(operation_log):
            if str(record.get("status", "")) in statuses and record.get("operation_id"):
                operation_ids.append(str(record["operation_id"]))
    return _dedupe(operation_ids)


def _log_path_if_recorded(run_state: JsonObject, filename: str) -> Path | None:
    try:
        path = _run_dir(run_state) / filename
    except ValueError:
        return None
    return path if path.exists() else None


def _manifest_versions(run_state: JsonObject, *, allow_not_recorded: bool) -> JsonObject:
    schema_versions = run_state.get("schema_versions")
    package_versions = run_state.get("package_versions")
    career_db_version = run_state.get("careerDbVersion")
    recorded_matching_versions = bool(run_state.get("matching_algorithm_version")) and bool(run_state.get("matching_config_version"))
    if isinstance(schema_versions, dict) and isinstance(package_versions, dict) and isinstance(career_db_version, dict) and (recorded_matching_versions or allow_not_recorded):
        return {
            "schema_versions": _schema_versions_from_recorded_state(schema_versions, allow_not_recorded),
            "package_versions": {str(key): str(value) for key, value in package_versions.items()},
            "careerDbVersion": dict(career_db_version),
            "matching_algorithm_version": _recorded_string(run_state, "matching_algorithm_version", allow_not_recorded),
            "matching_config_version": _recorded_string(run_state, "matching_config_version", allow_not_recorded),
        }
    if allow_not_recorded:
        return {
            "schema_versions": _schema_versions_from_recorded_state({}, True),
            "package_versions": {},
            "careerDbVersion": {"status": "unavailable", "reason": "career_db_not_configured"},
            "matching_algorithm_version": "not recorded",
            "matching_config_version": "not recorded",
        }
    return collectVersions(workspace=run_state.get("workspace"), run_state=run_state)


def _schema_versions_from_recorded_state(schema_versions: JsonObject, allow_not_recorded: bool) -> JsonObject:
    marker = "not recorded" if allow_not_recorded else ""
    return {
        "canonical_resume": str(schema_versions.get("canonical_resume", marker)),
        "job": str(schema_versions.get("job", marker)),
        "career_db": str(schema_versions.get("career_db", marker)),
        "change_operation": str(schema_versions.get("change_operation", marker)),
    }


def _recorded_string(run_state: JsonObject, key: str, allow_not_recorded: bool) -> str:
    value = run_state.get(key)
    if isinstance(value, str) and value:
        return value
    return "not recorded" if allow_not_recorded else ""


def _reconstructed_manifest_from_state(run_state: JsonObject) -> JsonObject:
    versions = _manifest_versions(run_state, allow_not_recorded=True)
    schema_versions = versions["schema_versions"]
    not_recorded = _not_recorded_fields(run_state, versions)
    metadata: JsonObject = {"field_sources": _manifest_field_sources()}
    if not_recorded:
        metadata["not_recorded_fields"] = not_recorded
        metadata["not_recorded_marker"] = "not recorded"
    manifest = {
        "run_id": _recorded_string(run_state, "run_id", True),
        "base_resume_id": _recorded_string(run_state, "base_resume_id", True),
        "base_resume_hash": _recorded_string(run_state, "base_resume_hash", True),
        "job_id": _recorded_string(run_state, "job_id", True),
        "config_hash": _recorded_string(run_state, "config_hash", True),
        "canonical_resume_schema_version": schema_versions["canonical_resume"],
        "job_schema_version": schema_versions["job"],
        "career_db_schema_version": schema_versions["career_db"],
        "careerDbVersion": dict(versions["careerDbVersion"]),
        "change_operation_schema_version": schema_versions["change_operation"],
        "matching_algorithm_version": versions["matching_algorithm_version"],
        "matching_config_version": versions["matching_config_version"],
        "renderer_template_version": _recorded_string(run_state, "renderer_template_version", True),
        "agent_model_config": dict(run_state.get("agent_model_config", {})) if isinstance(run_state.get("agent_model_config"), dict) else {},
        "initial_score": _recorded_number(run_state.get("initial_score")),
        "final_score": _recorded_number(run_state.get("final_score")),
        "facts_added": list(run_state.get("facts_added", [])),
        "facts_verified": list(run_state.get("facts_verified", [])),
        "operations_applied": _manifest_operation_ids(run_state, "operations_applied", {"applied"}),
        "operations_rejected": _manifest_operation_ids(run_state, "operations_rejected", {"rejected"}),
        "validation_status": str(run_state.get("validation_status", "unknown")),
        "output_artifact_paths": list(run_state.get("output_artifact_paths", [])),
        "question_answer_log_refs": _manifest_question_answer_refs(run_state),
        "unresolved_requirements": _manifest_unresolved_requirements(run_state),
        "schema_version": RUN_MANIFEST_SCHEMA["schema_version"],
        "package_versions": dict(versions["package_versions"]),
        "recovery_markers": list(run_state.get("recovery_markers", [])),
        "audit_refs": list(run_state.get("audit_refs", [])),
        "metadata": metadata,
    }
    return manifest


def _recorded_number(value: Any) -> float:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else 0.0


def _not_recorded_fields(run_state: JsonObject, versions: JsonObject) -> list[str]:
    fields = [
        "base_resume_id",
        "base_resume_hash",
        "job_id",
        "config_hash",
        "renderer_template_version",
        "initial_score",
        "final_score",
    ]
    missing = [field for field in fields if field not in run_state or run_state.get(field) in ("", None)]
    for field, key in [
        ("canonical_resume_schema_version", "canonical_resume"),
        ("job_schema_version", "job"),
        ("career_db_schema_version", "career_db"),
        ("change_operation_schema_version", "change_operation"),
    ]:
        if versions["schema_versions"].get(key) == "not recorded":
            missing.append(field)
    for field in ["matching_algorithm_version", "matching_config_version"]:
        if versions.get(field) == "not recorded":
            missing.append(field)
    return missing


def _manifest_field_sources() -> JsonObject:
    return {
        "run_id": "persisted run state",
        "base_resume_id": "persisted run state",
        "base_resume_hash": "persisted run state",
        "job_id": "persisted run state",
        "config_hash": "persisted run state",
        "schema_versions": "persisted run state",
        "careerDbVersion": "persisted run state",
        "matching_algorithm_version": "persisted run state",
        "matching_config_version": "persisted run state",
        "renderer_template_version": "persisted run state",
        "agent_model_config": "persisted run state",
        "initial_score": "persisted run state",
        "final_score": "persisted run state",
        "facts_added": "persisted run state",
        "facts_verified": "persisted run state",
        "operations_applied": "persisted run state plus operations.jsonl observations",
        "operations_rejected": "persisted run state plus operations.jsonl observations",
        "validation_status": "persisted run state",
        "output_artifact_paths": "persisted run state",
        "question_answer_log_refs": "questions.jsonl line refs when present, otherwise persisted run state",
        "unresolved_requirements": "persisted run state plus explicit unresolved_requirements entries in questions.jsonl",
        "recovery_markers": "persisted run state",
        "audit_refs": "persisted run state",
    }


def _extend_ref_unique(target: JsonObject, key: str, values: list[JsonObject]) -> None:
    existing = [item for item in target.get(key, []) if isinstance(item, dict)]
    by_identity = {_stable_hash(item): dict(item) for item in existing}
    for value in values:
        by_identity.setdefault(_stable_hash(value), dict(value))
    target[key] = list(by_identity.values())


def _record_audit(operation: str, checkpoint: str, timestamp: str) -> JsonObject:
    return {
        "operation": operation,
        "checkpoint": checkpoint,
        "accepted": True,
        "timestamp": timestamp,
    }


def _timestamp(clock: Callable[[], str] | None) -> str:
    return str(clock() if clock is not None else _utc_now())


def _utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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


def _advance_requirements(run_state: JsonObject, checkpoint: str) -> tuple[JsonObject, ...]:
    requirements = list(_ADVANCE_REQUIREMENTS.get(checkpoint, ()))
    if checkpoint == "BUILD_SELECTION_PLAN" and _render_overflow_decision(run_state)["predicate"]["action"] == "loop_back":
        requirements.append({"name": "render_overflow_constraints", "kind": "artifact"})
    return tuple(requirements)


def _required_input_names(run_state: JsonObject, checkpoint: str) -> list[str]:
    return [str(requirement["name"]) for requirement in _advance_requirements(run_state, checkpoint)]


def _blocking_reasons_for(run_state: JsonObject, checkpoint: str) -> list[str]:
    verified_names = _verified_requirement_names(run_state, checkpoint)
    reasons = [name for name in _required_input_names(run_state, checkpoint) if name not in verified_names]
    if checkpoint == "COMPLETE":
        complete = assertCanComplete(run_state)
        if not complete["can_complete"]:
            reasons.extend(complete["failed_gates"])
    return sorted(set(reasons))


def _verified_requirement_names(run_state: JsonObject, checkpoint: str) -> set[str]:
    evidence_by_checkpoint = run_state.get("verified_evidence", {})
    if not isinstance(evidence_by_checkpoint, dict):
        return set()
    checkpoint_evidence = evidence_by_checkpoint.get(checkpoint, {})
    if not isinstance(checkpoint_evidence, dict):
        return set()
    return {
        str(name)
        for name, evidence_ref in checkpoint_evidence.items()
        if isinstance(evidence_ref, dict) and evidence_ref.get("kind") in {"artifact", "dto", "run_state"}
    }


def _verify_evidence_ref(run_state: JsonObject, requirement: JsonObject, evidence_ref: Any) -> JsonObject:
    requirement_name = str(requirement["name"])
    expected_kind = str(requirement["kind"])
    if not isinstance(evidence_ref, dict):
        return _evidence_error(
            requirement_name,
            "invalid_evidence_ref",
            "Evidence must be a typed EvidenceRef object, not a literal or bare truth value.",
        )
    actual_kind = evidence_ref.get("kind")
    if actual_kind != expected_kind:
        return _evidence_error(
            requirement_name,
            "invalid_evidence_kind",
            f"Expected {expected_kind} evidence.",
            {"actual_kind": actual_kind},
        )
    if expected_kind == "artifact":
        return _verify_artifact_ref(run_state, requirement_name, evidence_ref)
    if expected_kind == "dto":
        return _verify_dto_ref(requirement, requirement_name, evidence_ref)
    if expected_kind == "run_state":
        return _verify_run_state_ref(run_state, requirement, requirement_name, evidence_ref)
    return _evidence_error(requirement_name, "unsupported_evidence_kind", f"Unsupported evidence kind: {expected_kind}")


def _verify_artifact_ref(run_state: JsonObject, requirement_name: str, evidence_ref: JsonObject) -> JsonObject:
    path_value = evidence_ref.get("path")
    sha256_value = evidence_ref.get("sha256")
    if not isinstance(path_value, str) or not path_value:
        return _evidence_error(requirement_name, "invalid_artifact_ref", "Artifact evidence requires a non-empty path.")
    if not isinstance(sha256_value, str) or not sha256_value:
        return _evidence_error(requirement_name, "invalid_artifact_ref", "Artifact evidence requires a sha256.")
    path = Path(path_value)
    if not path.is_absolute():
        workspace = run_state.get("workspace")
        path = Path(str(workspace)) / path if workspace else path
    if not path.exists() or not path.is_file():
        return _evidence_error(requirement_name, "artifact_missing", "Artifact evidence path does not exist.", {"path": str(path)})
    actual_sha256 = _file_sha256(path)
    if actual_sha256 != sha256_value:
        return _evidence_error(
            requirement_name,
            "artifact_hash_mismatch",
            "Artifact sha256 does not match.",
            {"path": str(path), "expected_sha256": sha256_value, "actual_sha256": actual_sha256},
        )
    return {"status": "ok", "evidence_ref": dict(evidence_ref)}


def _verify_dto_ref(requirement: JsonObject, requirement_name: str, evidence_ref: JsonObject) -> JsonObject:
    schema_id = evidence_ref.get("schema_id")
    expected_schema_id = requirement.get("schema_id")
    if schema_id != expected_schema_id:
        return _evidence_error(
            requirement_name,
            "invalid_schema_id",
            f"Expected DTO schema {expected_schema_id}.",
            {"actual_schema_id": schema_id},
        )
    if not isinstance(schema_id, str) or schema_id not in SCHEMAS:
        return _evidence_error(requirement_name, "unknown_schema_id", "DTO evidence references an unknown schema.", {"schema_id": schema_id})
    if "payload" not in evidence_ref:
        return _evidence_error(requirement_name, "missing_dto_payload", "DTO evidence requires a payload.")
    errors = _schema_errors(evidence_ref["payload"], SCHEMAS[schema_id], "")
    if errors:
        return _evidence_error(requirement_name, "dto_schema_error", "DTO payload failed schema validation.", {"schema_id": schema_id, "errors": errors})
    return {"status": "ok", "evidence_ref": dict(evidence_ref)}


def _verify_run_state_ref(run_state: JsonObject, requirement: JsonObject, requirement_name: str, evidence_ref: JsonObject) -> JsonObject:
    key = evidence_ref.get("key")
    expected_key = requirement.get("key")
    allowed_keys = {expected_key, *list(requirement.get("alternate_keys", []))}
    if key not in allowed_keys:
        return _evidence_error(requirement_name, "invalid_run_state_key", f"Expected run-state key {expected_key}.", {"actual_key": key})
    persisted = _load_persisted_run_state(run_state)
    if not isinstance(persisted, dict):
        return _evidence_error(requirement_name, "run_state_unavailable", "Persisted run state is unavailable.")
    statuses = requirement.get("statuses")
    if isinstance(statuses, list) and statuses:
        return _verify_operation_status_ref(persisted, requirement_name, evidence_ref, {str(status) for status in statuses})
    value = persisted.get(str(key))
    if value in (None, "", [], {}):
        return _evidence_error(requirement_name, "run_state_key_missing", "Required key is absent from persisted run state.", {"key": key})
    return {"status": "ok", "evidence_ref": dict(evidence_ref)}


def _verify_operation_status_ref(persisted: JsonObject, requirement_name: str, evidence_ref: JsonObject, statuses: set[str]) -> JsonObject:
    operation_ids = evidence_ref.get("operation_ids")
    if not isinstance(operation_ids, list) or not operation_ids or any(not isinstance(item, str) or not item for item in operation_ids):
        return _evidence_error(
            requirement_name,
            "missing_operation_ids",
            "Operation lifecycle evidence requires non-empty operation_ids.",
            {"allowed_statuses": sorted(statuses)},
        )
    records = {
        str(record.get("operation_id")): str(record.get("status", ""))
        for record in persisted.get("operation_statuses", [])
        if isinstance(record, dict) and record.get("operation_id")
    }
    missing = [operation_id for operation_id in operation_ids if operation_id not in records]
    wrong_status = [
        {"operation_id": operation_id, "status": records[operation_id]}
        for operation_id in operation_ids
        if operation_id in records and records[operation_id] not in statuses
    ]
    if missing:
        return _evidence_error(
            requirement_name,
            "operation_status_missing",
            "Operation ids are absent from persisted operation records.",
            {"operation_ids": missing, "allowed_statuses": sorted(statuses)},
        )
    if wrong_status:
        return _evidence_error(
            requirement_name,
            "operation_status_mismatch",
            "Operation ids are not in the required lifecycle state.",
            {"operations": wrong_status, "allowed_statuses": sorted(statuses)},
        )
    return {"status": "ok", "evidence_ref": dict(evidence_ref)}


def _completion_gate_state(run_state: JsonObject, verified_evidence: JsonObject) -> JsonObject:
    gate_state = dict(run_state)
    audit_ref = verified_evidence.get("audit_ref")
    if isinstance(audit_ref, dict):
        gate_state["audit_ref"] = dict(audit_ref)
    return gate_state


def _completion_artifact_gate_result(run_state: JsonObject, gate: str, declaration: JsonObject) -> JsonObject:
    ref = _completion_gate_ref(run_state, declaration)
    if not isinstance(ref, dict):
        return {"passed": False, "reason": "missing_ref"}
    verified = _verify_artifact_ref(run_state, gate, ref)
    if verified.get("status") == "ok":
        return {"passed": True, "reason": "ok", "ref": verified["evidence_ref"]}
    return {"passed": False, "reason": verified.get("type", "invalid_ref"), "error": verified, "ref": dict(ref)}


def _completion_gate_refs(run_state: JsonObject) -> JsonObject:
    refs: JsonObject = {}
    for gate, declaration in _COMPLETION_ARTIFACT_GATES.items():
        ref = _completion_gate_ref(run_state, declaration)
        if isinstance(ref, dict):
            refs[gate] = ref
    return refs


def _completion_gate_ref(run_state: JsonObject, declaration: JsonObject) -> JsonObject | None:
    for key in declaration.get("state_keys", []):
        value = run_state.get(str(key))
        if isinstance(value, dict) and value.get("kind") == "artifact":
            return dict(value)
    checkpoint = str(declaration["checkpoint"])
    name = str(declaration["name"])
    for container_name in ("stage_state", "verified_evidence"):
        container = run_state.get(container_name, {})
        if not isinstance(container, dict):
            continue
        checkpoint_evidence = container.get(checkpoint, {})
        if not isinstance(checkpoint_evidence, dict):
            continue
        ref = checkpoint_evidence.get(name)
        if isinstance(ref, dict) and ref.get("kind") == "artifact":
            return dict(ref)
    return None


def _hard_requirements_gate_passed(run_state: JsonObject) -> bool:
    if not run_state.get("unresolved_hard_requirements"):
        return True
    return not run_state.get("policy", {}).get("requireHardRequirementsResolved", True)


def _load_persisted_run_state(run_state: JsonObject) -> JsonObject | None:
    workspace = run_state.get("workspace")
    run_id = run_state.get("run_id")
    if not workspace or not run_id:
        return None
    path = _run_path(Path(str(workspace)), str(run_id))
    if not path.exists():
        return None
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return loaded if isinstance(loaded, dict) else None


def _hallucination_rejection_passed(run_state: JsonObject) -> bool:
    persisted = _load_persisted_run_state(run_state)
    if not isinstance(persisted, dict):
        return True
    records = persisted.get("operation_statuses", [])
    if not isinstance(records, list):
        return True
    flagged = [record for record in records if isinstance(record, dict) and _is_hallucination_flagged(record)]
    return all(str(record.get("status", "")) == "rejected" for record in flagged)


def _is_hallucination_flagged(record: JsonObject) -> bool:
    validation = record.get("validation")
    if not isinstance(validation, dict):
        return False
    grounding = validation.get("grounding", {})
    error_codes = {
        str(error.get("code", ""))
        for error in validation.get("errors", [])
        if isinstance(error, dict)
    }
    grounding_failure_codes = {
        "unsupported_guarded_claim",
        "unsupported_years_claim",
        "title_inflation",
    }
    return isinstance(grounding, dict) and grounding.get("supported") is False and bool(error_codes & grounding_failure_codes)


def _operation_status_records(checkpoint_result: JsonObject) -> list[JsonObject]:
    records: list[JsonObject] = []
    for key in ("operation_statuses", "operation_records", "validation_results"):
        records.extend(_operation_records_from_list(checkpoint_result.get(key)))
    records.extend(_operation_records_from_ids(checkpoint_result.get("operations_proposed"), "proposed"))
    records.extend(_operation_records_from_ids(checkpoint_result.get("operations_validated"), "validated"))
    records.extend(_operation_records_from_ids(checkpoint_result.get("operations_applied"), "applied"))
    records.extend(_operation_records_from_ids(checkpoint_result.get("operations_rejected"), "rejected"))
    records.extend(_operation_records_from_list(checkpoint_result.get("proposed"), default_status="proposed"))
    records.extend(_operation_records_from_list(checkpoint_result.get("validated"), default_status="validated"))
    records.extend(_operation_records_from_list(checkpoint_result.get("applied"), default_status="applied"))
    records.extend(_operation_records_from_list(checkpoint_result.get("rejected"), default_status="rejected"))
    return records


def _operation_records_from_ids(value: Any, status: str) -> list[JsonObject]:
    if not isinstance(value, list):
        return []
    records: list[JsonObject] = []
    for item in value:
        operation_id = str(item.get("operation_id", "")) if isinstance(item, dict) else str(item)
        if operation_id:
            record = dict(item) if isinstance(item, dict) else {"operation_id": operation_id}
            record["operation_id"] = operation_id
            record["status"] = str(record.get("status") or status)
            records.append(record)
    return records


def _operation_records_from_list(value: Any, default_status: str | None = None) -> list[JsonObject]:
    if not isinstance(value, list):
        return []
    records: list[JsonObject] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        operation_id = str(item.get("operation_id", ""))
        if not operation_id:
            validation = item.get("validation")
            if isinstance(validation, dict):
                operation_id = str(validation.get("operation_id", ""))
        if not operation_id:
            continue
        record = dict(item)
        record["operation_id"] = operation_id
        record["status"] = str(record.get("status") or default_status or record.get("validation_state") or "")
        if "validation" not in record and _looks_like_validation_result(item):
            record["validation"] = dict(item)
        records.append(record)
    return records


def _question_log_records(checkpoint_result: JsonObject) -> list[JsonObject]:
    records: list[JsonObject] = []
    for key in ("question_answer_records", "question_answer_log", "question_answers", "questions"):
        records.extend(_question_records_from_list(checkpoint_result.get(key)))
    for ref in checkpoint_result.get("question_answer_log_refs", []) or []:
        if isinstance(ref, str) and ref:
            records.append({"question_answer_ref": ref, "status": "recorded"})
        elif isinstance(ref, dict):
            records.extend(_question_records_from_list([ref]))
    return records


def _question_records_from_list(value: Any) -> list[JsonObject]:
    if not isinstance(value, list):
        return []
    records: list[JsonObject] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        record: JsonObject = {}
        for key in (
            "question_id",
            "requirement_id",
            "selected_requirement_id",
            "question_ref",
            "answer_ref",
            "question_answer_ref",
            "interaction_ref",
            "status",
            "career_store_interaction_id",
            "career_store_interaction_ref",
        ):
            if item.get(key) not in (None, ""):
                record[key] = item[key]
        fact_refs = item.get("fact_refs")
        if isinstance(fact_refs, list):
            record["fact_refs"] = [str(ref) for ref in fact_refs]
        unresolved = _normalized_unresolved_requirements(item.get("unresolved_requirements", []))
        if unresolved:
            record["unresolved_requirements"] = unresolved
        if record:
            records.append(record)
    return records


def _question_recovery_refs(records: list[JsonObject]) -> list[str]:
    refs: list[str] = []
    for record in records:
        for key in ("question_id", "question_answer_ref", "question_ref"):
            value = record.get(key)
            if isinstance(value, str) and value:
                refs.append(value)
                break
    return refs


def _extend_requirement_unique(run_state: JsonObject, requirements: Any) -> None:
    existing = _normalized_unresolved_requirements(run_state.get("unresolved_requirements", []))
    incoming = _normalized_unresolved_requirements(requirements)
    run_state["unresolved_requirements"] = _dedupe_dicts(existing + incoming)


def _record_resolution_loop_exit_unresolved(run_state: JsonObject, checkpoint_plan: JsonObject) -> None:
    predicate = checkpoint_plan.get("resolution_loop", {}).get("predicate", {})
    if predicate.get("action") != "advance_with_unresolved":
        return
    _extend_requirement_unique(run_state, _loop_exit_unresolved_requirements(predicate.get("unresolved_requirements", [])))


def _loop_exit_unresolved_requirements(requirements: Any) -> list[JsonObject]:
    if not isinstance(requirements, list):
        return []
    records: list[JsonObject] = []
    for item in requirements:
        if not isinstance(item, dict):
            continue
        requirement_id = item.get("requirement_id")
        status = item.get("status")
        if not isinstance(requirement_id, str) or not requirement_id:
            continue
        if status not in {"user_declined", "exhausted"}:
            continue
        records.append(
            {
                "requirement_id": requirement_id,
                "resolution_state": status,
                "reason": status,
            }
        )
    return records


def _append_unresolved_requirements(target: list[JsonObject], requirements: Any) -> None:
    target.extend(_normalized_unresolved_requirements(requirements))


def _normalized_unresolved_requirements(requirements: Any) -> list[JsonObject]:
    if not isinstance(requirements, list):
        return []
    normalized: list[JsonObject] = []
    for item in requirements:
        if not isinstance(item, dict):
            continue
        requirement_id = item.get("requirement_id")
        resolution_state = item.get("resolution_state")
        if not isinstance(requirement_id, str) or not requirement_id:
            continue
        if not isinstance(resolution_state, str) or not resolution_state:
            continue
        normalized.append(
            {
                "requirement_id": requirement_id,
                "resolution_state": resolution_state,
                "reason": str(item.get("reason", "")),
            }
        )
    return normalized


def _dedupe_dicts(values: list[JsonObject]) -> list[JsonObject]:
    result: list[JsonObject] = []
    seen: set[str] = set()
    for value in values:
        identity = _stable_hash(value)
        if identity in seen:
            continue
        seen.add(identity)
        result.append(dict(value))
    return result


def _looks_like_validation_result(value: JsonObject) -> bool:
    return "validation_state" in value or "grounding" in value or "errors" in value


def _merge_operation_statuses(run_state: JsonObject, records: list[JsonObject]) -> None:
    if not records:
        return
    merged = {
        str(record.get("operation_id")): dict(record)
        for record in run_state.get("operation_statuses", [])
        if isinstance(record, dict) and record.get("operation_id")
    }
    for record in records:
        merged[str(record["operation_id"])] = dict(record)
    run_state["operation_statuses"] = list(merged.values())


def _evidence_error(requirement: str, code: str, message: str, details: JsonObject | None = None) -> JsonObject:
    error: JsonObject = {"type": code, "requirement": requirement, "message": message}
    if details:
        error["details"] = details
    return error


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
__all__ = ["RUN_MANIFEST_SCHEMA", "SCHEMAS", "Checkpoint", "RunManifest", "RunManifestValidationError", "UnknownRunError", "createRun", "getNextCheckpoint", "advanceCheckpoint", "recordCheckpointResult", "buildRunManifest", "reconstructRunManifest", "recoverRun", "assertCanComplete"]
