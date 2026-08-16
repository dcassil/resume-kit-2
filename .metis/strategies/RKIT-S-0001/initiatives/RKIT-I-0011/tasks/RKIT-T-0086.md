---
id: find-matches-coherence-get
level: task
title: "find_matches coherence, get_unverified breadth, real filtering, enum parity + TEST_SPEC language (R3-R6) — close-out"
short_code: "RKIT-T-0086"
created_at: 2026-08-16T19:25:47.686789+00:00
updated_at: 2026-08-16T19:25:47.686789+00:00
parent: align-career-mcp-semantics-with
blocked_by: ["RKIT-T-0084", "RKIT-T-0085"]
archived: false

tags:
  - "#task"
  - "#phase/todo"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0011
---

# find_matches coherence, get_unverified breadth, filtering, enum parity, TEST_SPEC (R3–R6) — I-0011 close-out

## Parent Initiative

[[RKIT-I-0011]]

## Objective **[REQUIRED]**

Fix the three remaining semantic defects and land the parity substrate: (R3) `career.find_matches` concatenates the store's `matches` + `unresolved` lists while the store places weak matches in BOTH — each weak requirement appears twice with contradictory classifications, one with empty fact_ids and misleading "No confirmed career fact matched" reasoning; (R4) `career.get_unverified` queries only `verification_state='unknown'` and misses inferred facts (vision §7 line 524 requires unresolved/inferred/unknown); (R5) `types`/`verification` filters demonstrably filter on the real store; (R6, PARTIAL) enum parity within currently-declarable sets — full `parent`/`child` re-advertisement is BLOCKED by the protected career_store_guardrails pin on store_surface.json's 4-type relationship set and rides Daniel's approval batch. Plus the TEST_SPEC-language strengthening. Initiative close-out.

## Acceptance Criteria **[REQUIRED]**

- [ ] `find_matches`: one row per requirement `{requirement_id, resolution_state, fact_ids, reasoning}` built from `findCandidateMatches` WITHOUT the matches+unresolved concatenation; weak states (`possible_match`, `unknown`) appear once retaining candidate fact_ids; regression test asserts unique requirement ids and no empty-handed duplicate row.
- [ ] `resolution_state` values drawn only from the canonical section 4.4 set; non-canonical values (e.g. legacy `conflicted`) never leak — if the store emits one, the adapter fails loudly (store_error naming the value), never passes it through; test with a store double emitting a non-canonical state.
- [ ] `get_unverified` returns facts with verification_state in {unknown, inferred} plus unresolved proposals, via declared surfaces only (searchFacts with verification filter is available; if listing unresolved proposals needs a surface the store lacks, return what IS expressible and note the store gap for the approval batch/RKIT-I-0012 — no SQL, no private imports). Regression: an inferred fact IS returned (the audit's empty-Kubernetes-result failure).
- [ ] Filtering: real-store test that `types=['experience']` never returns a skill fact; verification filter equivalent (may already exist from T-0082/0085 — reference, don't duplicate).
- [ ] Enum parity test (three-way, within declarable sets): career-mcp manifest enums == career-store store_surface.json declared sets == canonical contract sets for verification_states and resolution_states; for relationship_types assert manifest == store_surface declared set AND separately assert store-ACCEPTED set (_RELATIONSHIP_TYPES via behavior, not private import) ⊇ declared — with a comment + report note that parent/child re-advertisement is deferred to the approval batch (guardrail-pinned).
- [ ] `career-mcp/TEST_SPEC.md`: "Reject invalid verification states" item requires the REAL store and acknowledges the canonical enum; Job A→B matching case language requires a real store (fake-only satisfaction forbidden). Fixture delivery stays RKIT-I-0015.
- [ ] Mutation probes reported: restore matches+unresolved concatenation → coherence test fails; restore unknown-only get_unverified → inferred-fact regression fails; leak a non-canonical state → parity/leak test fails.
- [ ] `--pr`, `--smoke`, `--future-contract` green; verify clean.

## Implementation Notes **[CONDITIONAL: Technical Task]**

### Technical Approach
- Check how store `findCandidateMatches` output is shaped post-I-0007 (matches/unresolved structure at ~store.py:516-525) before rewriting the merge.
- Recommended Agent: opus + high

### Dependencies
RKIT-T-0084/0085. Final task; after: initiative → completed, bump 0.17.0, push, handoff update (driver).

### Risk Considerations
- PROTECTED read-only: tools/* (career_store_guardrails pins store_surface relationship set — do NOT edit store_surface.json relationship_types), tests/boundary/*.
- Canonical-manifest sync discipline for any manifest edit.

## Status Updates **[REQUIRED]**

*To be added during implementation*
