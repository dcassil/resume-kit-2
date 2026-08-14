---
id: restore-canonical-enums-cross
level: task
title: "Restore canonical enums + cross-package reader/conflict-record migration"
short_code: "RKIT-T-0003"
created_at: 2026-08-14T03:10:17.492366+00:00
updated_at: 2026-08-14T03:10:17.492366+00:00
parent: resume-core-canonical-contracts
blocked_by: []
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

# Restore canonical enums + cross-package reader/conflict-record migration

## Parent Initiative

[[RKIT-I-0001]]

## Objective

Realign the two shared enums in `resume-core/resume_core/schemas.py` (`VerificationState`, `ResolutionState`) to the A-0006 canonical target sets and, in the same lockstep task, reconcile every reader across BOTH resume-core and career-store. This is the load-bearing substrate for the entire resume-core contract chain: because `career_store.VerificationState` IS `resume_core.VerificationState` (identity asserted at `test_shared_dto_schemas_contract.py:78`), the enum edit and its cross-package readers must land together or the tree will not import.

## Acceptance Criteria

- [ ] `resume_core.VerificationState` value set equals exactly `{"source_stated", "user_verified", "imported", "inferred", "unknown"}`: no `explicitly_missing`, no `conflicted`, `imported` present.
- [ ] `resume_core.ResolutionState` value set equals exactly `{"exact_match", "alias_match", "verified_fact_match", "related_match", "possible_match", "unknown", "explicitly_missing", "not_applicable"}`: `not_applicable` present, `conflicted` absent, `explicitly_missing` retained.
- [ ] `domain.py:30` `_VERIFIED_FACT_STATES` contains `VerificationState.IMPORTED.value` (not the raw string `"imported"`); no enum-substitute usage of the bare string `"imported"` remains in `domain.py`.
- [ ] career-store imports cleanly: `python3 -c 'import career_store'` raises no `AttributeError`; no reference to `VerificationState.CONFLICTED`, `VerificationState.EXPLICITLY_MISSING`, or `ResolutionState.CONFLICTED` remains as an enum-attribute access anywhere in `career-store/career_store/*.py`.
- [ ] `_fact_resolution` no longer reads a FACT's `verification_state == 'explicitly_missing'`; explicit-absence resolution is driven by `ResolutionState.EXPLICITLY_MISSING`, and existing `_fact_resolution` behavior for the explicit-missing case is preserved (same `ResolutionState` returned for the same explicit-missing input fixture).
- [ ] career-store conflict handling is migrated via the first-class conflict-record path (per the approved decision) with zero silent behavior loss: no code path that previously returned `'conflicted'` now returns `None` or raises.

## Implementation Notes

### Execution Profile

Recommended Agent: opus + high

Codex-exec autonomously implementable: no — the proposal marks this task `codexSuitable: false`; it crosses the resume-core/career-store package boundary, edits a shared enum whose identity is contract-asserted, and requires a judgment-bearing conflict-handling migration that cannot be mechanically inferred.

### Technical Approach

Realign the two shared enums in `resume-core/resume_core/schemas.py` to the A-0006 target sets:

- `VerificationState` becomes exactly `{source_stated, user_verified, imported, inferred, unknown}`: ADD `IMPORTED='imported'`; REMOVE `EXPLICITLY_MISSING` and `CONFLICTED`.
- `ResolutionState` becomes exactly `{exact_match, alias_match, verified_fact_match, related_match, possible_match, unknown, explicitly_missing, not_applicable}`: ADD `NOT_APPLICABLE='not_applicable'`; REMOVE `CONFLICTED`; KEEP `explicitly_missing`.

Then fix all readers in the SAME task (the enums are a single shared object — do not split the enum edit from its readers or the tree will not import):

- **(a)** resume-core `domain.py:30` — replace the raw string `'imported'` in `_VERIFIED_FACT_STATES` with `VerificationState.IMPORTED.value`.
- **(b)** resume-core `_fact_resolution` (`domain.py:1021-1023,1030-1031`) — currently keys off `VerificationState.EXPLICITLY_MISSING` on a FACT's `verification_state`; migrate this to read the fact's `resolution_state`/explicit-missing signal via `ResolutionState.EXPLICITLY_MISSING` instead, since a fact can no longer carry `verification_state='explicitly_missing'`.
- **(c)** career-store `matching.py:36` (`VerificationState.CONFLICTED` rank), `:46` (`ResolutionState.CONFLICTED` rank), `:250`, `:462-463`, `:506`, and `store.py:1166-1169` — all reference removed members and MUST be migrated per the approved conflict-handling disposition below.
- **(d)** update career-store `store_surface.json:33-34,49-50` enum lists and any `store.py` literal maps (lines `22-23,33-34,142,144,900,902,1016`) that hard-code `'conflicted'`/`'explicitly_missing'` as verification states.

**APPROVED DECISION (conflict handling = option 1):** Implement a first-class CONFLICT-RECORD path in career-store — migrate `matching.py`/`store.py` to EMIT conflict records instead of the removed `CONFLICTED` enum member; preserve current conflict-detection behavior with correct contracts. This is a CROSS-PACKAGE lockstep task (resume-core enum edit + career-store reader migration + `store_surface.json`) because `career_store.VerificationState` IS `resume_core.VerificationState`. Keep snake_case field names. The enum edit and its readers MUST land together or the tree will not import.

### Files

- `/Users/danielcassil/Code/resume-kit-2/resume-core/resume_core/schemas.py`
- `/Users/danielcassil/Code/resume-kit-2/resume-core/resume_core/domain.py`
- `/Users/danielcassil/Code/resume-kit-2/career-store/career_store/matching.py`
- `/Users/danielcassil/Code/resume-kit-2/career-store/career_store/store.py`
- `/Users/danielcassil/Code/resume-kit-2/career-store/store_surface.json`

### Dependencies

No task dependencies — startable once the initiative is active (`dependsOn: []`).

Semantic/cross-boundary links to hold in mind:
- The shared-DTO contract test and career-store contract/boundary tests are edited in a PAIRED task; run the gate on the COMBINED branch so the enum edit and the lockstep test edit land together.
- Downstream RKIT-I-0004 consumers depend on these canonical enum sets; getting the target sets exactly right here prevents compounding rework there.
- career-store owns its own package tests (including any xfail markers); coordinate the conflict-record contract with the owning package initiative.

### Risk Considerations

- **Cross-package blast radius:** the enum is a single shared object; missing a reader in either package breaks import of the whole tree. Every `CONFLICTED`/`EXPLICITLY_MISSING` enum-attribute access must be migrated in lockstep.
- **Protected-surface / straight-jacket constraints:** `schemas.py`, `store.py`, and `store_surface.json` are contract surfaces; changes must keep snake_case field names and preserve the asserted `VerificationState` identity — no drift in value strings.
- **Silent behavior loss:** the conflict-record migration must preserve current conflict-detection behavior exactly; no path that previously returned `'conflicted'` may now return `None` or raise.
- **Determinism:** enum value sets and resolution outputs must be reproducible; the explicit-missing `_fact_resolution` case must return the same `ResolutionState` for the same fixture.
- **Scope-boundary bleed:** limit changes to the five listed files and the enum-driven readers; do not fold in unrelated career-store refactors or downstream RKIT-I-0004 work.

## Verification Steps

1. `python3 -c "import resume_core; print(sorted(s.value for s in resume_core.VerificationState)); print(sorted(s.value for s in resume_core.ResolutionState))"` and confirm the two sets match the acceptance criteria exactly.
2. `python3 -c "import career_store"` must exit 0 with no `AttributeError`.
3. `python3 tools/run_gate.py --pr --root .` — the shared-DTO contract test and career-store contract/boundary tests must pass after the lockstep test edit in the paired task (run the gate on the combined branch).
4. `grep -rn 'CONFLICTED\|EXPLICITLY_MISSING' career-store/career_store/matching.py career-store/career_store/store.py` — every remaining hit must be a string literal in a conflict-record payload, never an enum attribute of `VerificationState`/`ResolutionState`.

## Status Updates

*To be added during implementation*