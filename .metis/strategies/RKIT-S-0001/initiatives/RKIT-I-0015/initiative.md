---
id: integrate-career-mcp-smoke-and-e2e
level: initiative
title: "Integrate Career-MCP Smoke and E2E Fixtures"
short_code: "RKIT-I-0015"
created_at: 2026-08-13T20:41:37.161505+00:00
updated_at: 2026-08-18T23:11:14.549699+00:00
parent: resume-kit-2-full-product-buildout
blocked_by: [RKIT-I-0011]
archived: false

tags:
  - "#initiative"
  - "#phase/active"


exit_criteria_met: false
estimated_complexity: M
strategy_id: RKIT-S-0001
initiative_id: integrate-career-mcp-smoke-and-e2e
---

# Integrate Career-MCP Smoke and E2E Fixtures Initiative

## Context **[REQUIRED]**

Package: `career-mcp`. The central problem this initiative exists to fix is the fake-vs-real fidelity gap: the TEST_SPEC's product scenarios are currently "covered" by hardcoded classifications inside a test double. The Job A → Job B `find_matches` expectations are canned dicts in `FakeCareerStore` (`tests/contract/test_career_mcp_contract.py:139-158`), so cross-job reuse through MCP is asserted against answers the store never produced. Real coverage today is thin: `tools/run_smoke.py:137-152` proves only the read path (search/get) against a real SQLite store plus raw-SQL rejection. Missing entirely: write-path smoke against the real store; the AWS six-years answer fixture, the GraphQL fixture, and the architecture-answer fixture exercised through career-mcp; Job A → Job B AWS/GraphQL reuse through MCP; the "MCP search results align with store service results" E2E item; targeted gap resolution through MCP (resume-cli currently bypasses MCP for it); and audit-identifies-changes E2E — TEST_SPEC.md:111-118 describes coverage that does not exist.

The previous sole dependency on RKIT-I-0014 (transport) serialized all of this behind the transport even though most missing coverage runs in-process today — and would immediately surface the confirmed real-store bugs. The real prerequisite is RKIT-I-0011: these scenarios exercise the semantics (enums, `find_matches` shape, `get_unverified` breadth, filters) that 0011 aligns; running them earlier would only certify the broken surface. Transport-dependent E2E variants follow RKIT-I-0014 in sequence but do not gate the in-process work; the audit-reconstruction E2E likewise follows RKIT-I-0013.

Re-baselined 2026-08-13 against the alignment audit and decided ADRs.

## Goals & Non-Goals **[REQUIRED]**

**Goals:**
- Fixture-driven in-process E2E through `call_tool` against a real store: the AWS six-years answer, GraphQL, and architecture-answer fixtures, and Job A → Job B AWS/GraphQL reuse through MCP.
- Write-path smoke: a propose → verify → add_relationship → search round-trip against real SQLite in `tools/run_smoke.py`.
- An executable MCP-vs-store alignment check: the same query through the store service and through MCP yields the same facts modulo the DTO-stripping contract.
- Stdio-transport variants of the same scenarios once RKIT-I-0014 lands, and audit-reconstruction E2E wiring once RKIT-I-0013 lands (prose-sequenced, not frontmatter blocks).

**Non-Goals:**
- Fixing the semantics defects themselves — RKIT-I-0011; this initiative proves them fixed and keeps them fixed.
- Transport implementation — RKIT-I-0014.
- Audit event content — RKIT-I-0013; this initiative only wires its reconstruction check into the E2E suite afterward.
- Inventing new fixture truth — fixture content ownership stays with the fixtures package; this initiative consumes stable inputs and expected observations.

## Requirements **[CONDITIONAL: Requirements-Heavy Initiative]**

### System Requirements
- R1: No TEST_SPEC product scenario may be satisfiable solely by FakeCareerStore expectations; the hardcoded `find_matches` classifications (`tests/contract/test_career_mcp_contract.py:139-158`) are replaced by real-store runs (protected-test edits authorized by RKIT-A-0006; assertion strength must increase).
- R2: Write-path smoke against a real store extends `tools/run_smoke.py:137-152`'s read-only coverage: `propose_fact`, `verify_fact` (with evidence), `add_relationship`, then a search reflecting the writes.
- R3: The AWS six-years, GraphQL, and architecture-answer fixture cases run through career-mcp tools end-to-end — the TEST_SPEC fixture-driven cases the audit found unexercised through MCP anywhere.
- R4: Job A → Job B reuse: facts learned answering Job A resolve AWS and GraphQL requirements for Job B via `career.find_matches` over a real store (TEST_SPEC.md:89-93, real-store enforced), asserting one coherent row per requirement (regression against the duplicate-row defect RKIT-I-0011 fixes).
- R5: An executable "MCP search results align with store service results" test (TEST_SPEC.md:111-118 E2E item, currently zero coverage).
- R6: Targeted gap resolution demonstrated through MCP tools (`get_unverified` → `verify_fact` path), not only via resume-cli's direct store access.

### Dependencies
- RKIT-I-0011 (aligned semantics are the subject under test). Prose-sequenced follow-ons: stdio variants after RKIT-I-0014; audit-reconstruction E2E after RKIT-I-0013. RKIT-A-0002/RKIT-A-0006 are decided inputs.

### Blocked Status
- Yes (blocked_by: ["RKIT-I-0011"]).

## Detailed Design **[REQUIRED]**

**Scenario harness.** A pytest fixture builds a temp SQLite career store via the public store service, seeds it through MCP write tools (never SQL, never store internals) from fixture inputs, then executes scenario steps through `call_tool` and asserts fixture-declared expected observations. Seeding through the MCP write path makes every scenario double as write-path coverage.

**Alignment check.** For each read scenario, run the equivalent store-service call and diff: MCP result equals store result minus the stripped sensitive fields — the diff asserts the stripping contract itself instead of assuming it.

**Job A → Job B.** Two job fixtures. Phase 1 answers Job A's AWS and GraphQL questions, creating verified facts through MCP. Phase 2 calls `find_matches` for Job B's requirements and asserts both resolve from stored facts with correct single-row per-requirement classifications and fact ids.

**Transport parameterization.** The harness runs scenarios through a driver interface with two implementations: the in-process adapter (now) and, post-RKIT-I-0014, a stdio subprocess client — so transport E2E reuses scenario definitions instead of forking them.

**Audit E2E wiring.** Post-RKIT-I-0013: a mutation scenario reconstructs changed facts from the audit stream inside the E2E suite (the reconstruction contract test itself lives in 0013; this initiative integrates it into the fixture flows).

## Testing Strategy **[CONDITIONAL: Separate Testing Initiative]**

This initiative is testing scope; the TEST_SPEC-strengthening items the audit flagged that land here:
- TEST_SPEC.md:89-93 rewritten to require Job A → B through a real store — the current wording is satisfiable by a canned fake dict and, per the audit, "proves nothing about the store-backed behavior the vision requires".
- TEST_SPEC.md:111-118 E2E items gain executable coverage: MCP-vs-store alignment (R5) and targeted gap resolution via MCP (R6); the audit item follows RKIT-I-0013.
- TEST_SPEC.md:18-25's forbidden list gains the missing `truncate_table` entry (vision section 7 line 533 lists it; the guardrail and manifest already include it — the spec is the outlier).
- A fake-only satisfiability check: no scenario assertion may depend on FakeCareerStore-provided classifications; real-store execution is the certifying tier.

## Alternatives Considered **[REQUIRED]**

- **Wait for the transport and run all E2E over stdio only.** Rejected: it serializes every fixture behind RKIT-I-0014 while most coverage runs in-process today; the in-process adapter is a supported first-class path per RKIT-A-0002, and the parameterized harness upgrades to stdio later without rework.
- **Keep the fake-backed expectations and add real-store runs alongside.** Rejected: retaining canned classifications preserves a green suite that certifies imaginary behavior — the exact failure mode under repair; RKIT-A-0006 authorizes replacing them with strictly stronger real-store assertions.
- **Drive the scenarios through resume-cli instead of MCP.** Rejected: the CLI talks to career-store directly and would bypass the MCP boundary entirely; the TEST_SPEC items under repair are specifically about the MCP surface proving safe, reusable career knowledge.

## Implementation Plan **[REQUIRED]**

1. Write-path smoke extension in `tools/run_smoke.py`.
2. Scenario harness with MCP-seeded real-store fixtures and the driver interface.
3. AWS/GraphQL/architecture fixture scenarios through `call_tool`.
4. Job A → Job B reuse scenario plus the MCP-vs-store alignment diff.
5. TEST_SPEC strengthening edits (real-store language for 89-93, `truncate_table`, executable E2E items).
6. Follow-ons in order of sibling completion: stdio parameterization after RKIT-I-0014; audit-reconstruction wiring after RKIT-I-0013.