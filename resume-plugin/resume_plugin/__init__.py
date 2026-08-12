"""Public adapter surface for the resume plugin package."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


PLUGIN_VERSION = "0.1.0"
CONTRACT_VERSION = 1
CONFIG_HASH = "delegated-to-workflow"
PACKAGE_VERSIONS = {
    "resume-cli": "public-api",
    "workflow": "public-api",
    "resume-core": "public-api",
    "resume-render": "public-api",
    "career-mcp": "public-api",
}
SCHEMA_VERSIONS = {
    "plugin_surface": str(CONTRACT_VERSION),
    "workflow_dtos": "public-api",
    "report_dtos": "public-api",
}

_TOOL_DEFINITIONS = (
    {
        "name": "resume_ingest",
        "description": "Map a resume ingest request to the public ingest workflow.",
        "workflow_command": "resume ingest",
        "input_schema": {
            "type": "object",
            "properties": {
                "resume_path": {"type": "string"},
                "workspace": {"type": "string"},
            },
        },
    },
    {
        "name": "resume_run",
        "description": "Map a job tailoring request to the public run workflow.",
        "workflow_command": "resume run",
        "input_schema": {
            "type": "object",
            "properties": {
                "job_path": {"type": "string"},
                "workspace": {"type": "string"},
            },
        },
    },
    {
        "name": "resume_resolve",
        "description": "Capture a user answer for the public requirement resolution workflow.",
        "workflow_command": "resume resolve",
        "input_schema": {
            "type": "object",
            "properties": {
                "selected_requirement_ids": {"type": "array", "items": {"type": "string"}},
                "answer": {"type": "string"},
            },
        },
    },
    {
        "name": "resume_report",
        "description": "Display public workflow report, diff, export, and audit outputs.",
        "workflow_command": "resume report",
        "input_schema": {
            "type": "object",
            "properties": {
                "run_id": {"type": "string"},
                "workspace": {"type": "string"},
            },
        },
    },
)


def _copy_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _copy_sequence(value: Any) -> list[Any]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return list(value)
    return []


def _as_text(value: Any, fallback: str = "") -> str:
    if value is None:
        return fallback
    return str(value)


def _metadata() -> dict[str, Any]:
    return {
        "underlying_package_versions": dict(PACKAGE_VERSIONS),
        "schema_versions": dict(SCHEMA_VERSIONS),
        "config_hash": CONFIG_HASH,
    }


def _safe_fact_summary(fact_context: Any) -> list[dict[str, Any]]:
    context = _copy_mapping(fact_context)
    facts = _copy_sequence(context.get("facts"))
    summary: list[dict[str, Any]] = []
    for fact in facts:
        item = _copy_mapping(fact)
        if not item:
            continue
        summary.append(
            {
                key: item[key]
                for key in ("fact_id", "text", "label", "summary", "verification_state")
                if key in item
            }
        )
    return summary


def _operation_id(operation: Mapping[str, Any], index: int) -> str:
    return _as_text(operation.get("operation_id") or operation.get("id"), f"operation_{index + 1}")


def _operation_status(operation: Mapping[str, Any]) -> str:
    return _as_text(operation.get("status"), "pending").lower()


def getPluginManifest() -> dict[str, Any]:
    """Return host-visible metadata for the adapter."""

    return {
        "plugin_id": "resume-plugin",
        "plugin_version": PLUGIN_VERSION,
        "display_name": "Resume Plugin Adapter",
        "tools": [dict(tool) for tool in _TOOL_DEFINITIONS],
        "skills": [
            {
                "name": "resume-workflow-adapter",
                "description": "Routes host resume requests to public workflow commands and presents returned DTOs.",
            }
        ],
        "compatibility": {
            "contract_version": CONTRACT_VERSION,
            "adapter_only": True,
            "host_api": "tool-registration",
        },
        **_metadata(),
    }


def registerTools(host: Any) -> dict[str, Any]:
    """Register tool descriptors with a host when it exposes a registration hook."""

    registered_tools = [dict(tool) for tool in _TOOL_DEFINITIONS]
    warnings: list[str] = []
    register = getattr(host, "register_tool", None)
    if register is None:
        register = getattr(host, "add_tool", None)

    if callable(register):
        for tool in registered_tools:
            register(dict(tool))
    else:
        warnings.append("host did not expose a tool registration hook; returning descriptors only")

    workflow_mappings = {tool["name"]: tool["workflow_command"] for tool in registered_tools}
    return {
        "status": "ok",
        "registered_tools": registered_tools,
        "workflow_mappings": workflow_mappings,
        "warnings": warnings,
        "underlying_package_versions": dict(PACKAGE_VERSIONS),
    }


def mapConversationToWorkflow(message: str, context: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Map host text to the equivalent public workflow command."""

    context_data = _copy_mapping(context)
    selected_requirement_ids = _copy_sequence(context_data.get("selected_requirement_ids"))
    normalized = message.lower()

    command = "resume report"
    scope = "report"
    confirmation_required = False
    arguments: dict[str, Any] = {
        "message": message,
        "context": {
            key: context_data[key]
            for key in ("workspace", "resume_path", "job_path", "run_id")
            if key in context_data
        },
    }

    if any(token in normalized for token in ("ingest", "import", "parse resume", "load resume")):
        command = "resume ingest"
        scope = "resume_ingest"
    elif any(token in normalized for token in ("tailor", "job", "match", "optimize", "run")):
        command = "resume run"
        scope = "job_tailoring"
    elif selected_requirement_ids or normalized.startswith(("yes", "no")):
        command = "resume resolve"
        scope = "requirement_confirmation"
        arguments["answer"] = message
    elif any(token in normalized for token in ("diff", "report", "audit", "export", "render")):
        command = "resume report"
        scope = "presentation"

    return {
        "status": "ok",
        "workflow_command": command,
        "arguments": arguments,
        "confirmation_required": confirmation_required,
        "selected_requirement_ids": selected_requirement_ids,
        "scope": scope,
        "warnings": [],
    }


def presentConfirmationRequest(request: Mapping[str, Any]) -> dict[str, Any]:
    """Format a code-selected confirmation request for a host conversation."""

    request_data = _copy_mapping(request)
    selected_requirement_ids = _copy_sequence(request_data.get("selected_requirement_ids"))
    prompt = _as_text(request_data.get("question"), "Please confirm the selected requirement.")
    fact_context_summary = _safe_fact_summary(request_data.get("fact_context"))

    return {
        "status": "ok",
        "selected_requirement_ids": selected_requirement_ids,
        "prompt": prompt,
        "fact_context_summary": fact_context_summary,
        "sensitive_fields_omitted": True,
    }


def presentDiff(operations: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Format workflow operation records for display."""

    applied_operations: list[dict[str, Any]] = []
    rejected_operations: list[dict[str, Any]] = []
    rejection_reasons: dict[str, str] = {}

    for index, raw_operation in enumerate(_copy_sequence(operations)):
        operation = _copy_mapping(raw_operation)
        status = _operation_status(operation)
        operation_id = _operation_id(operation, index)
        display_operation = {
            "operation_id": operation_id,
            "status": status,
            "target": operation.get("target") or operation.get("path"),
            "before": operation.get("before"),
            "after": operation.get("after"),
            "reason": operation.get("reason"),
        }
        if status == "rejected":
            rejected_operations.append(display_operation)
            rejection_reasons[operation_id] = _as_text(operation.get("reason"), "rejected by workflow")
        else:
            applied_operations.append(display_operation)

    display = {
        "applied_count": len(applied_operations),
        "rejected_count": len(rejected_operations),
    }
    return {
        "status": "ok",
        "applied_operations": applied_operations,
        "rejected_operations": rejected_operations,
        "rejection_reasons": rejection_reasons,
        "display": display,
    }


def presentReport(report: Mapping[str, Any]) -> dict[str, Any]:
    """Format public workflow reports for host display."""

    report_data = _copy_mapping(report)
    return {
        "status": "ok",
        "resolved_requirements": _copy_sequence(report_data.get("resolved_requirements")),
        "missing_requirements": _copy_sequence(report_data.get("missing_requirements")),
        "preferred_requirements": _copy_sequence(report_data.get("preferred_requirements")),
        "unresolved_requirements": _copy_sequence(report_data.get("unresolved_requirements")),
        "render_results": _copy_sequence(report_data.get("render_results")),
        "warnings": _copy_sequence(report_data.get("warnings")),
        "plugin_version": PLUGIN_VERSION,
        **_metadata(),
    }


def presentAuditSummary(audit: Mapping[str, Any]) -> dict[str, Any]:
    """Format an audit DTO without expanding sensitive source data."""

    audit_data = _copy_mapping(audit)
    return {
        "status": "ok",
        "run_identity": audit_data.get("run_identity"),
        "config_hash": audit_data.get("config_hash", CONFIG_HASH),
        "underlying_package_versions": _copy_mapping(
            audit_data.get("underlying_package_versions") or PACKAGE_VERSIONS
        ),
        "schema_versions": _copy_mapping(audit_data.get("schema_versions") or SCHEMA_VERSIONS),
        "fact_changes": _copy_sequence(audit_data.get("fact_changes")),
        "operations": _copy_sequence(audit_data.get("operations")),
        "validations": _copy_sequence(audit_data.get("validations")),
        "outputs": _copy_sequence(audit_data.get("outputs")),
        "sensitive_fields_omitted": True,
        "plugin_version": PLUGIN_VERSION,
    }


__all__ = [
    "getPluginManifest",
    "registerTools",
    "mapConversationToWorkflow",
    "presentConfirmationRequest",
    "presentDiff",
    "presentReport",
    "presentAuditSummary",
]
