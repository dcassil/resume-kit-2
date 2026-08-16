"""Private dedupe-registry enforcement helpers for workflow recovery."""

from __future__ import annotations

from typing import Any


JsonObject = dict[str, Any]

_REGISTRY_KEYS = ("already_applied_operations", "already_asked_questions", "already_written_facts")


def merge_recovery_registries(merged: JsonObject, persisted: JsonObject, incoming: JsonObject) -> None:
    for key in _REGISTRY_KEYS:
        merged[key] = _dedupe(list(persisted.get(key, [])) + list(incoming.get(key, [])))


def apply_checkpoint_idempotency(
    run_state: JsonObject,
    checkpoint_result: JsonObject,
    operation_records: list[JsonObject],
) -> tuple[JsonObject, list[JsonObject], JsonObject]:
    sanitized = dict(checkpoint_result)
    sanitized, fact_results = _filter_duplicate_facts(run_state, sanitized)
    sanitized, operation_records, operation_results = _filter_duplicate_applied_operations(
        run_state,
        sanitized,
        operation_records,
    )
    response_fields: JsonObject = {
        "fact_results": fact_results,
        "operation_results": operation_results,
    }
    if fact_results:
        sanitized["fact_results"] = fact_results
    if operation_results:
        sanitized["operation_results"] = operation_results
    return sanitized, operation_records, response_fields


def _filter_duplicate_facts(run_state: JsonObject, checkpoint_result: JsonObject) -> tuple[JsonObject, list[JsonObject]]:
    already = {str(value) for value in run_state.get("already_written_facts", [])}
    accepted: set[str] = set()
    results: list[JsonObject] = []
    updated = dict(checkpoint_result)
    for key in ("facts_verified", "facts_added"):
        values = updated.get(key)
        if not isinstance(values, list):
            continue
        kept: list[Any] = []
        for value in values:
            fact_id = _fact_id(value)
            if not fact_id:
                continue
            if fact_id in already or fact_id in accepted:
                results.append({"status": "duplicate", "reason": "already_written_fact", "fact_id": fact_id})
                continue
            accepted.add(fact_id)
            kept.append(value)
        updated[key] = kept
    return updated, _dedupe_dicts(results)


def _filter_duplicate_applied_operations(
    run_state: JsonObject,
    checkpoint_result: JsonObject,
    operation_records: list[JsonObject],
) -> tuple[JsonObject, list[JsonObject], list[JsonObject]]:
    already = {str(value) for value in run_state.get("already_applied_operations", [])}
    duplicate_ids: set[str] = set()
    results: list[JsonObject] = []
    kept_records: list[JsonObject] = []
    for record in operation_records:
        operation_id = _operation_id(record)
        if str(record.get("status", "")) == "applied" and operation_id in already:
            duplicate_ids.add(operation_id)
            results.append({"status": "duplicate", "reason": "already_applied_operation", "operation_id": operation_id})
            continue
        kept_records.append(record)
    if not duplicate_ids:
        return checkpoint_result, kept_records, []
    updated = dict(checkpoint_result)
    for key in ("operations_applied", "applied"):
        updated[key] = _filter_operation_list(updated.get(key), duplicate_ids, default_status="applied")
    for key in ("operation_statuses", "operation_records", "validation_results"):
        updated[key] = _filter_operation_list(updated.get(key), duplicate_ids)
    return updated, kept_records, _dedupe_dicts(results)


def _filter_operation_list(value: Any, duplicate_ids: set[str], default_status: str | None = None) -> list[Any]:
    if not isinstance(value, list):
        return []
    kept: list[Any] = []
    for item in value:
        operation_id = _operation_id(item)
        status = str(item.get("status") or default_status or item.get("validation_state") or "") if isinstance(item, dict) else str(default_status or "")
        if status == "applied" and operation_id in duplicate_ids:
            continue
        kept.append(item)
    return kept


def _fact_id(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("fact_id") or value.get("id") or "")
    return str(value) if value not in (None, "") else ""


def _operation_id(value: Any) -> str:
    if isinstance(value, dict):
        validation = value.get("validation")
        if isinstance(validation, dict) and validation.get("operation_id"):
            return str(validation["operation_id"])
        return str(value.get("operation_id") or "")
    return str(value) if value not in (None, "") else ""


def _dedupe(values: list[Any]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value)
        if text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _dedupe_dicts(values: list[JsonObject]) -> list[JsonObject]:
    seen: set[tuple[str, str, str]] = set()
    result: list[JsonObject] = []
    for value in values:
        identity = (
            str(value.get("status", "")),
            str(value.get("reason", "")),
            str(value.get("fact_id") or value.get("operation_id") or ""),
        )
        if identity in seen:
            continue
        seen.add(identity)
        result.append(dict(value))
    return result
