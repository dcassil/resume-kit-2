"""Deterministic AdapterRequest builder for grounded rewrite proposals."""

from __future__ import annotations

from importlib import resources
from typing import Any, Mapping, Sequence

from ._adapters import AdapterRequest
from ._rewrite_schemas import REWRITE_PROPOSAL_SCHEMA_ID
from ._schema_validation import JsonObject


REWRITE_PROPOSAL_PROMPT_TEMPLATE_ID = "resume-agent.rewrite-proposal@v1"
PROMPT_TEMPLATE_FILENAMES = {
    REWRITE_PROPOSAL_PROMPT_TEMPLATE_ID: f"{REWRITE_PROPOSAL_PROMPT_TEMPLATE_ID}.txt",
}


def build_rewrite_request(context: Mapping[str, Any] | Any) -> AdapterRequest | JsonObject:
    errors = rewrite_input_contract_errors(context)
    if errors:
        return _validation_error(errors[0])

    assert isinstance(context, Mapping)
    input_payload: JsonObject = {
        "schema_id": REWRITE_PROPOSAL_SCHEMA_ID,
        "original_text": _clean_text(context.get("original_text")),
        "target_path": _clean_text(context.get("target_path")),
        "allowed_facts": _normalize_allowed_facts(context.get("allowed_facts")),
        "requirement_ids": _requirement_ids(context),
        "voice_constraints": _object_or_empty(context.get("voice_constraints")),
        "length_constraints": _object_or_empty(context.get("length_constraints")),
        "prohibited_additions": _normalize_string_list(context.get("prohibited_additions", [])),
    }
    return AdapterRequest(
        prompt_template_id=REWRITE_PROPOSAL_PROMPT_TEMPLATE_ID,
        prompt=prompt_template_text(REWRITE_PROPOSAL_PROMPT_TEMPLATE_ID),
        input_payload=input_payload,
        output_schema_id=REWRITE_PROPOSAL_SCHEMA_ID,
    )


def rewrite_input_contract_errors(context: Mapping[str, Any] | Any) -> list[JsonObject]:
    if not isinstance(context, Mapping):
        return [_field_error("context", "Rewrite proposal context must be an object.")]

    original_text = _clean_text(context.get("original_text"))
    if not original_text:
        return [_field_error("original_text", "original_text must be a non-empty string.")]

    target_path = _clean_text(context.get("target_path"))
    if not target_path:
        return [_field_error("target_path", "target_path is required for rewrite proposals.")]
    if not _is_valid_json_pointer(target_path):
        return [_field_error("target_path", "target_path must be a valid JSON pointer.")]

    allowed_facts = _normalize_allowed_facts(context.get("allowed_facts"))
    if not allowed_facts:
        return [_field_error("allowed_facts", "allowed_facts must include at least one fact with fact_id and text.")]

    if not _requirement_ids(context):
        return [_field_error("requirement_ids", "requirement_ids must include at least one requirement id.")]

    return []


def prompt_template_text(prompt_template_id: str) -> str:
    filename = PROMPT_TEMPLATE_FILENAMES[prompt_template_id]
    return resources.files("resume_agent").joinpath("prompts", filename).read_text(encoding="utf-8")


def _validation_error(error: JsonObject) -> JsonObject:
    return {
        "status": "error",
        "error": {
            "type": "validation_error",
            "message": error["message"],
            "field_path": error["field_path"],
        },
    }


def _field_error(field_path: str, message: str) -> JsonObject:
    return {"code": "validation_error", "message": message, "severity": "error", "field_path": field_path}


def _normalize_allowed_facts(value: Any) -> list[JsonObject]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    facts: list[JsonObject] = []
    for item in value:
        if not isinstance(item, Mapping):
            continue
        fact_id = _clean_text(item.get("fact_id"))
        text = _clean_text(item.get("text"))
        if not fact_id or not text:
            continue
        fact: JsonObject = {"fact_id": fact_id, "text": text}
        for key in ["verification_state", "source", "evidence_id"]:
            field = _clean_text(item.get(key))
            if field:
                fact[key] = field
        normalized_terms = _normalize_string_list(item.get("normalized_terms", []))
        if normalized_terms:
            fact["normalized_terms"] = normalized_terms
        facts.append(fact)
    return facts


def _requirement_ids(context: Mapping[str, Any]) -> list[str]:
    explicit = _normalize_string_list(context.get("requirement_ids", []))
    if explicit:
        return explicit
    requirements = context.get("requirements", [])
    if not isinstance(requirements, Sequence) or isinstance(requirements, (str, bytes)):
        return []
    return _normalize_string_list([item.get("requirement_id") for item in requirements if isinstance(item, Mapping)])


def _normalize_string_list(values: Sequence[Any] | Any) -> list[str]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        values = []
    seen: set[str] = set()
    result: list[str] = []
    for item in values:
        text = _clean_text(item)
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result


def _object_or_empty(value: Any) -> JsonObject:
    return dict(value) if isinstance(value, Mapping) else {}


def _clean_text(value: Any) -> str:
    if not isinstance(value, str):
        value = str(value) if value is not None else ""
    return " ".join(value.split())


def _is_valid_json_pointer(value: str) -> bool:
    if not value.startswith("/") or value == "/":
        return False
    for token in value.strip("/").split("/"):
        if not token or _has_invalid_tilde_escape(token):
            return False
    return True


def _has_invalid_tilde_escape(token: str) -> bool:
    index = 0
    while index < len(token):
        if token[index] == "~":
            if index + 1 >= len(token) or token[index + 1] not in {"0", "1"}:
                return True
            index += 2
            continue
        index += 1
    return False


__all__ = [
    "REWRITE_PROPOSAL_PROMPT_TEMPLATE_ID",
    "build_rewrite_request",
    "prompt_template_text",
    "rewrite_input_contract_errors",
]
