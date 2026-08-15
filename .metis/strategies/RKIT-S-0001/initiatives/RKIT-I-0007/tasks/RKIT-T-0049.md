---
id: typed-candidate-generation-direct
level: task
title: "Typed candidate generation: direct vs traversal, dictionary deletion, pollution fix"
short_code: "RKIT-T-0049"
created_at: 2026-08-15T01:23:28.279934+00:00
updated_at: 2026-08-15T01:35:37.674003+00:00
parent: relationship-aware-matching-and
blocked_by: []
archived: false

tags:
  - "#task"
  - "#phase/completed"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0007
---

# Typed candidate generation: direct vs traversal, dictionary deletion, pollution fix

## Parent Initiative

[[RKIT-I-0007]]

## Objective

Fix the CRITICAL related-term pollution and the compiled-in alias dictionary (RKIT-I-0007 Requirements 1-2): `_fact_match_terms`/`_relationship_terms` no longer fold relationship-linked terms into a fact's direct term set; matching produces typed candidates (direct terms → exact; relationship traversal → candidates labeled by the relationship path); the compiled alias/service dictionaries are deleted and alias lookup is stored-relationship traversal only.

## Acceptance Criteria

## Acceptance Criteria

## Acceptance Criteria

- [x] Direct-term candidates and relationship-traversal candidates are generated separately; the candidate DTO carries `matchType` (exact_match|verified_fact_match|alias_match|related_match|possible_match) and `viaRelationships` [{relationshipId, type, confirmationStatus}] for every non-exact candidate (Detailed Design DTO).
- [x] THE AUDIT REGRESSION: with a related Azure→AWS relationship and allow_related_as_equivalent=False, the Azure fact yields at most related_match for an AWS requirement, no exact_match/alias_match appears, and the requirement is reported unresolved — outcome-asserted, not string-absence.
- [x] The compiled alias/service dictionaries are deleted; grep clean. Regression: "system design" does not resolve "API architecture" as exact_match absent a stored, confirmed relationship; the fixture pairs the dictionary satisfied (aws/graphql/node/postgres) no longer match without stored relationships.
- [x] Bounded traversal (depth 1) per the Detailed Design; deterministic candidate ordering.
- [x] Cross-job reuse preserved: existing recordJobMatch/findCandidateMatches behaviors that were legitimate keep working (verified_fact_match from user_verified facts on direct terms).
- [x] PR + smoke gates green; migration checks green; snapshot/fixture realignments (I-0051 baselines noted two scorer quirks tied to this area) reviewed and justified as strictly-more-honest.
- [x] No weakening of any existing assertion (the vacuous Azure string-absence contract test is REPLACED in T-0053; if it breaks here, strengthen it now instead — never weaken).

## Implementation Notes

### Technical Approach

Rework in store.py/store_support.py: candidate generation computes direct-term matches first, then one-hop relationship traversal emitting typed candidates. The policy mapping (relationship type, confirmation status, config) → permitted matchType arrives fully in T-0050; here apply the existing config flags honestly (related never exact; alias from stored alias relationships — confirmation enforcement tightens in T-0050). Keep the store's no-scoring boundary: emit typed candidates, never scores.

### Dependencies

I-0006 complete (gated verification states as inputs). First task of the I-0007 serial chain.

### Risk Considerations

The I-0051 snapshot baselines knowingly recorded two scorer quirks in this area (job-b empty matched_fact_ids; post-graphql resolving from resume evidence) — fixing pollution may change those baselines; review diffs as strictly-more-honest and note them. Smoke drives matching through workflow.

### Execution profile

Recommended Agent: opus + high

Rationale: the initiative's critical honesty defect; candidate-DTO shape is consumed by all later chunks and by resume-core.

## Status Updates

- 2026-08-15: Removed compiled dictionary expansion from term normalization and deleted the service alias constants from `terms.py`; aliases now require stored relationship traversal.
- 2026-08-15: Reworked `findCandidateMatches` support data so direct own-term candidates carry `matchType`/`terms` with an empty relationship path, while one-hop relationship candidates carry `viaRelationships` with relationship ID/type and `confirmationStatus`. The current schema does not yet expose a confirmation-status column, so candidates use the required `"unconfirmed"` placeholder when absent.
- 2026-08-15: Strengthened the Azure/AWS contract regression to outcome assertions and added dictionary-removal regressions for system-design/API-architecture plus AWS, GraphQL, Node, and Postgres pairs.
- 2026-08-15: Full verification completed: PR gate, smoke gate, unit discovery, migration checks, two snapshot regeneration runs, fixture expected stat, and deleted-symbol grep passed. Snapshot regeneration produced no `fixtures/expected` diff.