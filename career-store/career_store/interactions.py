"""Append-only interaction history substrate for career-store."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Callable
from typing import Any


JsonObject = dict[str, Any]

INTERACTION_TYPES: tuple[str, ...] = (
    "question_asked",
    "answer_recorded",
    "fact_confirmed",
    "rewrite_accepted",
    "rewrite_modified",
    "rewrite_rejected",
)

_INTERACTION_TYPE_SET = set(INTERACTION_TYPES)
_FILTER_KEYS = {"interaction_type", "subject_id", "created_at_from", "created_at_to"}


class InteractionError(ValueError):
    """Base class for typed interaction validation errors."""

    code = "invalid_interaction"
    field_path = "interaction"

    def to_error(self) -> JsonObject:
        return {
            "type": self.__class__.__name__,
            "code": self.code,
            "field_path": self.field_path,
            "message": str(self),
        }


class UnknownInteractionTypeError(InteractionError):
    code = "unknown_interaction_type"
    field_path = "interaction_type"

    def __init__(self, interaction_type: Any) -> None:
        self.interaction_type = interaction_type
        super().__init__(f"Unknown interaction_type: {interaction_type!r}.")

    def to_error(self) -> JsonObject:
        error = super().to_error()
        error["allowed_values"] = list(INTERACTION_TYPES)
        return error


class MalformedInteractionError(InteractionError):
    code = "malformed_interaction"

    def __init__(self, field_path: str, expected: str) -> None:
        self.field_path = field_path
        self.expected = expected
        super().__init__(f"Malformed {field_path}; expected {expected}.")


class MalformedInteractionFilterError(InteractionError):
    code = "malformed_interaction_filter"

    def __init__(self, field_path: str, expected: str) -> None:
        self.field_path = field_path
        self.expected = expected
        super().__init__(f"Malformed {field_path}; expected {expected}.")


def build_interaction_row(
    interaction_type: Any,
    subject_id: Any,
    input_json: Any,
    result_json: Any,
    created_at: str,
) -> JsonObject:
    clean_type = _validate_interaction_type(interaction_type)
    clean_subject_id = _required_text(subject_id, "subject_id")
    clean_input_json = _required_object(input_json, "input_json")
    clean_result_json = _optional_object(result_json, "result_json")
    input_payload = _to_json(clean_input_json)
    return {
        "id": _stable_id("interaction", clean_type, clean_subject_id, input_payload),
        "interaction_type": clean_type,
        "subject_id": clean_subject_id,
        "input_json": input_payload,
        "result_json": _to_json(clean_result_json),
        "created_at": created_at,
    }


def insert_interaction(conn: sqlite3.Connection, row: JsonObject) -> None:
    conn.execute(
        """
        INSERT OR IGNORE INTO interactions (
            id, interaction_type, subject_id, input_json, result_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            row["id"],
            row["interaction_type"],
            row["subject_id"],
            row["input_json"],
            row["result_json"],
            row["created_at"],
        ),
    )


def _record_interaction_in_transaction(
    conn: sqlite3.Connection,
    txn: Any,
    interaction_type: str,
    subject_id: str,
    input_json: JsonObject,
    result_json: JsonObject | None,
    created_at: str,
) -> JsonObject:
    row = build_interaction_row(interaction_type, subject_id, input_json, result_json, created_at)
    interaction_id = str(row["id"])
    txn.touch("interaction_id", interaction_id)
    existing = conn.execute("SELECT id FROM interactions WHERE id = ?", (interaction_id,)).fetchone()
    insert_interaction(conn, row)
    return {
        "id": interaction_id,
        "interaction_type": row["interaction_type"],
        "subject_id": row["subject_id"],
        "input_json": input_json,
        "result_json": result_json or {},
        "created_at": row["created_at"],
        "mutation_status": "unchanged" if existing else "created",
    }


def list_interactions(conn: sqlite3.Connection, filters: Any | None = None) -> list[JsonObject]:
    clean_filters = _validate_filters(filters)
    clauses: list[str] = []
    params: list[str] = []
    if clean_filters.get("interaction_type") is not None:
        clauses.append("interaction_type = ?")
        params.append(clean_filters["interaction_type"])
    if clean_filters.get("subject_id") is not None:
        clauses.append("subject_id = ?")
        params.append(clean_filters["subject_id"])
    if clean_filters.get("created_at_from") is not None:
        clauses.append("created_at >= ?")
        params.append(clean_filters["created_at_from"])
    if clean_filters.get("created_at_to") is not None:
        clauses.append("created_at <= ?")
        params.append(clean_filters["created_at_to"])
    query = "SELECT * FROM interactions"
    if clauses:
        query = f"{query} WHERE {' AND '.join(clauses)}"
    query = f"{query} ORDER BY created_at, id"
    rows = conn.execute(query, params).fetchall()
    return [_interaction_from_row(row) for row in rows]


def _record_interaction_result(
    transaction: Callable[..., Any],
    clock: Callable[[], str],
    audit: Callable[..., JsonObject],
    transaction_payload: Callable[[Any], JsonObject | None],
    schema_version: str,
    interaction_type: str,
    subject_id: str,
    input_json: JsonObject,
    result_json: JsonObject | None = None,
) -> JsonObject:
    now = clock()
    try:
        row = build_interaction_row(interaction_type, subject_id, input_json, result_json, now)
    except InteractionError as exc:
        return {
            "schema_version": schema_version,
            "status": "rejected",
            "mutation_status": "rejected",
            "interaction_id": None,
            "errors": [exc.to_error()],
            "transaction_result": None,
            "audit": audit("recordInteraction", mutated=False),
        }
    with transaction("recordInteraction", "created") as txn:
        conn = txn.connection
        assert conn is not None
        interaction = _record_interaction_in_transaction(
            conn,
            txn,
            row["interaction_type"],
            row["subject_id"],
            input_json,
            result_json,
            row["created_at"],
        )
        interaction_id = str(interaction["id"])
        mutation_status = str(interaction["mutation_status"])
        txn.set_mutation_status(mutation_status)
        result = {
            "schema_version": schema_version,
            "status": mutation_status,
            "mutation_status": mutation_status,
            "interaction_id": interaction_id,
            "interaction": {
                "id": interaction_id,
                "interaction_type": interaction["interaction_type"],
                "subject_id": interaction["subject_id"],
                "input_json": input_json,
                "result_json": result_json or {},
                "created_at": interaction["created_at"],
            },
            "transaction_result": None,
            "audit": audit("recordInteraction", mutated=True),
        }
    result["transaction_result"] = transaction_payload(txn.result)
    return result


def _list_interactions_result(
    connect: Callable[[], Any],
    audit: Callable[..., JsonObject],
    schema_version: str,
    filters: JsonObject | None = None,
) -> JsonObject:
    try:
        with connect() as conn:
            interactions = list_interactions(conn, filters)
    except InteractionError as exc:
        return {
            "schema_version": schema_version,
            "status": "error",
            "interactions": [],
            "errors": [exc.to_error()],
            "audit": audit("listInteractions", mutated=False),
        }
    return {
        "schema_version": schema_version,
        "status": "ok",
        "interactions": interactions,
        "audit": audit("listInteractions", mutated=False),
    }


def _interaction_from_row(row: sqlite3.Row) -> JsonObject:
    return {
        "id": str(row["id"]),
        "interaction_type": str(row["interaction_type"]),
        "subject_id": str(row["subject_id"]),
        "input_json": _from_json(str(row["input_json"]), {}),
        "result_json": _from_json(str(row["result_json"]), {}),
        "created_at": str(row["created_at"]),
    }


def _validate_filters(filters: Any | None) -> JsonObject:
    if filters is None:
        return {}
    if not isinstance(filters, dict):
        raise MalformedInteractionFilterError("filter", "object")
    unknown_keys = set(filters) - _FILTER_KEYS
    if unknown_keys:
        raise MalformedInteractionFilterError(f"filter.{sorted(unknown_keys)[0]}", f"one of {sorted(_FILTER_KEYS)}")
    clean: JsonObject = {}
    if filters.get("interaction_type") is not None:
        clean["interaction_type"] = _validate_interaction_type(filters["interaction_type"])
    if filters.get("subject_id") is not None:
        clean["subject_id"] = _required_filter_text(filters["subject_id"], "filter.subject_id")
    for key in ("created_at_from", "created_at_to"):
        if filters.get(key) is not None:
            clean[key] = _required_filter_text(filters[key], f"filter.{key}")
    if clean.get("created_at_from") and clean.get("created_at_to") and clean["created_at_from"] > clean["created_at_to"]:
        raise MalformedInteractionFilterError("filter.created_at", "created_at_from <= created_at_to")
    return clean


def _validate_interaction_type(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MalformedInteractionError("interaction_type", "non-empty string")
    interaction_type = value.strip()
    if interaction_type not in _INTERACTION_TYPE_SET:
        raise UnknownInteractionTypeError(interaction_type)
    return interaction_type


def _required_text(value: Any, field_path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MalformedInteractionError(field_path, "non-empty string")
    return value.strip()


def _required_filter_text(value: Any, field_path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MalformedInteractionFilterError(field_path, "non-empty string")
    return value.strip()


def _required_object(value: Any, field_path: str) -> JsonObject:
    if not isinstance(value, dict):
        raise MalformedInteractionError(field_path, "object")
    return dict(value)


def _optional_object(value: Any, field_path: str) -> JsonObject:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise MalformedInteractionError(field_path, "object")
    return dict(value)


def _stable_id(prefix: str, *parts: Any) -> str:
    payload = "\x1f".join(str(part) for part in parts)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]
    return f"{prefix}_{digest}"


def _to_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _from_json(value: str, fallback: Any) -> Any:
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


__all__ = [
    "INTERACTION_TYPES",
    "InteractionError",
    "MalformedInteractionError",
    "MalformedInteractionFilterError",
    "UnknownInteractionTypeError",
    "build_interaction_row",
    "insert_interaction",
    "list_interactions",
]
