---
id: chunk-3-matchdimension-weighted
level: task
title: "Chunk 3: MatchDimension weighted breakdown with config-sourced weights and evidence"
short_code: "RKIT-T-0025"
created_at: 2026-08-14T19:46:11.275815+00:00
updated_at: 2026-08-14T20:53:31.752471+00:00
parent: resume-core-deterministic
blocked_by: [RKIT-T-0024]
archived: false

tags:
  - "#task"
  - "#phase/completed"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0002
---

# Chunk 3: MatchDimension weighted breakdown with config-sourced weights and evidence

## Parent Initiative

[[RKIT-I-0002]]

## Objective

Give every score an explainable, weighted breakdown: add `dimensions: MatchDimension[]` to MatchResult, replace the hardcoded 10/3/2/1 `_default_weight` (domain.py:853-858) with config-sourced weights from `matching.weights`, and make the overall score the normalized weighted sum of dimensions. This makes section 5's "explainable score breakdowns" real and TEST_SPEC:103's "dimensions add/explain consistently" enforceable — today unenforceable because dimensions do not exist.

## Acceptance Criteria

## Acceptance Criteria

## Acceptance Criteria

- [ ] `MatchDimension` = {name (one of the section 13 weight keys), weight, score (0-1), contribution (weight × score), evidence (requirement/fact/term references)}; schema added and required on MatchResult.
- [ ] Overall score equals the normalized weighted sum of dimension contributions, asserted at a documented rounding precision; per-requirement resolution rows retained unchanged (consumers can explain both "why this score" and "why this requirement state").
- [ ] Dimensions populated for requiredSkills, preferredSkills, experience, roleAlignment, domainIndustry. `terminology` is present with its config weight but score 0 and empty evidence until Chunk 5 (documented placeholder — dimension list is contract-complete from day one).
- [ ] `matching.weights` drives weighting: a unit test varies one weight and asserts contributions change deterministically; `_default_weight` hardcoding removed, defaults live in the Chunk 1 config layer.
- [ ] Evidence refs point at real requirement/fact ids from the inputs — no fabricated refs. PR + smoke green; match snapshots regenerated + Daniel-re-reviewed (one cycle).

## Implementation Notes

### Execution Profile

Recommended Agent: opus + high

Codex-exec: yes with a tight prompt; the dimension partition rules need driver review before commit.

### Technical Approach

- Partition scoring inputs into the dimension taxonomy by existing requirement metadata: required-classification → requiredSkills; preferred → preferredSkills; years/experience-shaped → experience; role/title alignment → roleAlignment; domain/industry terms → domainIndustry. Deterministic rules, documented in the module docstring; ambiguous requirements default by classification rather than clever inference.
- Per-dimension score = resolution-weighted fraction of that dimension's requirements (consistent with existing ladder semantics); contribution = weight × score; overall = Σcontribution / Σweight.
- Keep the score scale consistent with current outputs where possible; where the overall score necessarily shifts, the snapshot re-review is the honesty gate.
- `decision`/`can_continue` recompute automatically off the new overall score via Chunk 2's decision function.

### Files

- `resume-core/resume_core/domain.py`, `schemas.py`
- `tests/unit/test_match_dimensions_unit.py` (new): weight-variation determinism, dimensions-sum-to-score, terminology placeholder shape
- Contract test strengthen-only realignment; `fixtures/expected/*match*.json` regenerate + re-review

### Dependencies

- [[RKIT-T-0024]] — extends the MatchResult shape and decision function from Chunk 2.

### Risk Considerations

- Score drift: re-partitioning may shift overall scores; every shift is surfaced through snapshot review, never silently absorbed.
- Floating-point flake: use a documented rounding precision for the sum assertion.
- Do not alter per-requirement row semantics — rows and dimensions are complementary views.

## Verification Steps

1. `python3 -m unittest tests.unit.test_match_dimensions_unit -v`
2. Regenerate snapshots → Daniel review → commit
3. `python3 tools/run_gate.py --pr --root .` and `--smoke` green.

## Status Updates

- 2026-08-14: Codex-implemented (new `match_dimensions.py`; MatchDimension schema required on match_result; `_default_weight` removed, weighting config-sourced; terminology placeholder score 0). Overall scores legitimately shifted with the re-partition (e.g. initial-job-a 56→49.7, job-b 46→38.3); driver reviewed the representative breakdown (requiredSkills 0.3/1.0, experience 0.25/1.0, domainIndustry 0.1/1.0, preferredSkills 0.1/0.67, terminology 0.1/0.0) — sane. Existing scoring-math unit tests realigned to new values incl. can_continue now deriving from decision (below-threshold → False): legitimate T-0024 semantics, not weakening. Driver additionally fixed float noise (weight 3.0000000000000004) by rounding config-scaled requirement weights to 9 decimals in `default_requirement_weight` before re-baselining. 8 snapshots re-baselined, no-drift proven. PR 257 + smoke green.