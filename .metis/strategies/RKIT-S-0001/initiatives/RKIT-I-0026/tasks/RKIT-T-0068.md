---
id: resolutionloopstate-dto
level: task
title: "ResolutionLoopState DTO, persistence, and the tri-state termination predicate"
short_code: "RKIT-T-0068"
created_at: 2026-08-15T04:05:15.509762+00:00
updated_at: 2026-08-15T04:05:15.509762+00:00
parent: workflow-requirement-resolution
blocked_by: []
archived: false

tags:
  - "#task"
  - "#phase/todo"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0026
---

# ResolutionLoopState DTO, persistence, and the tri-state termination predicate

## Parent Initiative

[[RKIT-I-0026]]

## Objective

Build the resolution-loop substrate (RKIT-I-0026 Requirements 1-4, Detailed Design "Loop-state DTO"/"Termination predicate"/"Topic selection"): a persisted ResolutionLoopState (impact-ordered open-requirement queue, exhaustion statuses, asked-question registry) and the section 14.D.9 termination predicate over the tri-state MatchResult.decision with `requireHardRequirementsResolved` gating.

## Acceptance Criteria

- [ ] `ResolutionLoopState` DTO persisted in run state and updated on every mutation: {open_requirements: ordered [{requirement_id, impact_rank, status: open|resolved|user_declined|exhausted}], asked_questions: [{question_id, requirement_id, interaction_ref}], facts_since_last_match (from the I-0023 watermark), iteration_count}. Interruption at any point recovers losslessly (recoverRun sees the full state).
- [ ] Termination predicate evaluated after each MATCH_BASE rerun: decision `continue` → advance to BUILD_SELECTION_PLAN; `resolve_gaps` + open non-exhausted requirements → next topic by impact rank (deterministic cursor; resume-core ranks impact, workflow holds the cursor — never agent/CLI choice); `resolve_gaps` + all exhausted → advance with honest unresolved recording (full manifest wiring is T-0070); `blocked` (unresolved hard requirement under requireHardRequirementsResolved) → blocked outcome with persisted reasons, no advance.
- [ ] Workflow exposes loop state and next-topic decisions as a queryable, read-only surface (no prompting, no question phrasing anywhere in the API).
- [ ] Contract tests: each predicate branch (a)-(d) driven through grounded advances; hard-requirement blocked case named.
- [ ] PR + smoke gates green; no weakening of any existing assertion; surface-manifest edits only if guardrail-accepted (else deferral note).

## Implementation Notes

### Technical Approach

Loop state as a run-state field flowing through the I-0022 persistence; predicate consumes resume-core's MatchResult.decision (tri-state landed in I-0002) recorded as grounded checkpoint evidence. Impact rank read from the recorded match result's dimension/requirement data.

### Dependencies

RKIT-I-0023 complete (watermark + grounded advances). First task of the I-0026 serial chain.

### Risk Considerations

Boundary discipline: no new API may accept or emit question text (registry stores ids/refs only). Deterministic queue ordering (impact rank, then requirement_id tiebreak).

### Execution profile

Recommended Agent: opus + high

Rationale: the loop-policy substrate every later workflow initiative and the CLI resolve UX consume; predicate semantics are contract-critical.

## Status Updates

*To be added during implementation*
