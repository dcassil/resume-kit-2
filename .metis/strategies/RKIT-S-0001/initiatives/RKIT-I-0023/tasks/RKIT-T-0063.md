---
id: hallucination-rejection-completion
level: task
title: "hallucination_rejection completion gate in assertCanComplete"
short_code: "RKIT-T-0063"
created_at: 2026-08-15T03:11:05.431420+00:00
updated_at: 2026-08-15T03:26:00.445834+00:00
parent: workflow-deterministic-checkpoint
blocked_by: [RKIT-T-0062]
archived: false

tags:
  - "#task"
  - "#phase/active"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0023
---

# hallucination_rejection completion gate in assertCanComplete

## Parent Initiative

[[RKIT-I-0023]]

## Objective

Add the missing completion gate (RKIT-I-0023 Requirement 4, Detailed Design "Hallucination-rejection gate"): assertCanComplete's required_gates gains `hallucination_rejection`, reading PERSISTED operation statuses (resume-core-owned lifecycle per RKIT-A-0006 item 3) and failing completion while any hallucination-flagged proposal lacks a rejected terminal status — satisfying workflow/TEST_SPEC.md:70's until-now-unenforced invalid-transition rule.

## Acceptance Criteria

## Acceptance Criteria

- [ ] required_gates includes `hallucination_rejection`; the gate reads persisted operation statuses from run state (grounded per T-0061 — no caller-asserted booleans).
- [ ] Completion FAILS with a named blocking reason while any proposal flagged as ungrounded/hallucinated is not in a rejected terminal state; completion succeeds once every flagged proposal is persisted as rejected.
- [ ] The flagged/rejected determination uses the resume-core operation lifecycle statuses (validated/rejected from validateChange GROUNDING failures) — workflow reads, never re-adjudicates.
- [ ] Contract tests: flagged+non-rejected → cannot complete (named reason); flagged+rejected → completes; no flagged proposals → gate passes vacuously.
- [ ] PR + smoke gates green; no weakening of any existing assertion.

## Implementation Notes

### Technical Approach

Gate function beside the existing required_gates entries; reads the run's persisted operation records (whatever the smoke/CLI path currently persists for proposals — extend the persisted shape minimally if statuses aren't yet recorded, honestly, as run-state evidence per T-0061).

### Dependencies

RKIT-T-0062 (state machine reaches the completion gate legitimately).

### Risk Considerations

If current smoke persists no proposal statuses, the gate must not fabricate them — record real validateChange outcomes in the smoke driver path (producer fix).

### Execution profile

Recommended Agent: opus + medium

Rationale: single gate on decided semantics; judgment is in the persisted-status plumbing.

## Status Updates

- 2026-08-15: Added workflow plumbing plan: persist operation status records from checkpoint results, add `hallucination_rejection` to `assertCanComplete`, and cover flagged/non-rejected, flagged/rejected, and no-flag cases in workflow contract tests. Protected `tools/run_smoke.py` was inspected read-only and does not currently drive workflow completion.
