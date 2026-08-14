---
id: chunk-5-terminology-scoring
level: task
title: "Chunk 5: Terminology scoring dimension over JobTerm"
short_code: "RKIT-T-0027"
created_at: 2026-08-14T19:46:11.360343+00:00
updated_at: 2026-08-14T19:46:11.360343+00:00
parent: resume-core-deterministic
blocked_by: ["RKIT-T-0026"]
archived: false

tags:
  - "#task"
  - "#phase/todo"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0002
---

# Chunk 5: Terminology scoring dimension over JobTerm

## Parent Initiative

[[RKIT-I-0002]]

## Objective

Activate the `terminology` scoring dimension (placeholder since Chunk 3) over the JobTerm substrate RKIT-I-0001 delivered: for each `JobModel.terminology` term, determine whether the resume uses the job's surface form versus only the canonical form; the dimension score is the weighted fraction of job terms mirrored. This gives the "prefer job terminology" product goal and workflow step E.2 their scoring substrate — without score pressure, terminology alignment has no mechanism to influence decisions (the initiative's rejected-alternative analysis).

## Acceptance Criteria

- [ ] The `terminology` dimension computes a real score: fraction of `JobModel.terminology` JobTerms whose job-surface form appears in the resume's surface text (deterministic text matching over normalized claims — no LLM, no fuzzy similarity).
- [ ] Evidence records, per term: the JobTerm, whether it matched in job-surface form, canonical-only form, or not at all, and where (claim/field refs) — feeding workflow E.2's terminology-alignment opportunities.
- [ ] `matching.weights.terminology` weights the dimension; weight 0 removes its score influence entirely (unit-tested) so callers can opt out without shape changes.
- [ ] A resume using only canonical forms scores lower on this dimension than one mirroring job surface forms, all else equal (unit-tested pair); jobs with empty `terminology` yield a well-defined dimension (score 1 or documented neutral — pick one, document, test).
- [ ] Overall-score sum invariant from Chunk 3 still holds with the live dimension. PR + smoke green; snapshots regenerated + Daniel-re-reviewed (terminology now contributes, most match snapshots will shift).

## Implementation Notes

### Execution Profile

Recommended Agent: opus + medium

Codex-exec: yes; the matching rule is deterministic string work over existing structures; driver reviews the empty-terminology semantics choice.

### Technical Approach

- Iterate `JobModel.terminology` (JobTerm substrate from RKIT-T-0008): each JobTerm carries surface and canonical forms. Match against the resume's normalized claim text (the claim-fields substrate from RKIT-T-0009 gives claim-level provenance to cite in evidence).
- Word-boundary, case-insensitive exact matching on the surface form; canonical-form-only matches count as "canonical-only" in evidence and do NOT count toward the mirrored fraction (that distinction IS the signal).
- Empty-terminology semantics: prefer score = 1.0 (nothing to mirror → no penalty) unless review finds a documented reason otherwise; document the choice in the module and TEST_SPEC.
- Replace the Chunk 3 placeholder wiring; no schema change needed (dimension shape already exists).

### Files

- `resume-core/resume_core/domain.py` (terminology dimension implementation)
- `tests/unit/test_terminology_dimension_unit.py` (new)
- `fixtures/expected/*match*.json` regenerate + re-review

### Dependencies

- [[RKIT-T-0026]] — serialized on the domain.py chain; relationship inputs must not double-count terminology matches.
- RKIT-I-0001's JobTerm (RKIT-T-0008) and claim-fields (RKIT-T-0009) substrates (completed).

### Risk Considerations

- Double-counting: terminology mirroring is a wording signal, not skill evidence — it must not affect requirement resolution states, only its own dimension.
- Matching too loose/tight: word-boundary exact matching is the deterministic middle; no substring soup ("Java" must not match "JavaScript").
- Snapshot churn: expected and reviewed in one cycle.

## Verification Steps

1. `python3 -m unittest tests.unit.test_terminology_dimension_unit -v`
2. Regenerate snapshots → Daniel review → commit
3. `python3 tools/run_gate.py --pr --root .` and `--smoke` green.

## Status Updates

*To be added during implementation*
