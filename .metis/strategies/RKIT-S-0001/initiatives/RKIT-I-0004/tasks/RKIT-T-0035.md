---
id: claim-level-grounding-over
level: task
title: "Claim-level grounding over ResumeField provenance"
short_code: "RKIT-T-0035"
created_at: 2026-08-14T22:54:23.813377+00:00
updated_at: 2026-08-14T23:19:31.241685+00:00
parent: resume-core-grounded-change
blocked_by: [RKIT-T-0034]
archived: false

tags:
  - "#task"
  - "#phase/completed"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0004
---

# Claim-level grounding over ResumeField provenance

## Parent Initiative

[[RKIT-I-0004]]

## Objective

Replace resume-level all-or-nothing grounding with per-claim provenance checking over the ResumeField weaving RKIT-I-0001 delivered: every claim extracted per ResumeField requires a provenance chain to a fact whose VerificationState is acceptable for the claim type; one provenanced claim no longer silences checking of all others (`_missing_provenance`, domain.py:1295-1303); `inferred` facts never silently ground a claim requiring verification (RKIT-I-0004 Requirements 5 and 7's verification half).

## Acceptance Criteria

## Acceptance Criteria

## Acceptance Criteria

- [ ] `_missing_provenance` (or its replacement) evaluates provenance PER CLAIM over ResumeField records: a resume with one provenanced claim and one unprovenanced claim reports the unprovenanced claim specifically (field pointer/claim identity in the finding), instead of passing wholesale.
- [ ] The final-resume claim set is grounded as base claims (provenance from normalization via `claim_fields.py`) plus applied-operation claims (provenance from each op's `provenance`/`linked_fact_ids`), per the initiative's Detailed Design; an operation grounded at validate time stays grounded at final-validation time because the same per-claim check runs over the same provenance.
- [ ] A claim whose only supporting fact is `inferred` does not ground when the claim type requires verification; the same claim grounds once the fact is `user_verified`/`source_stated`/`imported`. Tested both ways.
- [ ] The chunk-1 E2E suite (`tests/e2e/test_grounded_tailoring_final_validation.py`) still passes unmodified, or is strengthened-only if the per-claim model surfaces better findings.
- [ ] Unit tests cover: per-claim detection with mixed provenance, claim identity in findings, inferred-vs-verified grounding, and determinism (same input → same findings order/content).
- [ ] PR gate and smoke gate both green; snapshot regeneration (`python3 tools/regenerate_expected_snapshots.py --root . --write` twice) shows no drift after the second run; snapshot diffs reviewed and justified.
- [ ] No weakening of any existing assertion; protected edits (if any) strengthen-only under RKIT-A-0006 and reported for the approve/update-locks commit.

## Implementation Notes

### Technical Approach

RKIT-I-0001's `claim_fields.py` weaves claim-level ResumeField provenance with honest empty/unknown defaults — this is exactly the substrate. Rework the grounding walk in `validateGrounding` to iterate claims from ResumeField records rather than checking a resume-level provenance presence flag; each claim resolves its chain to facts and checks VerificationState admissibility (the VerificationState key invariant: `inferred` assists discovery but cannot ground without confirmation). Findings carry the claim's field pointer (use `pointers.py`). Applied-operation claims enter the same walk with the op's provenance (T-0034's status filtering decides which ops participate).

### Dependencies

RKIT-T-0034 (operation status filtering in final validation must exist so applied-op claims are drawn from the right op set). RKIT-I-0001 `claim_fields.py`/`pointers.py` substrate (done).

### Risk Considerations

This changes what validateGrounding reports for existing fixtures — expect snapshot churn in `fixtures/expected/`; review each diff (per-claim findings should be strictly more informative, never fewer rejections). The five `_GUARDED_TERMS` fixture behaviors must keep passing (they are demoted to regression fixtures in T-0036, but must not break here).

### Execution profile

Recommended Agent: opus + high

Rationale: core grounding-model rework across domain.py touching the initiative's central design; T-0036's honesty heuristics build directly on this claim walk.

## Status Updates

- 2026-08-14: Activated after T-0034 landed (commit with change_operations.py, gates 307/smoke green, driver probes confirmed status machine + mandatory-field enforcement + final-validation status filtering). Codex launched with binding decisions: per-claim walk over claim_fields.py weaving, pointer-carrying findings, inferred-never-grounds rule, base+applied-op claim union; guarded-terms mechanism explicitly out of scope (T-0036). Prompt at scratchpad t0035-prompt.md.
- 2026-08-14: Implementation session baseline read complete. Confirmed `validateGrounding` still uses whole-resume guarded text plus `_missing_provenance(resume)`, and `_missing_provenance` is all-or-nothing over root `resume.provenance`. T-0034 status filter exists in `change_operations.py` and final validation already passes only applied/accepted/modified ops to grounding. Straight Jacket verify is pre-existing red on protected `tools/pre-commit-resume-cli-guardrails.sh` and `tools/run_tests.py`; no protected edits planned.
- 2026-08-14: Implementation complete in working tree. Added `resume_core.grounding` for claim-record collection and per-claim verified provenance checks, wired `validateGrounding` to use base ResumeField claims plus applied-operation claims, and kept `inferred` non-grounding for claim verification. Added focused unit coverage for mixed per-claim provenance, pointer/claim identity findings, inferred-vs-verified fact behavior, applied-operation claim grounding, deterministic ordering, and the legacy-root-provenance compatibility bridge needed to avoid T-0036-style wholesale default-deny of unlinked legacy base fields. Smoke exposed that `resume-cli validate` was dropping applied operations, so `resume-cli` now reconstructs applied operations from `operations/tailor.json` and passes them into final validation/grounding; contract coverage strengthened for tailor→validate grounding pass. Verification green: PR gate 307 tests OK, smoke OK, unit discovery 100 tests OK, E2E 6 tests OK via `PYTHONPATH=resume-core` because direct `python3 -m unittest tests.e2e...` cannot import the editable package in this shell. Snapshot regeneration wrote 13 blocks twice and left `fixtures/expected/` with no diff.