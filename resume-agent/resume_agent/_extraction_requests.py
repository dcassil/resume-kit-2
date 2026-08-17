"""Deterministic AdapterRequest builders for model-based extraction proposals."""

from __future__ import annotations

import hashlib
from importlib import resources

from ._adapters import AdapterRequest
from ._extraction_schemas import JOB_EXTRACTION_SCHEMA_ID, RESUME_EXTRACTION_SCHEMA_ID
from ._schema_validation import JsonObject


RESUME_EXTRACTION_PROMPT_TEMPLATE_ID = "resume-agent.resume-extraction@v1"
JOB_EXTRACTION_PROMPT_TEMPLATE_ID = "resume-agent.job-extraction@v1"
PROMPT_TEMPLATE_FILENAMES = {
    RESUME_EXTRACTION_PROMPT_TEMPLATE_ID: f"{RESUME_EXTRACTION_PROMPT_TEMPLATE_ID}.txt",
    JOB_EXTRACTION_PROMPT_TEMPLATE_ID: f"{JOB_EXTRACTION_PROMPT_TEMPLATE_ID}.txt",
}


def build_resume_extraction_request(raw_text: str, *, source_id: str = "inline") -> AdapterRequest:
    return _build_extraction_request(
        raw_text=raw_text,
        source_id=source_id,
        prompt_template_id=RESUME_EXTRACTION_PROMPT_TEMPLATE_ID,
        output_schema_id=RESUME_EXTRACTION_SCHEMA_ID,
        input_key="resume_text",
    )


def build_job_extraction_request(raw_text: str, *, source_id: str = "inline") -> AdapterRequest:
    return _build_extraction_request(
        raw_text=raw_text,
        source_id=source_id,
        prompt_template_id=JOB_EXTRACTION_PROMPT_TEMPLATE_ID,
        output_schema_id=JOB_EXTRACTION_SCHEMA_ID,
        input_key="job_text",
    )


def prompt_template_text(prompt_template_id: str) -> str:
    filename = PROMPT_TEMPLATE_FILENAMES[prompt_template_id]
    return resources.files("resume_agent").joinpath("prompts", filename).read_text(encoding="utf-8")


def _build_extraction_request(
    *,
    raw_text: str,
    source_id: str,
    prompt_template_id: str,
    output_schema_id: str,
    input_key: str,
) -> AdapterRequest:
    text = raw_text if isinstance(raw_text, str) else ""
    input_payload: JsonObject = {
        "schema_id": output_schema_id,
        "source": {
            "kind": "raw_text",
            "source_id": source_id,
            "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        },
        input_key: text,
    }
    return AdapterRequest(
        prompt_template_id=prompt_template_id,
        prompt=prompt_template_text(prompt_template_id),
        input_payload=input_payload,
        output_schema_id=output_schema_id,
    )


__all__ = [
    "JOB_EXTRACTION_PROMPT_TEMPLATE_ID",
    "RESUME_EXTRACTION_PROMPT_TEMPLATE_ID",
    "build_job_extraction_request",
    "build_resume_extraction_request",
    "prompt_template_text",
]
