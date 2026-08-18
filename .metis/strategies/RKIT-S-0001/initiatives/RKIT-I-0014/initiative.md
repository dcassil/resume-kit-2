---
id: provide-real-career-mcp-transport
level: initiative
title: "Provide Real Career-MCP Transport and Host Runtime"
short_code: "RKIT-I-0014"
created_at: 2026-08-13T20:41:37.135885+00:00
updated_at: 2026-08-18T21:08:37.673601+00:00
parent: resume-kit-2-full-product-buildout
blocked_by: [RKIT-I-0009]
archived: false

tags:
  - "#initiative"
  - "#phase/active"


exit_criteria_met: false
estimated_complexity: M
strategy_id: RKIT-S-0001
initiative_id: provide-real-career-mcp-transport
---

# Provide Real Career-MCP Transport and Host Runtime Initiative

## Context **[REQUIRED]**

Package: `career-mcp`. No MCP server or protocol binding exists anywhere: no stdio/JSON-RPC server, no `tools/list`/`tools/call` protocol endpoint, no entry point an external agent runtime can connect to. `tool_surface.json:14-23` declares `mcp_endpoints`, but they exist only as Python methods on an in-process class, and the TEST_SPEC smoke item "MCP server/tool registry loads" (TEST_SPEC.md:102-107) is quietly satisfied by instantiating that class — the audit flagged this as the spec weakening the vision's agent-facing MCP surface (section 7) into an in-process library.

RKIT-A-0002 (decided) sets the design: the first transport is a stdio JSON-RPC MCP server; the server opens career-store by database path supplied at startup (config/CLI argument); the in-process adapter remains supported for CLI orchestration and tests; both paths use only the public store service API; HTTP/SSE and streamable HTTP are deferred until a remote host exists; v1 has no multi-user auth.

The previous dependency on RKIT-I-0013 (mutation audit) was artificial — nothing in the contracts requires audit before a transport exists, and it serialized the vision-required consumable MCP surface behind the entire chain. The real prerequisite is RKIT-I-0009: the server must serve the single canonical manifest.

Re-baselined 2026-08-13 against the alignment audit and decided ADRs.

## Goals & Non-Goals **[REQUIRED]**

**Goals:**
- A runnable stdio JSON-RPC MCP server: initialize handshake, `tools/list` from the canonical manifest, `tools/call` dispatching to the existing adapter.
- Store opened by DB path at startup via the public store service API (never SQL); clean shutdown.
- The in-process `create_career_mcp` path retained unchanged for CLI orchestration and tests.
- The smoke gate proves a real server process loads and serves the registry.

**Non-Goals:**
- HTTP/SSE/streamable transports — deferred by RKIT-A-0002 until a remote host exists.
- Multi-user authorization — rejected for v1 by RKIT-A-0002; policy semantics live in RKIT-I-0012.
- Fixture/E2E scenario breadth — RKIT-I-0015 (its transport-dependent items follow this initiative).
- Manifest canonicalization — consumed from RKIT-I-0009, not re-done here.

## Requirements **[CONDITIONAL: Requirements-Heavy Initiative]**

### System Requirements
- R1: An entry point (`python -m career_mcp` or console script) accepting a database path argument; startup fails loudly with a scrubbed, typed error if the path is missing or the store cannot open (RKIT-A-0002 item 3).
- R2: The server implements the MCP protocol over stdio JSON-RPC — initialize/capabilities, `tools/list` returning the eight tools from the canonical `career_mcp/tool_surface.json` (RKIT-I-0009), `tools/call` delegating to `call_tool` — making the `mcp_endpoints` declaration at `tool_surface.json:14-23` true for the first time.
- R3: Tool-level failures travel as typed envelopes inside successful JSON-RPC responses; protocol-level failures (malformed frame, unknown method) return JSON-RPC error objects — the two error channels never mix.
- R4: The server exposes no raw SQL or store internals; the existing guardrails and forbidden-capability boundaries hold identically over the transport.
- R5: A stdio call and an in-process call produce byte-equivalent tool results for the same store state (single implementation, thin shell).

### Dependencies
- RKIT-I-0009 (canonical manifest). RKIT-A-0002 is decided — the transport/store-opening design is settled input, not a blocker; the former RKIT-I-0013 dependency is removed as artificial.

### Blocked Status
- Yes (blocked_by: ["RKIT-I-0009"]).

## Detailed Design **[REQUIRED]**

**Server composition.** The server is a thin protocol shell over the existing adapter: parse stdio JSON-RPC frames, route initialize/`tools/list`/`tools/call`, delegate to the adapter's `list_tools`/`call_tool`, serialize the response. No tool logic moves; the adapter remains the single implementation both paths share, so adapter-level contract tests cover transport behavior minus framing.

**SDK choice.** Prefer the reference MCP Python SDK for framing and handshake correctness (version negotiation, notifications, capability advertisement); hand-rolled JSON-RPC only if adding the dependency proves unacceptable at integration time, recorded as a decision if so.

**Store lifecycle.** Startup opens the store service by `--db` path via the public factory; the service instance is injected into `create_career_mcp` exactly as tests inject theirs — one construction path, per RKIT-A-0002 item 3 (path for the server, injection for the in-process adapter, identical public API underneath). Shutdown on stdin EOF or SIGTERM closes the store cleanly.

**Error mapping.** JSON-RPC error codes for protocol errors (parse error, invalid request, method not found); tool results — including `rejected`/`error` envelopes from RKIT-I-0010's contract — travel as successful `tools/call` results, preserving the agent-visible typed envelope identically across both paths.

**Configuration.** DB path via CLI argument first, optional environment fallback documented — matching the ADR's "config/CLI argument" wording. No other configuration surface is introduced.

## Testing Strategy **[CONDITIONAL: Separate Testing Initiative]**

- Subprocess smoke test: spawn the server with a temp SQLite DB, perform initialize, assert `tools/list` equals the canonical manifest's eight tools, and round-trip one `career.search_facts` call. This is the TEST_SPEC-strengthening item for this scope: rewrite the "MCP server/tool registry loads" smoke item (TEST_SPEC.md:102-107) so only a real server process can satisfy it, closing the audit-flagged class-instantiation shortcut.
- Protocol contract tests: malformed frame yields a JSON-RPC error; unknown tool yields a typed envelope; parity test asserting the stdio result equals the in-process result for the same store state (R5).
- Startup-failure tests: missing or unopenable DB path exits nonzero with a scrubbed message.
- Guardrail run unchanged over the new entry point (no-SQL, forbidden capabilities).

## Alternatives Considered **[REQUIRED]**

- **HTTP/SSE or streamable HTTP first.** Rejected by RKIT-A-0002: no remote host exists, and remote transport drags multi-user auth burden forward prematurely.
- **In-process adapter only (status quo).** Rejected as sole path by RKIT-A-0002: not a consumable MCP surface; vision section 7 promises agent-callable tools and the smoke spec requires a loadable server; the adapter is kept as the secondary path.
- **Hand-rolled JSON-RPC framing instead of the MCP SDK.** Rejected by default: framing and handshake edge cases are where hand-rolled servers break against real hosts; take the SDK unless a dependency constraint surfaces, and record the reversal if it does.

## Implementation Plan **[REQUIRED]**

1. Server entry point with `--db` store opening and lifecycle management.
2. JSON-RPC/MCP binding (initialize, tools/list, tools/call) over the adapter.
3. Protocol-vs-tool error-channel mapping.
4. Subprocess smoke, stdio/in-process parity, and startup-failure tests; strengthen the TEST_SPEC smoke item.
5. Host registration documentation (how a local agent host launches and connects to the server).

## Status Updates

- 2026-08-18: RKIT-T-0111 integration decision recorded in code and report scope: hand-rolled stdlib-only newline-delimited JSON-RPC over stdio is used instead of the MCP SDK because the repo has no runtime dependencies and the smoke gate installs into a fresh environment where a new dependency would require network access. The server is a thin protocol shell over `create_career_mcp`, with `python -m career_mcp --db <path>` opening `career_store.openCareerStore` and injecting the resulting public store service.
