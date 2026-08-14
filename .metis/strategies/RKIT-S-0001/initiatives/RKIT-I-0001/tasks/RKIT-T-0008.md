---
id: complete-jobmodel-section-4-2
level: task
title: "Complete JobModel section 4.2 shape and JobTerm substrate with deterministic population"
short_code: "RKIT-T-0008"
created_at: 2026-08-14T03:12:22.631416+00:00
updated_at: 2026-08-14T16:12:03.416473+00:00
parent: resume-core-canonical-contracts
blocked_by: [RKIT-T-0003]
archived: false

tags:
  - "#task"
  - "#task"
  - "#phase/completed"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0001
---

# Complete JobModel section 4.2 shape and JobTerm substrate with deterministic population

## Parent Initiative

[[RKIT-I-0001]]

## Objective

This task completes the `JobModel` DTO to the canonical section-4.2 shape and introduces the `JobTerm` substrate that does not exist today, so the job side of the contract carries seniority, industries, domains, a distinct top-level `preferred[]` array, and a terminology surface. It matters because downstream scoring (RKIT-I-0002) and alignment (RKIT-I-0004) consume this shape, and shipping only the deterministic data structure now unblocks that work without prematurely coupling scoring semantics into the contract layer.

## Acceptance Criteria

## Acceptance Criteria

## Acceptance Criteria

- [ ] `JobModel` dataclass has fields: `schema_version`, `job_id`, `requirements`, `preferred` (separate list), `title`, `company`, `seniority`, `industries`, `domains`, `terminology`, `source`, `metadata`.
- [ ] A `JobTerm` dataclass and `JOB_TERM_SCHEMA` exist with fields `surface`, `canonical`, `source`, `weight`; `JobTerm.source` values are constrained to `{title, requirement, description}`.
- [ ] `normalizeJobModel` output dict includes `seniority`, `industries`, `domains`, `preferred`, and a non-empty `terminology` array for a job whose requirements carry `source_text`; terminology entries have `surface`+`canonical` populated deterministically.
- [ ] The top-level `preferred[]` array is distinct from `requirements[]`: a job with one required and one preferred requirement yields `requirements[]` and `preferred[]` that do not double-count (required/preferred/contextual remain distinct per CSA:131).
- [ ] Population is fully deterministic (same input → byte-identical `JobModel`) and imports no LLM/third-party dependency.

## Implementation Notes

### Execution Profile

Recommended Agent: opus + high

Codex-exec autonomously implementable: no — the proposal marks this task not codex-suitable; it requires reconciling the section-4.2 contract against existing normalization/ID invariants and a new substrate dataclass, which needs cross-file reasoning about the shared DTO contract rather than mechanical edits.

### Technical Approach

Extend `JobModel` (`schemas.py:125-133`) and its schema (`JOB_MODEL_SCHEMA` `schemas.py:262-273`) plus `normalizeJobModel` (`domain.py:250-276`) to the section-4.2 shape.

- ADD fields to `JobModel`: `seniority` (optional str), `industries` (list of ConceptRef/JsonObject, deterministic), `domains` (list of ConceptRef/JsonObject), a SEPARATE `preferred: list[JobRequirement]` array, and a `terminology: list[JobTerm]` substrate that does not exist today.
- Keep the top-level `preferred[]` array DISTINCT from `requirements[]`: do not merge the two. Preferred-ness on individual requirements stays as the `RequirementClassification.PREFERRED` value; the top-level `preferred[]` array is a new, distinct collection. (Binding decision: the top-level `preferred[]` array must remain distinct from `requirements[]`.)
- Define the `JobTerm` dataclass and `JOB_TERM_SCHEMA` with fields: `surface` (the job's literal wording), `canonical` (normalized form), `source` (one of `title`/`requirement`/`description`), `weight` (float hint).
- `normalizeJobModel` must POPULATE all new fields DETERMINISTICALLY with NO LLM: `seniority` parsed from title heuristics; `terminology` built from requirement `source_text`/`normalized_terms` + title tokens; `industries`/`domains` defaulted to `[]` when not derivable.
- SCOPE BOUNDARY (binding decision): this task ships the DATA SHAPE + deterministic (non-LLM) population ONLY. `JobTerm` is consumed as a SCORING dimension by RKIT-I-0002 — do NOT add scoring/weighting semantics here beyond emitting the `weight` hint. There is NO third-party dependency.
- Preserve existing requirement normalization and IDs.
- Update `JOB_MODEL_SCHEMA.required` if the design mandates `industries`/`domains`/`terminology` as required arrays. Default: required arrays present-but-possibly-empty; match the convention already used for `requirements`.

### Files

- `/Users/danielcassil/Code/resume-kit-2/resume-core/resume_core/schemas.py` (PROTECTED — shared-DTO contract surface)
- `/Users/danielcassil/Code/resume-kit-2/resume-core/resume_core/domain.py` (PROTECTED — shared-DTO normalization surface)

### Dependencies

- [[RKIT-T-0003]] — restores canonical enum members and reconciles cross-package readers (VerificationState, ResolutionState); `JobModel`/requirement normalization depends on the canonical enum surface being intact before this shape work lands.
- Downstream semantic link: `JobTerm` is consumed as a scoring dimension by RKIT-I-0002, and the completed `JobModel` shape feeds alignment work in RKIT-I-0004. Any `JOB_MODEL_SCHEMA.required` change must keep the owning package initiative's shared-DTO required-field test (and any xfail there) in sync.

### Risk Considerations

- **Protected-surface / straight-jacket constraints**: both `schemas.py` and `domain.py` are protected shared-DTO surfaces; changes must respect the straight-jacket contract and preserve existing requirement normalization and IDs rather than rewriting them.
- **Cross-package blast radius**: `JobModel` is consumed across packages; adding required arrays or changing the schema can break shared-DTO required-field tests and downstream readers — update the required-field test if `required` changes.
- **Determinism**: population must be byte-identical for identical input (no ordering nondeterminism, no LLM, no third-party dependency); title heuristics and terminology derivation must be stable/ordered.
- **Scope-boundary bleed**: resist adding scoring/weighting semantics — only emit the `weight` hint. Scoring over `JobTerm` belongs to RKIT-I-0002. Keep `preferred[]` distinct from `requirements[]` to avoid double-counting.

## Verification Steps

1. Unit test: `normalizeJobModel(<job with 'Senior' in title and 2 requirements one required one preferred>)`: assert `seniority` derived, `preferred[]` length 1, `requirements[]` length reflects the distinct classification, `terminology[]` non-empty with `surface`/`canonical` set.
2. `python3 -c "import resume_core; print(sorted(resume_core.SCHEMAS['JobModel']['properties']))"` : includes `seniority`, `industries`, `domains`, `preferred`, `terminology`.
3. Determinism check: run `normalizeJobModel` twice on the same fixture and assert `to_json_dict` outputs are equal.
4. `python3 tools/run_gate.py --pr --root .` : PR gate green (with the shared-DTO required-field test updated if `JobModel.required` changed).

## Status Updates

*To be added during implementation*