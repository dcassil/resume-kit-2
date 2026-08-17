"""Versioned model-output schemas for interview question and answer proposals."""

from __future__ import annotations

import copy

from ._schema_validation import JsonObject, JsonSchemaRegistry


QUESTION_GENERATION_SCHEMA_ID = "resume-agent.question-generation.v1"
ANSWER_INTERPRETATION_SCHEMA_ID = "resume-agent.answer-interpretation.v1"

CONFIDENCE_SCHEMA: JsonObject = {"type": "number", "minimum": 0}
RESOLUTION_STATES = (
    "exact_match",
    "alias_match",
    "verified_fact_match",
    "related_match",
    "possible_match",
    "unknown",
    "explicitly_missing",
    "not_applicable",
)
VERIFICATION_STATES = ("source_stated", "user" + "_verified", "imported", "inferred", "unknown")

TARGET_IDS_SCHEMA: JsonObject = {
    "type": "object",
    "required": ["requirement_ids", "fact_ids"],
    "properties": {
        "requirement_ids": {"type": "array", "items": {"type": "string", "minLength": 1}},
        "fact_ids": {"type": "array", "items": {"type": "string", "minLength": 1}},
    },
    "additionalProperties": False,
}

ANSWER_SPAN_SCHEMA: JsonObject = {
    "type": "object",
    "required": ["start", "end"],
    "properties": {
        "start": {"type": "integer"},
        "end": {"type": "integer"},
    },
    "additionalProperties": False,
}

ANSWER_EVIDENCE_REF_SCHEMA: JsonObject = {
    "type": "object",
    "required": ["evidence_id", "source_text", "span"],
    "properties": {
        "evidence_id": {"type": "string", "minLength": 1},
        "source_text": {"type": "string", "minLength": 1},
        "span": ANSWER_SPAN_SCHEMA,
    },
    "additionalProperties": False,
}

QUESTION_GENERATION_SCHEMA: JsonObject = {
    "schema_version": QUESTION_GENERATION_SCHEMA_ID,
    "type": "object",
    "required": [
        "schema_version",
        "proposal_type",
        "requires_validation",
        "question",
        "target_ids",
        "rationale",
        "confidence",
    ],
    "properties": {
        "schema_version": {"enum": [QUESTION_GENERATION_SCHEMA_ID]},
        "proposal_type": {"enum": ["question_generation"]},
        "requires_validation": {"enum": [True]},
        "question": {"type": "string", "minLength": 1},
        "target_ids": TARGET_IDS_SCHEMA,
        "rationale": {"type": "string", "minLength": 1},
        "confidence": CONFIDENCE_SCHEMA,
    },
    "additionalProperties": False,
}

REQUIREMENT_RESOLUTION_SCHEMA: JsonObject = {
    "type": "object",
    "required": ["requirement_id", "suggested_state", "confidence", "hedge_or_qualifier", "evidence"],
    "properties": {
        "requirement_id": {"type": "string", "minLength": 1},
        "suggested_state": {"enum": list(RESOLUTION_STATES)},
        "confidence": CONFIDENCE_SCHEMA,
        "hedge_or_qualifier": {"type": ["string", "null"]},
        "evidence": {"type": "array", "items": ANSWER_EVIDENCE_REF_SCHEMA},
    },
    "additionalProperties": False,
}

FACT_PROPOSAL_SCHEMA: JsonObject = {
    "type": "object",
    "required": [
        "fact_id",
        "category",
        "text",
        "normalized_terms",
        "source_evidence_ids",
        "evidence",
        "verification_state",
        "confidence",
        "hedge_or_qualifier",
    ],
    "properties": {
        "fact_id": {"type": "string", "minLength": 1},
        "category": {"type": "string", "minLength": 1},
        "text": {"type": "string", "minLength": 1},
        "normalized_terms": {"type": "array", "minItems": 1, "items": {"type": "string", "minLength": 1}},
        "source_evidence_ids": {"type": "array", "minItems": 1, "items": {"type": "string", "minLength": 1}},
        "evidence": {"type": "array", "minItems": 1, "items": ANSWER_EVIDENCE_REF_SCHEMA},
        "verification_state": {"enum": list(VERIFICATION_STATES)},
        "confidence": CONFIDENCE_SCHEMA,
        "hedge_or_qualifier": {"type": ["string", "null"]},
    },
    "additionalProperties": False,
}

EVIDENCE_PROPOSAL_SCHEMA: JsonObject = {
    "type": "object",
    "required": ["evidence_id", "kind", "text", "span", "confidence"],
    "properties": {
        "evidence_id": {"type": "string", "minLength": 1},
        "kind": {"enum": ["user_answer"]},
        "text": {"type": "string", "minLength": 1},
        "span": ANSWER_SPAN_SCHEMA,
        "confidence": CONFIDENCE_SCHEMA,
    },
    "additionalProperties": False,
}

ANSWER_INTERPRETATION_SCHEMA: JsonObject = {
    "schema_version": ANSWER_INTERPRETATION_SCHEMA_ID,
    "type": "object",
    "required": [
        "schema_version",
        "proposal_type",
        "requires_validation",
        "polarity",
        "requirementResolutions",
        "factProposals",
        "evidenceProposals",
        "uncertainty",
    ],
    "properties": {
        "schema_version": {"enum": [ANSWER_INTERPRETATION_SCHEMA_ID]},
        "proposal_type": {"enum": ["answer_interpretation"]},
        "requires_validation": {"enum": [True]},
        "polarity": {"enum": ["affirmed", "denied", "qualified", "unresponsive"]},
        "requirementResolutions": {"type": "array", "items": REQUIREMENT_RESOLUTION_SCHEMA},
        "factProposals": {"type": "array", "items": FACT_PROPOSAL_SCHEMA},
        "evidenceProposals": {"type": "array", "items": EVIDENCE_PROPOSAL_SCHEMA},
        "uncertainty": {"type": "array"},
    },
    "additionalProperties": False,
}

INTERVIEW_OUTPUT_SCHEMAS: JsonSchemaRegistry = {
    QUESTION_GENERATION_SCHEMA_ID: QUESTION_GENERATION_SCHEMA,
    ANSWER_INTERPRETATION_SCHEMA_ID: ANSWER_INTERPRETATION_SCHEMA,
}


def default_interview_output_schemas() -> JsonSchemaRegistry:
    return copy.deepcopy(INTERVIEW_OUTPUT_SCHEMAS)


__all__ = [
    "ANSWER_INTERPRETATION_SCHEMA",
    "ANSWER_INTERPRETATION_SCHEMA_ID",
    "INTERVIEW_OUTPUT_SCHEMAS",
    "QUESTION_GENERATION_SCHEMA",
    "QUESTION_GENERATION_SCHEMA_ID",
    "RESOLUTION_STATES",
    "VERIFICATION_STATES",
    "default_interview_output_schemas",
]
