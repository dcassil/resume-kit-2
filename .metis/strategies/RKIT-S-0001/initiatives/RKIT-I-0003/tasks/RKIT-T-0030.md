---
id: chunk-2-section-13-resume-config
level: task
title: "Chunk 2: Section 13 resume.* config wiring - min/max, sectionOrder, targetPages"
short_code: "RKIT-T-0030"
created_at: 2026-08-14T21:14:45.994575+00:00
updated_at: 2026-08-14T21:14:45.994575+00:00
parent: resume-core-selection-planning-and
blocked_by: ["RKIT-T-0029"]
archived: false

tags:
  - "#task"
  - "#phase/todo"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0003
---

# Chunk 2: Section 13 resume.* config wiring - min/max, sectionOrder, targetPages

## Parent Initiative

[[RKIT-I-0003]]

## Objective

Make the section 13 `resume.*` config namespace authoritative for selection: validated min AND max for skills, experience entries, and bulletsPerRole; `sectionOrder` (fixing the default divergence — section 13 says `['summary','skills','experience','projects','education']`, code says `['basics',...]` without projects, domain.py:423); and `targetPages` recorded in the plan. Replaces the ad-hoc flat `max_skills` key (domain.py:410-412) following the same accessor pattern as I-0002's `matching.*` wiring (deprecate now, remove at initiative end).

## Acceptance Criteria

- [ ] A `resume` config namespace parsed/validated in the matching_config.py style (typed unknown-key rejection, single-source defaults): `skills` {min,max}, `experience` {min,max}, `bulletsPerRole` {min,max}, `sectionOrder` (list of section names, validated against known sections), `targetPages` (number). Accessor `resolve_resume_config(config)`.
- [ ] Max constraints enforced: overflow drops lowest-relevance items (current relevance until Chunk 3). Min constraints NEVER fabricate: a below-min section yields a `deficit` row in constraint_report — honesty preserved.
- [ ] Default sectionOrder is section 13's `['summary','skills','experience','projects','education']`; configured order wins; the plan's sections follow the effective order.
- [ ] Flat `max_skills` accepted-with-deprecation mapped to `resume.skills.max` (warning; conflict → typed error); removal at initiative close (Chunk 5).
- [ ] targetPages read and recorded in plan metadata. Snapshots re-baselined (sectionOrder change WILL shift selection-plan and possibly run-manifest), no-drift proven, driver-reviewed; PR + smoke green.

## Implementation Notes

### Execution Profile

Recommended Agent: opus + high

### Technical Approach

- Extend `matching_config.py` or create sibling `resume_config.py` (prefer sibling; same helpers) with the accessor + defaults. Reuse `_issue`/value validators.
- Enforce in `rankResumeContent` via the Chunk 1 constraint_report: each min/max produces a row {constraint, limit, actual, status}.
- The sectionOrder divergence is a REAL behavior change (basics disappears from the ordering default; projects appears). Check how `basics` is consumed downstream (render/CLI) before dropping it from the default order — if basics must stay renderable, keep it pinned first outside the configurable order and document; do not silently break rendering. Run --smoke to catch this.

### Files

- `resume-core/resume_core/resume_config.py` (new), `domain.py`
- `tests/unit/test_resume_config_unit.py` (new; mapped in suite_manifest, gate wiring deferred)
- `fixtures/expected/selection-plan.json` (+ any manifest churn) regenerate + review

## Verification Steps

1. `python3 -m unittest tests.unit.test_resume_config_unit -v`
2. Regenerate snapshots ×2 → no drift; review
3. `python3 tools/run_gate.py --pr --root .` and `--smoke` green.

## Status Updates

*To be added during implementation*
