"""Private recovery contract helpers for workflow."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Callable

from career_store import openCareerStore

from .schemas import CAREER_DB_VERSION_UNAVAILABLE_STATUS


JsonObject = dict[str, Any]

_RECOVERY_INTEGRITY_CHECKS = ("career_db", "base_resume", "rejected_operations")
_RERUN_CHECKPOINTS = {"APPLY_CHANGES", "FINAL_MATCH", "GROUNDING_AUDIT", "ATS_STRUCTURE_VALIDATION", "RENDER"}


def recover_run(
    workspace: str | Path,
    run_id: str,
    run_path: Callable[[Path, str], Path],
    unknown_run_error: type[FileNotFoundError],
    validation_error: type[ValueError],
    issue: Callable[[str, str, str], JsonObject],
    dedupe: Callable[[list[Any]], list[Any]],
    normalize_resolution_loop_state: Callable[[JsonObject, JsonObject], JsonObject],
    normalize_render_overflow_state: Callable[[JsonObject, JsonObject], JsonObject],
    career_store: Any | None = None,
) -> JsonObject:
    workspace_path = Path(workspace)
    saved = run_path(workspace_path, run_id)
    if not saved.exists():
        raise unknown_run_error(run_id, workspace_path)
    loaded = json.loads(saved.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise validation_error([issue("invalid_run_state", "Persisted run state must be an object.", "")])
    run_state = dict(loaded)
    current = str(run_state.get("current_checkpoint", "INIT"))
    required_reruns = ["FINAL_MATCH"] if current in _RERUN_CHECKPOINTS else []
    integrity = _recovery_integrity(run_state, career_store=career_store)
    return {
        "status": "ok",
        "run_id": run_id,
        "resume_from_checkpoint": current,
        "already_applied_operations": dedupe(run_state.get("already_applied_operations", run_state.get("operations_applied", []))),
        "already_asked_questions": dedupe(run_state.get("already_asked_questions", [])),
        "already_written_facts": dedupe(run_state.get("already_written_facts", run_state.get("facts_verified", []))),
        "last_match_fact_watermark": dedupe(run_state.get("last_match_fact_watermark", [])),
        "resolution_loop_state": normalize_resolution_loop_state(run_state.get("resolution_loop_state", {}), run_state),
        "resolution_blocking_reasons": dedupe(run_state.get("resolution_blocking_reasons", [])),
        "render_overflow_state": normalize_render_overflow_state(run_state.get("render_overflow_state", {}), run_state),
        "render_overflow_blocking_reasons": dedupe(run_state.get("render_overflow_blocking_reasons", [])),
        "required_reruns": required_reruns,
        "integrity": integrity,
        "resumable": _recovery_resumable(integrity),
    }


def _recovery_integrity(run_state: JsonObject, *, career_store: Any | None = None) -> JsonObject:
    return {name: _recovery_integrity_check(name, run_state, career_store=career_store) for name in _RECOVERY_INTEGRITY_CHECKS}


def _recovery_integrity_check(name: str, run_state: JsonObject, *, career_store: Any | None = None) -> JsonObject:
    if name == "career_db":
        return _verify_career_db(run_state, career_store=career_store)
    if name == "base_resume":
        return _verify_base_resume(run_state)
    if name == "rejected_operations":
        return _verify_rejected_operations(run_state)
    return {
        "status": "unverified",
        "evidence_ref": None,
        "reason": f"unknown_integrity_check:{name}",
    }


def _recovery_resumable(integrity: JsonObject) -> bool:
    return all(check.get("status") != "failed" for check in integrity.values() if isinstance(check, dict))


def _verify_career_db(run_state: JsonObject, *, career_store: Any | None) -> JsonObject:
    recorded = run_state.get("careerDbVersion")
    if isinstance(recorded, dict) and recorded.get("status") == CAREER_DB_VERSION_UNAVAILABLE_STATUS:
        reason = str(recorded.get("reason") or "career_db_not_configured")
        return _unverified(reason, {"kind": "career_db_recorded_state", "state": _jsonable_dict(recorded)})
    if not isinstance(recorded, dict):
        return _failed("career_db_version_not_recorded", {"kind": "career_db_recorded_state", "state": None})

    recorded_schema_version = recorded.get("schema_version")
    if not isinstance(recorded_schema_version, str) or not recorded_schema_version:
        return _failed("career_db_schema_version_not_recorded", {"kind": "career_db_recorded_state", "state": _jsonable_dict(recorded)})

    try:
        state = _migration_state_from_store(run_state, career_store)
    except Exception as exc:  # pragma: no cover - defensive wrapper preserves recovery payload shape.
        return _failed(
            f"career_db_migration_state_unavailable:{exc}",
            {"kind": "career_db_recorded_state", "state": _jsonable_dict(recorded)},
        )

    evidence_ref = {"kind": "career_db_migration_state", "state": state}
    discrepancies: list[str] = []
    if state.get("status") != "ok":
        discrepancies.append(f"status_not_ok:{state.get('status')}")
    pending = state.get("pending_migrations")
    if isinstance(pending, list) and pending:
        discrepancies.append(f"pending_migrations:{','.join(str(item) for item in pending)}")
    elif not isinstance(pending, list):
        discrepancies.append("pending_migrations_missing")
    if state.get("schema_version") != recorded_schema_version:
        discrepancies.append(f"schema_version_mismatch:recorded={recorded_schema_version}:consulted={state.get('schema_version')}")
    if discrepancies:
        return _failed(";".join(discrepancies), evidence_ref)
    return _verified("career_db_migration_state_matches_recorded_version", evidence_ref)


def _migration_state_from_store(run_state: JsonObject, career_store: Any | None) -> JsonObject:
    store = career_store
    if store is None:
        database_path = _career_db_path(run_state)
        if database_path is None:
            raise ValueError("career_db_path_not_recorded")
        store = openCareerStore(str(database_path))
    getter = getattr(store, "getMigrationState", None)
    if not callable(getter):
        raise ValueError("career_store_missing_getMigrationState")
    state = getter()
    if is_dataclass(state):
        payload = asdict(state)
    elif isinstance(state, dict):
        payload = dict(state)
    else:
        raise ValueError("unsupported_migration_state")
    return _jsonable_dict(payload)


def _career_db_path(run_state: JsonObject) -> Path | None:
    recorded = run_state.get("careerDbVersion")
    if isinstance(recorded, dict) and recorded.get("database_path"):
        return Path(str(recorded["database_path"]))
    for key in ("career_db_path", "careerDbPath", "career_db", "careerDb"):
        raw = run_state.get(key)
        if raw:
            return Path(str(raw))
    workspace = run_state.get("workspace")
    if workspace:
        candidate = Path(str(workspace)) / "data" / "career.db"
        if candidate.exists():
            return candidate
    return None


def _verify_base_resume(run_state: JsonObject) -> JsonObject:
    recorded_hash = run_state.get("base_resume_hash")
    evidence_ref = _base_resume_evidence_ref(run_state)
    if not isinstance(recorded_hash, str) or not recorded_hash or recorded_hash == "not recorded":
        return _failed("base_resume_hash_not_recorded", evidence_ref)
    base_path = _base_resume_path(run_state)
    if base_path is None:
        return _failed("base_resume_path_not_recorded", evidence_ref)
    if not base_path.exists() or not base_path.is_file():
        return _failed("base_resume_file_missing", {**evidence_ref, "path": str(base_path)})
    actual_hash = _file_sha256(base_path)
    evidence = {"kind": "base_resume_hash", "path": _display_path(run_state, base_path), "sha256": actual_hash}
    if actual_hash != recorded_hash:
        return _failed(f"base_resume_hash_mismatch:recorded={recorded_hash}:actual={actual_hash}", evidence)
    return _verified("base_resume_hash_matches_recorded_hash", evidence)


def _base_resume_path(run_state: JsonObject) -> Path | None:
    evidence = _recorded_base_resume_evidence(run_state)
    if isinstance(evidence, dict):
        path_value = evidence.get("path")
        if isinstance(path_value, str) and path_value:
            return _resolve_path(run_state, path_value)
    return None


def _recorded_base_resume_evidence(run_state: JsonObject) -> JsonObject | None:
    for parent_key in ("stage_state", "verified_evidence"):
        parent = run_state.get(parent_key)
        if not isinstance(parent, dict):
            continue
        validate_base = parent.get("VALIDATE_BASE")
        if not isinstance(validate_base, dict):
            continue
        evidence = validate_base.get("canonical_resume_exists")
        if isinstance(evidence, dict):
            return dict(evidence)
    return None


def _base_resume_evidence_ref(run_state: JsonObject) -> JsonObject:
    evidence = _recorded_base_resume_evidence(run_state)
    if not isinstance(evidence, dict):
        return {"kind": "base_resume_hash", "path": None, "sha256": None}
    return {
        "kind": "base_resume_hash",
        "path": evidence.get("path"),
        "sha256": evidence.get("sha256"),
    }


def _verify_rejected_operations(run_state: JsonObject) -> JsonObject:
    log_path = _log_path_if_recorded(run_state, "operations.jsonl")
    if log_path is None:
        evidence_ref = {"kind": "operations_log_scan", "path": _expected_log_display_path(run_state, "operations.jsonl"), "record_count": 0}
        if _run_state_records_operations(run_state):
            return _failed("operations_log_missing", evidence_ref)
        return _verified("no_operations_recorded", evidence_ref)

    try:
        records = _read_jsonl_records(log_path)
    except Exception as exc:
        return _failed(
            f"operations_log_unreadable:{exc}",
            {"kind": "operations_log_scan", "path": _display_path(run_state, log_path), "record_count": 0},
        )
    rejected_seen: set[str] = set()
    offending: list[str] = []
    for record in records:
        operation_id = record.get("operation_id")
        status = record.get("status")
        if not isinstance(operation_id, str) or not operation_id:
            continue
        if status == "rejected":
            rejected_seen.add(operation_id)
        elif status == "applied" and operation_id in rejected_seen and operation_id not in offending:
            offending.append(operation_id)
    evidence_ref = {
        "kind": "operations_log_scan",
        "path": _display_path(run_state, log_path),
        "record_count": len(records),
        "rejected_operation_ids": sorted(rejected_seen),
    }
    if offending:
        evidence_ref["offending_operation_ids"] = sorted(offending)
        return _failed(f"rejected_operation_applied_later:{','.join(sorted(offending))}", evidence_ref)
    return _verified("rejected_operations_remain_rejected", evidence_ref)


def _run_state_records_operations(run_state: JsonObject) -> bool:
    for key in ("operation_log_refs", "operation_statuses", "operations_applied", "operations_rejected", "already_applied_operations"):
        value = run_state.get(key)
        if isinstance(value, list) and value:
            return True
    return False


def _log_path_if_recorded(run_state: JsonObject, filename: str) -> Path | None:
    try:
        path = _run_dir(run_state) / filename
    except ValueError:
        return None
    return path if path.exists() else None


def _run_dir(run_state: JsonObject) -> Path:
    workspace = run_state.get("workspace")
    run_id = run_state.get("run_id")
    if not workspace or not run_id:
        raise ValueError("Workflow log recovery requires a run_state with workspace and run_id.")
    return Path(str(workspace)) / ".workflow" / "runs" / str(run_id)


def _expected_log_display_path(run_state: JsonObject, filename: str) -> str | None:
    try:
        return _display_path(run_state, _run_dir(run_state) / filename)
    except ValueError:
        return None


def _read_jsonl_records(path: Path) -> list[JsonObject]:
    records: list[JsonObject] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        value = json.loads(line)
        if isinstance(value, dict):
            records.append(value)
    return records


def _resolve_path(run_state: JsonObject, path_value: str) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    workspace = run_state.get("workspace")
    return Path(str(workspace)) / path if workspace else path


def _display_path(run_state: JsonObject, path: Path) -> str:
    workspace = run_state.get("workspace")
    if workspace:
        try:
            return str(path.relative_to(Path(str(workspace))))
        except ValueError:
            pass
    return str(path)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verified(reason: str, evidence_ref: JsonObject) -> JsonObject:
    return {"status": "verified", "evidence_ref": evidence_ref, "reason": reason}


def _failed(reason: str, evidence_ref: JsonObject) -> JsonObject:
    return {"status": "failed", "evidence_ref": evidence_ref, "reason": reason}


def _unverified(reason: str, evidence_ref: JsonObject) -> JsonObject:
    return {"status": "unverified", "evidence_ref": evidence_ref, "reason": reason}


def _jsonable_dict(value: JsonObject) -> JsonObject:
    return json.loads(json.dumps(value, sort_keys=True, default=str))
