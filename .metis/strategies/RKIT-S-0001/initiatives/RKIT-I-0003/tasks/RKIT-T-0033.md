---
id: chunk-5-selection-unit-suites-and
level: task
title: "Chunk 5: Selection unit suites and TEST_SPEC strengthening"
short_code: "RKIT-T-0033"
created_at: 2026-08-14T21:14:46.127322+00:00
updated_at: 2026-08-14T21:14:46.127322+00:00
parent: resume-core-selection-planning-and
blocked_by: ["RKIT-T-0032"]
archived: false

tags:
  - "#task"
  - "#phase/todo"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0003
---

# Chunk 5: Selection unit suites and TEST_SPEC strengthening

## Parent Initiative

[[RKIT-I-0003]]

## Objective

Close out the initiative: complete the TEST_SPEC selection-planning unit cases (min/max respect for skills/experience/bullets, configured section order, projects placement), strengthen the specs so min constraints, the section-order default, and deficit flagging are explicitly required (the looseness that certified the max-only stub), and remove the deprecated flat `max_skills` key after migrating in-repo callers.

## Acceptance Criteria

- [ ] Unit cases exist and pass for: skills min/max, experience min/max, bulletsPerRole min/max (respect + deficit flags), configured sectionOrder honored, section 13 default order incl. projects placement. (Add to the chunk 1-4 modules or one consolidated module; no duplication.)
- [ ] resume-core TEST_SPEC + tests/TEST_SPEC.md explicitly require: min constraint enforcement via deficit flags (never fabrication), the section 13 default order, bullet-granularity entries, unconditional match-derived traceability, immutability, determinism. Strengthen-only.
- [ ] Flat `max_skills` REMOVED: in-repo producers migrated to `resume.skills.max`; supplying it now yields the typed unknown-key error (unit-tested); grep-verified no producers remain.
- [ ] Full verification: `--pr`, `--future-contract`, `--smoke` all green; snapshot no-drift; straight-jacket verify clean (protected files should not change; stop-and-batch if one must).

## Implementation Notes

### Execution Profile

Recommended Agent: opus + medium

### Technical Approach

- Mirror the I-0002 Chunk 6 pattern exactly (it worked): coverage audit first, migrate flat-key producers grep-driven (watch for unrelated `max_skills`-like strings), remove the deprecation mapping, strengthen specs additively.
- Verify no remaining declared-but-unmapped selection categories in suite_manifest.

### Files

- `tests/unit/*` (consolidation/additions), `resume-core/TEST_SPEC.md`, `tests/TEST_SPEC.md`
- `resume-core/resume_core/resume_config.py` (remove deprecation mapping), flat-key producers (resume-cli/workflow/fixtures/tests)

## Verification Steps

1. `grep -rn "max_skills" --include=*.py --include=*.json . | grep -v ".metis\|.agents"` → no producers
2. `python3 tools/run_gate.py --pr --root . && python3 tools/run_gate.py --future-contract --root . && python3 tools/run_gate.py --smoke --root .` all green
3. `straight-jacket verify` clean.

## Status Updates

*To be added during implementation*
