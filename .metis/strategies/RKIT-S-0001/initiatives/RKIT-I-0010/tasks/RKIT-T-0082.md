---
id: full-list-filter-mapping-argument
level: task
title: "Full-list filter mapping + argument fidelity: dedupe_key, include_conflicts, evidence_id (R3-R5)"
short_code: "RKIT-T-0082"
created_at: 2026-08-16T19:05:18.808731+00:00
updated_at: 2026-08-16T19:19:07.272203+00:00
parent: harden-career-mcp-tool-argument
blocked_by: [RKIT-T-0081]
archived: false

tags:
  - "#task"
  - "#phase/completed"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0010
---

# Full-list filter mapping + argument fidelity (R3–R5)

## Parent Initiative

[[RKIT-I-0010]]

## Objective **[REQUIRED]**

Kill the silent-data-loss paths in `career-mcp/career_mcp/__init__.py`: (R3) `search_facts` keeps only `arguments['verification'][0]` / `arguments['types'][0]` (~66-69) — a search for `['user_verified','source_stated']` empirically drops all source_stated facts; (R4) `dedupe_key` (~106-114) and `include_conflicts` (get_fact fallback ~85) are schema-accepted but silently discarded; (R5) `evidence_id` is optional and dropped (~129-133) though TEST_SPEC.md:53 requires rejecting missing evidence for verification operations that require it. Add the consumed-arguments assertion so future silently-dropped-argument bugs become test failures.

## Acceptance Criteria

## Acceptance Criteria

## Acceptance Criteria **[REQUIRED]**

- [ ] `career.search_facts` honors the FULL `verification` and `types` lists with union semantics. Store note: `store.searchFacts` ignores a type filter server-side (career-store/career_store/store.py:176-178) — the adapter post-filters returned facts by type and verification so MCP results are correct regardless; it never silently narrows. Union-semantics contract test pins `['user_verified','source_stated']` returning both.
- [ ] `dedupe_key` forwarded to the store on propose_fact; same key twice yields one fact or a typed error (idempotent-retry contract). If the store cannot honor it, the tool returns typed `validation_error` naming the unsupported argument — never a silent drop.
- [ ] `include_conflicts=true` observably changes `career.get_fact` output (conflict records included); forwarded, not dropped.
- [ ] `career.verify_fact`: when the requested verification state requires evidence, absent `evidence_id` → typed `validation_error`; present → forwarded to the store. Which states require evidence: consult career-store's verification transition engine (structural authorities from RKIT-I-0006) — do not invent a policy table in MCP; policy SEMANTICS stay RKIT-I-0012's.
- [ ] Per-tool accepted-arguments table drives forwarding; an assertion (test or runtime) fails any tool call whose validated arguments contain keys dispatch does not consume — with a test proving it catches a planted dropped argument.
- [ ] Contract tests for each fidelity case; all built on T-0081's envelope (typed errors asserted by `error.type`).
- [ ] `--pr` and `--smoke` green; verify clean.

## Implementation Notes **[CONDITIONAL: Technical Task]**

### Technical Approach
- Check what the real store's searchFacts/upsertFact/verifyFact/findConflicts signatures actually accept (public surface only) before wiring forwarding; where the store genuinely lacks a parameter (e.g. dedupe_key), implement the honest adapter-side behavior (search-before-insert is NOT allowed if it invents semantics — prefer typed validation_error naming the unsupported argument, per R4's fallback) and document for RKIT-I-0011.
- Recommended Agent: opus + medium

### Dependencies
RKIT-T-0081 (envelope helper). Serial (same file).

### Risk Considerations
- PROTECTED read-only: tools/*, tests/boundary/*. Manifest edits go to the canonical package copy + sync tool.
- Do not modify career-store in this task; store-side filter support is career-store scope (note gaps for RKIT-I-0011).

## Status Updates **[REQUIRED]**

- 2026-08-16: T-0081 committed (envelope + taxonomy; gates 417/smoke/verify green; driver probed real-store envelope). Codex launched on this task: full-list union filters w/ adapter post-filter, dedupe_key forward-or-typed-reject (no search-before-insert emulation), include_conflicts via public findConflicts composition, evidence requirement derived from the store transition engine, accepted-arguments assertion.