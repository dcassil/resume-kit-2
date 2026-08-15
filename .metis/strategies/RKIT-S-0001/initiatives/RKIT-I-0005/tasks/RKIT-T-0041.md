---
id: enum-restoration-persisted-value
level: task
title: "Enum restoration, persisted-value remap migration, surface/contract realignment"
short_code: "RKIT-T-0041"
created_at: 2026-08-14T23:56:07.483826+00:00
updated_at: 2026-08-15T00:16:37.690966+00:00
parent: durable-career-store-package-and
blocked_by: [RKIT-T-0040]
archived: false

tags:
  - "#task"
  - "#phase/active"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0005
---

# Enum restoration, persisted-value remap migration, surface/contract realignment

## Parent Initiative

[[RKIT-I-0005]]

## Objective

Restore the RKIT-A-0006 canonical enum vocabulary in career-store (store.py:16-35, store_surface.json:28-51) and remap persisted drifted values via a registry migration (RKIT-I-0005 Requirement 5): VerificationState = source_stated/user_verified/imported/inferred/unknown; ResolutionState regains `not_applicable` and drops `conflicted`; relationship types become alias/related/parent/child/equivalent plus `contradicts` (the A-0006-recorded extension).

## Acceptance Criteria

## Acceptance Criteria

- [ ] store.py enum sets match RKIT-A-0006 items 1, 2, 5 exactly; the shared resume-core DTO sets (already restored by RKIT-I-0001) and career-store sets are identical where they name the same enum — verified by a whole-set assertion, not membership spot checks.
- [ ] `store_surface.json` enum vocabulary realigned to the same sets (camelCase surface per A-0002); realign-only under A-0006.
- [ ] Registry migration remaps persisted drifted values: drifted verification values (e.g. `explicitly_missing`, `conflicted`) migrate to `unknown`, and where the prior state was `conflicted` a first-class conflict record is preserved/created so no conflict information is lost (A-0006 + I-0001's conflict-record path).
- [ ] Store APIs reject the removed drifted values on write with typed validation errors (no silent acceptance of `conflicted` as a verification state).
- [ ] Migration test verifies the remap row-by-row on a drifted fixture DB, including the conflict-record preservation case.
- [ ] career-store contract tests realigned strengthen-only (tests/contract/ not protected); if any boundary guardrail (tests/boundary/test_career_store_guardrails.py, tools/career_store_guardrails.py — PROTECTED) must change, STOP that sub-change and report for the accumulated approve/update-locks batch.
- [ ] PR + smoke gates green; no weakening of any existing assertion.

## Implementation Notes

### Technical Approach

Enum constants in store.py move to the canonical sets; write-path validation raises typed errors listing allowed values. The remap runs as registry migration after T-0040's entries: UPDATE facts SET verification_state='unknown' WHERE verification_state IN (...) with a pre-pass that INSERTs conflict records for rows previously `conflicted` (use the existing persisted-conflicts table from the I-0001-era conflict-record path). Relationship-type additions (`parent`/`child`) are vocabulary-only here — semantics belong to I-0007.

### Dependencies

RKIT-T-0040 (migrations sequence after schema realignment; conflict records may reference new columns).

### Risk Considerations

This is the surface-visible chunk: career-mcp/workflow/CLI may pass or assert drifted values — check `--smoke` and fix producers to canonical values, never re-accept drift. Boundary guardrails may pin the drifted sets; that requires the protected-edit report path, not a silent edit.

### Execution profile

Recommended Agent: opus + high

Rationale: cross-package vocabulary alignment with data migration and conflict-preservation semantics; wrong remap choices lose user data meaning irreversibly.

## Status Updates

- 2026-08-14: Read task and Requirement 5. Protected `tools/career_store_guardrails.py` pins canonical verification/resolution sets, but relationship types are still drifted at line 49 (`alias/equivalent/related/contradicts`, missing `parent`/`child`), so full `store_surface.json` relationship realignment must be deferred to Daniel's protected approve/update-locks batch.
- 2026-08-14: Implemented `005_enum_value_remap`, restored effective store relationship vocabulary to include `parent`/`child`, added typed write-path rejection for drifted verification/resolution values, and added row-by-row drifted fixture coverage including conflict preservation. Requested gates pass; full surface manifest relationship realignment remains deferred behind the protected guardrail pin.
