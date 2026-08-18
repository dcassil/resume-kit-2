---
id: transport-tests-subprocess-smoke
level: task
title: "Transport tests: subprocess smoke, stdio/in-process parity, startup failures, TEST_SPEC strengthening, host docs"
short_code: "RKIT-T-0112"
created_at: 2026-08-18T21:07:19.603072+00:00
updated_at: 2026-08-18T21:17:25.382868+00:00
parent: provide-real-career-mcp-transport
blocked_by: [RKIT-T-0111]
archived: false

tags:
  - "#task"
  - "#phase/active"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0014
---

# Transport tests: subprocess smoke, stdio/in-process parity, startup failures, TEST_SPEC strengthening, host docs

## Parent Initiative

[[RKIT-I-0014]]

## Objective

Prove the T-0111 server against a REAL process boundary and close the audit-flagged shortcut: subprocess smoke (spawn, handshake, tools/list = canonical eight+, round-trip a call), stdio/in-process byte-parity (R5), startup-failure behavior (R1), the TEST_SPEC "MCP server/tool registry loads" item rewritten so only a real server process can satisfy it, and host-registration documentation.

## Acceptance Criteria

## Acceptance Criteria

- [ ] Subprocess smoke test (contract tier, real `subprocess.Popen(["python3", "-m", "career_mcp", "--db", tmpdb])`): initialize handshake succeeds with protocol version + tools capability; `tools/list` returns exactly the canonical manifest's tool set (names compared against career_mcp/tool_surface.json programmatically, not hardcoded); one `career.search_facts` round-trip returns a typed ok envelope; clean shutdown on stdin close (exit 0, bounded wait). Timeout-guarded so a hung server fails the suite, never wedges it.
- [ ] Parity test (R5): same temp store state → the stdio `tools/call` result content byte-equals the in-process `call_tool` envelope (JSON-canonicalized comparison) for at least one read and one confirmed mutation.
- [ ] Startup-failure tests: missing `--db` → nonzero exit + scrubbed one-line stderr; unopenable path (e.g. directory or bogus file) → nonzero exit + typed message; NO traceback text in stderr (assert).
- [ ] Protocol-error tests over the real subprocess: malformed JSON line → -32700; unknown method → -32601; unknown tool via tools/call → typed unknown_tool envelope INSIDE a successful response (channels never mix, R3 re-proven over the wire).
- [ ] career-mcp/TEST_SPEC.md (:102-107 area) "MCP server/tool registry loads" REWRITTEN: satisfiable only by a real server process (names the subprocess smoke test); the in-process instantiation shortcut is explicitly no longer sufficient. Strengthen-only.
- [ ] Host registration docs: a short section (career-mcp/README.md or TEST_SPEC appendix — wherever the package documents usage) showing how a local agent host launches/connects: command line, --db argument, env fallback, an example Claude Code / generic MCP host config snippet.
- [ ] All new tests bridged into gate-run modules (check bridging explicitly; run_tests.py protected). Gates green: `--pr`, `--smoke`, `--future-contract`. No protected edits (tools/run_smoke.py stays untouched — the TEST_SPEC rewrite is the strengthening; extending the protected smoke runner is deferred to Daniel's batch if ever needed, note it in the report).

## Implementation Notes

### Technical Approach
Keep subprocess tests hermetic: tmp dirs, explicit timeouts (e.g. 10s), kill on teardown. Seed the temp store through the public store API before spawning. Compare tools/list against the manifest file so future tool additions can't drift.

### Dependencies
RKIT-T-0111 (the server).

### Risk Considerations
Subprocess tests in the PR gate must stay fast (<2s each ideally) and hermetic; if environment PYTHONPATH matters for `-m career_mcp` in the gate venv, mirror how existing tests locate packages.

Recommended Agent: opus + medium

## Status Updates

- 2026-08-18: Added real subprocess transport tests in `tests/contract/test_career_mcp_server_contract.py`, bridged them through `tests/contract/test_career_mcp_contract.py`, strengthened `career-mcp/TEST_SPEC.md`, and added `career-mcp/README.md` host registration docs. Focused server contract suite passes locally; subprocess classes add about 0.85s wall-clock over the previous in-process server-contract baseline.
