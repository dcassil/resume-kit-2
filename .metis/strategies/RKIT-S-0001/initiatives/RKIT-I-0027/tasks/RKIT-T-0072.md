---
id: render-overflow-loop-back-with
level: task
title: "Render-overflow loop-back with character-count requiredReduction and bounded honest blocking"
short_code: "RKIT-T-0072"
created_at: 2026-08-15T04:29:40.636408+00:00
updated_at: 2026-08-15T04:38:15.481520+00:00
parent: workflow-tailoring-validation
blocked_by: [RKIT-T-0071]
archived: false

tags:
  - "#task"
  - "#phase/active"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0027
---

# Render-overflow loop-back with character-count requiredReduction and bounded honest blocking

## Parent Initiative

[[RKIT-I-0027]]

## Objective

Implement the render-overflow loop-back that exists nowhere in the repo (RKIT-I-0027 Requirements 1-2, Detailed Design "Overflow loop"): a render checkpoint result carrying overflow constraints from resume-render measureLayout routes the machine back to the selection-plan checkpoint with `requiredReduction` as a CHARACTER COUNT (RKIT-A-0006 item 7 — not a page delta); iterations are bounded via the section 13 config vocabulary; bound exhaustion yields an honest blocked outcome; renderer truncation is forbidden.

## Acceptance Criteria

## Acceptance Criteria

- [ ] Render checkpoint result DTO includes overflow constraints {requiredReduction: character count, offending_sections}; on overflow, workflow records the constraint artifact, transitions back to BUILD_SELECTION_PLAN with the constraint as required input evidence, and increments overflow_iteration in run state.
- [ ] measureLayout is actually CALLED somewhere real (contract-test driver at minimum; check resume-render's public surface for its shape and whether its requiredReduction is currently a page delta — if so, realign resume-render's DTO to character count per A-0006 item 7, strengthen-only, producers fixed).
- [ ] The overflow iteration bound comes from the section 13 config vocabulary (namespaced key, typed unknown-key handling per the established config pattern); exceeding it produces a blocked outcome with persisted reasons — no path reaches COMPLETE, no truncation anywhere.
- [ ] Contract tests: overflow routes back with a character-count requiredReduction; bound exhaustion blocks with named reasons; a fitting render proceeds to completion.
- [ ] PR + smoke gates green; no weakening of any existing assertion.

## Implementation Notes

### Technical Approach

The loop-back reuses the checkpoint transition machinery (a permitted backward transition for this specific constraint-carrying case — extend the transition/evidence declarations); overflow_iteration lives in run state beside the resolution loop state. resume-render owns measurement; workflow consumes its recorded result.

### Dependencies

RKIT-T-0071 (render checkpoint evidence declarations exist).

### Risk Considerations

resume-render's measureLayout may be a stub or carry the drifted page-delta DTO — realign honestly (A-0006 item 7 decided the semantics); do not implement measurement logic in workflow. Config key joins the guardrails/section-13 pattern.

### Execution profile

Recommended Agent: opus + high

Rationale: cross-package loop with decided-but-unimplemented contract semantics; the honesty rule (no truncation, honest blocking) is the point.

## Status Updates

- 2026-08-15: Implemented render-overflow loop-back in workflow with persisted `render_overflow_state`, `overflow_iteration`, constraint artifacts, and dynamic `render_overflow_constraints` evidence on the backward transition to `BUILD_SELECTION_PLAN`.
- 2026-08-15: Realigned `resume_render.measureLayout` so `requiredReduction` / `required_reduction` are character counts, not page deltas, and added offending section reporting.
- 2026-08-15: Added section-13-style `workflow.maxRenderOverflowIterations` config resolver with typed unknown-key/value errors; bound exhaustion records named reasons and blocks completion.
