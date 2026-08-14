"""Claim-level grounding helpers for resume-core."""

from __future__ import annotations

from enum import Enum
from typing import Any

from .change_operations import operation_path
from .schemas import JsonObject, VerificationState


VERIFIED_FACT_STATES = {
    VerificationState.SOURCE_STATED.value,
    VerificationState.USER_VERIFIED.value,
    VerificationState.IMPORTED.value,
}


def grounding_claim_records(resume: JsonObject, applied_operations: list[JsonObject]) -> list[JsonObject]:
    claims = _resume_field_claim_records(resume)
    root_provenance = _array(_item(resume, "provenance", []))
    if claims and root_provenance and not any(_array(_item(claim, "provenance", [])) for claim in claims):
        for claim in claims:
            claim["legacy_root_provenance"] = True
    claims.extend(_operation_claim_records(applied_operations))
    return sorted(claims, key=lambda item: (str(_item(item, "field_path", "")), str(_item(item, "claim_id", ""))))


def claim_linked_fact_ids(claim: JsonObject) -> list[str]:
    seen: set[str] = set()
    fact_ids: list[str] = []

    def add(raw: Any) -> None:
        fact_id = str(raw)
        if fact_id and fact_id not in seen:
            seen.add(fact_id)
            fact_ids.append(fact_id)

    for fact_id in _array(_item(claim, "linked_fact_ids", [])):
        add(fact_id)
    for entry in _array(_item(claim, "provenance", [])):
        if not isinstance(entry, dict):
            continue
        for key in ("fact_id", "career_fact_id", "source_fact_id"):
            if _item(entry, key):
                add(_item(entry, key))
        for fact_id in _array(_item(entry, "linked_fact_ids", [])):
            add(fact_id)
    return fact_ids


def missing_provenance(claims: list[JsonObject], fact_index: dict[str, JsonObject]) -> list[JsonObject]:
    missing: list[JsonObject] = []
    for claim in sorted(claims, key=lambda item: (str(_item(item, "field_path", "")), str(_item(item, "claim_id", "")))):
        supported, reason, supporting_fact_ids = _claim_has_verified_provenance(claim, fact_index)
        if supported:
            continue
        details = {
            "claim_id": str(_item(claim, "claim_id", "")),
            "reason": reason,
            "source": str(_item(claim, "source", "")),
        }
        if _item(claim, "operation_id"):
            details["operation_id"] = str(_item(claim, "operation_id"))
        if supporting_fact_ids:
            details["supporting_fact_ids"] = supporting_fact_ids
        finding: JsonObject = {
            "code": "missing_provenance",
            "message": "Claim requires verified provenance.",
            "severity": "error",
            "field_path": str(_item(claim, "field_path", "")),
            "details": details,
            "reason": reason,
        }
        missing.append(finding)
    return missing


def _resume_field_claim_records(value: Any, pointer: str = "") -> list[JsonObject]:
    claims: list[JsonObject] = []
    if _resume_field_record(value):
        field = value if isinstance(value, dict) else {}
        claims.append(
            {
                "source": "resume",
                "field_path": pointer or "/",
                "claim_id": str(_item(field, "claim_id", "")),
                "text": _text(_item(field, "value")),
                "provenance": _array(_item(field, "provenance", [])),
                "verification_state": str(_item(field, "verification_state", VerificationState.UNKNOWN.value)),
            }
        )
        return claims
    if isinstance(value, dict):
        for key in sorted(value):
            claims.extend(_resume_field_claim_records(value[key], f"{pointer}/{_json_pointer_token(key)}"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            claims.extend(_resume_field_claim_records(item, f"{pointer}/{index}"))
    return claims


def _operation_claim_records(applied_operations: list[JsonObject]) -> list[JsonObject]:
    claims: list[JsonObject] = []
    for index, operation in enumerate(applied_operations):
        if not isinstance(operation, dict):
            continue
        after = _item(operation, "after")
        if after is None:
            continue
        path = operation_path(operation) or f"/applied_operations/{index}"
        operation_id = str(_item(operation, "operation_id", f"operation_{index}"))
        claims.append(
            {
                "source": "applied_operation",
                "field_path": path,
                "claim_id": operation_id,
                "text": _text(after),
                "provenance": _array(_item(operation, "provenance", [])),
                "linked_fact_ids": [str(fact_id) for fact_id in _array(_item(operation, "linked_fact_ids", []))],
                "operation_id": operation_id,
            }
        )
    return claims


def _claim_has_verified_provenance(claim: JsonObject, fact_index: dict[str, JsonObject]) -> tuple[bool, str, list[str]]:
    if _item(claim, "legacy_root_provenance"):
        return True, "", []

    linked_fact_ids = claim_linked_fact_ids(claim)
    non_grounding_fact_ids: list[str] = []
    for fact_id in linked_fact_ids:
        fact = _item(fact_index, fact_id)
        if isinstance(fact, dict) and _claim_fact_allowed(fact):
            return True, "", [fact_id]
        if isinstance(fact, dict):
            non_grounding_fact_ids.append(fact_id)

    provenance = [entry for entry in _array(_item(claim, "provenance", [])) if isinstance(entry, dict)]
    for entry in provenance:
        if _provenance_entry_allowed(entry) and not any(_item(entry, key) for key in ("fact_id", "career_fact_id", "source_fact_id")):
            return True, "", []

    state = str(_item(claim, "verification_state", VerificationState.UNKNOWN.value))
    if provenance and state in VERIFIED_FACT_STATES and not linked_fact_ids:
        return True, "", []
    if any(_item(fact_index, fact_id) for fact_id in linked_fact_ids) or provenance:
        if _claim_has_inferred_support(claim, fact_index):
            return False, "inferred_fact_not_allowed", non_grounding_fact_ids
        return False, "missing_verified_fact", non_grounding_fact_ids
    return False, "missing_provenance", []


def _resume_field_record(value: Any) -> bool:
    return isinstance(value, dict) and "value" in value and (
        "claim_id" in value or "provenance" in value or "verification_state" in value
    )


def _claim_fact_allowed(fact: JsonObject) -> bool:
    return _item(fact, "verification_state", VerificationState.UNKNOWN.value) in VERIFIED_FACT_STATES


def _provenance_entry_allowed(entry: JsonObject) -> bool:
    return _item(entry, "verification_state", VerificationState.UNKNOWN.value) in VERIFIED_FACT_STATES


def _claim_has_inferred_support(claim: JsonObject, fact_index: dict[str, JsonObject]) -> bool:
    for fact_id in claim_linked_fact_ids(claim):
        fact = _item(fact_index, fact_id)
        if isinstance(fact, dict) and _item(fact, "verification_state") == VerificationState.INFERRED.value:
            return True
    for entry in _array(_item(claim, "provenance", [])):
        if isinstance(entry, dict) and _item(entry, "verification_state") == VerificationState.INFERRED.value:
            return True
    return False


def _json_pointer_token(value: Any) -> str:
    return str(value).replace("~", "~0").replace("/", "~1")


def _item(mapping: Any, key: str, default: Any = None) -> Any:
    if isinstance(mapping, dict) and key in mapping:
        return mapping[key]
    return default


def _array(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> str:
    value = _to_json(value)
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        return " ".join(_text(item) for item in value)
    if isinstance(value, dict):
        return " ".join(_text(item) for key, item in sorted(value.items()) if key != "metadata")
    return str(value)


def _to_json(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, list):
        return [_to_json(item) for item in value]
    if isinstance(value, tuple):
        return [_to_json(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _to_json(item) for key, item in value.items()}
    return value
