"""Deterministic AdapterRequest builder for semantic equivalence proposals."""

from __future__ import annotations

from importlib import resources
from typing import Any, Mapping, Sequence

from ._adapters import AdapterRequest
from ._equivalence_schemas import EQUIVALENCE_DIRECTIONS, EQUIVALENCE_PROPOSAL_SCHEMA_ID
from ._schema_validation import JsonObject


EQUIVALENCE_PROPOSAL_PROMPT_TEMPLATE_ID = "resume-agent.equivalence-proposal@v1"
PROMPT_TEMPLATE_FILENAMES = {
    EQUIVALENCE_PROPOSAL_PROMPT_TEMPLATE_ID: f"{EQUIVALENCE_PROPOSAL_PROMPT_TEMPLATE_ID}.txt",
}


def build_equivalence_request(context: Mapping[str, Any] | Any) -> AdapterRequest | JsonObject:
    errors = equivalence_input_contract_errors(context)
    if errors:
        return _validation_error(errors[0])

    assert isinstance(context, Mapping)
    input_payload: JsonObject = {
        "schema_id": EQUIVALENCE_PROPOSAL_SCHEMA_ID,
        "candidates": _candidate_pairs(context),
        "evidence": _evidence_items(context),
    }
    return AdapterRequest(
        prompt_template_id=EQUIVALENCE_PROPOSAL_PROMPT_TEMPLATE_ID,
        prompt=prompt_template_text(EQUIVALENCE_PROPOSAL_PROMPT_TEMPLATE_ID),
        input_payload=input_payload,
        output_schema_id=EQUIVALENCE_PROPOSAL_SCHEMA_ID,
    )


def equivalence_input_contract_errors(context: Mapping[str, Any] | Any) -> list[JsonObject]:
    if not isinstance(context, Mapping):
        return [_field_error("context", "Equivalence proposal context must be an object.")]

    if context.get("candidate_pairs") is not None and _not_sequence(context.get("candidate_pairs")):
        return [_field_error("candidate_pairs", "candidate_pairs must be an array of candidate pair objects.")]
    if context.get("alias_misses") is not None and _not_sequence(context.get("alias_misses")):
        return [_field_error("alias_misses", "alias_misses must be an array of candidate pair objects.")]

    candidates = _candidate_pairs(context)
    if not candidates:
        return []

    evidence_ids = {_clean_text(item.get("evidence_id")) for item in _evidence_items(context)}
    for index, candidate in enumerate(candidates):
        if not candidate["evidence_refs"]:
            return [_field_error(f"candidates/{index}/evidence_refs", "Candidate pairs must include evidence_refs.")]
        unresolved = sorted(set(candidate["evidence_refs"]) - evidence_ids)
        if unresolved:
            return [
                _field_error(
                    f"candidates/{index}/evidence_refs",
                    f"Candidate evidence_refs must resolve into supplied evidence: {', '.join(unresolved)}.",
                )
            ]
        direction_hint = candidate.get("direction_hint")
        if direction_hint and direction_hint not in EQUIVALENCE_DIRECTIONS:
            return [_field_error(f"candidates/{index}/direction_hint", "direction_hint is not in the allowed vocabulary.")]

    return []


def has_equivalence_candidates(context: Mapping[str, Any]) -> bool:
    return bool(_candidate_pairs(context))


def equivalence_evidence_ids(context: Mapping[str, Any]) -> set[str]:
    return {_clean_text(item.get("evidence_id")) for item in _evidence_items(context) if _clean_text(item.get("evidence_id"))}


def prompt_template_text(prompt_template_id: str) -> str:
    filename = PROMPT_TEMPLATE_FILENAMES[prompt_template_id]
    return resources.files("resume_agent").joinpath("prompts", filename).read_text(encoding="utf-8")


def _candidate_pairs(context: Mapping[str, Any]) -> list[JsonObject]:
    raw_items: list[Any] = []
    for key in ("candidate_pairs", "alias_misses"):
        value = context.get(key, [])
        if _not_sequence(value):
            continue
        raw_items.extend(value)

    candidates: list[JsonObject] = []
    seen: set[tuple[str, str, tuple[str, ...]]] = set()
    for item in raw_items:
        candidate = _candidate_pair(item)
        if not candidate:
            continue
        key = (
            candidate["term_a"].casefold(),
            candidate["term_b"].casefold(),
            tuple(candidate["evidence_refs"]),
        )
        if key in seen:
            continue
        seen.add(key)
        candidate["candidate_id"] = f"candidate_{len(candidates) + 1}"
        candidates.append(candidate)
    return candidates


def _candidate_pair(item: Any) -> JsonObject:
    if isinstance(item, Mapping):
        term_a = _clean_text(item.get("term_a") or item.get("resume_term") or item.get("source_term"))
        term_b = _clean_text(item.get("term_b") or item.get("job_term") or item.get("target_term"))
        evidence_refs = _normalize_string_list(item.get("evidence_refs", []))
        if not evidence_refs:
            evidence_refs = _normalize_string_list(
                [
                    item.get("resume_evidence_id"),
                    item.get("job_evidence_id"),
                    item.get("source_evidence_id"),
                    item.get("target_evidence_id"),
                ]
            )
        direction_hint = _clean_text(item.get("direction_hint") or item.get("direction"))
        candidate: JsonObject = {"term_a": term_a, "term_b": term_b, "evidence_refs": evidence_refs}
        if direction_hint:
            candidate["direction_hint"] = direction_hint
        rationale_hint = _clean_text(item.get("rationale_hint") or item.get("reason"))
        if rationale_hint:
            candidate["rationale_hint"] = rationale_hint
        return candidate if term_a and term_b else {}

    if isinstance(item, Sequence) and not isinstance(item, (str, bytes)) and len(item) >= 2:
        term_a = _clean_text(item[0])
        term_b = _clean_text(item[1])
        return {"term_a": term_a, "term_b": term_b, "evidence_refs": []} if term_a and term_b else {}

    return {}


def _evidence_items(context: Mapping[str, Any]) -> list[JsonObject]:
    raw_items: list[Any] = []
    for key in ("evidence", "source_evidence", "resume_evidence", "job_evidence"):
        value = context.get(key, [])
        if not _not_sequence(value):
            raw_items.extend(value)

    items: list[JsonObject] = []
    seen: set[str] = set()
    for item in raw_items:
        if not isinstance(item, Mapping):
            continue
        evidence_id = _clean_text(item.get("evidence_id") or item.get("id"))
        text = _clean_text(item.get("text") or item.get("source_text") or item.get("snippet"))
        if not evidence_id or not text or evidence_id in seen:
            continue
        seen.add(evidence_id)
        evidence: JsonObject = {
            "evidence_id": evidence_id,
            "text": text,
            "source": _clean_text(item.get("source") or item.get("kind")) or "context",
        }
        items.append(evidence)
    return items


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


def _not_sequence(value: Any) -> bool:
    return isinstance(value, (str, bytes)) or not isinstance(value, Sequence)


def _clean_text(value: Any) -> str:
    if not isinstance(value, str):
        value = str(value) if value is not None else ""
    return " ".join(value.split())


__all__ = [
    "EQUIVALENCE_PROPOSAL_PROMPT_TEMPLATE_ID",
    "build_equivalence_request",
    "equivalence_evidence_ids",
    "equivalence_input_contract_errors",
    "has_equivalence_candidates",
    "prompt_template_text",
]
