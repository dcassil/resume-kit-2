---
id: restore-resumechangeoperation
level: task
title: "Restore ResumeChangeOperation shape with structural field validation"
short_code: "RKIT-T-0005"
created_at: 2026-08-14T03:12:22.511401+00:00
updated_at: 2026-08-14T03:12:22.511401+00:00
parent: resume-core-canonical-contracts
blocked_by: ["RKIT-T-0003"]
archived: false

tags:
  - "#task"
  - "#phase/todo"
  - "#task"
  - "#phase/todo"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0001
---

# Restore ResumeChangeOperation shape with structural field validation

## Parent Initiative

[[RKIT-I-0001]]

## Objective

Restore the `ResumeChangeOperation` DTO in resume-core to its canonical A-0006 / section-4.5 shape and enforce STRUCTURAL validation only in `validateChange`. This re-establishes the change-operation contract (verb set, status set, mandatory grounding fields) that downstream edit/apply machinery in RKIT-I-0004 will build transition and grounding semantics on top of, without prematurely importing that behavior here.

## Acceptance Criteria

- [ ] `ChangeOperationStatus` value set == {"proposed", "validated", "rejected", "applied", "accepted", "modified"}.
- [ ] `validateChange` accepts op verbs exactly in {"replace", "rewrite", "insert", "remove", "move"} and emits a typed `invalid_op` error for any verb outside that set.
- [ ] `ResumeChangeOperation` dataclass has a `reason: str` field; `RESUME_CHANGE_OPERATION_SCHEMA["required"]` == {"schema_version", "operation_id", "status", "op", "path", "reason", "linked_requirement_ids", "linked_fact_ids", "provenance"}.
- [ ] `validateChange` emits a typed `missing_field` error for an operation payload lacking reason, linked_requirement_ids, linked_fact_ids, or provenance.
- [ ] No status-machine transition enforcement, no verb apply semantics, and no new grounding rules added (diff limited to structural field/enum checks); existing grounding block domain.py:487-511 unchanged.

## Implementation Notes

### Execution Profile

Recommended Agent: opus + medium

Codex-exec autonomously implementable: no — the task requires careful scope discipline (structural-only, not semantic) plus paired shared-DTO test edits and a cross-package verb-transition decision (`add`→`insert`) that needs reasoning judgment beyond mechanical edits.

### Technical Approach

Restore the `ResumeChangeOperation` DTO in `resume-core/resume_core/schemas.py` to the A-0006 / section-4.5 shape and enforce STRUCTURAL validation only in `validateChange` (`domain.py`):

- Add `ChangeOperationStatus` members `ACCEPTED='accepted'` and `MODIFIED='modified'` so the final set is exactly {proposed, validated, rejected, applied, accepted, modified}.
- Add the missing operation verbs so the accepted set is exactly {replace, rewrite, insert, remove, move}. The current code (domain.py:464) restricts verbs to add/replace/remove; the current code uses `'add'`, which is NOT in the target verb set (target uses insert/move/rewrite). Decide the `add`→`insert` transition and update `_operation_kind` defaulting at domain.py:463 accordingly.
- Add the mandatory `reason: str` field to the `ResumeChangeOperation` dataclass (it does not exist today).
- Make `reason`, `linked_requirement_ids`, `linked_fact_ids`, and `provenance` structurally REQUIRED in `RESUME_CHANGE_OPERATION_SCHEMA.required`.
- `validateChange` must reject an operation missing any mandatory field (typed `missing_field` error), reject an op verb not in the 5-verb set (typed `invalid_op`), and reject a status not in the 6-status set.

BINDING CONSTRAINT (approved decision): This is STRUCTURAL validation ONLY — field presence + enum membership. Status-machine transition legality, verb apply semantics, and reason/provenance grounding semantics belong to RKIT-I-0004 and MUST NOT be added here. Do NOT touch the existing grounding logic at domain.py:487-511.

BINDING CONSTRAINT (approved decision): Preserve the existing snake_case field names (`linked_requirement_ids`, `linked_fact_ids`). The camelCase in the design doc is conceptual only — do NOT rename existing fields (see decisionsForHuman). ADD the missing `reason` field; do not restructure the others.

### Files

- `/Users/danielcassil/Code/resume-kit-2/resume-core/resume_core/schemas.py`
- `/Users/danielcassil/Code/resume-kit-2/resume-core/resume_core/domain.py`

### Dependencies

- [[RKIT-T-0003]] — Restore canonical enum members and reconcile cross-package readers (VerificationState, ResolutionState); the change-operation enums and readers must be canonical before this task layers the operation status/verb sets on top.
- Downstream semantic layer: status-machine transitions, verb apply semantics, and grounding are explicitly deferred to RKIT-I-0004, which consumes the structural contract restored here. The paired shared-DTO test that reflects the new required set lives with the owning package initiative and must be updated in the same change (see verification).

### Risk Considerations

- Scope-boundary bleed: the strongest risk is accidentally implementing RKIT-I-0004 semantics (transition legality, apply behavior, grounding rules). Keep the diff limited to structural field/enum checks; leave domain.py:487-511 untouched.
- Protected/straight-jacket surface: `schemas.py` is a shared canonical DTO surface — a wrong required-set or field rename ripples across every consumer package. Preserve snake_case names exactly; only add `reason`.
- Cross-package blast radius: adding `reason` and three fields to `required` will break any DTO fixture/test that constructs operations without them; the paired shared-DTO test edit is mandatory to keep the PR gate green.
- Determinism: validation must be pure structural checks (presence + enum membership) with typed errors, no side effects or semantic inference, so results are reproducible across consumers.
- Verb-transition correctness: the `add`→`insert` decision changes accepted input; ensure `_operation_kind` defaulting at domain.py:463 and any callers emitting `add` are reconciled so no legitimate op is spuriously rejected `invalid_op`.

## Verification Steps

1. `python3 -c "import resume_core; print(sorted(s.value for s in resume_core.ChangeOperationStatus)); print(sorted(resume_core.RESUME_CHANGE_OPERATION_SCHEMA['required']))"` — sets match acceptance criteria.
2. Add/adjust resume-core unit coverage: a rewrite/insert/move op validates structurally; an `add` or `foo` verb is rejected `invalid_op`; an op missing `reason` is rejected `missing_field`.
3. `python3 tools/run_gate.py --pr --root .` — PR gate green (with the paired shared-DTO test edit reflecting the new required set).

## Status Updates

*To be added during implementation*