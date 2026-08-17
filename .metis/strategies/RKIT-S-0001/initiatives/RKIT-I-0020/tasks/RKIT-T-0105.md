---
id: equivalence-handoff-e2e-proposal
level: task
title: "Equivalence handoff E2E: proposal to resume-core validation, boundary tests"
short_code: "RKIT-T-0105"
created_at: 2026-08-17T19:08:37.942769+00:00
updated_at: 2026-08-17T19:20:27.116797+00:00
parent: resume-agent-semantic-equivalence
blocked_by: [RKIT-T-0104]
archived: false

tags:
  - "#task"
  - "#phase/active"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0020
---

# Equivalence handoff E2E: proposal to resume-core validation, boundary tests

## Parent Initiative

[[RKIT-I-0020]]

## Objective

Prove the handoff chain the initiative's E2E requirement demands: a `proposeEquivalences` proposal (fixture-pinned fake adapter) flows to resume-core validation, and only AFTER validation does any relationship exist anywhere — plus boundary tests pinning that resume-agent never imports/calls resume-core or career-store and proposals never carry persisted-relationship or official-truth markers.

## Acceptance Criteria

## Acceptance Criteria

- [ ] E2E test (tests/e2e/ or the established E2E location — check tests/e2e/test_grounded_tailoring_final_validation.py for the pattern): fixture-pinned proposal emitted → validated through the appropriate EXISTING resume-core validation entry point (find the real one; do NOT invent new resume-core surface — if no fitting validator exists, validate via the documented DTO-schema route and assert the proposal is structurally consumable, reporting the gap honestly instead of stubbing) → a career-store relationship for the confirmed pair is created ONLY post-validation using the existing 6-type relationship vocabulary (equivalent/narrower_than/broader_than must map onto the store's declared vocabulary — check store_surface.json; report the mapping used).
- [ ] Negative E2E: an unvalidated/rejected proposal produces NO relationship anywhere (assert store state unchanged).
- [ ] Boundary assertions (non-protected test tier): resume_agent package imports neither resume_core nor career_store (AST/import scan mirroring existing boundary-style unit tests in non-protected tiers); no proposal DTO carries fields implying persistence or official truth (closed field-set assertion on the DTO schema).
- [ ] Asymmetric-direction assertion: a narrower_than proposal (React narrower_than JavaScript-framework-experience) validates in the narrow→broad direction and does NOT authorize the reverse claim — encode whatever resume-core's validation semantics support today and document precisely what is enforced vs deferred.
- [ ] resume-agent/TEST_SPEC.md E2E section (:113 area) updated to name the covering tests.
- [ ] Gates green: `--pr`, `--smoke`, `--future-contract`. No NEW protected edits (T-0104 already made the lockstep ones).

## Implementation Notes

### Technical Approach
Reuse T-0104's fake-adapter fixtures. The store side uses public career-store surfaces only (createRelationship/confirmRelationship path per store_surface.json — whatever the declared vocabulary supports). Keep the E2E in the discovered (non-protected) test tree and bridge into a gate-run module if E2E isn't auto-run — check how tests/e2e/test_grounded_tailoring_final_validation.py is wired into gates.

### Dependencies
RKIT-T-0104 (the surface and fixtures).

### Risk Considerations
Do not let the E2E quietly become a new public surface on resume-core or career-store; if the handoff needs surface that doesn't exist, that's a finding to report (and defer), not to build here.

Recommended Agent: opus + medium

## Status Updates

*To be added during implementation*