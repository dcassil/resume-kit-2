"""Validated workspace agent configuration for model adapter construction.

Defaults are part of the schema contract and are applied before hashing:

- model: claude-sonnet-4-6
- schema_mode: json_schema
- timeout_ms: 60000
- max_retries: 2
- cost_ceiling: 1.0
"""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping

from ._schema_validation import JsonObject, validate_json_schema


DEFAULT_AGENT_MODEL = "claude-sonnet-4-6"
DEFAULT_AGENT_SCHEMA_MODE = "json_schema"
DEFAULT_AGENT_TIMEOUT_MS = 60000
DEFAULT_AGENT_MAX_RETRIES = 2
DEFAULT_AGENT_COST_CEILING = 1.0

AGENT_CONFIG_KEYS = ("model", "schema_mode", "timeout_ms", "max_retries", "cost_ceiling")
AGENT_CONFIG_DEFAULTS: JsonObject = {
    "model": DEFAULT_AGENT_MODEL,
    "schema_mode": DEFAULT_AGENT_SCHEMA_MODE,
    "timeout_ms": DEFAULT_AGENT_TIMEOUT_MS,
    "max_retries": DEFAULT_AGENT_MAX_RETRIES,
    "cost_ceiling": DEFAULT_AGENT_COST_CEILING,
}

AGENT_CONFIG_SCHEMA: JsonObject = {
    "type": "object",
    "properties": {
        "model": {"type": "string", "minLength": 1},
        "schema_mode": {"enum": ["json_schema"]},
        "timeout_ms": {"type": "integer", "minimum": 1},
        "max_retries": {"type": "integer", "minimum": 0},
        "cost_ceiling": {"type": "number", "minimum": 0},
    },
    "additionalProperties": False,
}


@dataclass(frozen=True)
class AgentConfig:
    model: str = DEFAULT_AGENT_MODEL
    schema_mode: str = DEFAULT_AGENT_SCHEMA_MODE
    timeout_ms: int = DEFAULT_AGENT_TIMEOUT_MS
    max_retries: int = DEFAULT_AGENT_MAX_RETRIES
    cost_ceiling: float = DEFAULT_AGENT_COST_CEILING

    def to_dict(self) -> JsonObject:
        return {
            "model": self.model,
            "schema_mode": self.schema_mode,
            "timeout_ms": self.timeout_ms,
            "max_retries": self.max_retries,
            "cost_ceiling": self.cost_ceiling,
        }


@dataclass(frozen=True)
class AgentConfigResult:
    config: AgentConfig
    errors: list[JsonObject]
    warnings: list[JsonObject]

    @property
    def ok(self) -> bool:
        return not self.errors


class AgentConfigValidationError(ValueError):
    def __init__(self, errors: list[JsonObject]):
        self.errors = copy.deepcopy(errors)
        summary = "; ".join(
            f"{error.get('field_path', 'agent')}: {error.get('message', error.get('code', 'invalid'))}"
            for error in errors[:3]
        )
        if len(errors) > 3:
            summary = f"{summary}; ... {len(errors) - 3} more"
        super().__init__(f"Agent config validation failed: {summary}")


def resolve_agent_config(config: Mapping[str, Any] | None) -> AgentConfigResult:
    """Validate workspace config and return defaults merged into an AgentConfig."""

    raw = config if isinstance(config, Mapping) else {}
    errors: list[JsonObject] = []
    warnings: list[JsonObject] = []

    agent = raw.get("agent", {})
    if "agent" in raw and not isinstance(agent, dict):
        errors.append(_issue("invalid_agent_config_type", "agent must be an object.", "agent"))
        agent = {}

    values = dict(AGENT_CONFIG_DEFAULTS)
    if isinstance(agent, dict):
        violations = [_config_violation(item) for item in validate_json_schema(agent, AGENT_CONFIG_SCHEMA)]
        errors.extend(violations)
        invalid_fields = {
            str(item.get("field_path", "")).split(".", 1)[1]
            for item in violations
            if str(item.get("field_path", "")).startswith("agent.")
        }
        for key in AGENT_CONFIG_KEYS:
            if key in agent and key not in invalid_fields:
                values[key] = copy.deepcopy(agent[key])

    return AgentConfigResult(
        config=AgentConfig(
            model=str(values["model"]),
            schema_mode=str(values["schema_mode"]),
            timeout_ms=int(values["timeout_ms"]),
            max_retries=int(values["max_retries"]),
            cost_ceiling=float(values["cost_ceiling"]),
        ),
        errors=errors,
        warnings=warnings,
    )


def require_agent_config(config: Mapping[str, Any] | None) -> AgentConfig:
    result = resolve_agent_config(config)
    if result.errors:
        raise AgentConfigValidationError(result.errors)
    return result.config


def stable_agent_config_hash(agent_config: AgentConfig) -> str:
    if not isinstance(agent_config, AgentConfig):
        raise TypeError("stable_agent_config_hash requires a validated AgentConfig.")
    payload = json.dumps(agent_config.to_dict(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _config_violation(violation: JsonObject) -> JsonObject:
    converted = copy.deepcopy(violation)
    path = converted.get("field_path")
    if isinstance(path, str) and path:
        converted["field_path"] = f"agent.{path.replace('/', '.')}"
    else:
        converted["field_path"] = "agent"
    if converted.get("code") == "additional_property":
        converted["code"] = "unknown_agent_config_key"
        converted["message"] = "Unknown agent config key."
        converted.setdefault("details", {})["allowed"] = list(AGENT_CONFIG_KEYS)
    elif converted.get("code") in {"invalid_type", "invalid_enum", "min_length", "minimum"}:
        converted["code"] = "invalid_agent_config_value"
    return converted


def _issue(code: str, message: str, field_path: str, details: JsonObject | None = None) -> JsonObject:
    issue: JsonObject = {"code": code, "message": message, "severity": "error", "field_path": field_path}
    if details:
        issue["details"] = details
    return issue


__all__ = [
    "AGENT_CONFIG_DEFAULTS",
    "AGENT_CONFIG_KEYS",
    "AGENT_CONFIG_SCHEMA",
    "AgentConfig",
    "AgentConfigResult",
    "AgentConfigValidationError",
    "require_agent_config",
    "resolve_agent_config",
    "stable_agent_config_hash",
]
