---
id: matrix-regression-cross-session
level: task
title: "Matrix/regression/cross-session test pass and TEST_SPEC strengthening; I-0006 close-out"
short_code: "RKIT-T-0048"
created_at: 2026-08-15T00:37:23.746193+00:00
updated_at: 2026-08-15T01:22:07.930939+00:00
parent: evidence-backed-fact-and
blocked_by: [RKIT-T-0047]
archived: false

tags:
  - "#task"
  - "#phase/completed"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0006
---

# Matrix/regression/cross-session test pass and TEST_SPEC strengthening; I-0006 close-out

## Parent Initiative

[[RKIT-I-0006]]

## Objective

Close out RKIT-I-0006's Testing Strategy: consolidated contract regressions on the audit's exact probes, the full transition-matrix suite, merge retention tests, cross-session user_verified persistence, career-store/TEST_SPEC.md strengthening (downgrade protection + source_stated gating cases), and the three-gate close-out.

## Acceptance Criteria

## Acceptance Criteria

## Acceptance Criteria

- [ ] Audit-probe regressions: the literal strings "incorrect" and "yesterday I did nothing" — as raw text (rejected input) and as denied/unclear proposals — leave verification unchanged; named tests.
- [ ] Full transition-matrix suite driven from the EXPORTED matrix constant: every disallowed edge raises `DisallowedTransitionError`; every allowed edge succeeds only with its exact authority; explicitly includes inferred→source_stated with agent-only provenance failing.
- [ ] Merge suite: aliases retained, zero evidence rows lost, merged id resolvable, no escalation via merge, atomic interruption.
- [ ] Cross-session persistence: user_verified survives close/reopen and distinct job sessions (TEST_SPEC:71 finally executable).
- [ ] A test/sweep asserts the marker tables are gone and no store path consumes raw confirmation text for state decisions.
- [ ] career-store/TEST_SPEC.md strengthened with executable-case names for downgrade protection, source_stated gating, proposal validation, and merge retention (strengthen-only; guardrail-compatible — check the protected guardrail's spec parsing first, defer anything it would reject).
- [ ] All new I-0006 unit modules listed for the protected run_tests.py batch (with the three I-0005 modules already queued) — wire only if Daniel's approve/update-locks has landed (check straight-jacket state).
- [ ] Close-out gates ALL green: --pr, --smoke, --future-contract; counts reported; mutation probe documented (e.g. re-adding a marker-based promotion path fails the suite).

## Implementation Notes

### Technical Approach

Consolidation task following the T-0038/T-0043 close-out pattern: mostly test authorship over T-0044..0047 mechanisms, spec text, gate evidence, mutation probe.

### Dependencies

RKIT-T-0047 (all mechanisms final).

### Risk Considerations

Keep tests deterministic; guardrail parses parts of TEST_SPEC — verify compatibility before editing; protected batch keeps accumulating (report it).

### Execution profile

Recommended Agent: opus + medium

Rationale: adversarial case selection over an already-built mechanism set.

## Status Updates

*To be added during implementation*