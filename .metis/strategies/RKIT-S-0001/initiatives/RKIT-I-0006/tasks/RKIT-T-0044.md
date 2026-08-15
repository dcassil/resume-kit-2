---
id: interpretation-proposal-dto
level: task
title: "Interpretation proposal DTO, validation, substring-marker removal"
short_code: "RKIT-T-0044"
created_at: 2026-08-15T00:37:23.551637+00:00
updated_at: 2026-08-15T00:39:02.414175+00:00
parent: evidence-backed-fact-and
blocked_by: []
archived: false

tags:
  - "#task"
  - "#phase/active"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0006
---

# Interpretation proposal DTO, validation, substring-marker removal

## Parent Initiative

[[RKIT-I-0006]]

## Objective

Replace career-store's substring confirmation heuristic with structured interpretation-proposal validation per vision section 12 (RKIT-I-0006 Requirements 1-2): the affirmative/negation marker tables (store.py:51-76, 1243-1254) are removed; the confirmation surface accepts only the InterpretationProposal DTO; the store never derives meaning from raw answer text, which is retained as evidence only.

## Acceptance Criteria

## Acceptance Criteria

- [ ] The affirmative/negation substring marker tables and all their uses are removed from store.py; a grep for the marker constants returns nothing.
- [ ] InterpretationProposal DTO exists per the initiative's Detailed Design: `{factId, questionId?, outcome: "affirmed"|"denied"|"unclear", confirmedValue?, provenance: ProvenanceRef[]}`; validation rejects unknown outcome values, missing/empty provenance, and references to unknown facts with typed `InvalidInterpretationProposalError`.
- [ ] The audit's two empirical probes become permanent regressions: raw text "incorrect" and "yesterday I did nothing" — routed however the old path allowed — cannot promote any fact; both promoted inferred→user_verified before this task.
- [ ] denied and unclear outcomes never change verification state; raw answer text is persisted as evidence only.
- [ ] The free-text confirmation parameter is removed from the code path; if removing it from store_surface.json trips the PROTECTED guardrail's pinned surface expectations, defer the manifest edit to Daniel's approve/update-locks batch (T-0039/T-0041 pattern) and keep gates green.
- [ ] Full promotion via an affirmed user-provenance proposal still works (the legitimate path stays alive; full gating matrix is T-0045).
- [ ] PR + smoke gates green; no weakening of any existing assertion.

## Implementation Notes

### Technical Approach

New DTO + validation in schemas.py/store.py (or a small confirmations module) following career-store typed-error conventions. verifyFact's confirmation input becomes the proposal DTO; the transaction substrate from T-0042 wraps the write. Existing persisted confirmation-answer evidence rows are untouched (they are already evidence-only).

### Dependencies

RKIT-I-0005 complete (transaction substrate, canonical enums). First task of the I-0006 serial chain.

### Risk Considerations

workflow/career-mcp/CLI may call verifyFact with free-text confirmation — check `--smoke` and migrate callers to structured proposals (producer fix, never re-accept raw text). Guardrail may pin verifyFact's input contract — defer manifest edits if so.

### Execution profile

Recommended Agent: opus + high

Rationale: replaces the store's honesty-critical confirmation semantics; the DTO shape and validation rules are consumed by every later chunk.

## Status Updates

*To be added during implementation*