---
id: realign-shared-dto-contract-test
level: task
title: "Realign shared-DTO contract test and surface manifests to restored enum/field sets"
short_code: "RKIT-T-0004"
created_at: 2026-08-14T03:12:22.465126+00:00
updated_at: 2026-08-14T16:12:01.908600+00:00
parent: resume-core-canonical-contracts
blocked_by: [RKIT-T-0003, RKIT-T-0005, RKIT-T-0008]
archived: false

tags:
  - "#task"
  - "#task"
  - "#phase/completed"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0001
---

# Realign shared-DTO contract test and surface manifests to restored enum/field sets

## Parent Initiative

[[RKIT-I-0001]]

## Objective

This task realigns the protected shared-DTO contract test (and, if needed, the resume-core surface manifest) so the contract gate asserts the A-0006 target enum and required-field sets rather than the currently drifted ones. It closes the loop on the enum/shape restoration work by making the gate that guards those DTOs reflect the documented contract, ensuring downstream consumers can rely on a stable, correctly-gated shared-DTO surface.

## Acceptance Criteria

## Acceptance Criteria

## Acceptance Criteria

- [ ] `test_resume_core_enums_preserve_truth_and_match_states` asserts VerificationState value set == `{"source_stated", "user_verified", "imported", "inferred", "unknown"}` via whole-set `assertEqual` (not subset).
- [ ] The same test asserts ResolutionState value set == `{"exact_match", "alias_match", "verified_fact_match", "related_match", "possible_match", "unknown", "explicitly_missing", "not_applicable"}` via whole-set `assertEqual`.
- [ ] `test_resume_core_schema_required_fields_are_stable` expected map matches the final required-field sets produced by the ResumeChangeOperation and JobModel tasks (no stale field expectations).
- [ ] Assertion strength preserved or strengthened: no `assertEqual` downgraded to `assertIn`/subset; no test skipped or xfailed; fixture inputs unchanged.
- [ ] `straight_jacket_verify` (or `python3 tools/run_gate.py --pr`) reports no protected-file violation for this edit.

## Implementation Notes

### Execution Profile

Recommended Agent: opus + medium

Codex-exec autonomously implementable: no — editing a straight-jacket-protected contract test under a narrow authorization requires judgment about assertion-strength preservation and lockstep coordination with three upstream tasks, which exceeds safe autonomous scope.

### Technical Approach

Update the protected contract test `tests/contract/test_shared_dto_schemas_contract.py` in LOCKSTEP with the enum restoration so the gate reflects the A-0006 target contracts rather than the drifted current sets.

- `test_resume_core_enums_preserve_truth_and_match_states` (lines 45-62) must assert VerificationState == `{source_stated, user_verified, imported, inferred, unknown}` and ResolutionState == `{exact_match, alias_match, verified_fact_match, related_match, possible_match, unknown, explicitly_missing, not_applicable}`.
- `test_resume_core_schema_required_fields_are_stable` (lines 31-43) must be updated for the restored ResumeChangeOperation required set and any JobModel required-field change. Coordinate the exact expected sets with those tasks (RKIT-T-0005 and RKIT-T-0008) so this edit lands once, not thrice.
- The career-store `store_surface.json` enum lists are owned by the enum task — do NOT touch them here. This task owns ONLY the shared-DTO test file plus `resume-core/core_surface.json` IF its exported-symbol list or field manifests need adjustment. It lists symbol NAMES only today, so likely no change is required; verify this before editing and leave it untouched if unchanged.

APPROVED-DECISION NOTE (binding): The protected file edit is authorized ONLY by RKIT-A-0006 realignment-to-documented-contract. This means: strengthen-or-preserve assertion strength (keep whole-set `assertEqual`, do not weaken to a subset/`assertIn`), leave fixture truth unchanged, and re-register the straight-jacket entry if the protected manifest hash changes as a result. This authorization does not extend to any other edit type on the protected surface.

### Files

- `/Users/danielcassil/Code/resume-kit-2/tests/contract/test_shared_dto_schemas_contract.py` (PROTECTED — straight-jacket; edit authorized only under RKIT-A-0006 realignment-to-documented-contract)
- `/Users/danielcassil/Code/resume-kit-2/resume-core/core_surface.json` (surface manifest — edit only if the exported-symbol list or field manifest actually needs adjustment; likely no change)

### Dependencies

- [[RKIT-T-0003]] — restores the canonical enum members (VerificationState, ResolutionState); this test's enum assertions must match its restored sets, so it must land first.
- [[RKIT-T-0005]] — restores the ResumeChangeOperation shape and required fields; the required-field expected map depends on its final set.
- [[RKIT-T-0008]] — completes the JobModel section-4.2 shape; any JobModel required-field change must be reflected here, so coordinate the expected sets before editing.

Cross-initiative/semantic links: the restored contracts gated here are consumed downstream by RKIT-I-0004; keep expectations aligned with the documented A-0006 contract that initiative depends on. The straight-jacket registration for the contract test is owned by the package/initiative that maintains the protected-file manifest — re-register there if the hash changes.

### Risk Considerations

- Protected-surface / straight-jacket constraint: this is a straight-jacket-protected file; any edit outside the A-0006 realignment authorization is a violation. Assertion strength must be preserved or strengthened — accidental downgrade to `assertIn`/subset, skip, or xfail is the primary failure mode and is explicitly disallowed.
- Cross-package blast radius: the expected enum/required-field sets must match three upstream tasks exactly; a mismatch turns the gate red across packages. Coordinate the final sets so the edit lands once.
- Determinism: fixture inputs must remain unchanged so the gate stays deterministic; only expected-value sets change, not the inputs being asserted against.
- Scope-boundary bleed: career-store `store_surface.json` enum lists are owned by the enum task and `resume-core/core_surface.json` should change only if its manifest genuinely shifts — do not expand this task into either owner's territory.

## Verification Steps

1. `python3 -m unittest tests.contract.test_shared_dto_schemas_contract -v` (run inside the gate venv, or via `python3 tools/run_gate.py --pr --root .`): all tests in the module pass.
2. `git diff tests/contract/test_shared_dto_schemas_contract.py`: confirm only enum-set and required-field expectations changed, no assertion-type weakening.
3. `python3 tools/run_gate.py --pr --root .`: full PR gate green on the combined branch.

## Status Updates

*To be added during implementation*