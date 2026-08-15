---
id: mergefacts-with-alias-history
level: task
title: "mergeFacts with alias/history retention and id redirects"
short_code: "RKIT-T-0047"
created_at: 2026-08-15T00:37:23.698688+00:00
updated_at: 2026-08-15T01:06:02.716209+00:00
parent: evidence-backed-fact-and
blocked_by: [RKIT-T-0046]
archived: false

tags:
  - "#task"
  - "#phase/active"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0006
---

# mergeFacts with alias/history retention and id redirects

## Parent Initiative

[[RKIT-I-0006]]

## Objective

Implement fact merging per vision section 6 (RKIT-I-0006 Requirement 4, Detailed Design "Merge design"): `mergeFacts(survivorId, mergedId, provenance)` retains the losing fact's terms as aliases, preserves ALL evidence rows for both facts, records the merge in history, installs an id redirect so the merged-away id resolves to the survivor, and never escalates verification state outside the T-0045 engine.

## Acceptance Criteria

## Acceptance Criteria

- [ ] `mergeFacts(survivorId, mergedId, provenance)` exists as a store method: merged fact's normalized terms move into the survivor's alias set (alias relationships + the canonical_name/description columns from I-0005); typed `MergeConflictError` on invalid merges (unknown ids, self-merge, already-merged).
- [ ] Zero evidence rows lost: all evidence for both facts remains queryable under the survivor after merge.
- [ ] Evidence and job-match references re-point to the survivor; a merge history row records survivor/merged/provenance/timestamp; getFact(mergedId) resolves to the survivor (id redirect).
- [ ] Merge never silently escalates verification: survivor state follows the engine (e.g. merging an inferred fact into a user_verified survivor leaves user_verified; the reverse cannot promote).
- [ ] Runs atomically on the T-0042 transaction substrate; interruption leaves no partial merge.
- [ ] New store surface entry deferred if the protected guardrail pins the function set (expected — same batch as getMigrationState); the method + tests work regardless.
- [ ] PR + smoke gates green; no weakening of any existing assertion.

## Implementation Notes

### Technical Approach

Registry migration if a merge-history/redirect table is needed (one-line append to migrations.py). Redirect via a merged_into column or redirect table consulted by getFact/searchFacts. Deterministic ids for history rows.

### Dependencies

RKIT-T-0046 (engine-mediated state semantics final). I-0005 columns + transactions.

### Risk Considerations

Guardrail ALLOWED_SURFACES will reject a public mergeFacts manifest entry — defer the manifest declaration (T-0039 pattern), implement + test via the method. RKIT-I-0007 depends on the alias/evidence trail — retention correctness is load-bearing.

### Execution profile

Recommended Agent: opus + high

Rationale: destructive-operation semantics with retention invariants; irreversible data-shape decisions consumed by I-0007 matching.

## Status Updates

- 2026-08-15: Implemented `mergeFacts` in career-store with alias retention, evidence/job-match repointing, deterministic `fact_merges` history, `facts.merged_into_fact_id` redirects, redirect-aware `getFact`/`searchFacts`, and `MergeConflictError`. Added focused unit tests for retention, redirected-id search, no verification promotion, typed conflicts, and transaction rollback after injected interruption. Requested PR/smoke/unit/migration validations pass; `store_surface.json` remains intentionally deferred/protected.
