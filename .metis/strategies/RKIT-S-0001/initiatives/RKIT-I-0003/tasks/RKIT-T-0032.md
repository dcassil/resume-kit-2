---
id: chunk-4-bullet-level-selection
level: task
title: "Chunk 4: Bullet-level selection with unconditional match-derived traceability"
short_code: "RKIT-T-0032"
created_at: 2026-08-14T21:14:46.083741+00:00
updated_at: 2026-08-14T21:14:46.083741+00:00
parent: resume-core-selection-planning-and
blocked_by: ["RKIT-T-0031"]
archived: false

tags:
  - "#task"
  - "#phase/todo"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0003
---

# Chunk 4: Bullet-level selection with unconditional match-derived traceability

## Parent Initiative

[[RKIT-I-0003]]

## Objective

Extend selection to bullet granularity: plan entries address individual experience bullets by JSON path (not whole sections), `resume.bulletsPerRole` min/max enforce per role, and every match-derived keep/drop decision unconditionally carries reason + requirementIds/factIds (tightening the old "when supplied" wording). Also enforce that agent output cannot override structural maxima (regression-guarded).

## Acceptance Criteria

- [ ] Plan entries exist per experience bullet (path like `/experience/0/bullets/2`) with keep/drop actions; bulletsPerRole.max truncates lowest-relevance bullets per role; bulletsPerRole.min deficit-flags per role.
- [ ] Every entry whose decision derives from the match result has non-empty reason + requirement_ids (fact_ids where facts drove it); non-match-derived entries still carry a reason (e.g. "max_constraint_overflow", "unlinked_low_relevance"). No entry has an empty reason. Unit-tested.
- [ ] Structural-maxima guard: a test proves supplying an over-max "agent-proposed" selection cannot produce a plan exceeding configured maxima (retained requirement 8).
- [ ] Immutability + determinism invariants still green at bullet granularity.
- [ ] Snapshots re-baselined (selection-plan gains bullet entries — sizeable diff expected), no-drift proven, driver-reviewed; PR + smoke green.

## Implementation Notes

### Execution Profile

Recommended Agent: opus + high

### Technical Approach

- Reuse Chunk 3's requirement→content index at bullet level (bullets already carry claim-field provenance from RKIT-T-0009).
- Per-role enforcement iterates experience entries; document per-role tie-breaking (relevance, then bullet order).
- Keep whole-section entries for sections without sub-items (skills entries are individual items already).

### Files

- `resume-core/resume_core/domain.py` / `selection_ranking.py`
- `tests/unit/test_bullet_selection_unit.py` (new; mapped in suite_manifest, gate wiring deferred)
- `fixtures/expected/selection-plan.json` regenerate + review

## Verification Steps

1. `python3 -m unittest tests.unit.test_bullet_selection_unit -v`
2. Regenerate snapshots ×2 → no drift; review
3. `python3 tools/run_gate.py --pr --root .` and `--smoke` green.

## Status Updates

*To be added during implementation*
