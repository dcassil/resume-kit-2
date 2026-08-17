"""Private Anthropic Claude live proposal adapter for resume-agent.

The official `anthropic` package is intentionally an optional live-path-only
dependency. It is not imported at package import time and is not listed in the
project install requirements; callers that opt into live execution must install
it in their environment and provide ANTHROPIC_API_KEY.

Structured output uses `output_config={"format": {"type": "json_schema",
"schema": ...}}`. Temperature 0 is attached for the default
`json_schema` mode only. The shared adapter validator still revalidates the
parsed payload before any result leaves this adapter.
"""

from __future__ import annotations

import copy
import importlib
import json
from typing import Any, Mapping

from ._adapters import (
    AdapterCompletion,
    AdapterProviderError,
    AdapterRefusalError,
    AdapterRequest,
    ValidatingModelAdapter,
)
from ._agent_config import DEFAULT_AGENT_SCHEMA_MODE, AgentConfig
from ._call_audit import CallAuditSink
from ._schema_validation import JsonObject, JsonSchemaRegistry


DEFAULT_MAX_TOKENS = 4096


class AnthropicClaudeAdapter(ValidatingModelAdapter):
    def __init__(
        self,
        *,
        adapter_id: str,
        adapter_version: str,
        agent_config: AgentConfig,
        api_key: str,
        output_schemas: JsonSchemaRegistry | None = None,
        call_audit_sink: CallAuditSink | None = None,
    ) -> None:
        if not isinstance(agent_config, AgentConfig):
            raise TypeError("agent_config must be a validated AgentConfig.")
        if not api_key.strip():
            raise AdapterProviderError(
                "Anthropic live adapter requires ANTHROPIC_API_KEY.",
                details={"reason": "live_adapter_missing_api_key", "provider": "anthropic"},
            )

        self._anthropic = _load_anthropic_module()
        self._client = self._anthropic.Anthropic(
            api_key=api_key,
            timeout=agent_config.timeout_ms / 1000,
            max_retries=agent_config.max_retries,
        )
        self._agent_config = agent_config
        runtime_config: JsonObject = {
            "provider": "anthropic",
            "schema_mode": agent_config.schema_mode,
            "timeout_ms": agent_config.timeout_ms,
            "max_retries": agent_config.max_retries,
            "cost_ceiling": agent_config.cost_ceiling,
            "max_tokens": DEFAULT_MAX_TOKENS,
        }
        if agent_config.schema_mode == DEFAULT_AGENT_SCHEMA_MODE:
            runtime_config["temperature"] = 0
        super().__init__(
            adapter_id=adapter_id,
            adapter_version=adapter_version,
            model_id=agent_config.model,
            agent_config=agent_config,
            runtime_config=runtime_config,
            output_schemas=output_schemas,
            call_audit_sink=call_audit_sink,
        )

    def _complete_unchecked(self, request: AdapterRequest) -> AdapterCompletion:
        retries = 0
        usage: JsonObject = {}
        try:
            response = self._client.messages.create(**self._request_params(request))
            retries = _retry_count(response)
            usage = _usage_counts(response)
            if getattr(response, "stop_reason", None) == "refusal":
                raise _with_metadata(AdapterRefusalError("Anthropic refused the request."), retries, usage)
            return AdapterCompletion(payload=_parsed_payload(response), retries=retries, usage=usage)
        except Exception as exc:  # noqa: BLE001 - provider SDK failures must be normalized by class.
            raise _map_anthropic_exception(self._anthropic, exc, retries, usage) from exc

    def _request_params(self, request: AdapterRequest) -> JsonObject:
        schema = copy.deepcopy(self.output_schemas.get(request.output_schema_id, {"type": "object"}))
        params: JsonObject = {
            "model": self._agent_config.model,
            "max_tokens": DEFAULT_MAX_TOKENS,
            "messages": [
                {
                    "role": "user",
                    "content": _user_content(request),
                }
            ],
            "output_config": {
                "format": {
                    "type": "json_schema",
                    "schema": schema,
                }
            },
        }
        if self._agent_config.schema_mode == DEFAULT_AGENT_SCHEMA_MODE:
            params["temperature"] = 0
        return params


def _load_anthropic_module() -> Any:
    try:
        return importlib.import_module("anthropic")
    except ModuleNotFoundError as exc:
        raise AdapterProviderError(
            "Anthropic SDK is not installed. Install the optional live dependency `anthropic` before opt-in use.",
            details={"reason": "anthropic_sdk_missing", "optional_dependency": "anthropic"},
        ) from exc


def _user_content(request: AdapterRequest) -> str:
    payload = json.dumps(request.input_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return f"{request.prompt}\n\nRespond only with JSON matching schema {request.output_schema_id}.\nInput JSON:\n{payload}"


def _parsed_payload(response: Any) -> Any:
    direct = _json_value(getattr(response, "output", None)) or _json_value(getattr(response, "parsed", None))
    if direct is not None:
        return direct

    if isinstance(response, Mapping):
        direct = _json_value(response.get("output")) or _json_value(response.get("parsed"))
        if direct is not None:
            return direct
        content = response.get("content")
    else:
        content = getattr(response, "content", None)

    if isinstance(content, list):
        for block in content:
            block_payload = _payload_from_block(block)
            if block_payload is not None:
                return block_payload

    raise AdapterProviderError(
        "Anthropic response did not contain a JSON payload.",
        details={"reason": "anthropic_missing_structured_payload"},
    )


def _payload_from_block(block: Any) -> Any | None:
    for field_name in ("input", "json", "parsed"):
        value = block.get(field_name) if isinstance(block, Mapping) else getattr(block, field_name, None)
        mapped = _json_value(value)
        if mapped is not None:
            return mapped

    text = block.get("text") if isinstance(block, Mapping) else getattr(block, "text", None)
    if isinstance(text, str):
        try:
            loaded = json.loads(text)
        except json.JSONDecodeError as exc:
            raise AdapterProviderError(
                "Anthropic response text was not valid JSON.",
                details={"reason": "anthropic_invalid_json_payload", "line": exc.lineno, "column": exc.colno},
            ) from exc
        mapped = _json_value(loaded)
        if mapped is not None:
            return mapped
    return None


def _json_value(value: Any) -> Any | None:
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, list):
        return list(value)
    return None


def _map_anthropic_exception(anthropic: Any, exc: Exception, retries: int, usage: JsonObject) -> Exception:
    if isinstance(exc, (AdapterProviderError, AdapterRefusalError, TimeoutError)):
        return exc

    timeout_cls = getattr(anthropic, "APITimeoutError", ())
    rate_limit_cls = getattr(anthropic, "RateLimitError", ())
    status_cls = getattr(anthropic, "APIStatusError", ())
    connection_cls = getattr(anthropic, "APIConnectionError", ())

    if timeout_cls and isinstance(exc, timeout_cls):
        return _with_metadata(TimeoutError("Anthropic request timed out."), retries, usage)

    if rate_limit_cls and isinstance(exc, rate_limit_cls):
        return _with_metadata(_provider_error("Anthropic rate limit exceeded.", exc), retries, usage)

    if connection_cls and isinstance(exc, connection_cls):
        return _with_metadata(_provider_error("Anthropic connection failed.", exc), retries, usage)

    if status_cls and isinstance(exc, status_cls):
        status_code = getattr(exc, "status_code", None)
        if isinstance(status_code, int) and 500 <= status_code <= 599:
            return _with_metadata(_provider_error("Anthropic server error.", exc), retries, usage)
        return _with_metadata(_provider_error("Anthropic API status error.", exc), retries, usage)

    return _with_metadata(_provider_error("Anthropic provider failed.", exc), retries, usage)


def _provider_error(message: str, exc: Exception) -> AdapterProviderError:
    details: JsonObject = {
        "reason": "anthropic_provider_error",
        "exception_class": exc.__class__.__name__,
    }
    status_code = getattr(exc, "status_code", None)
    if isinstance(status_code, int):
        details["status_code"] = status_code
    return AdapterProviderError(message, details=details)


def _retry_count(response: Any) -> int:
    value = getattr(response, "retries", 0)
    if isinstance(value, int) and value >= 0:
        return value
    metadata = getattr(response, "metadata", None)
    retry_value = metadata.get("retries") if isinstance(metadata, Mapping) else None
    return retry_value if isinstance(retry_value, int) and retry_value >= 0 else 0


def _usage_counts(response: Any) -> JsonObject:
    usage = getattr(response, "usage", None)
    if isinstance(usage, Mapping):
        return dict(usage)
    if usage is not None:
        counts: JsonObject = {}
        for field_name in ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"):
            value = getattr(usage, field_name, None)
            if isinstance(value, int):
                counts[field_name] = value
        return counts
    return {}


def _with_metadata(exc: Exception, retries: int, usage: JsonObject) -> Exception:
    exc.retries = retries
    exc.usage = dict(usage)
    return exc


__all__ = ["AnthropicClaudeAdapter"]
