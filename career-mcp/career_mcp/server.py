"""Stdio JSON-RPC MCP transport for career-mcp.

RKIT-T-0111 records the integration decision to hand-roll newline-delimited
JSON-RPC 2.0 framing with the Python standard library instead of adding the
MCP SDK. The runtime dependency set is intentionally empty, and the smoke gate
installs this repo into a fresh environment where a new third-party dependency
would require network access. RKIT-A-0002 and RKIT-I-0014 explicitly allow this
choice when the dependency is unacceptable at integration time.

This module is only the transport shell. It owns request framing, MCP method
binding, and response serialization; tool behavior stays in the injected
adapter created by create_career_mcp. The v1 transport is single-user/local and
runs the async adapter call with asyncio.run once per tools/call request.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import sys
from typing import Any, TextIO


JsonObject = dict[str, Any]

JSONRPC_VERSION = "2.0"
MCP_PROTOCOL_VERSION = "2024-11-05"

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601


class CareerMcpJsonRpcServer:
    """Pure JSON-RPC request handler over an injected career-mcp adapter."""

    def __init__(self, adapter: Any) -> None:
        self._adapter = adapter

    def handle_request(self, request: JsonObject) -> JsonObject | None:
        request_id = request.get("id")
        if not _is_valid_request_object(request):
            return _error_response(request_id, INVALID_REQUEST, "Invalid Request")

        method = request["method"]
        if "id" not in request:
            return None
        if method == "initialize":
            return _success_response(request_id, self._initialize_result(request.get("params")))
        if method == "notifications/initialized":
            return None
        if method == "tools/list":
            return _success_response(request_id, {"tools": self._list_tools()})
        if method == "tools/call":
            params = request.get("params", {})
            if not isinstance(params, dict):
                return _error_response(request_id, INVALID_REQUEST, "Invalid Request")
            return self._handle_tools_call(request_id, params)
        return _error_response(request_id, METHOD_NOT_FOUND, "Method not found")

    def _initialize_result(self, params: Any) -> JsonObject:
        requested = params.get("protocolVersion") if isinstance(params, dict) else None
        protocol_version = requested if isinstance(requested, str) and requested else MCP_PROTOCOL_VERSION
        return {
            "protocolVersion": protocol_version,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "career-mcp", "version": "0.1.0"},
        }

    def _list_tools(self) -> list[JsonObject]:
        tools = self._adapter.list_tools()
        if inspect.isawaitable(tools):
            tools = asyncio.run(tools)
        return [
            {
                "name": tool["name"],
                "description": tool["description"],
                "inputSchema": tool["input_schema"],
            }
            for tool in tools
        ]

    def _handle_tools_call(self, request_id: Any, params: JsonObject) -> JsonObject:
        name = params.get("name")
        arguments = params.get("arguments", {})
        if not isinstance(name, str) or not isinstance(arguments, dict):
            return _error_response(request_id, INVALID_REQUEST, "Invalid Request")
        envelope = asyncio.run(self._adapter.call_tool(name, arguments))
        envelope_text = serialize_tool_envelope(envelope)
        return _success_response(
            request_id,
            {
                "content": [{"type": "text", "text": envelope_text}],
                "isError": envelope.get("status") != "ok",
            },
        )


def handle_json_rpc_line(server: CareerMcpJsonRpcServer, line: str) -> JsonObject | None:
    try:
        request = json.loads(line)
    except json.JSONDecodeError:
        return _error_response(None, PARSE_ERROR, "Parse error")
    if not isinstance(request, dict):
        return _error_response(None, INVALID_REQUEST, "Invalid Request")
    return server.handle_request(request)


def run_stdio_server(
    adapter: Any,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
) -> int:
    input_stream = stdin if stdin is not None else sys.stdin
    output_stream = stdout if stdout is not None else sys.stdout
    server = CareerMcpJsonRpcServer(adapter)
    for line in input_stream:
        response = handle_json_rpc_line(server, line)
        if response is None:
            continue
        output_stream.write(json.dumps(response, separators=(",", ":"), ensure_ascii=False) + "\n")
        output_stream.flush()
    return 0


def serialize_tool_envelope(envelope: JsonObject) -> str:
    return json.dumps(envelope, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def close_store(store: Any) -> None:
    close = getattr(store, "close", None)
    if callable(close):
        close()


def _is_valid_request_object(request: JsonObject) -> bool:
    return request.get("jsonrpc") == JSONRPC_VERSION and isinstance(request.get("method"), str)


def _success_response(request_id: Any, result: JsonObject) -> JsonObject:
    return {"jsonrpc": JSONRPC_VERSION, "id": request_id, "result": result}


def _error_response(request_id: Any, code: int, message: str) -> JsonObject:
    return {"jsonrpc": JSONRPC_VERSION, "id": request_id, "error": {"code": code, "message": message}}


__all__ = [
    "CareerMcpJsonRpcServer",
    "INVALID_REQUEST",
    "METHOD_NOT_FOUND",
    "PARSE_ERROR",
    "close_store",
    "handle_json_rpc_line",
    "run_stdio_server",
    "serialize_tool_envelope",
]
