"""Canonical DTOs and JSON schema fragments for career-store surfaces."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from resume_core import Error, Result, ResolutionState, VerificationState


JsonObject = dict[str, Any]
INTERPRETATION_PROPOSAL_OUTCOMES = {"affirmed", "denied", "unclear"}


class InvalidInterpretationProposalError(ValueError):
    """Typed validation error for malformed store interpretation proposals."""

    def __init__(
        self,
        code: str,
        field_path: str,
        message: str,
        allowed_values: list[str] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.field_path = field_path
        self.message = message
        self.allowed_values = allowed_values

    def to_error(self) -> JsonObject:
        payload: JsonObject = {
            "type": self.__class__.__name__,
            "code": self.code,
            "field_path": self.field_path,
            "message": self.message,
        }
        if self.allowed_values is not None:
            payload["allowed_values"] = self.allowed_values
        return payload


class RelationshipType(str, Enum):
    ALIAS = "alias"
    EQUIVALENT = "equivalent"
    RELATED = "related"
    PARENT = "parent"
    CHILD = "child"
    CONTRADICTS = "contradicts"


@dataclass(frozen=True)
class Evidence:
    evidence_id: str
    source: str
    text: str
    source_id: str | None = None
    source_span: JsonObject | None = None
    observed_at: str | None = None
    metadata: JsonObject = field(default_factory=dict)


ProvenanceRef = JsonObject


@dataclass(frozen=True)
class InterpretationProposal:
    factId: str
    outcome: str
    provenance: list[ProvenanceRef]
    questionId: str | None = None
    confirmedValue: Any | None = None


@dataclass(frozen=True)
class Fact:
    fact_id: str
    type: str
    text: str
    normalized_terms: list[str]
    verification_state: VerificationState | str
    canonical_name: str | None = None
    description: str | None = None
    years: int | None = None
    confidence: float | None = None
    evidence_ids: list[str] = field(default_factory=list)
    created_at: str | None = None
    updated_at: str | None = None
    metadata: JsonObject = field(default_factory=dict)


CareerFact = Fact


@dataclass(frozen=True)
class FactRelationship:
    relationship_id: str
    from_fact_id: str
    to_fact_id: str
    relationship_type: RelationshipType | str
    evidence_or_rationale: JsonObject = field(default_factory=dict)
    confidence: float | None = None
    created_at: str | None = None
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True)
class ConflictRecord:
    conflict_id: str
    fact_ids: list[str]
    reason: str
    status: str = "open"
    evidence_ids: list[str] = field(default_factory=list)
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True)
class JobAssociation:
    job_match_id: str
    job_id: str
    requirement_id: str
    fact_ids: list[str]
    resolution_state: ResolutionState | str
    match_type: str | None = None
    confidence: float | None = None
    user_confirmed: bool | None = None
    created_at: str | None = None
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True)
class TransactionResult:
    schema_version: str
    status: str
    mutation_status: str
    ids: dict[str, str] = field(default_factory=dict)
    errors: list[Error | JsonObject] = field(default_factory=list)
    audit: JsonObject = field(default_factory=dict)


@dataclass(frozen=True)
class MigrationState:
    schema_version: str
    database_path: str
    applied_migrations: list[str] = field(default_factory=list)
    pending_migrations: list[str] = field(default_factory=list)
    status: str = "unknown"
    metadata: JsonObject = field(default_factory=dict)


FACT_SCHEMA: JsonObject = {
    "schema_version": "career-fact.v1",
    "type": "object",
    "required": ["fact_id", "type", "text", "normalized_terms", "verification_state"],
    "properties": {
        "fact_id": {"type": "string"},
        "type": {"type": "string"},
        "text": {"type": "string"},
        "normalized_terms": {"type": "array", "items": {"type": "string"}},
        "verification_state": {"enum": [state.value for state in VerificationState]},
        "canonical_name": {"type": ["string", "null"]},
        "description": {"type": ["string", "null"]},
        "years": {"type": ["integer", "null"]},
        "confidence": {"type": ["number", "null"]},
        "evidence_ids": {"type": "array", "items": {"type": "string"}},
    },
}

EVIDENCE_SCHEMA: JsonObject = {
    "schema_version": "evidence.v1",
    "type": "object",
    "required": ["evidence_id", "source", "text"],
    "properties": {
        "evidence_id": {"type": "string"},
        "source": {"type": "string"},
        "source_id": {"type": ["string", "null"]},
        "text": {"type": "string"},
        "source_span": {"type": ["object", "null"]},
        "observed_at": {"type": ["string", "null"]},
    },
}

FACT_RELATIONSHIP_SCHEMA: JsonObject = {
    "schema_version": "fact-relationship.v1",
    "type": "object",
    "required": ["relationship_id", "from_fact_id", "to_fact_id", "relationship_type"],
    "properties": {
        "relationship_id": {"type": "string"},
        "from_fact_id": {"type": "string"},
        "to_fact_id": {"type": "string"},
        "relationship_type": {"enum": [state.value for state in RelationshipType]},
        "evidence_or_rationale": {"type": "object"},
        "confidence": {"type": ["number", "null"]},
    },
}

INTERPRETATION_PROPOSAL_SCHEMA: JsonObject = {
    "schema_version": "interpretation-proposal.v1",
    "type": "object",
    "required": ["factId", "outcome", "provenance"],
    "properties": {
        "factId": {"type": "string"},
        "questionId": {"type": ["string", "null"]},
        "outcome": {"enum": sorted(INTERPRETATION_PROPOSAL_OUTCOMES)},
        "confirmedValue": {},
        "provenance": {"type": "array", "items": {"type": "object"}},
    },
}

SCHEMAS: dict[str, JsonObject] = {
    "Fact": FACT_SCHEMA,
    "CareerFact": FACT_SCHEMA,
    "Evidence": EVIDENCE_SCHEMA,
    "FactRelationship": FACT_RELATIONSHIP_SCHEMA,
    "InterpretationProposal": INTERPRETATION_PROPOSAL_SCHEMA,
}


__all__ = [
    "CareerFact",
    "ConflictRecord",
    "Evidence",
    "Fact",
    "FactRelationship",
    "INTERPRETATION_PROPOSAL_OUTCOMES",
    "INTERPRETATION_PROPOSAL_SCHEMA",
    "InterpretationProposal",
    "InvalidInterpretationProposalError",
    "MigrationState",
    "ProvenanceRef",
    "RelationshipType",
    "ResolutionState",
    "Result",
    "SCHEMAS",
    "TransactionResult",
    "VerificationState",
    "JobAssociation",
]
