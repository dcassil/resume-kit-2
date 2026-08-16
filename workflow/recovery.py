"""Private recovery contract helpers for workflow."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable


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
    integrity = _recovery_integrity(run_state)
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


def _recovery_integrity(run_state: JsonObject) -> JsonObject:
    return {name: _recovery_integrity_check(name, run_state) for name in _RECOVERY_INTEGRITY_CHECKS}


def _recovery_integrity_check(name: str, run_state: JsonObject) -> JsonObject:
    return {
        "status": "unverified",
        "evidence_ref": None,
        "reason": "verification_not_implemented",
    }


def _recovery_resumable(integrity: JsonObject) -> bool:
    return all(check.get("status") != "failed" for check in integrity.values() if isinstance(check, dict))
