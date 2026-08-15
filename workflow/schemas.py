"""Canonical DTOs and JSON schema fragments for workflow artifacts."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


JsonObject = dict[str, Any]

RUN_MANIFEST_SCHEMA_VERSION = "run-manifest.v1"
CAREER_DB_VERSION_UNAVAILABLE_STATUS = "unavailable"
NON_EMPTY_STRING: JsonObject = {"type": "string", "minLength": 1}
VERSION_STRING: JsonObject = {"type": "string", "minLength": 1, "not": {"enum": ["0.0.0"]}}


class Checkpoint(str, Enum):
    INIT = "INIT"
    INGEST_RESUME = "INGEST_RESUME"
    VALIDATE_BASE = "VALIDATE_BASE"
    EXTRACT_PERSIST_CAREER_FACTS = "EXTRACT_PERSIST_CAREER_FACTS"
    INGEST_JOB = "INGEST_JOB"
    NORMALIZE_JOB = "NORMALIZE_JOB"
    MATCH_BASE = "MATCH_BASE"
    RESOLVE_GAPS = "RESOLVE_GAPS"
    BUILD_SELECTION_PLAN = "BUILD_SELECTION_PLAN"
    PROPOSE_TAILORING_CHANGES = "PROPOSE_TAILORING_CHANGES"
    VALIDATE_CHANGES = "VALIDATE_CHANGES"
    APPLY_CHANGES = "APPLY_CHANGES"
    FINAL_MATCH = "FINAL_MATCH"
    GROUNDING_AUDIT = "GROUNDING_AUDIT"
    ATS_STRUCTURE_VALIDATION = "ATS_STRUCTURE_VALIDATION"
    RENDER = "RENDER"
    RENDER_VALIDATION = "RENDER_VALIDATION"
    COMPLETE = "COMPLETE"


@dataclass(frozen=True)
class RunManifest:
    run_id: str
    base_resume_id: str
    base_resume_hash: str
    job_id: str
    config_hash: str
    canonical_resume_schema_version: str
    job_schema_version: str
    career_db_schema_version: str
    careerDbVersion: JsonObject
    change_operation_schema_version: str
    matching_algorithm_version: str
    matching_config_version: str
    renderer_template_version: str
    agent_model_config: JsonObject
    initial_score: float
    final_score: float
    facts_added: list[str] = field(default_factory=list)
    facts_verified: list[str] = field(default_factory=list)
    operations_applied: list[str] = field(default_factory=list)
    operations_rejected: list[str] = field(default_factory=list)
    validation_status: str = "unknown"
    output_artifact_paths: list[str] = field(default_factory=list)
    schema_version: str = RUN_MANIFEST_SCHEMA_VERSION
    package_versions: dict[str, str] = field(default_factory=dict)
    recovery_markers: list[JsonObject] = field(default_factory=list)
    audit_refs: list[str] = field(default_factory=list)
    metadata: JsonObject = field(default_factory=dict)


RUN_MANIFEST_SCHEMA: JsonObject = {
    "schema_version": RUN_MANIFEST_SCHEMA_VERSION,
    "type": "object",
    "required": [
        "run_id",
        "base_resume_id",
        "base_resume_hash",
        "job_id",
        "config_hash",
        "canonical_resume_schema_version",
        "job_schema_version",
        "career_db_schema_version",
        "careerDbVersion",
        "change_operation_schema_version",
        "matching_algorithm_version",
        "matching_config_version",
        "renderer_template_version",
        "agent_model_config",
        "initial_score",
        "final_score",
        "facts_added",
        "facts_verified",
        "operations_applied",
        "operations_rejected",
        "validation_status",
        "output_artifact_paths",
    ],
    "properties": {
        "run_id": {"type": "string"},
        "base_resume_id": NON_EMPTY_STRING,
        "base_resume_hash": NON_EMPTY_STRING,
        "job_id": NON_EMPTY_STRING,
        "config_hash": {"type": "string"},
        "canonical_resume_schema_version": VERSION_STRING,
        "job_schema_version": VERSION_STRING,
        "career_db_schema_version": VERSION_STRING,
        "careerDbVersion": {
            "oneOf": [
                {
                    "type": "object",
                    "required": ["schema_version", "database_path", "applied_migrations", "pending_migrations", "status", "metadata"],
                    "properties": {
                        "schema_version": VERSION_STRING,
                        "database_path": {"type": "string"},
                        "applied_migrations": {"type": "array", "items": {"type": "string"}},
                        "pending_migrations": {"type": "array", "items": {"type": "string"}},
                        "status": {"type": "string"},
                        "metadata": {"type": "object"},
                    },
                },
                {
                    "type": "object",
                    "required": ["status", "reason"],
                    "properties": {
                        "status": {"enum": [CAREER_DB_VERSION_UNAVAILABLE_STATUS]},
                        "reason": {"enum": ["career_db_not_configured"]},
                    },
                },
            ]
        },
        "change_operation_schema_version": VERSION_STRING,
        "matching_algorithm_version": VERSION_STRING,
        "matching_config_version": VERSION_STRING,
        "renderer_template_version": VERSION_STRING,
        "agent_model_config": {"type": "object"},
        "initial_score": {"type": "number"},
        "final_score": {"type": "number"},
        "facts_added": {"type": "array", "items": {"type": "string"}},
        "facts_verified": {"type": "array", "items": {"type": "string"}},
        "operations_applied": {"type": "array", "items": {"type": "string"}},
        "operations_rejected": {"type": "array", "items": {"type": "string"}},
        "validation_status": {"type": "string"},
        "output_artifact_paths": {"type": "array", "items": {"type": "string"}},
        "schema_version": VERSION_STRING,
        "package_versions": {"type": "object", "additionalProperties": VERSION_STRING},
        "recovery_markers": {"type": "array", "items": {"type": "object"}},
        "audit_refs": {"type": "array", "items": {"type": "string"}},
    },
}

SCHEMAS: dict[str, JsonObject] = {
    "RunManifest": RUN_MANIFEST_SCHEMA,
}
