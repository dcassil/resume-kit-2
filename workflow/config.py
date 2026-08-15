"""Validated workflow configuration resolution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


JsonObject = dict[str, Any]

WORKFLOW_CONFIG_VERSION = "workflow-config.v1"
WORKFLOW_KEYS = ("maxRenderOverflowIterations",)

DEFAULT_MAX_RENDER_OVERFLOW_ITERATIONS = 2


@dataclass(frozen=True)
class WorkflowConfig:
    max_render_overflow_iterations: int

    def to_dict(self) -> JsonObject:
        return {"maxRenderOverflowIterations": self.max_render_overflow_iterations}


@dataclass(frozen=True)
class WorkflowConfigResult:
    config: WorkflowConfig
    errors: list[JsonObject]
    warnings: list[JsonObject]

    @property
    def ok(self) -> bool:
        return not self.errors


def resolve_workflow_config(config: JsonObject | None) -> WorkflowConfigResult:
    """Resolve section-13 workflow config with defaults and typed validation."""

    raw = config if isinstance(config, dict) else {}
    errors: list[JsonObject] = []
    warnings: list[JsonObject] = []

    workflow = _workflow_payload(raw, errors)
    values: JsonObject = {}
    if isinstance(workflow, dict):
        values.update(workflow)
        _reject_unknown_workflow_keys(values, errors)

    max_iterations = DEFAULT_MAX_RENDER_OVERFLOW_ITERATIONS
    if "maxRenderOverflowIterations" in values:
        max_iterations = _non_negative_int_value(
            values["maxRenderOverflowIterations"],
            DEFAULT_MAX_RENDER_OVERFLOW_ITERATIONS,
            "workflow.maxRenderOverflowIterations",
            errors,
        )

    return WorkflowConfigResult(
        config=WorkflowConfig(max_render_overflow_iterations=max_iterations),
        errors=errors,
        warnings=warnings,
    )


def _workflow_payload(raw: JsonObject, errors: list[JsonObject]) -> JsonObject:
    if "workflow" not in raw:
        return {}
    workflow = raw.get("workflow")
    if not isinstance(workflow, dict):
        errors.append(_issue("invalid_workflow_config_type", "workflow must be an object.", "workflow"))
        return {}
    return workflow


def _reject_unknown_workflow_keys(values: JsonObject, errors: list[JsonObject]) -> None:
    allowed = set(WORKFLOW_KEYS)
    for key in sorted(set(values) - allowed):
        errors.append(
            _issue(
                "unknown_workflow_config_key",
                "Unknown workflow config key.",
                f"workflow.{key}",
                {"allowed": sorted(allowed)},
            )
        )


def _non_negative_int_value(value: Any, default: int, field_path: str, errors: list[JsonObject]) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        errors.append(_issue("invalid_workflow_config_value", "Workflow config value must be an integer.", field_path))
        return int(default)
    if value < 0:
        errors.append(_issue("invalid_workflow_config_value", "Workflow config value must be non-negative.", field_path))
        return int(default)
    return int(value)


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
