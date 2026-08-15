---
id: public-surface-boundary-test-spec
level: task
title: "Public-surface boundary, TEST_SPEC overflow/completion cases, driving-surface review; I-0027 close-out"
short_code: "RKIT-T-0073"
created_at: 2026-08-15T04:29:40.693749+00:00
updated_at: 2026-08-15T04:47:32.275510+00:00
parent: workflow-tailoring-validation
blocked_by: [RKIT-T-0072]
archived: false

tags:
  - "#task"
  - "#phase/active"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0027
---

# Public-surface boundary, TEST_SPEC overflow/completion cases, driving-surface review; I-0027 close-out

## Parent Initiative

[[RKIT-I-0027]]

## Objective

Close out RKIT-I-0027 (Requirements 4-5 + Testing Strategy): a boundary test enforces workflow imports only public surfaces of resume-core/resume-render; workflow/TEST_SPEC.md gains the overflow loop-back and grounded-completion cases; the stage-level checkpoint-driving surface is reviewed and documented for RKIT-I-0040's `resume run` wiring (interface shape only, no CLI code); three-gate close-out with mutation probe.

## Acceptance Criteria

## Acceptance Criteria

- [ ] Boundary test (unprotected): workflow's imports of resume_core/resume_render are public-surface only (no package-private module imports) — structural AST/import inspection.
- [ ] workflow/TEST_SPEC.md state-machine section gains: the render-overflow loop-back case (character-count requiredReduction routes back to selection) and grounded-completion cases (per-gate ref presence + hash match) — strengthen-only, guardrail-compat checked.
- [ ] Driving-surface review documented in this task's Status Updates + the initiative doc: the exact call sequence RKIT-I-0040 uses to drive `resume run` through the same checkpoints as individual commands (getNextCheckpoint → produce evidence → advanceCheckpoint → recordCheckpointResult per stage; loop surfaces; assertCanComplete) — interface shape only, verifying no orchestration logic must be duplicated CLI-side.
- [ ] Gap check the Testing Strategy: overflow routing, bound exhaustion, grounded completion (T-0071/T-0072) — named; add anything missing.
- [ ] Mutation probe documented: re-accepting a boolean completion gate (or letting overflow exceed the bound silently) fails the suite; restored green.
- [ ] New unit modules listed for the protected run_tests.py batch; close-out gates ALL green: --pr, --smoke, --future-contract; counts reported.

## Implementation Notes

### Technical Approach

Established close-out pattern; the boundary test mirrors T-0070's structural style (AST import walk over workflow/*.py).

### Dependencies

RKIT-T-0072 (all mechanisms final).

### Risk Considerations

TEST_SPEC guardrail-compat as usual; the driving-surface review is documentation + verification, not new API.

### Execution profile

Recommended Agent: opus + medium

Rationale: consolidation + interface documentation on decided shapes.

## Status Updates

2026-08-15:
- Guardrail-compat baseline checked before TEST_SPEC edit: `python3 tools/workflow_guardrails.py --root .` passed.
- Boundary-test design: added an unprotected AST import inspection over `workflow/*.py` that rejects `resume_core`/`resume_render` submodule imports, wildcard imports, dynamic submodule imports, and root imports of names not listed in each package root `__all__`.
- TEST_SPEC state-machine strengthening: added render-overflow loop-back, bound-exhaustion blocking, and grounded COMPLETE cases requiring per-gate artifact ref presence plus hash match.
- Driving-surface review for RKIT-I-0040: createRun -> loop of getNextCheckpoint (including resolution_loop + blocking_reasons and render_overflow) -> produce grounded evidence via package calls -> advanceCheckpoint -> recordCheckpointResult (+ overflow loop-back handling) -> assertCanComplete -> buildRunManifest. No workflow orchestration logic needs CLI-side duplication; I-0040 still needs to map required_inputs to package calls/artifact writes and reload persisted run state between iterations.
