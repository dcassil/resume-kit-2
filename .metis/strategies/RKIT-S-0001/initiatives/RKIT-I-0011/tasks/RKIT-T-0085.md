---
id: contract-test-rewrite-real-store
level: task
title: "Contract-test rewrite: real-store tier + verified-fake conformance (R2)"
short_code: "RKIT-T-0085"
created_at: 2026-08-16T19:25:47.630259+00:00
updated_at: 2026-08-16T19:31:56.476527+00:00
parent: align-career-mcp-semantics-with
blocked_by: [RKIT-T-0084]
archived: false

tags:
  - "#task"
  - "#phase/active"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0011
---

# Contract-test rewrite: real-store tier + verified-fake conformance (R2)

## Parent Initiative

[[RKIT-I-0011]]

## Objective **[REQUIRED]**

Rebuild the career-mcp contract-test architecture so the authoritative tier exercises the REAL store (temp SQLite via public `openCareerStore`) — the audit's root finding was that all fake-path tests certified a dialect production never runs. Any remaining fake must be a VERIFIED fake: a conformance test asserts its method signatures and vocabulary against `career-store/store_surface.json`, so it can never drift into a private dialect again.

## Acceptance Criteria

## Acceptance Criteria **[REQUIRED]**

- [ ] Real-store tier: every career.* tool has at least one contract test driving it against a real temp-SQLite store through the public API (ok path + at least one rejection path per mutating tool, asserted via the typed envelope).
- [ ] If a fake remains for speed/edge-shaping: a conformance test asserts (a) its public method names == store_surface.json `surfaces` ∩ methods-the-adapter-calls, (b) its accepted vocabulary (verification/resolution/relationship enums) matches the declared sets, (c) it raises/rejects with store-shaped results. If conformance can't be expressed meaningfully, delete the fake instead.
- [ ] Named permanent regression tests for the audit's empirical failures (those provable TODAY): store rejects nothing that the manifest advertises (manifest-driven property test over advertised enum values where store support exists); `types` filter excludes non-matching facts on the real store; verify_fact `imported` end-to-end IF the store's canonical VerificationState accepts it (it does since RKIT-I-0001 — prove it through MCP).
- [ ] No assertion weakened relative to the deleted fake-path tests (strengthen-only; map old assertion → new home in the report).
- [ ] `--pr` and `--smoke` green; verify clean.

## Implementation Notes **[CONDITIONAL: Technical Task]**

### Technical Approach
- Reuse the real-store test idioms T-0081/0082 introduced (tempfile sqlite + asyncio.run(call_tool(...))).
- Bridge new modules into gate-run modules if the static runner list doesn't discover them (T-0078 idiom); list for deferred run_tests.py wiring.
- Recommended Agent: opus + high

### Dependencies
RKIT-T-0084 (single-dialect adapter). Serial.

### Risk Considerations
- PROTECTED read-only: tools/*, tests/boundary/*. tests/contract/ is unprotected (RKIT-A-0006 authorizes realignment; strengthen-only).

## Status Updates **[REQUIRED]**

- 2026-08-16: T-0084 committed (dual dispatch deleted, STORE_METHOD_BY_TOOL mapping, fake mechanically camelCased; gates 427/smoke/verify green; NO_SNAKE_STORE_CALLS grep clean — sole remaining hasattr is a camelCase findConflicts capability check). Codex launched on the real-store tier + verified-fake conformance.
- 2026-08-16: Added real temp-SQLite MCP contract tier for all 8 `career.*` tools, verified-fake conformance checks, and imported/inferred verifyFact authority routing. Targeted contract/store tests are green; full requested gates pending.
- 2026-08-16: Full requested validation passed: career_mcp_guardrails, PR gate (440 tests), smoke, straight-jacket verify, and double snapshot regeneration with empty `fixtures/expected/` diff.
