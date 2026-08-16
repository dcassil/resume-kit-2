---
id: delete-snake-case-dual-dispatch
level: task
title: "Delete snake_case dual dispatch: single camelCase store-surface routing (R1)"
short_code: "RKIT-T-0084"
created_at: 2026-08-16T19:25:47.570560+00:00
updated_at: 2026-08-16T19:27:10.014325+00:00
parent: align-career-mcp-semantics-with
blocked_by: []
archived: false

tags:
  - "#task"
  - "#phase/active"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0011
---

# Delete snake_case dual dispatch: single camelCase store-surface routing (R1)

## Parent Initiative

[[RKIT-I-0011]]

## Objective **[REQUIRED]**

Remove the audit's root-cause defect in `career-mcp/career_mcp/__init__.py`: the adapter prefers a private snake_case store dialect (`search_facts`/`get_fact`/`propose_fact`/... preference sites formerly at :62,82,103,118,126,137,152,163 — re-locate in the current post-I-0010 file) that only the test FakeCareerStore implements. After this task the adapter calls ONLY the declared camelCase `store_surface.json` surface (`searchFacts`/`getFact`/`upsertFact`/`verifyFact`/`addEvidence`/`addRelationship`/`findCandidateMatches`) via a per-tool mapping table; DTO conversion at the boundary is shape-only (key naming, sensitive-field stripping); vocabulary passes through untranslated (no drift-hiding translation shim — RKIT-A-0006).

## Acceptance Criteria

## Acceptance Criteria **[REQUIRED]**

- [ ] Every snake_case store-method preference/dispatch branch is deleted; a grep for the snake_case store method names in career_mcp production code returns nothing (except MCP tool names themselves, which are `career.snake_case` by contract — only STORE-method dialect goes).
- [ ] Per-tool mapping table routes each career.* tool to its declared store function; `career.get_unverified` and `career.find_matches` route through declared surfaces (semantic fixes to their OUTPUT are RKIT-T-0086 — keep current output shape where tests pin it).
- [ ] All RKIT-I-0010 behaviors survive on the single path: envelope invariant, taxonomy, full-list union post-filtering, dedupe_key typed rejection, include_conflicts composition, evidence_id gate, TOOL_ARGUMENTS assertion (their tests must stay green, adjusted only where they explicitly drove the fake path).
- [ ] Existing fake-path contract tests: minimally repaired to keep the suite green THIS task (full rewrite to real-store tier is RKIT-T-0085) — where a test's fake lacks camelCase methods, either upgrade the fake mechanically or switch the test to the real store; do NOT weaken assertions.
- [ ] `--pr` and `--smoke` green; verify clean; career_mcp_guardrails passes.

## Implementation Notes **[CONDITIONAL: Technical Task]**

### Technical Approach
- The real store path already exists as the "fallback" — this is mostly branch deletion plus making the mapping table explicit. Watch get_unverified (currently queries verification_state='unknown' only) — keep behavior, don't fix here.
- Recommended Agent: opus + high

### Dependencies
None within I-0011 (first task). Serial chain T-0084→0085→0086 (same files).

### Risk Considerations
- PROTECTED read-only: tools/*, tests/boundary/*. Canonical manifest + sync tool discipline (RKIT-I-0009) applies to any manifest edit.
- Smoke drives the MCP registry — run --smoke, not just --pr.

## Status Updates **[REQUIRED]**

- 2026-08-16: I-0010 complete (v0.16.0 pushed 5ec4ee1). I-0011 decomposed T-0084..0086. Driver verified: store CODE accepts parent/child/contradicts (_RELATIONSHIP_TYPES store.py:79) but protected career_store_guardrails.py:49/178 pins store_surface.json to the 4-type set — parent/child re-advertisement deferred to approval batch; T-0086 scoped accordingly. Codex launched on dual-dispatch deletion.