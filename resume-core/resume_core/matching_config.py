"""Validated matching configuration resolution for resume-core."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any


JsonObject = dict[str, Any]

MATCHING_CONFIG_VERSION = "matching-config.v1"
MATCHING_WEIGHT_KEYS = (
    "requiredSkills",
    "experience",
    "roleAlignment",
    "domainIndustry",
    "preferredSkills",
    "terminology",
)
MATCHING_KEYS = ("scoreAutoThreshold", "weights", "requireHardRequirementsResolved")
DEPRECATED_FLAT_KEYS = ("policy", "require_hard_resolution")

DEFAULT_SCORE_AUTO_THRESHOLD = 7.5
DEFAULT_REQUIRE_HARD_REQUIREMENTS_RESOLVED = False
DEFAULT_MATCHING_WEIGHTS: dict[str, float] = {
    "requiredSkills": 0.30,
    "experience": 0.25,
    "roleAlignment": 0.15,
    "domainIndustry": 0.10,
    "preferredSkills": 0.10,
    "terminology": 0.10,
}


@dataclass(frozen=True)
class MatchingConfig:
    score_auto_threshold: float
    weights: dict[str, float]
    require_hard_requirements_resolved: bool

    def to_dict(self) -> JsonObject:
        return {
            "scoreAutoThreshold": self.score_auto_threshold,
            "weights": copy.deepcopy(self.weights),
            "requireHardRequirementsResolved": self.require_hard_requirements_resolved,
        }


@dataclass(frozen=True)
class MatchingConfigResult:
    config: MatchingConfig
    errors: list[JsonObject]
    warnings: list[JsonObject]

    @property
    def ok(self) -> bool:
        return not self.errors


def resolve_matching_config(config: JsonObject | None) -> MatchingConfigResult:
    """Resolve section-13 matching config with defaults and flat-key migration."""

    raw = config if isinstance(config, dict) else {}
    errors: list[JsonObject] = []
    warnings: list[JsonObject] = []

    has_explicit_matching_namespace = "matching" in raw
    matching, reject_unknown_matching_keys = _matching_payload(raw, errors)
    values: JsonObject = {}
    if isinstance(matching, dict):
        values.update(matching)

    if reject_unknown_matching_keys:
        _reject_unknown_matching_keys(values, errors)

    root_flat_values = _deprecated_flat_values(raw, errors, warnings)
    nested_flat_values = _deprecated_flat_values(values, errors, warnings) if has_explicit_matching_namespace else []

    score_auto_threshold = _number_value(
        values.get("scoreAutoThreshold", DEFAULT_SCORE_AUTO_THRESHOLD),
        DEFAULT_SCORE_AUTO_THRESHOLD,
        "matching.scoreAutoThreshold",
        errors,
    )
    weights = _weights_value(values.get("weights"), errors)

    explicit_require = values.get("requireHardRequirementsResolved")
    require_hard_requirements_resolved = DEFAULT_REQUIRE_HARD_REQUIREMENTS_RESOLVED
    explicit_require_set = "requireHardRequirementsResolved" in values
    if explicit_require_set:
        require_hard_requirements_resolved = _bool_value(
            explicit_require,
            DEFAULT_REQUIRE_HARD_REQUIREMENTS_RESOLVED,
            "matching.requireHardRequirementsResolved",
            errors,
        )

    for source_key, mapped_value in [*root_flat_values, *nested_flat_values]:
        if explicit_require_set and mapped_value != require_hard_requirements_resolved:
            errors.append(
                _issue(
                    "conflicting_matching_config_key",
                    "Deprecated flat matching config conflicts with matching.requireHardRequirementsResolved.",
                    source_key,
                    {"target": "matching.requireHardRequirementsResolved"},
                )
            )
        elif not explicit_require_set:
            require_hard_requirements_resolved = require_hard_requirements_resolved or mapped_value

    return MatchingConfigResult(
        config=MatchingConfig(
            score_auto_threshold=score_auto_threshold,
            weights=weights,
            require_hard_requirements_resolved=require_hard_requirements_resolved,
        ),
        errors=errors,
        warnings=warnings,
    )


def _matching_payload(raw: JsonObject, errors: list[JsonObject]) -> tuple[JsonObject, bool]:
    if "matching" in raw:
        matching = raw.get("matching")
        if not isinstance(matching, dict):
            errors.append(_issue("invalid_matching_config_type", "matching must be an object.", "matching"))
            return {}, True
        return matching, True

    direct_values = {key: raw[key] for key in (*MATCHING_KEYS, *DEPRECATED_FLAT_KEYS) if key in raw}
    return direct_values, False


def _reject_unknown_matching_keys(values: JsonObject, errors: list[JsonObject]) -> None:
    allowed = {*MATCHING_KEYS, *DEPRECATED_FLAT_KEYS}
    for key in sorted(set(values) - allowed):
        errors.append(
            _issue(
                "unknown_matching_config_key",
                "Unknown matching config key.",
                f"matching.{key}",
                {"allowed": sorted(allowed)},
            )
        )


def _deprecated_flat_values(values: JsonObject, errors: list[JsonObject], warnings: list[JsonObject]) -> list[tuple[str, bool]]:
    mapped: list[tuple[str, bool]] = []
    if "policy" in values:
        warnings.append(
            _issue(
                "deprecated_matching_config_key",
                "policy is deprecated; use matching.requireHardRequirementsResolved.",
                "policy",
                {"target": "matching.requireHardRequirementsResolved"},
                severity="warning",
            )
        )
        mapped.append(("policy", values.get("policy") == "strict"))
    if "require_hard_resolution" in values:
        warnings.append(
            _issue(
                "deprecated_matching_config_key",
                "require_hard_resolution is deprecated; use matching.requireHardRequirementsResolved.",
                "require_hard_resolution",
                {"target": "matching.requireHardRequirementsResolved"},
                severity="warning",
            )
        )
        mapped.append(
            (
                "require_hard_resolution",
                _bool_value(values.get("require_hard_resolution"), False, "require_hard_resolution", errors),
            )
        )
    return mapped


def _weights_value(raw: Any, errors: list[JsonObject]) -> dict[str, float]:
    weights = copy.deepcopy(DEFAULT_MATCHING_WEIGHTS)
    if raw is None:
        return weights
    if not isinstance(raw, dict):
        errors.append(_issue("invalid_matching_config_type", "matching.weights must be an object.", "matching.weights"))
        return weights

    for key in sorted(set(raw) - set(MATCHING_WEIGHT_KEYS)):
        errors.append(
            _issue(
                "unknown_matching_config_key",
                "Unknown matching weight key.",
                f"matching.weights.{key}",
                {"allowed": list(MATCHING_WEIGHT_KEYS)},
            )
        )
    for key in MATCHING_WEIGHT_KEYS:
        if key in raw:
            weights[key] = _number_value(raw[key], weights[key], f"matching.weights.{key}", errors)
    return weights


def _number_value(value: Any, default: float, field_path: str, errors: list[JsonObject]) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        errors.append(_issue("invalid_matching_config_value", "Matching config value must be a number.", field_path))
        return float(default)
    return float(value)


def _bool_value(value: Any, default: bool, field_path: str, errors: list[JsonObject]) -> bool:
    if not isinstance(value, bool):
        errors.append(_issue("invalid_matching_config_value", "Matching config value must be a boolean.", field_path))
        return bool(default)
    return value


def _issue(
    code: str,
    message: str,
    field_path: str | None = None,
    details: JsonObject | None = None,
    *,
    severity: str = "error",
) -> JsonObject:
    issue: JsonObject = {"code": code, "message": message, "severity": severity}
    if field_path is not None:
        issue["field_path"] = field_path
    if details:
        issue["details"] = details
    return issue
