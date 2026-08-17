"""Audit event construction for the local career MCP adapter."""

from __future__ import annotations

import copy
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from . import policy


JsonObject = dict[str, Any]

GENERIC_STORE_ERROR_MESSAGE = "Career store operation failed."
SQL_IDENTIFIER_PATTERN = r'(?:[A-Za-z_][A-Za-z0-9_]*|"[^"]+"|`[^`]+`|\[[^\]]+\])'
PERSISTENCE_LEAK_PATTERNS = (
    re.compile(r"\b" + "insert" + r"\s+" + "into" + r"\b", re.IGNORECASE),
    re.compile(r"\b" + "update" + r"\s+" + SQL_IDENTIFIER_PATTERN + r"\s+" + "set" + r"\b", re.IGNORECASE),
    re.compile(r"\b" + "delete" + r"\s+" + "from" + r"\b", re.IGNORECASE),
    re.compile(r"\b" + "select" + r"\b[\s\S]{0,240}?\b" + "from" + r"\b", re.IGNORECASE),
    re.compile(r"\bsqlite3\.[A-Za-z_][A-Za-z0-9_.]*", re.IGNORECASE),
    re.compile(r"\bsqlite(?:3)?\s+(?:OperationalError|IntegrityError|DatabaseError|ProgrammingError|Error)\b", re.IGNORECASE),
    re.compile(r"\b(?:UNIQUE|FOREIGN\s+KEY|CHECK|NOT\s+NULL)\s+constraint\s+failed\b", re.IGNORECASE),
    re.compile(r"\bno\s+such\s+(?:table|column)\b", re.IGNORECASE),
    re.compile(
        r"\b(?:facts|evidence|relationships|conflicts|interactions|migrations)\."
        r"(?:[A-Za-z_][A-Za-z0-9_]*)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:sqlite_schema|schema_migrations|fact_merges|job_matches|raw_sql|transaction_result|"
        r"normalized_terms_json|metadata_json|evidence_json|fact_ids_json|evidence_ids_json|merged_into_fact_id)\b",
        re.IGNORECASE,
    ),
)
SENSITIVE_ARGUMENT_KEYS = {
    "api_key",
    "authorization",
    "contact_data",
    "email",
    "evidence_ids_json",
    "evidence_json",
    "fact_ids_json",
    "metadata_json",
    "merged_into_fact_id",
    "normalized_terms_json",
    "password",
    "phone",
    "raw_sql",
    "secret",
    "sensitive",
    "sensitive_raw_data",
    "sqlite_schema",
    "schema_migrations",
    "ssn",
    "token",
    "transaction_result",
}


def default_operation_id() -> str:
    return str(uuid.uuid4())


def default_timestamp_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def safe_text_message(text: str) -> str:
    if any(pattern.search(text) for pattern in PERSISTENCE_LEAK_PATTERNS):
        return GENERIC_STORE_ERROR_MESSAGE
    return text


def redact_arguments(arguments: JsonObject) -> JsonObject:
    return _redact_value(copy.deepcopy(arguments))


def build_audit_event(
    *,
    tool: str,
    result: JsonObject,
    arguments: JsonObject,
    operation_id: str,
    timestamp: str,
    policy_decision: policy.PolicyDecision | None,
) -> JsonObject:
    status = str(result.get("status", "error"))
    if not policy.tool_mutates(tool):
        return {"tool": tool, "status": status}

    event: JsonObject = {
        "operation_id": operation_id,
        "timestamp": timestamp,
        "tool": tool,
        "is_mutation": True,
        "status": status,
        "args_redacted": redact_arguments(arguments),
        "affected_fact_ids": _affected_fact_ids(result),
        "resulting_verification_state": str(result.get("verification_state", "unknown")),
        "conflict_flag": bool(result.get("conflicts")),
        "confirmation_required": _confirmation_required(result, policy_decision),
    }
    if status != "ok":
        event["error_type"] = _error_type(result)
    return event


def emit_audit_event(audit_sink: Any, event: JsonObject) -> None:
    if audit_sink is None:
        return
    if callable(audit_sink):
        audit_sink(event)
    elif hasattr(audit_sink, "append"):
        audit_sink.append(event)


def _redact_value(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: JsonObject = {}
        for key, item in value.items():
            normalized_key = str(key).casefold()
            if normalized_key in SENSITIVE_ARGUMENT_KEYS or _is_persistence_internal_key(normalized_key):
                continue
            else:
                redacted[str(key)] = _redact_value(item)
        return redacted
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    if isinstance(value, str):
        return safe_text_message(value)
    return value


def _is_persistence_internal_key(key: str) -> bool:
    return key.endswith("_json") or key in {"raw_sql", "transaction_result"}


def _affected_fact_ids(result: JsonObject) -> list[str]:
    affected = result.get("affected_fact_ids")
    if isinstance(affected, list):
        return [str(fact_id) for fact_id in affected if str(fact_id)]
    fact_id = result.get("fact_id")
    if isinstance(fact_id, str) and fact_id:
        return [fact_id]
    return []


def _confirmation_required(result: JsonObject, policy_decision: policy.PolicyDecision | None) -> bool:
    if "confirmation_required" in result:
        return bool(result.get("confirmation_required"))
    data = result.get("data")
    if isinstance(data, dict) and "confirmation_required" in data:
        return bool(data.get("confirmation_required"))
    if policy_decision is not None:
        return policy_decision.requires_confirmation
    return False


def _error_type(result: JsonObject) -> str:
    error = result.get("error")
    if isinstance(error, dict):
        return str(error.get("type", "store_error"))
    return "store_error"


__all__ = [
    "GENERIC_STORE_ERROR_MESSAGE",
    "PERSISTENCE_LEAK_PATTERNS",
    "build_audit_event",
    "default_operation_id",
    "default_timestamp_utc",
    "emit_audit_event",
    "redact_arguments",
    "safe_text_message",
]
