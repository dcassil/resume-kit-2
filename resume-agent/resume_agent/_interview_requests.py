"""Deterministic AdapterRequest builders for interview proposals."""

from __future__ import annotations

from importlib import resources
from typing import Any, Mapping, Sequence

from ._adapters import AdapterRequest
from ._interview_schemas import ANSWER_INTERPRETATION_SCHEMA_ID, QUESTION_GENERATION_SCHEMA_ID
from ._schema_validation import JsonObject


QUESTION_GENERATION_PROMPT_TEMPLATE_ID = "resume-agent.question-generation@v1"
ANSWER_INTERPRETATION_PROMPT_TEMPLATE_ID = "resume-agent.answer-interpretation@v1"
PROMPT_TEMPLATE_FILENAMES = {
    QUESTION_GENERATION_PROMPT_TEMPLATE_ID: f"{QUESTION_GENERATION_PROMPT_TEMPLATE_ID}.txt",
    ANSWER_INTERPRETATION_PROMPT_TEMPLATE_ID: f"{ANSWER_INTERPRETATION_PROMPT_TEMPLATE_ID}.txt",
}


def build_question_request(
    topic: str,
    target_ids: Mapping[str, Sequence[Any]] | Sequence[Any],
    context_snippets: Sequence[Any],
) -> AdapterRequest:
    input_payload: JsonObject = {
        "schema_id": QUESTION_GENERATION_SCHEMA_ID,
        "topic": _clean_text(topic),
        "target_ids": _normalize_target_ids(target_ids),
        "context_snippets": _normalize_string_list(context_snippets),
    }
    return AdapterRequest(
        prompt_template_id=QUESTION_GENERATION_PROMPT_TEMPLATE_ID,
        prompt=prompt_template_text(QUESTION_GENERATION_PROMPT_TEMPLATE_ID),
        input_payload=input_payload,
        output_schema_id=QUESTION_GENERATION_SCHEMA_ID,
    )


def build_answer_interpretation_request(question: str, answer_text: str, topic: str) -> AdapterRequest:
    input_payload: JsonObject = {
        "schema_id": ANSWER_INTERPRETATION_SCHEMA_ID,
        "question": _clean_text(question),
        "answer_text": _clean_text(answer_text),
        "topic": _clean_text(topic),
    }
    return AdapterRequest(
        prompt_template_id=ANSWER_INTERPRETATION_PROMPT_TEMPLATE_ID,
        prompt=prompt_template_text(ANSWER_INTERPRETATION_PROMPT_TEMPLATE_ID),
        input_payload=input_payload,
        output_schema_id=ANSWER_INTERPRETATION_SCHEMA_ID,
    )


def prompt_template_text(prompt_template_id: str) -> str:
    filename = PROMPT_TEMPLATE_FILENAMES[prompt_template_id]
    return resources.files("resume_agent").joinpath("prompts", filename).read_text(encoding="utf-8")


def _normalize_target_ids(target_ids: Mapping[str, Sequence[Any]] | Sequence[Any]) -> JsonObject:
    if isinstance(target_ids, Mapping):
        requirement_ids = _normalize_string_list(target_ids.get("requirement_ids", []))
        fact_ids = _normalize_string_list(target_ids.get("fact_ids", []))
    else:
        requirement_ids = _normalize_string_list(target_ids)
        fact_ids = []
    return {"requirement_ids": requirement_ids, "fact_ids": fact_ids}


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


def _clean_text(value: Any) -> str:
    if not isinstance(value, str):
        value = str(value) if value is not None else ""
    return " ".join(value.split())


__all__ = [
    "ANSWER_INTERPRETATION_PROMPT_TEMPLATE_ID",
    "QUESTION_GENERATION_PROMPT_TEMPLATE_ID",
    "build_answer_interpretation_request",
    "build_question_request",
    "prompt_template_text",
]
