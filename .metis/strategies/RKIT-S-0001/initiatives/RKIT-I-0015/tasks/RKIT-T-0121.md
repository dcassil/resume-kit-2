---
id: real-store-scenario-harness-aws
level: task
title: "Real-store scenario harness: AWS/GraphQL/architecture fixtures, Job A→B reuse, MCP-vs-store alignment, gap resolution, stdio parameterization"
short_code: "RKIT-T-0121"
created_at: 2026-08-18T23:10:05.103360+00:00
updated_at: 2026-08-18T23:11:14.738805+00:00
parent: integrate-career-mcp-smoke-and-e2e
blocked_by: []
archived: false

tags:
  - "#task"
  - "#phase/active"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0015
---

# Real-store scenario harness: AWS/GraphQL/architecture fixtures, Job A→B reuse, MCP-vs-store alignment, gap resolution, stdio parameterization

## Parent Initiative

[[RKIT-I-0015]]

## Objective

Close the fake-vs-real fidelity gap (initiative R1, R3–R6): a scenario harness drives fixture cases through `call_tool` against a REAL SQLite store (seeded through MCP write tools, never SQL/store internals), replacing the canned FakeCareerStore `find_matches` classifications; the harness is driver-parameterized so every scenario also runs over the I-0014 stdio transport.

## Acceptance Criteria

## Acceptance Criteria

- [ ] Scenario harness (tests/e2e/ or contract tier — follow repo conventions): temp SQLite store via public `openCareerStore`; seeding through MCP write tools with `confirmed: true` (I-0012) from fixture inputs; scenario steps through `call_tool`; assertions from fixture-declared expected observations. Driver interface with TWO implementations: in-process adapter AND stdio subprocess client reusing the I-0014 server (same scenario definitions, no forks; stdio variants may run a representative subset if runtime cost demands — state the split).
- [ ] R3 fixture scenarios through MCP end to end: AWS six-years answer, GraphQL, architecture-answer (find these fixture truths in the fixtures package / smoke inputs — consume, don't invent).
- [ ] R4 Job A → Job B reuse: phase 1 answers Job A's AWS + GraphQL questions creating verified facts through MCP; phase 2 `career.find_matches` for Job B resolves BOTH from stored facts — one coherent row per requirement with correct classification + fact ids (regression against the pre-I-0011 duplicate-row defect).
- [ ] R1: the hardcoded FakeCareerStore find_matches classifications (tests/contract/test_career_mcp_contract.py:139-158 area — verify current lines) are REPLACED by real-store runs; no TEST_SPEC product scenario satisfiable by fake-only expectations (add the fake-only satisfiability check: scenario assertions must not depend on fake-provided classifications). RKIT-A-0006 strengthen-only.
- [ ] R5: executable MCP-vs-store alignment — for each read scenario, the equivalent public store-service call diffed against the MCP result: equal modulo the declared DTO-stripping contract (the diff asserts the stripping contract itself).
- [ ] R6: targeted gap resolution through MCP (`get_unverified` → `verify_fact` with evidence + confirmed) demonstrated in a scenario — not via direct store access.
- [ ] Audit-reconstruction wiring (post-I-0013 follow-on): one mutation scenario reconstructs its changed facts from the audit stream inside the E2E flow (reuse the T-0109 reconstruction helpers/pattern — the contract test stays in I-0013's suite; this integrates it into fixture flows).
- [ ] All suites bridged into gate-run modules (state where); subprocess scenarios timeout-guarded and hermetic. Gates green: `--pr`, `--smoke`, `--future-contract`. No protected edits (T-0122 owns run_smoke.py).

## Implementation Notes

### Technical Approach
Reuse the I-0014 subprocess harness from tests/contract/test_career_mcp_server_contract.py for the stdio driver. FakeCareerStore remains as the VERIFIED fake for unit tiers (I-0011's conformance test governs it) — this task removes its role as scenario-certifier only.

### Dependencies
I-0011 semantics, I-0012 confirmation, I-0013 audit, I-0014 transport — all landed.

### Risk Considerations
Mind mutating-tool policy: every write needs confirmed:true or scenarios will policy-reject. The verified-fake conformance test must stay green — don't delete the fake, demote it.

Recommended Agent: opus + high

## Status Updates

- 2026-08-18: Added real-store scenario harness in `tests/e2e/test_career_mcp_real_store_scenarios_e2e.py` with in-process and stdio drivers, MCP-only seeding, fixture answer coverage, Job A→B reuse, MCP-vs-store alignment, gap resolution, and in-flow audit reconstruction. Bridged through `tests.contract.test_career_mcp_contract`.
