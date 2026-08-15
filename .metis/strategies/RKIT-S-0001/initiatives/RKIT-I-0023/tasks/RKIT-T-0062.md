---
id: match-watermark-and-terminating
level: task
title: "Match watermark and terminating RESOLVE_GAPS loop-back with deadlock regression"
short_code: "RKIT-T-0062"
created_at: 2026-08-15T03:11:05.376990+00:00
updated_at: 2026-08-15T03:26:00.041280+00:00
parent: workflow-deterministic-checkpoint
blocked_by: [RKIT-T-0061]
archived: false

tags:
  - "#task"
  - "#phase/completed"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0023
---

# Match watermark and terminating RESOLVE_GAPS loop-back with deadlock regression

## Parent Initiative

[[RKIT-I-0023]]

## Objective

Fix the verified non-terminating RESOLVE_GAPS→MATCH_BASE loop (RKIT-I-0023 Requirement 3, Detailed Design "Loop-termination substrate"): run state gains `last_match_fact_watermark` snapshotting facts_verified at each completed MATCH_BASE; loop-back fires only when facts exist beyond the watermark; BUILD_SELECTION_PLAN through COMPLETE become reachable after gap resolution.

## Acceptance Criteria

## Acceptance Criteria

## Acceptance Criteria

- [ ] Run state records `last_match_fact_watermark` (snapshot of facts_verified at the most recent completed MATCH_BASE); MATCH_BASE completion updates it.
- [ ] The loop-back condition (old workflow/__init__.py:76-77 cumulative facts_verified keying) becomes "facts beyond watermark exist" — cumulative facts_verified is PRESERVED as audit data (the rejected alternative was clearing it; do not).
- [ ] DEADLOCK REGRESSION (the audit's verified simulation): verify a fact → rerun MATCH_BASE → assert BUILD_SELECTION_PLAN is reachable and the machine can traverse to COMPLETE's gate; with no new facts beyond the watermark, loop-back does NOT fire.
- [ ] Watermark persists across run-state save/load (recoverRun sees it); mechanism only — no resolution policy (RKIT-I-0026's scope).
- [ ] PR + smoke gates green; no weakening of any existing assertion.

## Implementation Notes

### Technical Approach

Watermark as a run-state field flowing through the I-0022-validated persistence. Loop-back comparison on fact identity sets (or counts if identity unavailable — prefer sets for correctness under out-of-order verification; state the choice).

### Dependencies

RKIT-T-0061 (grounded advances — MATCH_BASE completion is now a grounded, recorded event to hang the watermark on).

### Risk Considerations

Legacy persisted runs without the watermark field: treat as watermark-at-zero (loop-back may fire once more — honest) — document the choice.

### Execution profile

Recommended Agent: opus + medium

Rationale: focused control-flow fix with the design decided; judgment is in watermark representation.

## Status Updates

2026-08-15:
- Implemented `last_match_fact_watermark` as a persisted list of fact IDs compared with set semantics.
- Updated RESOLVE_GAPS loop-back to fire only when `facts_verified - last_match_fact_watermark` is non-empty; `facts_verified` remains cumulative audit data.
- `recordCheckpointResult(..., "MATCH_BASE", ...)` snapshots the current verified-fact set into the watermark.
- `recoverRun` returns the persisted watermark; missing legacy field defaults to an empty watermark, so legacy runs may loop once more.
- Added regression coverage for the verified deadlock path and watermark persistence/legacy behavior.
- Validation run:
  - `python3 tools/run_gate.py --pr --root .` passed, 365 tests.
  - `python3 tools/run_gate.py --smoke --root .` passed.
  - `python3 -m unittest discover -s tests/unit -v` passed, 189 tests.
  - `straight-jacket verify --json` still reports pre-existing protected checksum mismatches in `tools/pre-commit-resume-cli-guardrails.sh`, `tools/run_smoke.py`, `tools/run_tests.py`, and `tools/TEST_SPEC.md`; none were edited for this task.