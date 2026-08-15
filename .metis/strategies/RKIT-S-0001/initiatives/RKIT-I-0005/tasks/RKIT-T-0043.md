---
id: delete-dead-matching-py-no-scoring
level: task
title: "Delete dead matching.py, no-scoring guardrail, TEST_SPEC realignment pass"
short_code: "RKIT-T-0043"
created_at: 2026-08-14T23:56:07.575439+00:00
updated_at: 2026-08-15T00:36:31.768+00:00
parent: durable-career-store-package-and
blocked_by: [RKIT-T-0042]
archived: false

tags:
  - "#task"
  - "#phase/completed"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0005
---

# Delete dead matching.py, no-scoring guardrail, TEST_SPEC realignment pass

## Parent Initiative

[[RKIT-I-0005]]

## Objective

Close out RKIT-I-0005 (Requirements 7-8 + Testing Strategy): delete the dead parallel `career_store/matching.py` (unused, unexported, divergent semantics, Must-Not-Own scoring at matching.py:497-508) after salvaging its `_YEARS_RE` pattern for RKIT-I-0008; add the no-scoring-export guardrail test; realign career-store/TEST_SPEC.md's drifted 6-value verification set; run the full three-gate close-out.

## Acceptance Criteria

## Acceptance Criteria

## Acceptance Criteria

- [ ] `career_store/matching.py` is deleted; `git grep -n "career_store.matching\|from .matching\|from career_store import matching"` returns zero code hits.
- [ ] `_YEARS_RE` (and only what RKIT-I-0008's years-heuristic fix needs) is salvaged — parked in a clearly-owned location (e.g. a small internal util or documented verbatim in RKIT-I-0008's initiative doc) so deletion loses nothing I-0008 needs.
- [ ] A test asserts the package exports no scoring-shaped function (scoring is Must-Not-Own for career-store, CONTRACT_SURFACE_ALIGNMENT.md:37). If this belongs in the PROTECTED boundary guardrails, implement it as an unprotected unit/contract test instead OR stop and report the protected need — do not edit protected files silently.
- [ ] `career-store/TEST_SPEC.md` (package spec — NOT the protected tools/TEST_SPEC.md) realigned strengthen-only: the drifted 6-value verification set (lines ~66-72) becomes the canonical 5-value A-0006 set; the `jobs` table cases added in T-0040 are enumerated; mandatory migration/transaction behaviors from T-0039/T-0042 are specified.
- [ ] New I-0005 unit modules (if any were created outside gate-wired suites) reported for run_tests.py wiring in the accumulated protected batch — or wired now if Daniel's approve/update-locks has landed by then (check `straight_jacket verify` state first).
- [ ] Initiative close-out gates ALL green: `--pr`, `--smoke`, `--future-contract`; test counts reported.
- [ ] No weakening of any existing assertion anywhere.

## Implementation Notes

### Technical Approach

Mechanical deletion plus spec/consolidation work following T-0038's close-out pattern. Verify matching.py is genuinely unimported before deleting (`git grep`), delete, run gates. TEST_SPEC realignment is the package-level spec file — confirm it is not in the straight-jacket protected list before editing (protected list: tools/TEST_SPEC.md, tools/*_guardrails.py, boundary tests, run_gate/run_smoke/run_tests, tool_manifest.json).

### Dependencies

RKIT-T-0042 (all mechanisms final before the spec freeze and close-out gates).

### Risk Considerations

If the boundary guardrails already import or reference matching.py symbols, deletion breaks a protected test — that becomes a reported protected edit, not a workaround. TEST_SPEC realignment must not drop any currently-specified behavior (strengthen-only).

### Execution profile

Recommended Agent: opus + low

Rationale: deletion, spec text, and gate runs with the design already decided; the only judgment is the protected-boundary check.

## Status Updates

*To be added during implementation*