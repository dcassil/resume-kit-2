---
id: five-point-interruption-contract
level: task
title: "Five-point interruption contract-test matrix + TEST_SPEC recovery strengthening"
short_code: "RKIT-T-0078"
created_at: 2026-08-16T18:09:42.455795+00:00
updated_at: 2026-08-16T18:38:37.356285+00:00
parent: workflow-recovery-and-idempotency
blocked_by: [RKIT-T-0074, RKIT-T-0075, RKIT-T-0076, RKIT-T-0077]
archived: false

tags:
  - "#task"
  - "#phase/active"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0025
---

# Five-point interruption contract-test matrix + TEST_SPEC recovery strengthening

## Parent Initiative

[[RKIT-I-0025]]

## Objective **[REQUIRED]**

Close out RKIT-I-0025 with the full contract-test matrix over the five TEST_SPEC interruption points (workflow/TEST_SPEC.md "Failure Recovery Test Cases": job ingest, user verification, proposed operations, partially applied operation sequence, render overflow) — today ZERO such tests exist despite the spec claiming them — and strengthen workflow/TEST_SPEC.md's recovery section so every spec assertion names its covering test. Initiative close-out: version bump + mutation probes.

## Acceptance Criteria

## Acceptance Criteria **[REQUIRED]**

- [ ] One contract-test module (e.g. tests/contract/test_workflow_recovery_matrix.py — contract tests are NOT protected) simulating interruption at each of the five points. Per point, assert ALL spec assertions: resumes from persisted deterministic state; career_db/base_resume/rejected_operations integrity verified with evidence; no re-asked question, re-written fact, or re-applied operation; correct computed rerun set for that point (job ingest → {}; user verification → {}; proposed operations → {} or per-map; partially applied sequence → {GROUNDING_AUDIT, FINAL_MATCH}; render overflow → {RENDER, RENDER_VALIDATION}); COMPLETE blocked until reruns recorded post-recovery.
- [ ] Regression tests present (from T-0074..0077, add here if missing): store-double invalid → integrity failed (line-401 literal regression); unknown run → UnknownRunError (line-385 fabrication regression); COMPLETE-blocked-until-rerun (line-387/198-212 regression); rejected-then-applied scan failure.
- [ ] workflow/TEST_SPEC.md (UNPROTECTED — distinct from tools/TEST_SPEC.md) recovery section strengthened: five-point matrix enumerated with explicit per-point cases matching the new module; spec claims match the suite (audit-flagged gap).
- [ ] Mutation probes run and reported: (1) restore the `"valid"` literal → matrix fails; (2) restore hardcoded `['FINAL_MATCH']` → matrix fails; (3) skip a required rerun before COMPLETE → gate test fails; (4) re-apply an applied operation silently → duplicate-detection test fails.
- [ ] New test modules listed for the DEFERRED run_tests.py approval batch (do not edit protected tools/run_tests.py); confirm the behaviors are also exercised via discovered contract tests in the PR gate.
- [ ] `--pr`, `--smoke`, AND `--future-contract` green (close-out chunk).

## Implementation Notes **[CONDITIONAL: Technical Task]**

### Technical Approach
- Simulate interruption by driving createRun→advance/record to the target checkpoint, then constructing a fresh recovery via recoverRun on the persisted state — no process-kill machinery needed; persistence IS the interruption boundary.
- Reuse the smoke/CLI workspace fixtures for a realistic run; store doubles per T-0075's injection seam.
- Recommended Agent: opus + medium

### Dependencies
RKIT-T-0074..0077 (all recovery behavior). Final task; after it: initiative → completed, pyproject.toml minor bump to 0.14.0, push develop, update handoff.

### Risk Considerations
- Protected files forbidden (tools/*, tests/boundary/*). tools/TEST_SPEC.md is protected; workflow/TEST_SPEC.md is not — touch only the latter.
- Snapshot churn is not expected (no scoring changes); if fixtures/expected/ diffs appear, investigate rather than regenerate blindly.

## Status Updates **[REQUIRED]**

- 2026-08-16: T-0074..0077 all landed and committed (PR 401/smoke/verify green at T-0077; driver probed duplicate-operation typed result end-to-end). Codex launched on close-out: five-point matrix module test_workflow_recovery_matrix.py, workflow/TEST_SPEC.md recovery section alignment, four mutation probes (mutate→fail→revert), --future-contract added to verify set. Version bump to 0.14.0 + push is the driver's job after this task.