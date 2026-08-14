"""Claim-level ResumeField weaving helpers for resume normalization."""

from __future__ import annotations

import copy
import hashlib
from enum import Enum
from typing import Any

from .schemas import JsonObject, VerificationState


def provenance_index(provenance: list[Any]) -> dict[str, list[JsonObject]]:
    index: dict[str, list[JsonObject]] = {}
    for entry in provenance:
        if isinstance(entry, dict) and "claim_id" in entry:
            claim_id = str(entry["claim_id"])
            index.setdefault(claim_id, []).append(copy.deepcopy(entry))
    return index


def weave_claim_fields(resume: JsonObject, provenance_by_claim: dict[str, list[JsonObject]]) -> None:
    if "summary" in resume:
        resume["summary"] = _summary_resume_fields(_item(resume, "summary"), provenance_by_claim)

    resume["skills"] = [
        _resume_field(item, f"skills/{index}", provenance_by_claim)
        for index, item in enumerate(_array(_item(resume, "skills", [])))
    ]

    for experience_index, entry in enumerate(_array(_item(resume, "experience", []))):
        if not isinstance(entry, dict) or "bullets" not in entry:
            continue
        entry["bullets"] = [
            _resume_field(item, f"experience/{experience_index}/bullets/{bullet_index}", provenance_by_claim)
            for bullet_index, item in enumerate(_array(_item(entry, "bullets", [])))
        ]


def _summary_resume_fields(value: Any, provenance_by_claim: dict[str, list[JsonObject]]) -> Any:
    if isinstance(value, str):
        lines = [line.strip() for line in value.splitlines() if line.strip()]
        if len(lines) > 1:
            return [_resume_field(line, f"summary/{index}", provenance_by_claim) for index, line in enumerate(lines)]
    if isinstance(value, list):
        return [_resume_field(item, f"summary/{index}", provenance_by_claim) for index, item in enumerate(value)]
    return _resume_field(value, "summary", provenance_by_claim)


def _resume_field(value: Any, path: str, provenance_by_claim: dict[str, list[JsonObject]]) -> JsonObject:
    if isinstance(value, dict) and "value" in value:
        field = copy.deepcopy(value)
    else:
        field = {"value": copy.deepcopy(value)}

    claim_id = str(_item(field, "claim_id") or _stable_claim_id(path, _item(field, "value")))
    field["claim_id"] = claim_id

    provenance = [
        copy.deepcopy(entry)
        for entry in _array(_item(field, "provenance", []))
        if _identifiable_provenance(entry)
    ]
    provenance.extend(copy.deepcopy(entry) for entry in provenance_by_claim.get(claim_id, []) if _identifiable_provenance(entry))
    field["provenance"] = provenance
    field["verification_state"] = _claim_verification_state(field, provenance)
    return field


def _stable_claim_id(path: str, value: Any) -> str:
    return _stable_id("claim", {"path": path, "value": value})


def _identifiable_provenance(entry: Any) -> bool:
    return isinstance(entry, dict) and bool(_item(entry, "source")) and bool(_item(entry, "text"))


def _claim_verification_state(field: JsonObject, provenance: list[JsonObject]) -> str:
    valid_states = {item.value for item in VerificationState}
    if not provenance:
        return VerificationState.UNKNOWN.value

    existing_state = _item(field, "verification_state")
    if existing_state in valid_states:
        return str(existing_state)

    for entry in provenance:
        state = _item(entry, "verification_state")
        if state in valid_states:
            return str(state)

    return VerificationState.SOURCE_STATED.value


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


def _stable_id(prefix: str, value: Any) -> str:
    digest = hashlib.sha256(_text(value).encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{digest}"
