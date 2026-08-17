"""Versioned model-output schemas for resume and job extraction proposals."""

from __future__ import annotations

import copy

from ._schema_validation import JsonObject, JsonSchemaRegistry


RESUME_EXTRACTION_SCHEMA_ID = "resume-agent.resume-extraction.v1"
JOB_EXTRACTION_SCHEMA_ID = "resume-agent.job-extraction.v1"

CONFIDENCE_SCHEMA: JsonObject = {"type": "number", "minimum": 0}
UNCERTAINTY_SCHEMA: JsonObject = {"type": "object"}

LINE_RANGE_SCHEMA: JsonObject = {
    "type": "object",
    "required": ["start", "end"],
    "properties": {
        "start": {"type": "integer"},
        "end": {"type": "integer"},
    },
    "additionalProperties": False,
}

SPAN_SCHEMA: JsonObject = {
    "type": "object",
    "required": ["start", "end"],
    "properties": {
        "start": {"type": "integer"},
        "end": {"type": "integer"},
    },
    "additionalProperties": False,
}

EVIDENCE_REF_SCHEMA: JsonObject = {
    "type": "object",
    "required": ["evidence_id", "source_text", "span", "lines"],
    "properties": {
        "evidence_id": {"type": "string", "minLength": 1},
        "source_text": {"type": "string", "minLength": 1},
        "span": SPAN_SCHEMA,
        "lines": LINE_RANGE_SCHEMA,
    },
    "additionalProperties": False,
}

EXTRACTED_VALUE_SCHEMA: JsonObject = {
    "type": "object",
    "required": ["value", "evidence", "confidence"],
    "properties": {
        "value": {"type": "string", "minLength": 1},
        "normalized": {"type": "string", "minLength": 1},
        "evidence": {"type": "array", "minItems": 1, "items": EVIDENCE_REF_SCHEMA},
        "confidence": CONFIDENCE_SCHEMA,
        "uncertainty": UNCERTAINTY_SCHEMA,
    },
    "additionalProperties": False,
}

SKILL_SCHEMA: JsonObject = {
    "type": "object",
    "required": ["name", "category", "normalized_terms", "evidence", "confidence"],
    "properties": {
        "name": {"type": "string", "minLength": 1},
        "category": {"type": "string", "minLength": 1},
        "normalized_terms": {"type": "array", "minItems": 1, "items": {"type": "string", "minLength": 1}},
        "evidence": {"type": "array", "minItems": 1, "items": EVIDENCE_REF_SCHEMA},
        "confidence": CONFIDENCE_SCHEMA,
        "uncertainty": UNCERTAINTY_SCHEMA,
    },
    "additionalProperties": False,
}

HIGHLIGHT_SCHEMA: JsonObject = {
    "type": "object",
    "required": ["text", "evidence", "confidence"],
    "properties": {
        "text": {"type": "string", "minLength": 1},
        "normalized_terms": {"type": "array", "items": {"type": "string", "minLength": 1}},
        "evidence": {"type": "array", "minItems": 1, "items": EVIDENCE_REF_SCHEMA},
        "confidence": CONFIDENCE_SCHEMA,
        "uncertainty": UNCERTAINTY_SCHEMA,
    },
    "additionalProperties": False,
}

EMPLOYMENT_SCHEMA: JsonObject = {
    "type": "object",
    "required": ["organization", "role", "start_date", "end_date", "current", "evidence", "confidence"],
    "properties": {
        "organization": {"type": "string", "minLength": 1},
        "role": {"type": "string", "minLength": 1},
        "start_date": {"type": ["string", "null"]},
        "end_date": {"type": ["string", "null"]},
        "current": {"type": "boolean"},
        "evidence": {"type": "array", "minItems": 1, "items": EVIDENCE_REF_SCHEMA},
        "confidence": CONFIDENCE_SCHEMA,
        "uncertainty": UNCERTAINTY_SCHEMA,
    },
    "additionalProperties": False,
}

EXPERIENCE_SCHEMA: JsonObject = {
    "type": "object",
    "required": ["role", "organization", "employment", "highlights", "skills", "evidence", "confidence"],
    "properties": {
        "role": {"type": "string", "minLength": 1},
        "organization": {"type": "string", "minLength": 1},
        "employment": EMPLOYMENT_SCHEMA,
        "location": {"type": ["string", "null"]},
        "highlights": {"type": "array", "items": HIGHLIGHT_SCHEMA},
        "skills": {"type": "array", "items": {"type": "string", "minLength": 1}},
        "evidence": {"type": "array", "minItems": 1, "items": EVIDENCE_REF_SCHEMA},
        "confidence": CONFIDENCE_SCHEMA,
        "uncertainty": UNCERTAINTY_SCHEMA,
    },
    "additionalProperties": False,
}

EDUCATION_SCHEMA: JsonObject = {
    "type": "object",
    "required": ["institution", "degree", "field", "evidence", "confidence"],
    "properties": {
        "institution": {"type": "string", "minLength": 1},
        "degree": {"type": "string", "minLength": 1},
        "field": {"type": "string", "minLength": 1},
        "graduation_date": {"type": ["string", "null"]},
        "evidence": {"type": "array", "minItems": 1, "items": EVIDENCE_REF_SCHEMA},
        "confidence": CONFIDENCE_SCHEMA,
        "uncertainty": UNCERTAINTY_SCHEMA,
    },
    "additionalProperties": False,
}

CERTIFICATION_SCHEMA: JsonObject = {
    "type": "object",
    "required": ["name", "issuer", "evidence", "confidence"],
    "properties": {
        "name": {"type": "string", "minLength": 1},
        "issuer": {"type": "string", "minLength": 1},
        "date": {"type": ["string", "null"]},
        "evidence": {"type": "array", "minItems": 1, "items": EVIDENCE_REF_SCHEMA},
        "confidence": CONFIDENCE_SCHEMA,
        "uncertainty": UNCERTAINTY_SCHEMA,
    },
    "additionalProperties": False,
}

PROJECT_SCHEMA: JsonObject = {
    "type": "object",
    "required": ["name", "description", "skills", "evidence", "confidence"],
    "properties": {
        "name": {"type": "string", "minLength": 1},
        "description": {"type": "string", "minLength": 1},
        "skills": {"type": "array", "items": {"type": "string", "minLength": 1}},
        "evidence": {"type": "array", "minItems": 1, "items": EVIDENCE_REF_SCHEMA},
        "confidence": CONFIDENCE_SCHEMA,
        "uncertainty": UNCERTAINTY_SCHEMA,
    },
    "additionalProperties": False,
}

REQUIREMENT_SCHEMA: JsonObject = {
    "type": "object",
    "required": [
        "requirement_id",
        "classification",
        "concept",
        "importance",
        "weight",
        "source_text",
        "normalized_terms",
        "seniority",
        "industries",
        "domains",
        "evidence",
        "confidence",
    ],
    "properties": {
        "requirement_id": {"type": "string", "minLength": 1},
        "classification": {"enum": ["required", "preferred", "contextual"]},
        "concept": {"type": "string", "minLength": 1},
        "importance": {"type": "string", "minLength": 1},
        "weight": {"type": "number", "minimum": 0},
        "source_text": {"type": "string", "minLength": 1},
        "normalized_terms": {"type": "array", "minItems": 1, "items": {"type": "string", "minLength": 1}},
        "years": {"type": ["object", "null"]},
        "seniority": {"type": "array", "items": EXTRACTED_VALUE_SCHEMA},
        "industries": {"type": "array", "items": EXTRACTED_VALUE_SCHEMA},
        "domains": {"type": "array", "items": EXTRACTED_VALUE_SCHEMA},
        "evidence": {"type": "array", "minItems": 1, "items": EVIDENCE_REF_SCHEMA},
        "confidence": CONFIDENCE_SCHEMA,
        "uncertainty": UNCERTAINTY_SCHEMA,
    },
    "additionalProperties": False,
}

TERM_SCHEMA: JsonObject = {
    "type": "object",
    "required": ["surface", "canonical", "source", "weight", "evidence", "confidence"],
    "properties": {
        "surface": {"type": "string", "minLength": 1},
        "canonical": {"type": "string", "minLength": 1},
        "source": {"enum": ["title", "requirement", "description"]},
        "weight": {"type": "number", "minimum": 0},
        "evidence": {"type": "array", "minItems": 1, "items": EVIDENCE_REF_SCHEMA},
        "confidence": CONFIDENCE_SCHEMA,
        "uncertainty": UNCERTAINTY_SCHEMA,
    },
    "additionalProperties": False,
}

RESUME_EXTRACTION_SCHEMA: JsonObject = {
    "schema_version": RESUME_EXTRACTION_SCHEMA_ID,
    "type": "object",
    "required": [
        "schema_version",
        "proposal_type",
        "requires_validation",
        "resume_id",
        "source",
        "basics",
        "skills",
        "experience",
        "education",
        "certifications",
        "projects",
        "employment",
        "source_evidence",
        "uncertainty",
    ],
    "properties": {
        "schema_version": {"enum": [RESUME_EXTRACTION_SCHEMA_ID]},
        "proposal_type": {"enum": ["resume_extraction"]},
        "requires_validation": {"enum": [True]},
        "resume_id": {"type": "string", "minLength": 1},
        "source": {"type": "object"},
        "basics": {"type": "object", "additionalProperties": EXTRACTED_VALUE_SCHEMA},
        "skills": {"type": "array", "items": SKILL_SCHEMA},
        "experience": {"type": "array", "items": EXPERIENCE_SCHEMA},
        "education": {"type": "array", "items": EDUCATION_SCHEMA},
        "certifications": {"type": "array", "items": CERTIFICATION_SCHEMA},
        "projects": {"type": "array", "items": PROJECT_SCHEMA},
        "employment": {"type": "array", "items": EMPLOYMENT_SCHEMA},
        "source_evidence": {"type": "array", "minItems": 1, "items": EVIDENCE_REF_SCHEMA},
        "uncertainty": {"type": "array"},
        "metadata": {"type": "object"},
    },
    "additionalProperties": False,
}

JOB_EXTRACTION_SCHEMA: JsonObject = {
    "schema_version": JOB_EXTRACTION_SCHEMA_ID,
    "type": "object",
    "required": [
        "schema_version",
        "proposal_type",
        "requires_validation",
        "job_id",
        "source",
        "title",
        "company",
        "seniority",
        "industries",
        "domains",
        "requirements",
        "preferred",
        "terminology",
        "source_evidence",
        "uncertainty",
    ],
    "properties": {
        "schema_version": {"enum": [JOB_EXTRACTION_SCHEMA_ID]},
        "proposal_type": {"enum": ["job_extraction"]},
        "requires_validation": {"enum": [True]},
        "job_id": {"type": "string", "minLength": 1},
        "source": {"type": "object"},
        "title": {"type": ["object", "null"], "properties": EXTRACTED_VALUE_SCHEMA["properties"], "required": EXTRACTED_VALUE_SCHEMA["required"]},
        "company": {"type": ["object", "null"], "properties": EXTRACTED_VALUE_SCHEMA["properties"], "required": EXTRACTED_VALUE_SCHEMA["required"]},
        "seniority": {"type": "array", "items": EXTRACTED_VALUE_SCHEMA},
        "industries": {"type": "array", "items": EXTRACTED_VALUE_SCHEMA},
        "domains": {"type": "array", "items": EXTRACTED_VALUE_SCHEMA},
        "requirements": {"type": "array", "items": REQUIREMENT_SCHEMA},
        "preferred": {"type": "array", "items": REQUIREMENT_SCHEMA},
        "terminology": {"type": "array", "items": TERM_SCHEMA},
        "source_evidence": {"type": "array", "minItems": 1, "items": EVIDENCE_REF_SCHEMA},
        "uncertainty": {"type": "array"},
        "metadata": {"type": "object"},
    },
    "additionalProperties": False,
}

EXTRACTION_OUTPUT_SCHEMAS: JsonSchemaRegistry = {
    RESUME_EXTRACTION_SCHEMA_ID: RESUME_EXTRACTION_SCHEMA,
    JOB_EXTRACTION_SCHEMA_ID: JOB_EXTRACTION_SCHEMA,
}


def default_extraction_output_schemas() -> JsonSchemaRegistry:
    return copy.deepcopy(EXTRACTION_OUTPUT_SCHEMAS)


__all__ = [
    "EXTRACTION_OUTPUT_SCHEMAS",
    "JOB_EXTRACTION_SCHEMA",
    "JOB_EXTRACTION_SCHEMA_ID",
    "RESUME_EXTRACTION_SCHEMA",
    "RESUME_EXTRACTION_SCHEMA_ID",
    "default_extraction_output_schemas",
]
