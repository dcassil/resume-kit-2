---
id: chunk-1-contentselectionplan-dto
level: task
title: "Chunk 1: ContentSelectionPlan DTO, constraint report, immutability and determinism"
short_code: "RKIT-T-0029"
created_at: 2026-08-14T21:14:45.946943+00:00
updated_at: 2026-08-14T21:23:58.791629+00:00
parent: resume-core-selection-planning-and
blocked_by: []
archived: false

tags:
  - "#task"
  - "#phase/completed"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0003
---

# Chunk 1: ContentSelectionPlan DTO, constraint report, immutability and determinism

## Parent Initiative

[[RKIT-I-0003]]

## Objective

Establish the `ContentSelectionPlan` artifact shape that all later chunks populate: ordered sections, per-entry JSON-path addressing at bullet granularity with action/relevance/reason/requirementIds/factIds, a constraint report, and plan metadata — plus the two structural guarantees (input-resume immutability, run-to-run determinism) as tested invariants. This is the substrate chunk; a wrong DTO shape here compounds through ranking, selection, and the downstream RKIT-I-0004 applyChanges consumer.

## Acceptance Criteria

## Acceptance Criteria

## Acceptance Criteria

- [ ] `ContentSelectionPlan` schema defined in `schemas.py` and required from `rankResumeContent`'s result envelope: {schema_version, sections (ordered), entries[] each {path (JSON pointer), action ∈ {keep, drop, reorder}, relevance (number), reason (string), requirement_ids[], fact_ids[]}, constraint_report[] each {constraint, limit, actual, status ∈ {satisfied, violated, deficit}}, metadata {target_pages, config_snapshot}}.
- [ ] `rankResumeContent` populates the new shape for current behavior (skills cap becomes a constraint_report row; existing ordering becomes entries) — behavior parity where possible, shape completeness even where later chunks will refine values.
- [ ] Immutability test: deep-copy the input resume, run rankResumeContent, assert the input is byte-identical (the plan is a separate artifact).
- [ ] Determinism test: identical inputs produce identical plans across two runs.
- [ ] Contract test realigned strengthen-only for the new plan shape; `selection-plan.json` snapshot regenerated (shape change expected — driver reviews), no-drift proven; PR + smoke green.

## Implementation Notes

### Execution Profile

Recommended Agent: opus + high

Codex-exec: yes with a tight prompt; the DTO is consumed by I-0004's applyChanges downstream, so the driver reviews the shape before commit.

### Technical Approach

- Model on the section 4 DTO conventions already in `schemas.py` (snake_case, schema_version'd). Keep per-entry fields unconditional: `requirement_ids`/`fact_ids` are empty lists (not absent) when a decision is not match-derived.
- `rankResumeContent` (domain.py:399-432) keeps its current decisions in this chunk but expresses them in the new shape; `del match_result` stays (removed in Chunk 3) — parity first, behavior later.
- constraint_report gets one row per enforced constraint; only the max_skills cap exists today — record it truthfully.
- config_snapshot records the effective selection config used (currently the flat max_skills read; Chunk 2 replaces the source).

### Files

- `resume-core/resume_core/schemas.py`, `domain.py`
- `tests/unit/test_selection_plan_shape_unit.py` (new: shape, immutability, determinism) — mapped in `tests/suite_manifest.json` (gate wiring in the pending password batch)
- `tests/contract/test_resume_core_contract.py` strengthen-only; `fixtures/expected/selection-plan.json` regenerate + review

## Verification Steps

1. `python3 -m unittest tests.unit.test_selection_plan_shape_unit -v`
2. `python3 tools/regenerate_expected_snapshots.py --root . --write` ×2 → no drift; review selection-plan diff
3. `python3 tools/run_gate.py --pr --root .` and `--smoke` green.

## Status Updates

### 2026-08-14 implementation checkpoint
- Added ContentSelectionPlan DTO schema family and exports in resume-core schemas.
- Reworked rankResumeContent to keep `del match_result`, preserve `ranked_content`, and emit the new `selection_plan` shape with ordered sections, entries, max_skills constraint_report, target_pages, and config_snapshot.
- Added unit coverage for shape, byte-identical input immutability, and deterministic repeat runs; mapped the module in tests/suite_manifest.json.
- Strengthened resume-core/shared DTO contracts; focused unit test is green and touched contracts pass when run with package roots on PYTHONPATH.
- Regenerated selection-plan snapshot twice with no drift; final diff is `fixtures/expected/selection-plan.json` only under fixtures/expected.
- Verification completed: focused unit green, PR gate green, smoke gate green, Straight Jacket verify clean.