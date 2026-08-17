"""Versioned model-output schema for grounded rewrite proposals."""

from __future__ import annotations

import copy

from ._schema_validation import JsonObject, JsonSchemaRegistry


REWRITE_PROPOSAL_SCHEMA_ID = "resume-agent.rewrite-proposal.v1"
RESUME_CHANGE_OPERATION_SCHEMA_VERSION = "resume-change-operation.v1"

CHANGE_OPERATION_VERBS = ("replace", "rewrite", "insert", "remove", "move")

CONFIDENCE_SCHEMA: JsonObject = {"type": "number", "minimum": 0}

SPAN_SCHEMA: JsonObject = {
    "type": "object",
    "required": ["start", "end"],
    "properties": {
        "start": {"type": "integer"},
        "end": {"type": "integer"},
    },
    "additionalProperties": False,
}

PROVENANCE_REF_SCHEMA: JsonObject = {
    "type": "object",
    "required": ["source", "text"],
    "properties": {
        "source": {"type": "string", "minLength": 1},
        "text": {"type": "string", "minLength": 1},
        "fact_id": {"type": "string", "minLength": 1},
        "evidence_id": {"type": "string", "minLength": 1},
        "span": SPAN_SCHEMA,
    },
    "additionalProperties": False,
}

GROUNDING_REF_SCHEMA: JsonObject = {
    "type": "object",
    "required": ["term", "fact_id", "span"],
    "properties": {
        "term": {"type": "string", "minLength": 1},
        "claim": {"type": "string", "minLength": 1},
        "fact_id": {"type": "string", "minLength": 1},
        "span": SPAN_SCHEMA,
    },
    "additionalProperties": False,
}

REWRITE_OPERATION_SCHEMA: JsonObject = {
    "type": "object",
    "required": [
        "schema_version",
        "operation_id",
        "status",
        "op",
        "operation_type",
        "path",
        "target_path",
        "reason",
        "before",
        "after",
        "linked_requirement_ids",
        "linked_fact_ids",
        "requirementIds",
        "factIds",
        "provenance",
        "confidence",
        "grounding",
    ],
    "properties": {
        "schema_version": {"enum": [RESUME_CHANGE_OPERATION_SCHEMA_VERSION]},
        "operation_id": {"type": "string", "minLength": 1},
        "status": {"enum": ["proposed"]},
        "op": {"enum": list(CHANGE_OPERATION_VERBS)},
        "operation_type": {"enum": list(CHANGE_OPERATION_VERBS)},
        "path": {"type": "string", "minLength": 1},
        "target_path": {"type": "string", "minLength": 1},
        "reason": {"type": "string", "minLength": 1},
        "before": {"type": "string"},
        "after": {"type": "string", "minLength": 1},
        "linked_requirement_ids": {"type": "array", "minItems": 1, "items": {"type": "string", "minLength": 1}},
        "linked_fact_ids": {"type": "array", "minItems": 1, "items": {"type": "string", "minLength": 1}},
        "requirementIds": {"type": "array", "minItems": 1, "items": {"type": "string", "minLength": 1}},
        "factIds": {"type": "array", "minItems": 1, "items": {"type": "string", "minLength": 1}},
        "provenance": {"type": "array", "minItems": 1, "items": PROVENANCE_REF_SCHEMA},
        "confidence": CONFIDENCE_SCHEMA,
        "grounding": {"type": "array", "items": GROUNDING_REF_SCHEMA},
    },
    "additionalProperties": False,
}

REWRITE_PROPOSAL_SCHEMA: JsonObject = {
    "schema_version": REWRITE_PROPOSAL_SCHEMA_ID,
    "type": "object",
    "required": ["schema_version", "proposal_type", "requires_validation", "uncertainty", "operations"],
    "properties": {
        "schema_version": {"enum": [REWRITE_PROPOSAL_SCHEMA_ID]},
        "proposal_type": {"enum": ["rewrite_proposal"]},
        "requires_validation": {"enum": [True]},
        "uncertainty": {"type": "array"},
        "operations": {"type": "array", "minItems": 1, "items": REWRITE_OPERATION_SCHEMA},
    },
    "additionalProperties": False,
}

REWRITE_OUTPUT_SCHEMAS: JsonSchemaRegistry = {
    REWRITE_PROPOSAL_SCHEMA_ID: REWRITE_PROPOSAL_SCHEMA,
}


def default_rewrite_output_schemas() -> JsonSchemaRegistry:
    return copy.deepcopy(REWRITE_OUTPUT_SCHEMAS)


__all__ = [
    "CHANGE_OPERATION_VERBS",
    "GROUNDING_REF_SCHEMA",
    "PROVENANCE_REF_SCHEMA",
    "RESUME_CHANGE_OPERATION_SCHEMA_VERSION",
    "REWRITE_OPERATION_SCHEMA",
    "REWRITE_OUTPUT_SCHEMAS",
    "REWRITE_PROPOSAL_SCHEMA",
    "REWRITE_PROPOSAL_SCHEMA_ID",
    "default_rewrite_output_schemas",
]
