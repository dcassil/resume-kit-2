"""Contract tests for the career-mcp stdio JSON-RPC MCP server."""

from __future__ import annotations

import asyncio
import io
import json
import os
import select
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Any

import career_mcp
import career_mcp.__main__ as career_mcp_main
from career_store import openCareerStore
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
SUBPROCESS_TIMEOUT_SECONDS = 10
FIXED_CLOCK = "2026-01-01T00:00:00Z"


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


def canonical_json_text(value: dict[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def subprocess_env() -> dict[str, str]:
    env = os.environ.copy()
    package_paths = [str(ROOT / "career-mcp"), str(ROOT / "career-store")]
    if env.get("PYTHONPATH"):
        package_paths.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(package_paths)
    env.pop("CAREER_MCP_DB", None)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def seed_real_store(db_path: Path, observed_at: str = FIXED_CLOCK) -> None:
    store = openCareerStore(str(db_path), clock=lambda: observed_at)
    store.upsertFact(
        {"type": "skill", "text": "React", "verification_state": "unknown"},
        {"source": "resume_source", "text": "Built React applications."},
        source="resume_source",
        policy={"allow_inferred_final": True},
    )


class CareerMcpProcess:
    def __init__(self, test_case: unittest.TestCase, db_path: Path) -> None:
        self.test_case = test_case
        self.process = subprocess.Popen(
            ["python3", "-m", "career_mcp", "--db", str(db_path)],
            cwd=ROOT,
            env=subprocess_env(),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        test_case.addCleanup(self.kill_if_running)

    def request(self, request: dict[str, Any]) -> dict[str, Any]:
        self.write_line(canonical_json_text(request))
        return self.read_response()

    def write_line(self, line: str) -> None:
        assert self.process.stdin is not None
        self.process.stdin.write(line + "\n")
        self.process.stdin.flush()

    def read_response(self) -> dict[str, Any]:
        line = self.read_line()
        return json.loads(line)

    def read_line(self) -> str:
        assert self.process.stdout is not None
        ready, _write, _error = select.select([self.process.stdout], [], [], SUBPROCESS_TIMEOUT_SECONDS)
        if not ready:
            self.kill_if_running()
            self.test_case.fail("Timed out waiting for career-mcp subprocess response.")
        line = self.process.stdout.readline()
        if not line:
            stderr = self.process.stderr.read() if self.process.stderr is not None else ""
            self.test_case.fail(f"career-mcp subprocess exited before a response. stderr={stderr!r}")
        return line

    def close_and_wait(self) -> int:
        if self.process.stdin is not None and not self.process.stdin.closed:
            self.process.stdin.close()
        try:
            code = self.process.wait(timeout=SUBPROCESS_TIMEOUT_SECONDS)
            self.close_pipes()
            return code
        except subprocess.TimeoutExpired:
            self.kill_if_running()
            self.test_case.fail("Timed out waiting for career-mcp subprocess shutdown.")
            raise AssertionError("unreachable")

    def kill_if_running(self) -> None:
        if self.process.poll() is not None:
            self.close_pipes()
            return
        self.process.kill()
        try:
            self.process.wait(timeout=SUBPROCESS_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            pass
        self.close_pipes()

    def close_pipes(self) -> None:
        for pipe in (self.process.stdin, self.process.stdout, self.process.stderr):
            if pipe is not None and not pipe.closed:
                pipe.close()


def run_cli_subprocess(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", "-m", "career_mcp", *args],
        cwd=ROOT,
        env=subprocess_env(),
        input="",
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=SUBPROCESS_TIMEOUT_SECONDS,
        check=False,
    )


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


class CareerMcpSubprocessTransportContractTests(unittest.TestCase):
    def make_db_path(self, directory: str, name: str = "career.db") -> Path:
        return Path(directory) / name

    def test_subprocess_smoke_handshake_tools_list_call_and_clean_shutdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = self.make_db_path(tmp)
            seed_real_store(db_path)
            process = CareerMcpProcess(self, db_path)

            initialize = process.request(
                {"jsonrpc": "2.0", "id": "init", "method": "initialize", "params": {"protocolVersion": "2024-11-05"}}
            )
            self.assertEqual(initialize["result"]["protocolVersion"], "2024-11-05")
            self.assertEqual(initialize["result"]["capabilities"], {"tools": {}})

            tools = process.request({"jsonrpc": "2.0", "id": "tools", "method": "tools/list"})
            self.assertEqual([tool["name"] for tool in tools["result"]["tools"]], [tool["name"] for tool in SURFACE["tools"]])

            call = process.request(
                {
                    "jsonrpc": "2.0",
                    "id": "search",
                    "method": "tools/call",
                    "params": {"name": "career.search_facts", "arguments": {"query": "React", "limit": 1}},
                }
            )
            self.assertNotIn("error", call)
            envelope = response_envelope(call)
            self.assertEqual(envelope["status"], "ok")
            self.assertEqual(envelope["tool"], "career.search_facts")
            self.assertTrue(envelope["facts"])

            self.assertEqual(process.close_and_wait(), 0)

    def test_subprocess_tools_call_content_matches_in_process_for_read_and_confirmed_mutation(self):
        read_arguments = {"query": "React", "limit": 1}
        mutation_arguments = {
            "type": "skill",
            "text": "TypeScript",
            "source": "agent_interpretation",
            "confirmed": True,
        }

        with tempfile.TemporaryDirectory() as tmp:
            read_direct_db = self.make_db_path(tmp, "read_direct.db")
            read_process_db = self.make_db_path(tmp, "read_process.db")
            seed_real_store(read_direct_db)
            seed_real_store(read_process_db)

            read_process = CareerMcpProcess(self, read_process_db)
            read_response = read_process.request(
                {
                    "jsonrpc": "2.0",
                    "id": "read",
                    "method": "tools/call",
                    "params": {"name": "career.search_facts", "arguments": read_arguments},
                }
            )
            self.assertEqual(read_process.close_and_wait(), 0)

            read_store = openCareerStore(str(read_direct_db), clock=lambda: FIXED_CLOCK)
            read_direct = asyncio.run(career_mcp.create_career_mcp(store=read_store).call_tool("career.search_facts", read_arguments))
            self.assertEqual(
                canonical_json_text(json.loads(read_response["result"]["content"][0]["text"])),
                canonical_json_text(read_direct),
            )

            mutation_direct_db = self.make_db_path(tmp, "mutation_direct.db")
            mutation_process_db = self.make_db_path(tmp, "mutation_process.db")
            seed_real_store(mutation_direct_db)
            seed_real_store(mutation_process_db)

            mutation_process = CareerMcpProcess(self, mutation_process_db)
            mutation_response = mutation_process.request(
                {
                    "jsonrpc": "2.0",
                    "id": "mutation",
                    "method": "tools/call",
                    "params": {"name": "career.propose_fact", "arguments": mutation_arguments},
                }
            )
            self.assertEqual(mutation_process.close_and_wait(), 0)

            mutation_process_envelope = json.loads(mutation_response["result"]["content"][0]["text"])
            observed_at = mutation_process_envelope["audit"]["observed_at"]
            mutation_store = openCareerStore(str(mutation_direct_db), clock=lambda: observed_at)
            mutation_direct = asyncio.run(
                career_mcp.create_career_mcp(store=mutation_store).call_tool("career.propose_fact", mutation_arguments)
            )
            self.assertEqual(canonical_json_text(mutation_process_envelope), canonical_json_text(mutation_direct))

    def test_subprocess_protocol_errors_keep_json_rpc_and_tool_error_channels_distinct(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = self.make_db_path(tmp)
            seed_real_store(db_path)
            process = CareerMcpProcess(self, db_path)

            process.write_line("{not json}")
            malformed = process.read_response()
            self.assertEqual(malformed["error"]["code"], PARSE_ERROR)

            unknown_method = process.request({"jsonrpc": "2.0", "id": "unknown", "method": "career.missing"})
            self.assertEqual(unknown_method["error"]["code"], METHOD_NOT_FOUND)

            unknown_tool = process.request(
                {
                    "jsonrpc": "2.0",
                    "id": "unknown_tool",
                    "method": "tools/call",
                    "params": {"name": "career.unknown", "arguments": {}},
                }
            )
            self.assertNotIn("error", unknown_tool)
            envelope = response_envelope(unknown_tool)
            self.assertEqual(envelope["status"], "error")
            self.assertEqual(envelope["error"]["type"], "unknown_tool")

            self.assertEqual(process.close_and_wait(), 0)


class CareerMcpSubprocessStartupFailureContractTests(unittest.TestCase):
    def test_subprocess_missing_db_path_exits_nonzero_with_one_scrubbed_stderr_line(self):
        completed = run_cli_subprocess([])

        self.assertNotEqual(completed.returncode, 0)
        lines = completed.stderr.splitlines()
        self.assertEqual(lines, ["career_mcp_startup_error type=missing_db"])
        self.assertNotRegex(completed.stderr.lower(), r"traceback")

    def test_subprocess_unopenable_db_path_exits_nonzero_with_typed_stderr_and_no_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            completed = run_cli_subprocess(["--db", tmp])

        self.assertNotEqual(completed.returncode, 0)
        lines = completed.stderr.splitlines()
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0], f"career_mcp_startup_error type=store_open_failed path={tmp!r}")
        self.assertNotRegex(completed.stderr.lower(), r"traceback")


if __name__ == "__main__":
    unittest.main()
