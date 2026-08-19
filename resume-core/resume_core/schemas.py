"""Canonical DTOs and JSON schema fragments for resume-core surfaces."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from enum import Enum
from typing import Any


JsonObject = dict[str, Any]

RESULT_SCHEMA_VERSION = "result.v1"
ERROR_SCHEMA_VERSION = "error.v1"
CANONICAL_RESUME_SCHEMA_VERSION = "canonical-resume.v1"
JOB_REQUIREMENT_SCHEMA_VERSION = "job-requirement.v1"
JOB_TERM_SCHEMA_VERSION = "job-term.v1"
TERM_RELATIONSHIP_SCHEMA_VERSION = "term-relationship.v1"
JOB_MODEL_SCHEMA_VERSION = "job-model.v1"
MATCH_DIMENSION_SCHEMA_VERSION = "match-dimension.v1"
MATCH_RESULT_SCHEMA_VERSION = "match-result.v1"
CONTENT_SELECTION_ENTRY_SCHEMA_VERSION = "content-selection-entry.v1"
CONTENT_SELECTION_CONSTRAINT_REPORT_SCHEMA_VERSION = "content-selection-constraint-report.v1"
CONTENT_SELECTION_PLAN_SCHEMA_VERSION = "content-selection-plan.v1"
RENDERABLE_RESUME_SCHEMA_VERSION = "renderable-resume.v1"
RESUME_CHANGE_OPERATION_SCHEMA_VERSION = "resume-change-operation.v1"


class Status(str, Enum):
    OK = "ok"
    WARNING = "warning"
    ERROR = "error"
    REJECTED = "rejected"
    BLOCKED = "blocked"
    PASS = "pass"
    FAIL = "fail"
    CREATED = "created"
    UPDATED = "updated"


class ErrorSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    BLOCKING = "blocking"


class VerificationState(str, Enum):
    SOURCE_STATED = "source_stated"
    USER_VERIFIED = "user_verified"
    IMPORTED = "imported"
    INFERRED = "inferred"
    UNKNOWN = "unknown"


class ResolutionState(str, Enum):
    EXACT_MATCH = "exact_match"
    ALIAS_MATCH = "alias_match"
    VERIFIED_FACT_MATCH = "verified_fact_match"
    RELATED_MATCH = "related_match"
    POSSIBLE_MATCH = "possible_match"
    UNKNOWN = "unknown"
    EXPLICITLY_MISSING = "explicitly_missing"
    NOT_APPLICABLE = "not_applicable"


class RequirementClassification(str, Enum):
    REQUIRED = "required"
    PREFERRED = "preferred"
    CONTEXTUAL = "contextual"


class ChangeOperationStatus(str, Enum):
    PROPOSED = "proposed"
    VALIDATED = "validated"
    REJECTED = "rejected"
    APPLIED = "applied"
    ACCEPTED = "accepted"
    MODIFIED = "modified"


class TermRelationshipKind(str, Enum):
    ALIAS = "alias"
    RELATED = "related"
    PARENT = "parent"
    CHILD = "child"
    CONTRADICTS = "contradicts"


@dataclass(frozen=True)
class Error:
    code: str
    message: str
    field_path: str | None = None
    severity: ErrorSeverity = ErrorSeverity.ERROR
    details: JsonObject = field(default_factory=dict)


@dataclass(frozen=True)
class Result:
    schema_version: str
    status: Status | str
    value: Any = None
    errors: list[Error] = field(default_factory=list)
    warnings: list[Error] = field(default_factory=list)
    audit: JsonObject = field(default_factory=dict)


@dataclass(frozen=True)
class ResumeField:
    value: Any
    claim_id: str | None = None
    provenance: list[JsonObject] = field(default_factory=list)
    verification_state: VerificationState | str = VerificationState.UNKNOWN


@dataclass(frozen=True)
class CanonicalResume:
    schema_version: str
    resume_id: str
    source: JsonObject
    basics: JsonObject = field(default_factory=dict)
    experience: list[JsonObject] = field(default_factory=list)
    skills: list[str | ResumeField | JsonObject] = field(default_factory=list)
    education: list[JsonObject] = field(default_factory=list)
    certifications: list[JsonObject] = field(default_factory=list)
    awards: list[JsonObject] = field(default_factory=list)
    projects: list[JsonObject] = field(default_factory=list)
    additional_sections: list[JsonObject] = field(default_factory=list)
    provenance: list[JsonObject] = field(default_factory=list)
    verification_state: VerificationState | str = VerificationState.SOURCE_STATED
    ingest_warnings: list[Error | JsonObject] = field(default_factory=list)
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True)
class JobRequirement:
    requirement_id: str
    classification: RequirementClassification | str
    concept: str
    importance: str
    weight: float
    source_text: str
    normalized_terms: list[str] = field(default_factory=list)
    years: str | None = None
    required: bool | None = None
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True)
class JobTerm:
    surface: str
    canonical: str
    source: str
    weight: float


@dataclass(frozen=True)
class JobModel:
    schema_version: str
    job_id: str
    requirements: list[JobRequirement | JsonObject]
    preferred: list[JobRequirement | JsonObject] = field(default_factory=list)
    title: str | None = None
    company: str | None = None
    seniority: str | None = None
    industries: list[str | JsonObject] = field(default_factory=list)
    domains: list[str | JsonObject] = field(default_factory=list)
    terminology: list[JobTerm | JsonObject] = field(default_factory=list)
    source: JsonObject = field(default_factory=dict)
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True)
class RequirementMatch:
    requirement_id: str
    resolution_state: ResolutionState | str
    score: float
    matched_fact_ids: list[str] = field(default_factory=list)
    explanation: str = ""
    blocking: bool = False
    evidence: list[JsonObject] = field(default_factory=list)
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True)
class MatchDimension:
    name: str
    weight: float
    score: float
    contribution: float
    evidence: list[JsonObject] = field(default_factory=list)


@dataclass(frozen=True)
class MatchResult:
    schema_version: str
    match_id: str
    job_id: str
    resume_id: str
    score: float
    max_score: float
    threshold: float
    hardRequirementsResolved: bool
    decision: str
    dimensions: list[MatchDimension | JsonObject]
    requirement_results: list[RequirementMatch | JsonObject]
    unresolved_requirement_ids: list[str] = field(default_factory=list)
    can_continue: bool = True
    explanations: list[str] = field(default_factory=list)
    config_hash: str | None = None
    algorithm_version: str | None = None
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True)
class ContentSelectionEntry:
    path: str
    action: str
    relevance: float
    reason: str
    requirement_ids: list[str] = field(default_factory=list)
    fact_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ContentSelectionConstraintReport:
    constraint: str
    limit: Any
    actual: Any
    status: str


@dataclass(frozen=True)
class ContentSelectionPlan:
    schema_version: str
    sections: list[str]
    entries: list[ContentSelectionEntry | JsonObject]
    constraint_report: list[ContentSelectionConstraintReport | JsonObject]
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True)
class RenderableResume:
    schema_version: str
    contact: JsonObject
    sections: list[JsonObject]
    summary: str | None = None


@dataclass(frozen=True)
class ResumeChangeOperation:
    schema_version: str
    operation_id: str
    status: ChangeOperationStatus | str
    op: str
    path: str
    reason: str
    before: Any = None
    after: Any = None
    linked_requirement_ids: list[str] = field(default_factory=list)
    linked_fact_ids: list[str] = field(default_factory=list)
    provenance: list[JsonObject] = field(default_factory=list)
    validation_state: str | None = None
    errors: list[Error | JsonObject] = field(default_factory=list)
    metadata: JsonObject = field(default_factory=dict)


def to_json_dict(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {key: to_json_dict(item) for key, item in asdict(value).items()}
    if isinstance(value, list):
        return [to_json_dict(item) for item in value]
    if isinstance(value, tuple):
        return [to_json_dict(item) for item in value]
    if isinstance(value, dict):
        return {str(key): to_json_dict(item) for key, item in value.items()}
    return value


def require_fields(payload: JsonObject, required_fields: set[str], schema_name: str) -> list[Error]:
    return [
        Error(code="missing_field", message=f"{schema_name} requires {field_name}.", field_path=field_name)
        for field_name in sorted(required_fields - set(payload))
    ]


RESULT_SCHEMA: JsonObject = {
    "schema_version": RESULT_SCHEMA_VERSION,
    "type": "object",
    "required": ["schema_version", "status"],
    "properties": {
        "schema_version": {"type": "string"},
        "status": {"type": "string"},
        "value": {},
        "errors": {"type": "array"},
        "warnings": {"type": "array"},
        "audit": {"type": "object"},
    },
}

ERROR_SCHEMA: JsonObject = {
    "schema_version": ERROR_SCHEMA_VERSION,
    "type": "object",
    "required": ["code", "message", "severity"],
    "properties": {
        "code": {"type": "string"},
        "message": {"type": "string"},
        "field_path": {"type": ["string", "null"]},
        "severity": {"enum": [state.value for state in ErrorSeverity]},
        "details": {"type": "object"},
    },
}

CANONICAL_RESUME_SCHEMA: JsonObject = {
    "schema_version": CANONICAL_RESUME_SCHEMA_VERSION,
    "type": "object",
    "required": ["schema_version", "resume_id", "source", "experience", "skills", "education"],
    "properties": {
        "schema_version": {"type": "string"},
        "resume_id": {"type": "string"},
        "source": {"type": "object"},
        "basics": {"type": "object"},
        "experience": {"type": "array"},
        "skills": {"type": "array"},
        "education": {"type": "array"},
        "provenance": {"type": "array"},
        "verification_state": {"enum": [state.value for state in VerificationState]},
    },
}

JOB_REQUIREMENT_SCHEMA: JsonObject = {
    "schema_version": JOB_REQUIREMENT_SCHEMA_VERSION,
    "type": "object",
    "required": ["requirement_id", "classification", "concept", "importance", "weight", "source_text", "normalized_terms", "years"],
    "properties": {
        "requirement_id": {"type": "string"},
        "classification": {"enum": [state.value for state in RequirementClassification]},
        "concept": {"type": "string"},
        "importance": {"type": "string"},
        "weight": {"type": "number"},
        "source_text": {"type": "string"},
        "normalized_terms": {"type": "array", "items": {"type": "string"}},
        "years": {"type": ["string", "object", "null"]},
    },
}

JOB_TERM_SCHEMA: JsonObject = {
    "schema_version": JOB_TERM_SCHEMA_VERSION,
    "type": "object",
    "required": ["surface", "canonical", "source", "weight"],
    "properties": {
        "surface": {"type": "string"},
        "canonical": {"type": "string"},
        "source": {"enum": ["title", "requirement", "description"]},
        "weight": {"type": "number"},
    },
}

TERM_RELATIONSHIP_SCHEMA: JsonObject = {
    "schema_version": TERM_RELATIONSHIP_SCHEMA_VERSION,
    "type": "object",
    "required": ["from", "to", "kind", "provenance"],
    "properties": {
        "from": {"type": "string"},
        "to": {"type": "string"},
        "kind": {"enum": [kind.value for kind in TermRelationshipKind]},
        "provenance": {},
    },
}

JOB_MODEL_SCHEMA: JsonObject = {
    "schema_version": JOB_MODEL_SCHEMA_VERSION,
    "type": "object",
    "required": ["schema_version", "job_id", "requirements", "preferred", "industries", "domains", "terminology"],
    "properties": {
        "schema_version": {"type": "string"},
        "job_id": {"type": "string"},
        "title": {"type": ["string", "null"]},
        "company": {"type": ["string", "null"]},
        "seniority": {"type": ["string", "null"]},
        "industries": {"type": "array", "items": {"type": ["string", "object"]}},
        "domains": {"type": "array", "items": {"type": ["string", "object"]}},
        "requirements": {"type": "array", "items": JOB_REQUIREMENT_SCHEMA},
        "preferred": {"type": "array", "items": JOB_REQUIREMENT_SCHEMA},
        "terminology": {"type": "array", "items": JOB_TERM_SCHEMA},
        "source": {"type": "object"},
        "metadata": {"type": "object"},
    },
}

MATCH_DIMENSION_SCHEMA: JsonObject = {
    "schema_version": MATCH_DIMENSION_SCHEMA_VERSION,
    "type": "object",
    "required": ["name", "weight", "score", "contribution", "evidence"],
    "properties": {
        "name": {
            "enum": [
                "requiredSkills",
                "experience",
                "roleAlignment",
                "domainIndustry",
                "preferredSkills",
                "terminology",
            ]
        },
        "weight": {"type": "number"},
        "score": {"type": "number", "minimum": 0, "maximum": 1},
        "contribution": {"type": "number"},
        "evidence": {"type": "array"},
    },
}

MATCH_RESULT_SCHEMA: JsonObject = {
    "schema_version": MATCH_RESULT_SCHEMA_VERSION,
    "type": "object",
    "required": [
        "schema_version",
        "match_id",
        "job_id",
        "resume_id",
        "score",
        "max_score",
        "threshold",
        "hardRequirementsResolved",
        "decision",
        "dimensions",
        "requirement_results",
    ],
    "properties": {
        "schema_version": {"type": "string"},
        "match_id": {"type": "string"},
        "job_id": {"type": "string"},
        "resume_id": {"type": "string"},
        "score": {"type": "number"},
        "max_score": {"type": "number"},
        "threshold": {"type": "number"},
        "hardRequirementsResolved": {"type": "boolean"},
        "decision": {"enum": ["continue", "resolve_gaps", "blocked"]},
        "dimensions": {"type": "array", "items": MATCH_DIMENSION_SCHEMA},
        "requirement_results": {"type": "array"},
        "unresolved_requirement_ids": {"type": "array", "items": {"type": "string"}},
        "can_continue": {"type": "boolean"},
    },
}

CONTENT_SELECTION_ENTRY_SCHEMA: JsonObject = {
    "schema_version": CONTENT_SELECTION_ENTRY_SCHEMA_VERSION,
    "type": "object",
    "required": ["path", "action", "relevance", "reason", "requirement_ids", "fact_ids"],
    "properties": {
        "path": {"type": "string"},
        "action": {"enum": ["keep", "drop", "reorder"]},
        "relevance": {"type": "number"},
        "reason": {"type": "string"},
        "requirement_ids": {"type": "array", "items": {"type": "string"}},
        "fact_ids": {"type": "array", "items": {"type": "string"}},
    },
}

CONTENT_SELECTION_CONSTRAINT_REPORT_SCHEMA: JsonObject = {
    "schema_version": CONTENT_SELECTION_CONSTRAINT_REPORT_SCHEMA_VERSION,
    "type": "object",
    "required": ["constraint", "limit", "actual", "status"],
    "properties": {
        "constraint": {"type": "string"},
        "limit": {},
        "actual": {},
        "status": {"enum": ["satisfied", "violated", "deficit"]},
    },
}

CONTENT_SELECTION_PLAN_SCHEMA: JsonObject = {
    "schema_version": CONTENT_SELECTION_PLAN_SCHEMA_VERSION,
    "type": "object",
    "required": ["schema_version", "sections", "entries", "constraint_report", "metadata"],
    "properties": {
        "schema_version": {"type": "string"},
        "sections": {"type": "array", "items": {"type": "string"}},
        "entries": {"type": "array", "items": CONTENT_SELECTION_ENTRY_SCHEMA},
        "constraint_report": {"type": "array", "items": CONTENT_SELECTION_CONSTRAINT_REPORT_SCHEMA},
        "metadata": {
            "type": "object",
            "required": ["target_pages", "config_snapshot"],
            "properties": {
                "target_pages": {},
                "config_snapshot": {"type": "object"},
            },
        },
    },
}

RENDERABLE_RESUME_ENTRY_SCHEMA: JsonObject = {
    "schema_version": RENDERABLE_RESUME_SCHEMA_VERSION,
    "type": "object",
    "required": [],
    "properties": {
        "title": {"type": "string"},
        "company": {"type": "string"},
        "organization": {"type": "string"},
        "start_date": {"type": "string"},
        "end_date": {"type": "string"},
        "date": {"type": "string"},
        "summary": {"type": "string"},
        "description": {"type": "string"},
        "degree": {"type": "string"},
        "field": {"type": "string"},
        "credential": {"type": "string"},
        "issuer": {"type": "string"},
        "bullets": {"type": "array", "items": {"type": ["string", "number", "boolean"]}},
        "skills": {"type": "array", "items": {"type": ["string", "number", "boolean"]}},
    },
}

RENDERABLE_RESUME_SECTION_SCHEMA: JsonObject = {
    "schema_version": RENDERABLE_RESUME_SCHEMA_VERSION,
    "type": "object",
    "required": ["id", "title", "entries"],
    "properties": {
        "id": {"type": "string"},
        "title": {"type": "string"},
        "format": {"type": "string"},
        "entries": {
            "type": "array",
            "items": {
                "oneOf": [
                    {"type": ["string", "number", "boolean"]},
                    RENDERABLE_RESUME_ENTRY_SCHEMA,
                ]
            },
        },
    },
}

RENDERABLE_RESUME_SCHEMA: JsonObject = {
    "schema_version": RENDERABLE_RESUME_SCHEMA_VERSION,
    "type": "object",
    "required": ["schema_version", "contact", "sections"],
    "properties": {
        "schema_version": {"type": "string"},
        "contact": {
            "type": "object",
            "required": ["name", "email", "phone", "links"],
            "properties": {
                "name": {"type": "string"},
                "email": {"type": "string"},
                "phone": {"type": "string"},
                "links": {"type": "array"},
            },
        },
        "summary": {"type": ["string", "null"]},
        "sections": {"type": "array", "items": RENDERABLE_RESUME_SECTION_SCHEMA},
    },
}

RESUME_CHANGE_OPERATION_SCHEMA: JsonObject = {
    "schema_version": RESUME_CHANGE_OPERATION_SCHEMA_VERSION,
    "type": "object",
    "required": [
        "schema_version",
        "operation_id",
        "status",
        "op",
        "path",
        "reason",
        "linked_requirement_ids",
        "linked_fact_ids",
        "provenance",
    ],
    "properties": {
        "schema_version": {"type": "string"},
        "operation_id": {"type": "string"},
        "status": {"enum": [state.value for state in ChangeOperationStatus]},
        "op": {"enum": ["replace", "rewrite", "insert", "remove", "move"]},
        "path": {"type": "string"},
        "reason": {"type": "string"},
        "before": {},
        "after": {},
        "linked_requirement_ids": {"type": "array", "items": {"type": "string"}},
        "linked_fact_ids": {"type": "array", "items": {"type": "string"}},
        "provenance": {"type": "array"},
    },
}

SCHEMAS: dict[str, JsonObject] = {
    "Result": RESULT_SCHEMA,
    "Error": ERROR_SCHEMA,
    "CanonicalResume": CANONICAL_RESUME_SCHEMA,
    "JobModel": JOB_MODEL_SCHEMA,
    "JobRequirement": JOB_REQUIREMENT_SCHEMA,
    "JobTerm": JOB_TERM_SCHEMA,
    "TermRelationship": TERM_RELATIONSHIP_SCHEMA,
    "MatchDimension": MATCH_DIMENSION_SCHEMA,
    "MatchResult": MATCH_RESULT_SCHEMA,
    "ContentSelectionEntry": CONTENT_SELECTION_ENTRY_SCHEMA,
    "ContentSelectionConstraintReport": CONTENT_SELECTION_CONSTRAINT_REPORT_SCHEMA,
    "ContentSelectionPlan": CONTENT_SELECTION_PLAN_SCHEMA,
    "RenderableResume": RENDERABLE_RESUME_SCHEMA,
    "ResumeChangeOperation": RESUME_CHANGE_OPERATION_SCHEMA,
}
