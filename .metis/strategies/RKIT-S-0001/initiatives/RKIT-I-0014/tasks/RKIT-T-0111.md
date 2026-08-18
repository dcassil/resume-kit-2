---
id: stdio-json-rpc-mcp-server-entry
level: task
title: "Stdio JSON-RPC MCP server: entry point, store lifecycle, protocol binding, error channels"
short_code: "RKIT-T-0111"
created_at: 2026-08-18T21:07:19.534465+00:00
updated_at: 2026-08-18T21:08:38.025445+00:00
parent: provide-real-career-mcp-transport
blocked_by: []
archived: false

tags:
  - "#task"
  - "#phase/active"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0014
---

# Stdio JSON-RPC MCP server: entry point, store lifecycle, protocol binding, error channels

## Parent Initiative

[[RKIT-I-0014]]

## Objective

Make career-mcp a real, connectable MCP surface for the first time (R1–R4): `python -m career_mcp --db <path>` runs a stdio JSON-RPC MCP server — initialize handshake, `tools/list` from the canonical manifest, `tools/call` delegating to the existing adapter — as a thin shell with zero tool logic moved, honest error channels, and clean store lifecycle.

## Acceptance Criteria

## Acceptance Criteria

- [ ] **DEPENDENCY DECISION (settled by driver, record in code + report):** hand-rolled stdlib-only stdio JSON-RPC framing — NOT the mcp SDK. Rationale: the repo is stdlib-only at runtime by design, and the smoke gate installs into a fresh venv where a new third-party dependency would need network access; RKIT-A-0002/the initiative explicitly authorize hand-rolling "if adding the dependency proves unacceptable at integration time, recorded as a decision". Record this in the server module docstring and the initiative Status Update.
- [ ] New module `career-mcp/career_mcp/server.py` + `career-mcp/career_mcp/__main__.py`: `python -m career_mcp --db <path>` (optional documented env fallback CAREER_MCP_DB). Missing/unopenable path → nonzero exit with a scrubbed, typed one-line error to stderr (no tracebacks, no SQL/paths beyond what the user supplied); store opened via the PUBLIC store factory only, injected into `create_career_mcp` exactly as tests inject theirs (one construction path).
- [ ] Protocol binding over stdio: newline-delimited JSON-RPC 2.0 (and Content-Length framing ONLY if trivially cheap — pick one, document it): `initialize` (protocol version + capabilities advertising tools), `notifications/initialized` accepted, `tools/list` returning the canonical manifest's tools verbatim (name/description/inputSchema shape MCP hosts expect — map from tool_surface.json without duplicating it), `tools/call` → adapter `call_tool`, result serialized as MCP content (the typed envelope as JSON text content, structured envelope preserved).
- [ ] Error channels never mix (R3): malformed JSON frame → JSON-RPC parse error (-32700); invalid request → -32600; unknown method → -32601; tool-level failures (validation_error/policy_error/rejected envelopes) travel INSIDE successful tools/call responses. Tests pin each code.
- [ ] Lifecycle: stdin EOF and SIGTERM both close the store cleanly and exit 0; no atexit surprises; no threads left running.
- [ ] Thin-shell proof (R5 substrate): server contains NO tool logic — grep-proof that server.py imports only the adapter/factory surface; a unit test drives the server loop in-process (feeding frames to the handler function) asserting a tools/call result byte-equals the adapter's call_tool envelope for the same store state.
- [ ] In-process `create_career_mcp` path untouched (existing contract tests unmodified).
- [ ] Guardrails hold over the new entry point: `python3 tools/career_mcp_guardrails.py --root .` passes (no SQL imports, no forbidden capabilities in the new modules).
- [ ] Gates green: `--pr`, `--smoke`, `--future-contract`. No protected edits. New test module bridged into a gate-run module (check bridging explicitly).

## Implementation Notes

### Technical Approach
Separate the pure frame-handling function (dict in → dict out) from the stdio pump loop so tests exercise the handler without subprocesses (T-0112 adds the real subprocess smoke). Async adapter: run call_tool via asyncio.run per request (single-user local; no concurrency requirements in v1 — note it).

### Dependencies
I-0009 canonical manifest (landed), I-0010/0011/0012 adapter behavior (landed).

### Risk Considerations
tool_surface.json schemas must map to MCP inputSchema without mutation — if the manifest lacks a required MCP field, ADAPT in the mapping layer, never edit the canonical manifest shape the guardrail pins. tools/run_smoke.py is protected — T-0112 owns the smoke TEST_SPEC rewrite; do not touch protected files here.

Recommended Agent: opus + high

## Status Updates

- 2026-08-18: Implemented a stdlib-only newline-delimited JSON-RPC stdio shell in `career-mcp/career_mcp/server.py` and `career-mcp/career_mcp/__main__.py`. The dependency decision is documented in the server module docstring. Contract coverage was added in `tests/contract/test_career_mcp_server_contract.py` and bridged into `tests/contract/test_career_mcp_contract.py`; `career-mcp/TEST_SPEC.md` now names the server coverage without changing the T-0112-owned smoke wording.
