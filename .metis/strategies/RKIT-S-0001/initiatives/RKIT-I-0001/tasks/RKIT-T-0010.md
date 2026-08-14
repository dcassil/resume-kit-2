---
id: resume-core-test-spec-unit-suites
level: task
title: "Resume-core TEST_SPEC unit suites and spec-strengthening for restored contracts"
short_code: "RKIT-T-0010"
created_at: 2026-08-14T03:12:22.710865+00:00
updated_at: 2026-08-14T03:12:22.710865+00:00
parent: resume-core-canonical-contracts
blocked_by: ["RKIT-T-0005","RKIT-T-0006","RKIT-T-0007","RKIT-T-0008","RKIT-T-0009"]
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

# Resume-core TEST_SPEC unit suites and spec-strengthening for restored contracts

## Parent Initiative

[[RKIT-I-0001]]

## Objective

This task pins every behavior restored by RKIT-I-0001 with resume-core unit assertions and matching TEST_SPEC.md entries, so the canonical contracts are locked by tests beyond the shared-DTO contract test. It is authored last, after the behavior tasks land, so its assertions target the real restored signatures rather than anticipated ones — turning the initiative's restored guarantees into an enforceable, regression-proof test surface.

## Acceptance Criteria

- [ ] New/updated unit assertions exist for all six behavior areas below, each with at least one positive and one negative case.
- [ ] TEST_SPEC.md documents: imported-accepted, invalid_date rejection, reversed_range rejection, ResumeChangeOperation 5-verb/6-status/mandatory-field structural rules, validateResume resume_id/source enforcement, JobTerm determinism, and normalizeResume honest empty-provenance default.
- [ ] All new tests pass under the gate venv; no assertion is weakened relative to the pre-existing suite; no test is skipped/xfailed.
- [ ] Coverage explicitly asserts the honesty invariant: a sourceless claim never emerges as source_stated.

## Implementation Notes

### Execution Profile

Recommended Agent: opus + medium

Codex-exec autonomously implementable: no — assertions must target the real restored signatures across five upstream behavior tasks and edit a straight-jacket-protected spec/test under strengthen-only rules, which requires cross-package judgment codex-exec cannot safely exercise.

### Technical Approach

Add and strengthen the resume-core unit test suites and TEST_SPEC.md entries that lock in every behavior restored by this initiative, so the contracts are pinned by tests beyond the shared-DTO contract test. Cover all six behavior areas, each with at least one positive and one negative case:

1. **Enum membership regression** — `imported` accepted as a `verification_state`; `explicitly_missing` rejected as a `verification_state` but valid as a `resolution_state`; `not_applicable` valid as a `resolution_state`; `conflicted` absent from both.
2. **ResumeChangeOperation structural validation** — 5 verbs, 6 statuses, and mandatory `reason` / `linked_requirement_ids` / `linked_fact_ids` / `provenance` rejection when absent.
3. **validateResume full-required-field enforcement** — `resume_id` and `source` required.
4. **Date canonicalization** — typed `invalid_date` / `reversed_range` rejection across all case shapes.
5. **JobModel section-4.2 fields + JobTerm population determinism.**
6. **normalizeResume per-claim provenance honest-defaults** — empty provenance resolves to `unknown`, never a silent `source_stated`.

Update `resume-core/TEST_SPEC.md` to document each new required behavior with a spec line.

Binding guidance (approved decision): this task is authored AFTER the behavior tasks (RKIT-T-0005 through RKIT-T-0009) land so the assertions target real signatures rather than anticipated ones. This task ALSO owns the resume-core changing-surface unit cases that RKIT-I-0051 REQ-009 (RKIT-T-0021) deliberately deferred here: `date_normalization`, `requirement_normalization`, `change_validation`, `state_transitions`, and the `verification`/`resolution`-enum cases. Where this task edits a straight-jacket-protected spec or test, the authorization is the A-0006 realignment: assertions may only be strengthened or preserved, never weakened — strengthen-only on any protected spec/test.

### Files

- `/Users/danielcassil/Code/resume-kit-2/resume-core/TEST_SPEC.md` (PROTECTED — straight-jacket spec; strengthen-or-preserve only, authorized by A-0006 realignment)
- `/Users/danielcassil/Code/resume-kit-2/tests/contract/test_resume_core_contract.py` (PROTECTED — straight-jacket test; strengthen-or-preserve only, authorized by A-0006 realignment)

### Dependencies

- [[RKIT-T-0005]] — Restore ResumeChangeOperation shape with structural field validation (verbs, statuses, mandatory fields); its real signature must exist before area 2 assertions can target it.
- [[RKIT-T-0006]] — Add schema-backed structural validation of validateResume against exported constants; area 3 assertions depend on the real required-field enforcement.
- [[RKIT-T-0007]] — Replace warn-only date handling with canonicalization and typed rejection; area 4 assertions depend on the typed invalid_date/reversed_range signatures.
- [[RKIT-T-0008]] — Complete JobModel section-4.2 shape and JobTerm substrate with deterministic population; area 5 assertions depend on the real fields and deterministic JobTerm output.
- [[RKIT-T-0009]] — Weave claim-level ResumeField provenance and verification through normalizeResume; area 6 honesty-invariant assertions depend on the real normalizeResume default behavior.

Cross-initiative / semantic links: this task absorbs the resume-core changing-surface unit cases (date_normalization, requirement_normalization, change_validation, state_transitions, verification/resolution-enum) that RKIT-I-0051 REQ-009 (RKIT-T-0021) deferred here — resume-core is the owning package initiative for those xfail-deferred cases. Downstream, the pinned contracts feed RKIT-I-0004 (applied-operations threading), which relies on these locked signatures.

### Risk Considerations

- **Protected-surface / straight-jacket constraints**: Both edited files are straight-jacket protected. The only authorized change class is strengthen-or-preserve under the A-0006 realignment; weakening or deleting any existing assertion is out of bounds and will fail the straight-jacket verify.
- **Cross-package blast radius**: Because assertions target signatures produced by five upstream tasks, any drift between the anticipated and real signatures propagates here. Author last and read the landed code, not the task descriptions.
- **Determinism**: JobTerm population and normalizeprovenance defaults must be asserted deterministically — no reliance on ordering or timestamp-sensitive output that could make the suite flaky.
- **Scope-boundary bleed**: This task pins contracts via tests only; it must not modify behavior source to make a test pass. If a restored behavior is wrong, that is fixed in its owning behavior task, not patched here.

## Verification Steps

1. `python3 -m unittest tests.contract.test_resume_core_contract -v` (via the gate venv): all pass.
2. `python3 tools/run_gate.py --pr --root .` : full PR gate green.
3. `git diff resume-core/TEST_SPEC.md` : confirm every restored behavior has a documented spec line.

## Status Updates

*To be added during implementation*