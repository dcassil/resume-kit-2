"""Private call-audit record schema, hashing, and sink primitives."""

from __future__ import annotations

import copy
import hashlib
import json
from importlib import resources
from typing import Any, Literal, Mapping, Protocol

from ._schema_validation import JsonObject, JsonSchemaRegistry, validate_json_schema


CallAuditOutcome = Literal["ok", "timeout", "schema_invalid", "refused", "provider_error"]
CALL_AUDIT_OUTCOMES: tuple[str, ...] = ("ok", "timeout", "schema_invalid", "refused", "provider_error")
CALL_AUDIT_RECORD_FIELDS: tuple[str, ...] = (
    "call_id",
    "adapter_id",
    "adapter_version",
    "model_id",
    "prompt_hash",
    "schema_hash",
    "config_hash",
    "retry_count",
    "outcome",
    "timestamps",
    "usage",
)

CALL_AUDIT_RECORD_SCHEMA: JsonObject = {
    "type": "object",
    "required": list(CALL_AUDIT_RECORD_FIELDS),
    "properties": {
        "call_id": {"type": "string", "minLength": 1},
        "adapter_id": {"type": "string", "minLength": 1},
        "adapter_version": {"type": "string", "minLength": 1},
        "model_id": {"type": "string", "minLength": 1},
        "prompt_hash": {"type": "string", "minLength": 1},
        "schema_hash": {"type": "string", "minLength": 1},
        "config_hash": {"type": "string", "minLength": 1},
        "retry_count": {"type": "integer", "minimum": 0},
        "outcome": {"enum": list(CALL_AUDIT_OUTCOMES)},
        "timestamps": {"type": "object"},
        "usage": {"type": "object"},
    },
    "additionalProperties": False,
}


class CallAuditRecordValidationError(ValueError):
    def __init__(self, violations: list[JsonObject]):
        self.violations = copy.deepcopy(violations)
        summary = "; ".join(
            f"{item.get('field_path', 'record')}: {item.get('message', item.get('code', 'invalid'))}"
            for item in violations[:3]
        )
        if len(violations) > 3:
            summary = f"{summary}; ... {len(violations) - 3} more"
        super().__init__(f"Call-audit record validation failed: {summary}")


class CallAuditSink(Protocol):
    def record(self, record: JsonObject) -> None:
        """Collect one validated call-audit record."""


class InMemoryCallAuditSink:
    """Default collecting sink used when callers do not inject their own."""

    def __init__(self) -> None:
        self._records: list[JsonObject] = []

    def record(self, record: JsonObject) -> None:
        self._records.append(require_call_audit_record(record))

    @property
    def records(self) -> list[JsonObject]:
        return copy.deepcopy(self._records)

    def clear(self) -> None:
        self._records.clear()


def require_call_audit_record(record: Mapping[str, Any]) -> JsonObject:
    candidate = dict(record) if isinstance(record, Mapping) else {"record": record}
    violations = validate_json_schema(candidate, CALL_AUDIT_RECORD_SCHEMA)
    if violations:
        raise CallAuditRecordValidationError(violations)
    return copy.deepcopy(candidate)


def build_call_audit_record(
    *,
    request: Any,
    result: Any,
    output_schemas: JsonSchemaRegistry,
    config_hash: str,
    sequence: int,
) -> JsonObject:
    prompt_hash = hash_prompt_template(request)
    schema_hash = hash_output_schema(request.output_schema_id, output_schemas)
    outcome = _outcome(result)
    record = {
        "call_id": deterministic_call_id(
            adapter_id=result.adapter_id,
            adapter_version=result.adapter_version,
            model_id=result.model_id,
            prompt_hash=prompt_hash,
            schema_hash=schema_hash,
            config_hash=config_hash,
            input_payload=request.input_payload,
            sequence=sequence,
        ),
        "adapter_id": result.adapter_id,
        "adapter_version": result.adapter_version,
        "model_id": result.model_id,
        "prompt_hash": prompt_hash,
        "schema_hash": schema_hash,
        "config_hash": config_hash,
        "retry_count": result.retries,
        "outcome": outcome,
        # Logical counters are deliberate deterministic sentinels. Workflow can
        # add wall-clock context when embedding records in run artifacts.
        "timestamps": {"started": sequence, "completed": sequence},
        "usage": copy.deepcopy(result.usage),
    }
    return require_call_audit_record(record)


def deterministic_call_id(
    *,
    adapter_id: str,
    adapter_version: str,
    model_id: str,
    prompt_hash: str,
    schema_hash: str,
    config_hash: str,
    input_payload: Mapping[str, Any],
    sequence: int,
) -> str:
    material = json.dumps(
        {
            "adapter_id": adapter_id,
            "adapter_version": adapter_version,
            "model_id": model_id,
            "prompt_hash": prompt_hash,
            "schema_hash": schema_hash,
            "config_hash": config_hash,
            "canonical_input_json": _canonical_json(input_payload),
            "sequence": sequence,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def hash_prompt_template(request: Any) -> str:
    return hashlib.sha256(_prompt_template_bytes(request)).hexdigest()


def hash_output_schema(output_schema_id: str, output_schemas: JsonSchemaRegistry) -> str:
    schema = output_schemas.get(output_schema_id)
    if not isinstance(schema, dict):
        schema = {"schema_id": output_schema_id, "registered": False}
    return hashlib.sha256(_canonical_json(schema).encode("utf-8")).hexdigest()


def _prompt_template_bytes(request: Any) -> bytes:
    filename = f"{request.prompt_template_id}.txt"
    try:
        return resources.files("resume_agent").joinpath("prompts", filename).read_bytes()
    except FileNotFoundError:
        return str(request.prompt).encode("utf-8")


def _canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _outcome(result: Any) -> CallAuditOutcome:
    if result.status == "ok":
        return "ok"
    error = getattr(result, "error", None)
    failure_type = getattr(error, "type", "provider_error")
    if failure_type in CALL_AUDIT_OUTCOMES:
        return failure_type
    return "provider_error"


__all__ = [
    "CALL_AUDIT_OUTCOMES",
    "CALL_AUDIT_RECORD_FIELDS",
    "CALL_AUDIT_RECORD_SCHEMA",
    "CallAuditOutcome",
    "CallAuditRecordValidationError",
    "CallAuditSink",
    "InMemoryCallAuditSink",
    "build_call_audit_record",
    "deterministic_call_id",
    "hash_output_schema",
    "hash_prompt_template",
    "require_call_audit_record",
]
