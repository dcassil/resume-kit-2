"""Contract tests for the career-mcp stdio JSON-RPC MCP server."""

from __future__ import annotations

import asyncio
import io
import json
import unittest
from pathlib import Path
from typing import Any

import career_mcp
import career_mcp.__main__ as career_mcp_main
from career_mcp.server import (
    INVALID_REQUEST,
    METHOD_NOT_FOUND,
    PARSE_ERROR,
    CareerMcpJsonRpcServer,
    handle_json_rpc_line,
    serialize_tool_envelope,
)


ROOT = Path(__file__).resolve().parents[2]
SURFACE = json.loads((ROOT / "career-mcp" / "career_mcp" / "tool_surface.json").read_text(encoding="utf-8"))


class SimpleStore:
    def __init__(self) -> None:
        self.closed = False
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def close(self) -> None:
        self.closed = True

    def searchFacts(
        self,
        query: str,
        filters: dict[str, Any] | None = None,
        limit: int | None = None,
        include_evidence: bool = False,
    ) -> dict[str, Any]:
        self.calls.append(
            (
                "searchFacts",
                {"query": query, "filters": filters, "limit": limit, "include_evidence": include_evidence},
            )
        )
        return {
            "status": "ok",
            "facts": [
                {
                    "fact_id": "fact_react",
                    "type": "skill",
                    "text": "React",
                    "verification_state": "source_stated",
                    "evidence": [{"source": "resume", "text": "React"}],
                }
            ],
        }

    def upsertFact(
        self,
        fact: dict[str, Any],
        evidence: dict[str, Any] | None,
        source: str,
        policy: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.calls.append(("upsertFact", {"fact": fact, "evidence": evidence, "source": source, "policy": policy}))
        return {
            "status": "created",
            "mutation_status": "created",
            "fact_id": "fact_new",
            "verification_state": "unknown",
            "conflicts": [],
            "confirmation_required": False,
            "audit": {"operation": "upsertFact", "mutated": True},
        }


def response_envelope(response: dict[str, Any]) -> dict[str, Any]:
    return json.loads(response["result"]["content"][0]["text"])


class CareerMcpServerProtocolContractTests(unittest.TestCase):
    def make_server(self) -> tuple[SimpleStore, Any, CareerMcpJsonRpcServer]:
        store = SimpleStore()
        adapter = career_mcp.create_career_mcp(store=store)
        return store, adapter, CareerMcpJsonRpcServer(adapter)

    def test_initialize_advertises_tools_capability(self):
        _store, _adapter, server = self.make_server()

        response = server.handle_request(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05"}}
        )

        self.assertEqual(response["result"]["protocolVersion"], "2024-11-05")
        self.assertEqual(response["result"]["capabilities"], {"tools": {}})
        self.assertEqual(response["result"]["serverInfo"]["name"], "career-mcp")

    def test_initialized_notification_is_accepted_without_response(self):
        _store, _adapter, server = self.make_server()

        response = server.handle_request({"jsonrpc": "2.0", "method": "notifications/initialized"})

        self.assertIsNone(response)

    def test_tools_list_maps_canonical_manifest_without_mutating_it(self):
        _store, _adapter, server = self.make_server()
        before = json.loads(json.dumps(SURFACE, sort_keys=True))

        response = server.handle_request({"jsonrpc": "2.0", "id": "tools", "method": "tools/list"})
        listed = response["result"]["tools"]

        self.assertEqual(json.loads(json.dumps(SURFACE, sort_keys=True)), before)
        self.assertEqual([tool["name"] for tool in listed], [tool["name"] for tool in SURFACE["tools"]])
        for listed_tool, manifest_tool in zip(listed, SURFACE["tools"], strict=True):
            self.assertEqual(listed_tool["description"], manifest_tool["description"])
            self.assertEqual(listed_tool["inputSchema"], manifest_tool["input_schema"])
            self.assertNotIn("input_schema", listed_tool)

    def test_tools_call_content_byte_equals_direct_adapter_envelope(self):
        _store, adapter, server = self.make_server()
        arguments = {"query": "React", "limit": 5}
        direct = asyncio.run(adapter.call_tool("career.search_facts", arguments))

        response = server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": "call",
                "method": "tools/call",
                "params": {"name": "career.search_facts", "arguments": arguments},
            }
        )

        self.assertNotIn("error", response)
        self.assertEqual(response["result"]["content"][0]["type"], "text")
        self.assertEqual(response["result"]["content"][0]["text"], serialize_tool_envelope(direct))

    def test_protocol_errors_pin_json_rpc_error_codes(self):
        _store, _adapter, server = self.make_server()

        parse_error = handle_json_rpc_line(server, "{not json}\n")
        invalid = server.handle_request({"jsonrpc": "2.0", "id": "bad"})
        unknown = server.handle_request({"jsonrpc": "2.0", "id": "missing", "method": "career.missing"})

        self.assertEqual(parse_error["error"]["code"], PARSE_ERROR)
        self.assertEqual(invalid["error"]["code"], INVALID_REQUEST)
        self.assertEqual(unknown["error"]["code"], METHOD_NOT_FOUND)

    def test_tool_failures_stay_inside_successful_tools_call_responses(self):
        _store, _adapter, server = self.make_server()
        cases = [
            (
                "career.unknown",
                {},
                "error",
                "unknown_tool",
            ),
            (
                "career.search_facts",
                {},
                "error",
                "validation_error",
            ),
            (
                "career.propose_fact",
                {"type": "skill", "text": "React", "source": "agent_interpretation"},
                "rejected",
                "policy_error",
            ),
        ]

        for name, arguments, status, error_type in cases:
            with self.subTest(name=name):
                response = server.handle_request(
                    {
                        "jsonrpc": "2.0",
                        "id": name,
                        "method": "tools/call",
                        "params": {"name": name, "arguments": arguments},
                    }
                )

                self.assertNotIn("error", response)
                envelope = response_envelope(response)
                self.assertEqual(envelope["status"], status)
                self.assertEqual(envelope["error"]["type"], error_type)


class CareerMcpCliLifecycleContractTests(unittest.TestCase):
    def test_missing_db_path_exits_nonzero_with_one_typed_stderr_line(self):
        stderr = io.StringIO()

        code = career_mcp_main.main([], stdin=io.StringIO(""), stdout=io.StringIO(), stderr=stderr, env={})

        self.assertNotEqual(code, 0)
        lines = stderr.getvalue().splitlines()
        self.assertEqual(len(lines), 1)
        self.assertRegex(lines[0], r"^career_mcp_startup_error type=missing_db$")
        self.assertNotRegex(stderr.getvalue().lower(), r"traceback|sqlite|select|insert|update|delete")

    def test_store_open_failure_is_scrubbed_and_uses_supplied_path_only(self):
        stderr = io.StringIO()

        def failing_store_factory(_path: str) -> Any:
            raise RuntimeError("sqlite select from /internal/secret.db")

        code = career_mcp_main.main(
            ["--db", "supplied.db"],
            stdin=io.StringIO(""),
            stdout=io.StringIO(),
            stderr=stderr,
            env={},
            store_factory=failing_store_factory,
        )

        self.assertEqual(code, 1)
        lines = stderr.getvalue().splitlines()
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0], "career_mcp_startup_error type=store_open_failed path='supplied.db'")
        self.assertNotRegex(stderr.getvalue().lower(), r"traceback|sqlite|select|/internal/secret")

    def test_env_db_fallback_builds_adapter_from_public_store_and_closes_on_eof(self):
        stderr = io.StringIO()
        stdout = io.StringIO()
        captured: dict[str, Any] = {}

        def store_factory(path: str) -> SimpleStore:
            captured["path"] = path
            store = SimpleStore()
            captured["store"] = store
            return store

        def adapter_factory(store: Any) -> Any:
            captured["adapter_store"] = store
            return object()

        code = career_mcp_main.main(
            [],
            stdin=io.StringIO(""),
            stdout=stdout,
            stderr=stderr,
            env={"CAREER_MCP_DB": "env.db"},
            store_factory=store_factory,
            adapter_factory=adapter_factory,
        )

        self.assertEqual(code, 0)
        self.assertEqual(captured["path"], "env.db")
        self.assertIs(captured["adapter_store"], captured["store"])
        self.assertTrue(captured["store"].closed)
        self.assertEqual(stderr.getvalue(), "")

    def test_sigterm_shutdown_path_closes_store_and_exits_zero(self):
        captured: dict[str, Any] = {}

        def store_factory(_path: str) -> SimpleStore:
            store = SimpleStore()
            captured["store"] = store
            return store

        def server_runner(_adapter: Any, _stdin: Any, _stdout: Any) -> int:
            raise career_mcp_main._CleanShutdown()  # noqa: SLF001 - contract probe for signal path.

        code = career_mcp_main.main(
            ["--db", "career.db"],
            stdin=io.StringIO(""),
            stdout=io.StringIO(),
            stderr=io.StringIO(),
            env={},
            store_factory=store_factory,
            server_runner=server_runner,
        )

        self.assertEqual(code, 0)
        self.assertTrue(captured["store"].closed)


if __name__ == "__main__":
    unittest.main()
