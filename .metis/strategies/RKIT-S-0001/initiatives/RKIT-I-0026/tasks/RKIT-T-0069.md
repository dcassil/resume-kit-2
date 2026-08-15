---
id: single-rerun-discipline-over-the
level: task
title: "Single-rerun discipline over the watermark with multi-iteration deadlock regression"
short_code: "RKIT-T-0069"
created_at: 2026-08-15T04:05:15.568002+00:00
updated_at: 2026-08-15T04:17:08.192303+00:00
parent: workflow-requirement-resolution
blocked_by: [RKIT-T-0068]
archived: false

tags:
  - "#task"
  - "#phase/active"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0026
---

# Single-rerun discipline over the watermark with multi-iteration deadlock regression

## Parent Initiative

[[RKIT-I-0026]]

## Objective

Enforce the single-rerun discipline (RKIT-I-0026 Detailed Design "Single-rerun discipline") on the T-0068 loop: a batch of newly verified facts (watermark delta non-empty) triggers exactly ONE MATCH_BASE rerun; the watermark update on rerun completion makes a second rerun from the same facts impossible; the multi-iteration contract regression proves the section-14 tail is reachable across successive fact batches.

## Acceptance Criteria

## Acceptance Criteria

- [ ] Watermark-delta check drives the rerun decision through the T-0068 predicate; identical fact batch CANNOT trigger two reruns (contract test).
- [ ] Multi-iteration simulation contract test: two successive fact batches → two reruns total (one each) → decision continue → BUILD_SELECTION_PLAN reached and traversal proceeds toward COMPLETE's gate — the direct regression for the audited non-termination under multi-batch conditions.
- [ ] iteration_count increments per rerun; facts_since_last_match resets with the watermark; loop-state persistence remains lossless mid-iteration.
- [ ] No cumulative facts_verified destruction (audit data preserved — re-assert).
- [ ] PR + smoke gates green; no weakening of any existing assertion.

## Implementation Notes

### Technical Approach

Mostly wiring the T-0062 watermark into the T-0068 predicate evaluation point plus tests; the mechanism exists — this task makes the loop policy consume it exactly once per batch.

### Dependencies

RKIT-T-0068 (predicate + loop state).

### Risk Considerations

Ordering: watermark must update at rerun COMPLETION (not scheduling) or a failed rerun would swallow the batch.

### Execution profile

Recommended Agent: opus + medium

Rationale: focused wiring + regression authorship on decided mechanics.

## Status Updates

- 2026-08-14: Implemented pending-resolution-rerun tracking so `iteration_count` increments only when a RESOLVE_GAPS -> MATCH_BASE rerun completes. Added contract coverage for identical-batch single-rerun discipline and two successive fact batches reaching BUILD_SELECTION_PLAN and COMPLETE's gate while preserving cumulative `facts_verified`. Verification passed: `python3 tools/run_gate.py --pr --root .`, `python3 tools/run_gate.py --smoke --root .`, and `python3 -m unittest discover -s tests/unit -v`.
