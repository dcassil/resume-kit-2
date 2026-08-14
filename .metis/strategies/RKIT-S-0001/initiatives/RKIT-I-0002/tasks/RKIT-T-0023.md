---
id: chunk-1-section-13-matching-config
level: task
title: "Chunk 1: Section 13 matching.* config wiring, validation, flat-key deprecation"
short_code: "RKIT-T-0023"
created_at: 2026-08-14T19:46:11.187064+00:00
updated_at: 2026-08-14T20:34:37.655433+00:00
parent: resume-core-deterministic
blocked_by: []
archived: false

tags:
  - "#task"
  - "#phase/completed"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0002
---

# Chunk 1: Section 13 matching.* config wiring, validation, flat-key deprecation

## Parent Initiative

[[RKIT-I-0002]]

## Objective

Wire the section 13 `matching.*` config namespace through resume-core's shared config validation layer so scoring and gating read documented, validated keys instead of the ad-hoc flat keys (`policy`, `require_hard_resolution`) the audit found at `domain.py:1092-1093, 795`. This is the substrate chunk: every later chunk (threshold, decision, weights, terminology) reads its knobs through what this task builds, so the parse/validate/default plumbing must land first and be right.

## Acceptance Criteria

## Acceptance Criteria

## Acceptance Criteria

- [ ] A `matching` config namespace is parsed and validated: `scoreAutoThreshold` (number), `weights` (object with exactly the section 13 keys: requiredSkills, experience, roleAlignment, domainIndustry, preferredSkills, terminology — each a number), `requireHardRequirementsResolved` (bool). Unknown keys inside `matching` or `matching.weights` produce a TYPED validation error (consistent with the RKIT-I-0001 config validation style), not silent acceptance.
- [ ] Documented defaults per section 13 apply when keys are absent; defaults are defined in one place and covered by a unit test.
- [ ] Flat keys `policy` and `require_hard_resolution` are accepted-with-deprecation for the migration window: they map onto the new namespace, a deprecation warning is surfaced in the validation result (non-fatal), and a conflict between a flat key and its `matching.*` equivalent is a typed validation error. (Removal of the flat keys happens in Chunk 6 / RKIT-T-0028, after in-repo callers migrate — approved decision: deprecate in I-0002, remove at end of I-0002.)
- [ ] `scoreMatch` and validateChange-adjacent config reads consume the parsed `matching` config object — no call site reads the flat keys directly anymore (grep-verifiable).
- [ ] All existing tests green: `python3 tools/run_gate.py --pr --root .` (257) and `--smoke` pass. Existing fixtures/config files that use flat keys keep working via the deprecation mapping (snapshot baselines unchanged in this chunk).

## Implementation Notes

### Execution Profile

Recommended Agent: opus + high

Codex-exec: yes, with a tight prompt encoding the decisions above — but this is substrate the whole initiative consumes, so the driver must review the parsed-config object shape carefully before committing.

### Technical Approach

- Extend the config parsing/validation layer RKIT-I-0001 established (see `resume-core/resume_core/` config handling and the section 13 vocabulary in `PRODUCT_VISION_AND_CONTRACTS.md`) with a `matching` sub-schema. Follow the same typed-rejection pattern as `dates.py` / validateResume: structured error objects, no exceptions-as-control-flow surprises.
- Introduce one internal accessor (e.g. `resolve_matching_config(config) -> MatchingConfig`) that: applies defaults, maps deprecated flat keys, records deprecation warnings, rejects unknown keys/conflicts. All scoring code calls this accessor — never raw dict lookups.
- Migration mapping: `require_hard_resolution` → `matching.requireHardRequirementsResolved`; `policy` maps to its documented equivalent (inspect current semantics at domain.py:795,1092-1093 and map faithfully; if `policy` carries semantics beyond matching config, leave that portion untouched and document).
- Do NOT change gating/scoring behavior in this chunk beyond the config source: behavior parity is the goal; the requireHardRequirementsResolved gating FIX is Chunk 2's scope.

### Files

- `resume-core/resume_core/` config module (extend) + `domain.py` call sites (read via accessor)
- `tests/unit/test_matching_config_unit.py` (new): defaults, unknown-key rejection, flat-key mapping, conflict rejection, deprecation warning presence
- resume-core TEST_SPEC additions for the config contract (NON-protected package spec)

### Dependencies

None within I-0002 (chain root). Builds on RKIT-I-0001's config validation layer (completed).

### Risk Considerations

- Behavior parity: changing the config source must not change scores — the I-0051 snapshot-comparison test (tests/snapshots) is the guard; it must stay green in this chunk.
- Flat-key semantics: map `policy` faithfully; if uncertain, preserve current behavior and document rather than guess.
- Downstream lock-in: every later chunk reads MatchingConfig; get the accessor shape reviewed before commit.

## Verification Steps

1. `python3 -m unittest tests.unit.test_matching_config_unit -v`
2. `grep -rn "require_hard_resolution\|\"policy\"" resume-core/resume_core/domain.py` — only the deprecation mapping site remains.
3. `python3 tools/run_gate.py --pr --root .` and `--smoke` green; snapshot test unchanged.

## Status Updates

- 2026-08-14: Codex-implemented, reviewed, committed. New `matching_config.py` with `resolve_matching_config` → {config, errors, warnings}; snake_case internal fields; defaults single-sourced; `policy:"strict"` → requireHardRequirementsResolved=True (faithful to old domain.py behavior), conflicts → `conflicting_matching_config_key`. No flat-key reads left in domain.py. 6 new unit tests green; PR 257 + smoke green; snapshots unchanged (behavior parity proven). Gate wiring of the new unit module deferred to the end-of-initiative password batch.