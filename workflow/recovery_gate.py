"""Private completion-gate helpers for recovery reruns."""

from __future__ import annotations

from typing import Any


JsonObject = dict[str, Any]


def checkpoint_result_event(run_state: JsonObject, checkpoint: str, result_sequence: int, result_ref: JsonObject) -> JsonObject:
    return {
        "checkpoint": checkpoint,
        "result_sequence": result_sequence,
        "recovery_sequence": latest_recovery_sequence(run_state),
        "result_ref": dict(result_ref),
    }


def recovery_reruns_gate_result(run_state: JsonObject) -> JsonObject:
    latest_recovery = latest_recovery_event(run_state)
    if latest_recovery is None:
        return {"passed": True, "reason": "ok"}
    required = [str(checkpoint) for checkpoint in latest_recovery.get("required_reruns", [])]
    if not required:
        return {"passed": True, "reason": "ok"}
    recovery_sequence = coerce_sequence(latest_recovery.get("recovery_sequence"))
    fresh = fresh_recovery_rerun_checkpoints(run_state, recovery_sequence)
    missing = [checkpoint for checkpoint in required if checkpoint not in fresh]
    if not missing:
        return {"passed": True, "reason": "ok"}
    return {
        "passed": False,
        "reason": {
            "recovery_sequence": recovery_sequence,
            "missing_or_stale_checkpoints": missing,
        },
    }


def latest_recovery_event(run_state: JsonObject) -> JsonObject | None:
    events = [event for event in run_state.get("recovery_events", []) if isinstance(event, dict)]
    if not events:
        return None
    return dict(max(events, key=lambda event: coerce_sequence(event.get("recovery_sequence"))))


def latest_recovery_sequence(run_state: JsonObject) -> int:
    latest = latest_recovery_event(run_state)
    if latest is None:
        return 0
    return coerce_sequence(latest.get("recovery_sequence"))


def fresh_recovery_rerun_checkpoints(run_state: JsonObject, recovery_sequence: int) -> set[str]:
    fresh: set[str] = set()
    for event in run_state.get("checkpoint_result_events", []):
        if not isinstance(event, dict):
            continue
        if coerce_sequence(event.get("recovery_sequence")) != recovery_sequence:
            continue
        checkpoint = event.get("checkpoint")
        if isinstance(checkpoint, str) and checkpoint:
            fresh.add(checkpoint)
    return fresh


def next_checkpoint_result_sequence(run_state: JsonObject) -> int:
    sequence = 1
    for event in run_state.get("checkpoint_result_events", []):
        if not isinstance(event, dict):
            continue
        sequence = max(sequence, coerce_sequence(event.get("result_sequence")) + 1)
    return sequence


def coerce_sequence(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
