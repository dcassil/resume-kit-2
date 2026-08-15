"""Private support helpers for the SQLite-backed career store."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from typing import Any

from .schemas import InterpretationProposal


JsonObject = dict[str, Any]

_FORBIDDEN_RESULT_KEYS = {
    "raw_sql",
    "connection",
    "internal_rows",
    "silent_user_verified_promotion",
    "implicit_confirmation",
    "destructive_delete",
    "related_as_equivalent_without_policy",
    "official_score",
    "destructive_resolution",
    "resume_patch",
    "working_resume",
    "base_resume",
}


def _stable_id(prefix: str, *parts: Any) -> str:
    payload = "\x1f".join(str(part) for part in parts)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]
    return f"{prefix}_{digest}"


def _to_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _from_json(value: str | None, fallback: Any) -> Any:
    if value is None:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_bool(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, (int, float)):
        return 1 if value else 0
    normalized = _normalize(value)
    if normalized in {"true", "yes", "confirmed", "user confirmed", "1"}:
        return 1
    if normalized in {"false", "no", "unconfirmed", "0"}:
        return 0
    return None


def _add_if_not_none(target: JsonObject, key: str, value: Any) -> None:
    if value is not None:
        target[key] = value


def _job_metadata(metadata: JsonObject) -> JsonObject:
    job_keys = {"title", "job_title", "company", "employer", "url", "job_url", "source", "source_id"}
    return {key: value for key, value in metadata.items() if key in job_keys}


def _normalize(value: Any) -> str:
    text = str(value).casefold().strip()
    return " ".join("".join(char if char.isalnum() else " " for char in text).split())


def _state_value(value: Any) -> str:
    return str(getattr(value, "value", value))


def _validation_error(code: str, field_path: str, allowed_values: set[str]) -> JsonObject:
    return {
        "code": code,
        "field_path": field_path,
        "message": f"Invalid {field_path}.",
        "allowed_values": sorted(allowed_values),
    }


def _has_explicit_confirmation(policy: JsonObject, evidence: JsonObject | None, source: str) -> bool:
    if policy.get("explicit_confirmation") is True:
        return True
    if policy.get("confirmation") is True or policy.get("confirmed") is True:
        return True
    if source in {"user_confirmation", "manual_confirmation", "explicit_user_answer"}:
        return True
    if evidence:
        if evidence.get("source") in {"user_confirmation", "manual_confirmation", "explicit_user_answer"}:
            return True
        metadata = evidence.get("metadata", {})
        if isinstance(metadata, dict) and (metadata.get("explicit") is True or metadata.get("confirmed") is True):
            return True
    return False


def _authority_ref(evidence: JsonObject | None, source: str, fallback_text: str) -> JsonObject:
    if isinstance(evidence, dict):
        ref = dict(evidence)
    else:
        ref = {}
    ref["source"] = str(ref.get("source") or source)
    ref["text"] = str(ref.get("text") or fallback_text)
    if isinstance(ref.get("metadata"), dict):
        ref["metadata"] = dict(ref["metadata"])
    return ref


def _source_document_ref(fact_id: str, evidence: JsonObject | None, source: str, policy: JsonObject) -> JsonObject:
    ref = _authority_ref(evidence, source, "Source document stated this career fact.")
    metadata = dict(ref.get("metadata", {})) if isinstance(ref.get("metadata"), dict) else {}
    if not any(ref.get(key) for key in ("source_id", "source_span")) and not any(
        metadata.get(key) for key in ("document_id", "resume_id", "claim_id")
    ):
        if ref["source"] in {"resume", "job", "document", "profile"}:
            metadata["document_id"] = str(policy.get("document_id") or policy.get("resume_id") or ref["source"])
            metadata["claim_id"] = fact_id
    if metadata:
        ref["metadata"] = metadata
    return ref


def _inference_ref(fact_id: str, evidence: JsonObject | None, source: str) -> JsonObject:
    ref = _authority_ref(evidence, source, "Agent inferred this career fact.")
    metadata = dict(ref.get("metadata", {})) if isinstance(ref.get("metadata"), dict) else {}
    if not any(metadata.get(key) for key in ("agent_id", "model", "rationale", "inference_id")):
        metadata["rationale"] = f"upsertFact inference for {fact_id}"
    ref["metadata"] = metadata
    return ref


def _upsert_user_proposal(fact_id: str, evidence: JsonObject | None, source: str) -> InterpretationProposal:
    ref = _authority_ref(evidence, source, "User explicitly confirmed this career fact.")
    return InterpretationProposal(
        factId=fact_id,
        questionId=None,
        outcome="affirmed",
        confirmedValue=None,
        provenance=[ref],
    )


def _conflict_object(fact_ids: list[str], reason: str, metadata: JsonObject) -> JsonObject:
    clean_fact_ids = sorted(set(fact_id for fact_id in fact_ids if fact_id))
    return {
        "conflict_id": _stable_id("conflict", "|".join(clean_fact_ids), reason),
        "fact_ids": clean_fact_ids,
        "reason": reason,
        "status": "open",
        "evidence_ids": [],
        "metadata": metadata,
    }


def _conflict_from_row(row: sqlite3.Row) -> JsonObject:
    return {
        "conflict_id": str(row["conflict_id"]),
        "fact_ids": _from_json(str(row["fact_ids_json"]), []),
        "reason": str(row["reason"]),
        "status": str(row["status"]),
        "evidence_ids": _from_json(str(row["evidence_ids_json"]), []),
        "metadata": _from_json(str(row["metadata_json"]), {}),
    }


def _dedupe_conflicts(conflicts: list[JsonObject]) -> list[JsonObject]:
    deduped = {str(conflict["conflict_id"]): conflict for conflict in conflicts}
    return [deduped[key] for key in sorted(deduped)]


def _clean_result(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _clean_result(item) for key, item in value.items() if key not in _FORBIDDEN_RESULT_KEYS}
    if isinstance(value, list):
        return [_clean_result(item) for item in value]
    return value
