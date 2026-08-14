---
id: chunk-2-matchresult-4-3-completion
level: task
title: "Chunk 2: MatchResult 4.3 completion - threshold, hardRequirementsResolved, decision"
short_code: "RKIT-T-0024"
created_at: 2026-08-14T19:46:11.232911+00:00
updated_at: 2026-08-14T19:46:11.232911+00:00
parent: resume-core-deterministic
blocked_by: ["RKIT-T-0023"]
archived: false

tags:
  - "#task"
  - "#phase/todo"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0002
---

# Chunk 2: MatchResult 4.3 completion - threshold, hardRequirementsResolved, decision

## Parent Initiative

[[RKIT-I-0002]]

## Objective

Complete `MatchResult` to the section 4.3 / RKIT-A-0006 item 4 contract: add `threshold` (from `matching.scoreAutoThreshold`), `hardRequirementsResolved` (bool), and the tri-state `decision` (`continue` / `resolve_gaps` / `blocked`) computed by a pure decision function. Critically, this chunk FIXES the audit's empirically verified defect: `matching.requireHardRequirementsResolved: true` currently does NOT gate continuation (domain.py:1092-1093). After this chunk, an unresolved hard requirement under that config yields `decision: 'blocked'`.

## Acceptance Criteria

- [ ] `scoreMatch`'s result includes `threshold` (sourced from resolved `matching.scoreAutoThreshold`), `hardRequirementsResolved`, and `decision` taking exactly the three contract values; resume-core schemas (schemas.py:148-162 region) updated to require them.
- [ ] Decision is a pure function of (score, threshold, hardRequirementsResolved, config): `blocked` dominates when `requireHardRequirementsResolved` is true and any hard requirement is unresolved; else `resolve_gaps` when score < threshold; else `continue`. Unit-tested over the full case matrix.
- [ ] The audit's reproduced-failure scenario is a test: config `matching.requireHardRequirementsResolved: true` + one unresolved hard requirement → `decision: 'blocked'` (and `can_continue` false). This test would FAIL against pre-chunk code.
- [ ] `can_continue` retained and derived (`decision == 'continue'`) for the migration window — no caller-visible regression; contract test asserts derivation consistency.
- [ ] Shared-DTO/contract tests realigned strengthen-only for the new required fields; PR + smoke gates green. The I-0051 match snapshots (initial/post-aws/post-graphql/final/job-b) WILL change (new fields): regenerate via `tools/regenerate_expected_snapshots.py --write`, present the diff for Daniel's review, commit reviewed baselines.

## Implementation Notes

### Execution Profile

Recommended Agent: opus + high

Codex-exec: yes with a tight prompt; driver must run the snapshot regenerate and get Daniel's baseline re-approval before commit.

### Technical Approach

- Add fields to the MatchResult schema and populate in `scoreMatch` (domain.py:336-350 region). `hardRequirementsResolved` = no required-classification requirement in an unresolved state per the resolution ladder (related/possible do NOT count as resolved for hard requirements — preserve the invariant).
- Implement `decide_match(score, threshold, hard_resolved, config)` as a standalone pure function; `scoreMatch` calls it.
- Fix the domain.py:1092-1093 read to consume the Chunk 1 MatchingConfig accessor.
- Downstream shim check: MatchResult consumers in CLI/workflow may need the same treatment as the I-0001 DTO lesson — run `--smoke` before commit; document any compat shims (owned by RKIT-I-0037/0040).

### Files

- `resume-core/resume_core/domain.py`, `schemas.py`
- `tests/contract/test_resume_core_contract.py` + shared-DTO contract test (strengthen-only realignment per A-0006)
- `tests/unit/test_match_decision_unit.py` (new)
- `fixtures/expected/*match*.json` regenerated + re-reviewed

### Dependencies

- [[RKIT-T-0023]] — MatchingConfig accessor supplies threshold + requireHardRequirementsResolved.

### Risk Considerations

- Baseline churn: 5+ match snapshots change; do ONE regenerate+review cycle here, not per-field.
- Smoke breakage: MatchResult shape changes hit CLI/workflow consumers — `--smoke` before commit (I-0001 lesson).
- Invariant: related/possible must never satisfy hardRequirementsResolved; regression-tested.

## Verification Steps

1. `python3 -m unittest tests.unit.test_match_decision_unit -v` (incl. the audit-reproduction case)
2. `python3 tools/regenerate_expected_snapshots.py --root . --write` → review diff with Daniel → commit
3. `python3 tools/run_gate.py --pr --root .` and `--smoke` green.

## Status Updates

*To be added during implementation*
