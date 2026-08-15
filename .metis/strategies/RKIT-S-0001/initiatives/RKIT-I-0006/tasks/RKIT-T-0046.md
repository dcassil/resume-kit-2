---
id: rewire-verify-confirm-surface-and
level: task
title: "Rewire verify/confirm surface and import path through the engine; downgrade protection"
short_code: "RKIT-T-0046"
created_at: 2026-08-15T00:37:23.651390+00:00
updated_at: 2026-08-15T01:06:02.320201+00:00
parent: evidence-backed-fact-and
blocked_by: [RKIT-T-0045]
archived: false

tags:
  - "#task"
  - "#phase/completed"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0006
---

# Rewire verify/confirm surface and import path through the engine; downgrade protection

## Parent Initiative

[[RKIT-I-0006]]

## Objective

Route every verification-state write through the T-0045 engine (RKIT-I-0006 Requirement 3's enforcement half): verifyFact, the upsert merge precedence path, and the import path all use the chokepoint; no inline state assignment remains; user_verified never downgrades except by explicit user-provenance correction and persists across store reopen and job sessions (TEST_SPEC:70-71).

## Acceptance Criteria

## Acceptance Criteria

## Acceptance Criteria

- [ ] verifyFact accepts only engine-mediated transitions: inferred→user_verified with affirmed user-provenance proposal succeeds; inferred→source_stated with agent-only provenance FAILS typed (the audited ungated escalation); inferred→source_stated with source-document evidence succeeds.
- [ ] The upsertFact merge-precedence logic (store.py:885-905 era) cannot silently change verification state outside the engine; incoming lower-authority states never overwrite user_verified.
- [ ] The import path enters facts as `imported` via its own authority; nothing else can write `imported`.
- [ ] Downgrade protection: user_verified→anything without explicit user-provenance correction raises typed errors; with correction it succeeds and writes the transition evidence row.
- [ ] Cross-session persistence test: user_verified facts stay user_verified across store close/reopen and across distinct job sessions.
- [ ] A sweep (grep) proves no remaining direct verification_state assignment outside the engine chokepoint and migrations.
- [ ] PR + smoke gates green; producers (workflow/CLI/mcp) fixed minimally if they relied on ungated writes; no weakening of any existing assertion.

## Implementation Notes

### Technical Approach

Replace inline state writes in store.py with engine calls carrying the appropriate authority object. The remap migration (005) is exempt (data migration, not runtime writes). Keep result shapes additive.

### Dependencies

RKIT-T-0045 (engine + matrix).

### Risk Considerations

Smoke drives verifyFact through the workflow — the free-text-to-proposal migration from T-0044 plus this gating may require workflow/CLI producer updates in the same change. Never loosen the engine to keep a producer green.

### Execution profile

Recommended Agent: opus + medium

Rationale: substantive rewiring but the engine and DTO decisions are already made; reasoning is in sweep completeness and producer fixes.

## Status Updates

- 2026-08-15: Rewired `upsertFact` create/merge transitions to call `evaluate_verification_transition` with source-document, import, inference, or user-confirmation authority before persisting state. `user_verified` merge precedence is now an engine-mediated promotion or a no-op; lower-authority incoming state cannot overwrite it.
- 2026-08-15: Rewired `verifyFact` source-stated transitions to source-document authority and user_verified downgrades to explicit-user-correction authority. Added focused unit coverage for source-stated evidence, import provenance, downgrade protection, upsert merge precedence, and reopened-store/job-session persistence.