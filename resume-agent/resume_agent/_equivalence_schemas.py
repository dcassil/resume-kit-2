"""Versioned model-output schema for semantic equivalence proposals."""

from __future__ import annotations

import copy

from ._schema_validation import JsonObject, JsonSchemaRegistry


EQUIVALENCE_PROPOSAL_SCHEMA_ID = "resume-agent.equivalence-proposal.v1"

EQUIVALENCE_DIRECTIONS = ("equivalent", "narrower_than", "broader_than")

CONFIDENCE_SCHEMA: JsonObject = {"type": "number", "minimum": 0}

EQUIVALENCE_PROPOSAL_SCHEMA: JsonObject = {
    "type": "object",
    "required": [
        "id",
        "term_a",
        "term_b",
        "direction",
        "rationale",
        "evidence_refs",
        "confidence",
        "requires_validation",
    ],
    "properties": {
        "id": {"type": "string", "minLength": 1},
        "term_a": {"type": "string", "minLength": 1},
        "term_b": {"type": "string", "minLength": 1},
        "direction": {"enum": list(EQUIVALENCE_DIRECTIONS)},
        "rationale": {"type": "string", "minLength": 1},
        "evidence_refs": {"type": "array", "minItems": 1, "items": {"type": "string", "minLength": 1}},
        "confidence": CONFIDENCE_SCHEMA,
        "requires_validation": {"enum": [True]},
    },
    "additionalProperties": False,
}

EQUIVALENCE_PROPOSAL_LIST_SCHEMA: JsonObject = {
    "schema_version": EQUIVALENCE_PROPOSAL_SCHEMA_ID,
    "type": "array",
    "items": EQUIVALENCE_PROPOSAL_SCHEMA,
}

EQUIVALENCE_OUTPUT_SCHEMAS: JsonSchemaRegistry = {
    EQUIVALENCE_PROPOSAL_SCHEMA_ID: EQUIVALENCE_PROPOSAL_LIST_SCHEMA,
}


def default_equivalence_output_schemas() -> JsonSchemaRegistry:
    return copy.deepcopy(EQUIVALENCE_OUTPUT_SCHEMAS)


__all__ = [
    "CONFIDENCE_SCHEMA",
    "EQUIVALENCE_DIRECTIONS",
    "EQUIVALENCE_OUTPUT_SCHEMAS",
    "EQUIVALENCE_PROPOSAL_LIST_SCHEMA",
    "EQUIVALENCE_PROPOSAL_SCHEMA",
    "EQUIVALENCE_PROPOSAL_SCHEMA_ID",
    "default_equivalence_output_schemas",
]
