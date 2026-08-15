---
id: verification-transition-engine
level: task
title: "Verification transition engine: data-declared matrix, typed errors, transition evidence"
short_code: "RKIT-T-0045"
created_at: 2026-08-15T00:37:23.604045+00:00
updated_at: 2026-08-15T00:37:23.604045+00:00
parent: evidence-backed-fact-and
blocked_by: ["RKIT-T-0044"]
archived: false

tags:
  - "#task"
  - "#phase/todo"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0006
---

# Verification transition engine: data-declared matrix, typed errors, transition evidence

## Parent Initiative

[[RKIT-I-0006]]

## Objective

Build the single verification transition engine (RKIT-I-0006 Requirement 3, Detailed Design "Transition engine"): a data-declared matrix `{(from, to) → required authority}` over the canonical five-state set, evaluated in one chokepoint, with typed `DisallowedTransitionError(from, to, requiredAuthority)` and an append-only transition evidence row for every allowed transition.

## Acceptance Criteria

- [ ] A module-level exported transition matrix declares every allowed (from, to) edge with its required authority: inferred→user_verified requires an affirmed user-provenance proposal; inferred→source_stated requires source-document evidence (closing store.py:318-345); imported enters only via the import path; user_verified downgrades only via explicit user-provenance correction; everything else is disallowed.
- [ ] One chokepoint function evaluates the matrix; typed `DisallowedTransitionError` names from/to/requiredAuthority; the matrix constant is exported so tests can assert the FULL edge set.
- [ ] Every allowed transition appends an evidence row `{factId, priorState, newState, authorityKind, provenanceRefs, createdAt}` — append-only, no updates; runs inside the T-0042 transaction substrate.
- [ ] Authority validation: user-provenance affirmed proposal (from T-0044 DTO), source-document evidence ref, import provenance — each authority kind checked structurally, not by string sniffing.
- [ ] Unit tests assert the full matrix (allowed AND disallowed edges) and the evidence-row content for a representative allowed transition of each authority kind.
- [ ] PR + smoke gates green; no weakening of any existing assertion.

## Implementation Notes

### Technical Approach

New `career_store/verification.py` (or similar): matrix constant + evaluate(from, to, authority) chokepoint. This task builds the engine and its tests; T-0046 rewires the public surfaces through it (some wiring here is fine if it keeps gates green, but the full sweep incl. downgrade protection is T-0046's).

### Dependencies

RKIT-T-0044 (proposal DTO is the user-provenance authority input).

### Risk Considerations

Do not let two gating paths coexist silently — if old inline checks remain until T-0046, mark them clearly. Evidence rows must use deterministic ids per store convention.

### Execution profile

Recommended Agent: opus + high

Rationale: the honesty chokepoint for all of career-store; matrix/authority design is consumed by verify, import, and merge.

## Status Updates

*To be added during implementation*
