---
id: schema-backed-validateresume
level: task
title: "Schema-backed validateResume against exported constants (resume_id, source)"
short_code: "RKIT-T-0006"
created_at: 2026-08-14T03:12:22.551383+00:00
updated_at: 2026-08-14T03:12:22.551383+00:00
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

# Schema-backed validateResume against exported constants (resume_id, source)

## Parent Initiative

[[RKIT-I-0001]]

## Objective

Make `validateResume` enforce the full canonical required-field contract by driving its presence check off the exported `CANONICAL_RESUME_SCHEMA['required']` constant rather than a hand-picked subset. This closes the gap where `resume_id` and `source` — required by the schema — are silently unvalidated today, so structural validation and the exported schema constant can never drift apart again.

## Acceptance Criteria

- [ ] `validateResume` on a resume dict missing `resume_id` emits a typed `missing_field` error with field_path `resume_id`; likewise for missing `source`.
- [ ] The required-field set `validateResume` enforces is derived from `CANONICAL_RESUME_SCHEMA['required'] == ["schema_version", "resume_id", "source", "experience", "skills", "education"]` (not a hard-coded subset).
- [ ] A resume produced by `normalizeResume` then passed to `validateResume` yields zero `missing_field` errors (no double-reporting of backfilled `resume_id`/`source`).
- [ ] No third-party validation dependency is imported; validation uses stdlib only (no `import jsonschema`).
- [ ] Existing `verification_state` validity check now accepts `verification_state='imported'` (regression guard tied to the enum task) and rejects a genuinely unknown state.

## Implementation Notes

### Execution Profile

Recommended Agent: opus + medium

Codex-exec autonomously implementable: yes — the change is well-scoped to two files with a fully specified data-driven behavior and concrete unit-level acceptance criteria, so an autonomous agent can implement and self-verify it deterministically.

### Technical Approach

`validateResume` (domain.py:214-247) currently enforces only a hand-picked subset of required fields: the loop at domain.py:223-225 checks `(schema_version, experience, skills, education)`, while `CANONICAL_RESUME_SCHEMA['required']` (schemas.py:233) also lists `resume_id` and `source`. Rework the presence check so the required-field set is read directly from the exported `CANONICAL_RESUME_SCHEMA['required']` constant, eliminating the drift between the schema and the validator.

- Drive the presence check off `CANONICAL_RESUME_SCHEMA['required']` via a **small hand-rolled stdlib walker**. Per the approved decision, this MUST be a hand-rolled stdlib walker over `CANONICAL_RESUME_SCHEMA['required']` — **do NOT add a `jsonschema` dependency**. Stdlib-only dependency hygiene is an audited invariant and an explicitly rejected alternative here.
- Emit exactly one typed `missing_field` error per missing required field.
- Ensure there is **no double-error** when `normalizeResume` has already backfilled `resume_id`/`source` — a resume that has passed through the `normalizeResume` path must still produce a clean `validateResume`.
- Optionally generalize the walker so `validateJob`/`normalizeJobModel` can validate against `JOB_MODEL_SCHEMA['required']`, but the load-bearing deliverable is `validateResume` covering `resume_id` and `source`. Do not let the optional generalization expand scope or blast radius beyond what is needed for the resume path.
- Keep the existing `verification_state`, provenance-shape, and date checks intact. The date behavior is replaced by the date task (RKIT-T-0003), not this one — do not re-touch date logic here.

### Files

- `/Users/danielcassil/Code/resume-kit-2/resume-core/resume_core/domain.py`
- `/Users/danielcassil/Code/resume-kit-2/resume-core/resume_core/schemas.py`

### Dependencies

- [[RKIT-T-0003]] — this task's `verification_state` regression guard depends on the canonical enum members (including `imported`) being restored and cross-package readers reconciled; the acceptance criterion that `verification_state='imported'` is accepted cannot pass until that enum work lands.
- Downstream semantic link: strengthening `validateResume` feeds the `validateFinalResume` threading work in RKIT-I-0004; keep error typing/shape consistent with what that initiative consumes.
- `resume-core` is the owning package initiative; any xfail markers introduced against the pre-fix behavior belong there and should be reconciled once this lands.

### Risk Considerations

- **Straight-jacket / protected-surface constraint**: the approved decision binds this to a hand-rolled stdlib walker; introducing `jsonschema` (or any third-party validator) violates the audited stdlib-only invariant and is a rejected alternative — treat any such import as out of bounds.
- **Double-error / determinism**: the `normalizeResume` backfill path must not produce spurious `missing_field` errors; validate that the normalized output is clean so behavior is deterministic across the normalize→validate pipeline.
- **Cross-package blast radius**: `validateResume` error shape/typing is consumed downstream (RKIT-I-0004, cross-package readers). Changing the required set changes what errors surface — keep error typing stable and scoped to added `missing_field` entries.
- **Scope-boundary bleed**: do not modify date checks (owned by RKIT-T-0003) or expand the optional job-model generalization into a larger refactor; the load-bearing deliverable is strictly `validateResume` covering `resume_id` and `source`.

## Verification Steps

1. Unit test: `validateResume({'schema_version':..., 'experience':[], 'skills':[], 'education':[]})` returns errors including `missing_field` for `resume_id` and `source`.
2. Unit test: `validateResume(normalizeResume(<minimal structured resume>).canonical_resume)` returns status ok with no `missing_field` errors.
3. `python3 -c "import resume_core; r=resume_core.validateResume({'schema_version':'canonical-resume.v1','resume_id':'x','source':{},'experience':[],'skills':[],'education':[],'verification_state':'imported'}); print(r['status'], r['errors'])"` : status ok, no `invalid_verification_state`.
4. `python3 tools/run_gate.py --pr --root .` : PR gate green.

## Status Updates

*To be added during implementation*