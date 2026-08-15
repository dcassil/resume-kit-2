---
id: exhaustion-honesty-into-the
level: task
title: "Exhaustion honesty into the manifest, TEST_SPEC termination cases, no-interaction boundary; I-0026 close-out"
short_code: "RKIT-T-0070"
created_at: 2026-08-15T04:05:15.623143+00:00
updated_at: 2026-08-15T04:22:53.142427+00:00
parent: workflow-requirement-resolution
blocked_by: [RKIT-T-0069]
archived: false

tags:
  - "#task"
  - "#phase/active"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0026
---

# Exhaustion honesty into the manifest, TEST_SPEC termination cases, no-interaction boundary; I-0026 close-out

## Parent Initiative

[[RKIT-I-0026]]

## Objective

Close out RKIT-I-0026 (Requirement 5 + Testing Strategy): exiting the loop with unresolved gaps records them into run state feeding the manifest's unresolved_requirements field (populating I-0022's schema obligation with real loop outcomes); workflow/TEST_SPEC.md:57 gains the three termination cases; a boundary test keeps the no-interaction surface structural; three-gate close-out with mutation probe.

## Acceptance Criteria

## Acceptance Criteria

- [ ] Loop exit with unresolved gaps records {requirement_id, resolution_state, reason} entries into run state; buildRunManifest/reconstructRunManifest carry them in unresolved_requirements (real content, no longer only empty defaults); recorded reasons distinguish user_declined vs exhausted.
- [ ] workflow/TEST_SPEC.md :57 region gains the three named cases: (a) new facts → exactly one rerun → continue → BUILD_SELECTION_PLAN; (b) exhaustion with unresolved non-hard gaps → advance with unresolved_requirements recorded; (c) unresolved hard requirement + requireHardRequirementsResolved → blocked, not advanced. Strengthen-only, guardrail-compat checked.
- [ ] Boundary test: the workflow public surface (__all__ + store of public callables) contains no user-interaction or question-phrasing API — structural, not keyword-based.
- [ ] Gap check the Testing Strategy: multi-iteration regression (T-0069), single-rerun discipline (T-0069), predicate branches (T-0068) — all named; add anything missing.
- [ ] Mutation probe documented: reverting the termination predicate to the old cumulative-facts condition (or dropping exhaustion recording) fails the suite; restored green.
- [ ] New unit modules listed for the protected run_tests.py batch; close-out gates ALL green: --pr, --smoke, --future-contract; counts reported.

## Implementation Notes

### Technical Approach

Established close-out pattern; unresolved recording plugs into the T-0066 reconstruction sources (state-recorded, log-consistent).

### Dependencies

RKIT-T-0069 (loop mechanics final).

### Risk Considerations

Manifest equality contract (reconstructed == built) must keep holding once unresolved_requirements carries real content — record once, read from the same source.

### Execution profile

Recommended Agent: opus + medium

Rationale: consolidation on decided shapes.

## Status Updates

*To be added during implementation*