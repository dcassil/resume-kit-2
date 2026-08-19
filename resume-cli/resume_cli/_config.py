"""Section-13 workspace configuration contract for resume-cli."""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

from resume_agent import resolve_agent_config
from resume_core import resolve_guardrails_config, resolve_matching_config, resolve_resume_config


JsonObject = dict[str, Any]

CONFIG_VERSION = "resume-cli.config.v1"

_SCHEMA_VERSION_KEYS = (
    "canonical_resume",
    "job",
    "career_db",
    "change_operation",
    "renderer_template",
)
_TOP_LEVEL_KEYS = (
    "config_version",
    "schema_versions",
    "matching",
    "resume",
    "guardrails",
    "agent",
)
_LEGACY_REPLACEMENTS = {
    "policy": "matching.scoreAutoThreshold and matching.weights",
    "require_hard_resolution": "matching.requireHardRequirementsResolved",
    "allow_inferred_facts": "guardrails.allow_inferred_facts",
    "max_skills": "resume.skills.max",
}


@dataclass(frozen=True)
class WorkspaceConfig:
    config: JsonObject
    frozen_config: Any
    config_hash: str
    errors: list[JsonObject]
    warnings: list[JsonObject]


class WorkspaceConfigValidationError(ValueError):
    """Raised when config.json violates the resume-cli config contract."""

    def __init__(self, errors: list[JsonObject], *, config_path: Path | None = None) -> None:
        self.errors = copy.deepcopy(errors)
        self.config_path = config_path
        summary = "; ".join(
            f"{error.get('field_path', 'config')}: {error.get('message', error.get('code', 'invalid'))}"
            for error in errors[:3]
        )
        if len(errors) > 3:
            summary = f"{summary}; ... {len(errors) - 3} more"
        location = f"{config_path}: " if config_path is not None else ""
        super().__init__(f"{location}config validation failed: {summary}")


def schema_versions() -> JsonObject:
    return {
        "canonical_resume": "canonical-resume.v1",
        "job": "job-model.v1",
        "career_db": "career-store.v1",
        "change_operation": "resume-change-operation.v1",
        "renderer_template": "ats-clean@1.0.0",
    }


def default_config() -> JsonObject:
    return {
        "config_version": CONFIG_VERSION,
        "schema_versions": schema_versions(),
        "matching": resolve_matching_config({}).config.to_dict(),
        "resume": resolve_resume_config({}).config.to_dict(),
        "guardrails": resolve_guardrails_config({}).config.to_dict(),
        "agent": resolve_agent_config({}).config.to_dict(),
    }


def load_workspace_config(config_path: Path) -> WorkspaceConfig:
    raw = json.loads(config_path.read_text(encoding="utf-8")) if config_path.exists() else default_config()
    result = resolve_workspace_config(raw)
    if result.errors:
        raise WorkspaceConfigValidationError(result.errors, config_path=config_path)
    return result


def resolve_workspace_config(raw: Any) -> WorkspaceConfig:
    errors: list[JsonObject] = []
    warnings: list[JsonObject] = []
    if not isinstance(raw, dict):
        errors.append(_issue("invalid_cli_config_type", "config.json must contain an object.", "config"))
        config = default_config()
        return _workspace_config(config, errors, warnings)

    _reject_top_level_keys(raw, errors)
    _validate_cli_metadata(raw, errors)

    resolver_input = _resolver_input(raw)
    matching_result = resolve_matching_config(resolver_input)
    resume_result = resolve_resume_config(resolver_input)
    guardrails_result = resolve_guardrails_config(resolver_input)
    agent_result = resolve_agent_config(resolver_input)
    errors.extend([*matching_result.errors, *resume_result.errors, *guardrails_result.errors, *agent_result.errors])
    warnings.extend([*matching_result.warnings, *resume_result.warnings, *guardrails_result.warnings, *agent_result.warnings])

    config = {
        "config_version": raw.get("config_version", CONFIG_VERSION),
        "schema_versions": _resolved_schema_versions(raw.get("schema_versions", {})),
        "matching": matching_result.config.to_dict(),
        "resume": resume_result.config.to_dict(),
        "guardrails": guardrails_result.config.to_dict(),
        "agent": agent_result.config.to_dict(),
    }
    return _workspace_config(config, errors, warnings)


def stable_config_hash(config: JsonObject) -> str:
    config_payload = copy.deepcopy(config) if isinstance(config, dict) else {}
    config_payload["agent"] = resolve_agent_config(config_payload).config.to_dict()
    payload = json.dumps(_jsonable(config_payload), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def freeze_json(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({str(key): freeze_json(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(freeze_json(item) for item in value)
    if isinstance(value, tuple):
        return tuple(freeze_json(item) for item in value)
    return value


def _workspace_config(config: JsonObject, errors: list[JsonObject], warnings: list[JsonObject]) -> WorkspaceConfig:
    copied = copy.deepcopy(config)
    return WorkspaceConfig(
        config=copied,
        frozen_config=freeze_json(copied),
        config_hash=stable_config_hash(copied),
        errors=copy.deepcopy(errors),
        warnings=copy.deepcopy(warnings),
    )


def _reject_top_level_keys(raw: JsonObject, errors: list[JsonObject]) -> None:
    allowed = set(_TOP_LEVEL_KEYS)
    for key in sorted(set(raw) - allowed):
        if key in _LEGACY_REPLACEMENTS:
            replacement = _LEGACY_REPLACEMENTS[key]
            errors.append(
                _issue(
                    "legacy_cli_config_key",
                    f"Legacy flat config key is not supported; use {replacement}.",
                    key,
                    {"replacement": replacement},
                )
            )
        else:
            errors.append(
                _issue(
                    "unknown_cli_config_key",
                    "Unknown resume-cli config key.",
                    key,
                    {"allowed": sorted(_TOP_LEVEL_KEYS)},
                )
            )


def _resolver_input(raw: JsonObject) -> JsonObject:
    resolver_input = {key: copy.deepcopy(value) for key, value in raw.items() if key not in _LEGACY_REPLACEMENTS}
    resume = resolver_input.get("resume")
    if isinstance(resume, dict):
        for key in ("skills", "experience", "bulletsPerRole"):
            range_value = resume.get(key)
            if isinstance(range_value, dict) and range_value.get("max") is None:
                range_value.pop("max", None)
    return resolver_input


def _validate_cli_metadata(raw: JsonObject, errors: list[JsonObject]) -> None:
    if "config_version" in raw and raw["config_version"] != CONFIG_VERSION:
        errors.append(
            _issue(
                "invalid_cli_config_value",
                f"config_version must be {CONFIG_VERSION}.",
                "config_version",
                {"expected": CONFIG_VERSION},
            )
        )
    schema_versions_value = raw.get("schema_versions", {})
    if "schema_versions" in raw and not isinstance(schema_versions_value, dict):
        errors.append(_issue("invalid_cli_config_type", "schema_versions must be an object.", "schema_versions"))
        return
    if isinstance(schema_versions_value, dict):
        allowed = set(_SCHEMA_VERSION_KEYS)
        for key in sorted(set(schema_versions_value) - allowed):
            errors.append(
                _issue(
                    "unknown_cli_config_key",
                    "Unknown schema_versions config key.",
                    f"schema_versions.{key}",
                    {"allowed": sorted(_SCHEMA_VERSION_KEYS)},
                )
            )


def _resolved_schema_versions(raw_schema_versions: Any) -> JsonObject:
    resolved = schema_versions()
    if isinstance(raw_schema_versions, dict):
        for key in _SCHEMA_VERSION_KEYS:
            if key in raw_schema_versions:
                resolved[key] = copy.deepcopy(raw_schema_versions[key])
    return resolved


def _issue(code: str, message: str, field_path: str, details: JsonObject | None = None) -> JsonObject:
    issue: JsonObject = {"code": code, "message": message, "severity": "error", "field_path": field_path}
    if details:
        issue["details"] = details
    return issue


def _jsonable(value: Any) -> Any:
    if isinstance(value, MappingProxyType):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value
