---
id: conflict-lifecycle
level: task
title: "Conflict lifecycle: adjudicateConflict routing through the verification engine"
short_code: "RKIT-T-0055"
created_at: 2026-08-15T02:07:49.717199+00:00
updated_at: 2026-08-15T02:30:56.546387+00:00
parent: conflict-audit-recovery-and
blocked_by: [RKIT-T-0054]
archived: false

tags:
  - "#task"
  - "#phase/completed"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0008
---

# Conflict lifecycle: adjudicateConflict routing through the verification engine

## Parent Initiative

[[RKIT-I-0008]]

## Objective

Give conflicts their workflow half (RKIT-I-0008 Requirement 1, Detailed Design "Conflict lifecycle"): conflicts transition open → resolved | dismissed via `adjudicateConflict(conflictId, decision, provenance)`; resolution never deletes or overwrites competing claims; adjudication affecting a fact routes through RKIT-I-0006's transition engine, never direct writes.

## Acceptance Criteria

## Acceptance Criteria

## Acceptance Criteria

- [ ] Registry migration adds status (open/resolved/dismissed, default open), resolution_provenance, resolved_at, winning_claim_ref to conflict rows — original claim payloads never rewritten.
- [ ] `adjudicateConflict(conflictId, decision, provenance)`: validates provenance structurally, appends the adjudication, typed errors for unknown conflict/invalid decision/already-adjudicated (or idempotent re-adjudication with the same decision — choose and document); transactional.
- [ ] Both competing claims remain retrievable post-resolution (evidence intact); the adjudication is recorded, not an overwrite.
- [ ] When the decision affects a fact's value or verification state, the change is emitted as a call into the I-0006 transition engine with the appropriate authority — observed by test as an engine call, never a direct verification_state write.
- [ ] An adjudication interaction row may be recorded via T-0054's substrate (adjudication provenance trail) — if implemented, through recordInteraction only.
- [ ] Store surface entry DEFERRED to the protected approval batch; PR + smoke + migration checks green; no weakening of any existing assertion.

## Implementation Notes

### Technical Approach

Migration 009 for the lifecycle columns. adjudicateConflict lives in store.py routed through the transaction substrate; engine routing reuses the T-0045 chokepoint with explicit_user_correction/user-provenance authorities as appropriate.

### Dependencies

RKIT-T-0054 (interaction recording available for the adjudication trail).

### Risk Considerations

Decision-to-authority mapping is the judgment point: a user-provenance adjudication that confirms one claim maps to the affirmed-proposal/correction authorities; agent-only adjudication must NOT be able to change verification state (engine will reject — test that).

### Execution profile

Recommended Agent: opus + high

Rationale: workflow semantics bridging two engines (conflict lifecycle + verification transitions) with no-overwrite retention invariants.

## Status Updates

*To be added during implementation*

- 2026-08-15: Implemented migration 009 (`009_conflict_lifecycle`) for conflict lifecycle columns and added transactional `CareerStore.adjudicateConflict(...)` routing optional verification-state changes through the T-0045 verification engine. Adjudication appends resolution metadata and an `answer_recorded` interaction via the interaction substrate; original conflict claim/evidence payloads are preserved. Added unit coverage for resolve, dismiss, idempotent replay, conflicting re-adjudication, engine-call observation, and agent-only rejection. Required gates run: PR gate pass, smoke gate pass, full unit discovery pass, migration checks pass. Straight Jacket verify still reports pre-existing protected checksum mismatches in `tools/pre-commit-resume-cli-guardrails.sh`, `tools/run_tests.py`, and `tools/TEST_SPEC.md`; this task did not modify those files.