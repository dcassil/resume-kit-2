"""Provider-neutral proposal adapter DTOs, typed failures, and live construction guard."""

from __future__ import annotations

import copy
import os
from dataclasses import dataclass, field
from typing import Any, Literal, Mapping, Protocol

from ._agent_config import AgentConfig, resolve_agent_config
from ._schema_validation import JsonObject, JsonSchemaRegistry, validate_schema_id


AdapterFailureType = Literal["timeout", "schema_invalid", "refused", "provider_error"]
ADAPTER_FAILURE_TYPES: tuple[str, ...] = ("timeout", "schema_invalid", "refused", "provider_error")


@dataclass(frozen=True)
class AdapterRequest:
    prompt_template_id: str
    prompt: str
    input_payload: JsonObject
    output_schema_id: str


@dataclass(frozen=True)
class AdapterCompletion:
    payload: JsonObject
    retries: int = 0
    usage: JsonObject = field(default_factory=dict)


@dataclass(frozen=True)
class AdapterFailure:
    type: AdapterFailureType
    message: str
    violations: list[JsonObject] = field(default_factory=list)
    details: JsonObject = field(default_factory=dict)

    def to_error(self) -> JsonObject:
        error: JsonObject = {"type": self.type, "message": self.message}
        if self.violations:
            error["violations"] = copy.deepcopy(self.violations)
        if self.details:
            error["details"] = copy.deepcopy(self.details)
        return error


@dataclass(frozen=True)
class AdapterResult:
    status: Literal["ok", "error"]
    adapter_id: str
    adapter_version: str
    model_id: str
    runtime_config: JsonObject
    retries: int
    usage: JsonObject
    payload: JsonObject | None = None
    error: AdapterFailure | None = None

    @classmethod
    def ok(
        cls,
        *,
        payload: JsonObject,
        adapter_id: str,
        adapter_version: str,
        model_id: str,
        runtime_config: Mapping[str, Any],
        retries: int,
        usage: Mapping[str, Any],
    ) -> AdapterResult:
        return cls(
            status="ok",
            payload=copy.deepcopy(payload),
            error=None,
            adapter_id=adapter_id,
            adapter_version=adapter_version,
            model_id=model_id,
            runtime_config=dict(runtime_config),
            retries=retries,
            usage=dict(usage),
        )

    @classmethod
    def failed(
        cls,
        *,
        error: AdapterFailure,
        adapter_id: str,
        adapter_version: str,
        model_id: str,
        runtime_config: Mapping[str, Any],
        retries: int,
        usage: Mapping[str, Any],
    ) -> AdapterResult:
        return cls(
            status="error",
            payload=None,
            error=error,
            adapter_id=adapter_id,
            adapter_version=adapter_version,
            model_id=model_id,
            runtime_config=dict(runtime_config),
            retries=retries,
            usage=dict(usage),
        )

    def to_dict(self) -> JsonObject:
        result: JsonObject = {
            "status": self.status,
            "adapter_id": self.adapter_id,
            "adapter_version": self.adapter_version,
            "model_id": self.model_id,
            "runtime_config": copy.deepcopy(self.runtime_config),
            "retries": self.retries,
            "usage": copy.deepcopy(self.usage),
        }
        if self.status == "ok":
            result["payload"] = copy.deepcopy(self.payload)
        elif self.error is not None:
            result["error"] = self.error.to_error()
        return result


class AdapterSchemaInvalidError(Exception):
    def __init__(self, violations: list[JsonObject]):
        super().__init__("Adapter output failed schema checks.")
        self.violations = copy.deepcopy(violations)


class AdapterRefusalError(Exception):
    pass


class AdapterProviderError(Exception):
    def __init__(self, message: str = "", *, details: Mapping[str, Any] | None = None):
        super().__init__(message)
        self.details = dict(details or {})


class LiveAdapterConstructionBlockedError(AdapterProviderError):
    pass


class ModelAdapter(Protocol):
    def complete(self, request: AdapterRequest) -> AdapterResult:
        """Return either a schema-checked payload or a typed failure result."""


class ValidatingModelAdapter:
    def __init__(
        self,
        *,
        adapter_id: str,
        adapter_version: str,
        model_id: str,
        agent_config: AgentConfig | None = None,
        runtime_config: Mapping[str, Any] | None = None,
        output_schemas: JsonSchemaRegistry | None = None,
    ) -> None:
        self.adapter_id = adapter_id
        self.adapter_version = adapter_version
        self.model_id = model_id
        base_runtime_config = agent_config.to_dict() if agent_config is not None else {}
        base_runtime_config.update(runtime_config or {})
        self.runtime_config = base_runtime_config
        self.output_schemas = dict(output_schemas or {})

    def complete(self, request: AdapterRequest) -> AdapterResult:
        retries = 0
        usage: JsonObject = {}
        try:
            completion = self._normalize_completion(self._complete_unchecked(request))
            retries = completion.retries
            usage = completion.usage
            violations = validate_schema_id(completion.payload, request.output_schema_id, self.output_schemas)
            if violations:
                raise AdapterSchemaInvalidError(violations)
            return AdapterResult.ok(
                payload=completion.payload,
                adapter_id=self.adapter_id,
                adapter_version=self.adapter_version,
                model_id=self.model_id,
                runtime_config=self.runtime_config,
                retries=retries,
                usage=usage,
            )
        except Exception as exc:  # noqa: BLE001 - adapter seam must normalize every failure.
            return AdapterResult.failed(
                error=_failure_from_exception(exc),
                adapter_id=self.adapter_id,
                adapter_version=self.adapter_version,
                model_id=self.model_id,
                runtime_config=self.runtime_config,
                retries=_retry_count(exc, retries),
                usage=_usage_counts(exc, usage),
            )

    def _complete_unchecked(self, request: AdapterRequest) -> AdapterCompletion | JsonObject:
        raise NotImplementedError

    def _normalize_completion(self, value: AdapterCompletion | JsonObject) -> AdapterCompletion:
        if isinstance(value, AdapterCompletion):
            return value
        if isinstance(value, dict):
            return AdapterCompletion(payload=value)
        return AdapterCompletion(payload={"value": value})


class _PlaceholderLiveModelAdapter(ValidatingModelAdapter):
    def __init__(
        self,
        *,
        adapter_id: str = "resume-agent-live-placeholder",
        adapter_version: str = "0.0.0",
        agent_config: AgentConfig | None = None,
        output_schemas: JsonSchemaRegistry | None = None,
    ) -> None:
        resolved_agent_config = agent_config or resolve_agent_config({}).config
        super().__init__(
            adapter_id=adapter_id,
            adapter_version=adapter_version,
            model_id=resolved_agent_config.model,
            agent_config=resolved_agent_config,
            runtime_config={"live_adapter_status": "not_implemented"},
            output_schemas=output_schemas,
        )

    def _complete_unchecked(self, _request: AdapterRequest) -> AdapterCompletion:
        raise AdapterProviderError("Live resume-agent adapter is not implemented yet.")


def create_live_model_adapter(
    *,
    env: Mapping[str, str] | None = None,
    adapter_id: str = "resume-agent-live-placeholder",
    adapter_version: str = "0.0.0",
    agent_config: AgentConfig | None = None,
    output_schemas: JsonSchemaRegistry | None = None,
) -> ModelAdapter:
    """Construct the future live adapter only when explicitly opted in.

    Official gates are safe by default: absent RESUME_AGENT_ALLOW_LIVE=1, live
    construction is blocked. RESUME_AGENT_GATE_PROFILE=1 always blocks live
    construction so protected gate scripts do not need parameter plumbing.
    """

    environment = env or os.environ
    if environment.get("RESUME_AGENT_GATE_PROFILE") == "1" or environment.get("RESUME_AGENT_ALLOW_LIVE") != "1":
        raise LiveAdapterConstructionBlockedError(
            "Live resume-agent adapter construction is blocked. Set RESUME_AGENT_ALLOW_LIVE=1 outside "
            "RESUME_AGENT_GATE_PROFILE=1 to opt in.",
            details={
                "reason": "live_adapter_requires_explicit_opt_in",
                "allow_env": "RESUME_AGENT_ALLOW_LIVE",
                "gate_env": "RESUME_AGENT_GATE_PROFILE",
            },
        )
    if agent_config is not None and not isinstance(agent_config, AgentConfig):
        raise TypeError("agent_config must be a validated AgentConfig.")
    return _PlaceholderLiveModelAdapter(
        adapter_id=adapter_id,
        adapter_version=adapter_version,
        agent_config=agent_config or resolve_agent_config({}).config,
        output_schemas=output_schemas,
    )


def _failure_from_exception(exc: Exception) -> AdapterFailure:
    if isinstance(exc, AdapterSchemaInvalidError):
        return AdapterFailure(
            type="schema_invalid",
            message=str(exc),
            violations=copy.deepcopy(exc.violations),
        )
    if isinstance(exc, TimeoutError):
        return AdapterFailure(type="timeout", message=str(exc) or "Adapter call timed out.")
    if isinstance(exc, AdapterRefusalError):
        return AdapterFailure(type="refused", message=str(exc) or "Adapter refused the request.")
    if isinstance(exc, AdapterProviderError):
        return AdapterFailure(
            type="provider_error",
            message=str(exc) or "Adapter provider failed.",
            details=copy.deepcopy(exc.details),
        )
    return AdapterFailure(type="provider_error", message=str(exc) or exc.__class__.__name__)


def _retry_count(exc: Exception, default: int) -> int:
    value = getattr(exc, "retries", default)
    return value if isinstance(value, int) and value >= 0 else default


def _usage_counts(exc: Exception, default: JsonObject) -> JsonObject:
    value = getattr(exc, "usage", default)
    return dict(value) if isinstance(value, dict) else dict(default)


__all__ = [
    "ADAPTER_FAILURE_TYPES",
    "AdapterCompletion",
    "AdapterFailure",
    "AdapterFailureType",
    "AdapterProviderError",
    "AdapterRefusalError",
    "AdapterRequest",
    "AdapterResult",
    "AdapterSchemaInvalidError",
    "LiveAdapterConstructionBlockedError",
    "ModelAdapter",
    "ValidatingModelAdapter",
    "create_live_model_adapter",
]
