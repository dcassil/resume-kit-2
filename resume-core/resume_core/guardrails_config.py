"""Validated guardrails configuration resolution for resume-core."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .matching_config import _issue


JsonObject = dict[str, Any]

GUARDRAILS_CONFIG_VERSION = "guardrails-config.v1"
GUARDRAILS_KEYS = ("allow_inferred_facts",)
REMOVED_FLAT_KEYS = ("allow_inferred_facts",)

DEFAULT_ALLOW_INFERRED_FACTS = False


@dataclass(frozen=True)
class GuardrailsConfig:
    allow_inferred: bool

    def to_dict(self) -> JsonObject:
        return {"allow_inferred_facts": self.allow_inferred}


@dataclass(frozen=True)
class GuardrailsConfigResult:
    config: GuardrailsConfig
    errors: list[JsonObject]
    warnings: list[JsonObject]

    @property
    def ok(self) -> bool:
        return not self.errors


def resolve_guardrails_config(config: JsonObject | None) -> GuardrailsConfigResult:
    """Resolve section-13 guardrails config with defaults and typed validation."""

    raw = config if isinstance(config, dict) else {}
    errors: list[JsonObject] = []
    warnings: list[JsonObject] = []

    guardrails = _guardrails_payload(raw, errors)
    values: JsonObject = {}
    if isinstance(guardrails, dict):
        values.update(guardrails)
        _reject_unknown_guardrails_keys(values, errors)

    _reject_removed_flat_keys(raw, errors)

    allow_inferred = DEFAULT_ALLOW_INFERRED_FACTS
    if "allow_inferred_facts" in values:
        allow_inferred = _bool_value(
            values["allow_inferred_facts"],
            DEFAULT_ALLOW_INFERRED_FACTS,
            "guardrails.allow_inferred_facts",
            errors,
        )

    return GuardrailsConfigResult(
        config=GuardrailsConfig(allow_inferred=allow_inferred),
        errors=errors,
        warnings=warnings,
    )


def _guardrails_payload(raw: JsonObject, errors: list[JsonObject]) -> JsonObject:
    if "guardrails" not in raw:
        return {}
    guardrails = raw.get("guardrails")
    if not isinstance(guardrails, dict):
        errors.append(_issue("invalid_guardrails_config_type", "guardrails must be an object.", "guardrails"))
        return {}
    return guardrails


def _reject_unknown_guardrails_keys(values: JsonObject, errors: list[JsonObject]) -> None:
    allowed = set(GUARDRAILS_KEYS)
    for key in sorted(set(values) - allowed):
        errors.append(
            _issue(
                "unknown_guardrails_config_key",
                "Unknown guardrails config key.",
                f"guardrails.{key}",
                {"allowed": sorted(allowed)},
            )
        )


def _reject_removed_flat_keys(raw: JsonObject, errors: list[JsonObject]) -> None:
    allowed = ["guardrails"]
    for key in REMOVED_FLAT_KEYS:
        if key in raw:
            errors.append(_issue("unknown_guardrails_config_key", "Unknown guardrails config key.", key, {"allowed": allowed}))


def _bool_value(value: Any, default: bool, field_path: str, errors: list[JsonObject]) -> bool:
    if not isinstance(value, bool):
        errors.append(_issue("invalid_guardrails_config_value", "Guardrails config value must be a boolean.", field_path))
        return bool(default)
    return value
