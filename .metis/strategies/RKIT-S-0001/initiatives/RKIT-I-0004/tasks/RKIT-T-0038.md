---
id: adversarial-honesty-suite-test
level: task
title: "Adversarial honesty suite, TEST_SPEC strengthening, unit-module gate wiring"
short_code: "RKIT-T-0038"
created_at: 2026-08-14T22:54:23.957714+00:00
updated_at: 2026-08-14T23:55:05.798177+00:00
parent: resume-core-grounded-change
blocked_by: [RKIT-T-0037]
archived: false

tags:
  - "#task"
  - "#phase/completed"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0004
---

# Adversarial honesty suite, TEST_SPEC strengthening, unit-module gate wiring

## Parent Initiative

[[RKIT-I-0004]]

## Objective

Close out RKIT-I-0004's Testing Strategy: a consolidated adversarial honesty suite beyond fixtures, per-claim provenance tests, the full operation-lifecycle matrix, TEST_SPEC.md strengthening (mandatory operation fields enumerated, replacing the stale reason reference at TEST_SPEC.md:128), and wiring this initiative's new unit modules into the protected `run_tests.py` gate list (add-only, per the warn-only-hook workflow).

## Acceptance Criteria

## Acceptance Criteria

## Acceptance Criteria

- [ ] Adversarial honesty suite exists (new unit/e2e module(s)): novel fabricated scale/title/skill claims NOT present in any fixture or guard list are rejected; truthful numeric-vs-word years phrasing is accepted; an unrelated years figure elsewhere cannot satisfy thresholds; the three audit fabrications covered as named regressions.
- [ ] Per-claim provenance tests: one provenanced claim does not silence checking of the others (regression for the old domain.py:1295-1303 behavior).
- [ ] Operation lifecycle matrix tests: every mandatory-field omission rejected; the full verb table (5 verbs) and the full status-transition table (legal AND illegal transitions) covered.
- [ ] `tools/TEST_SPEC.md` (protected) strengthened-only: the mandatory operation fields (`reason`, `linked_requirement_ids`, `linked_fact_ids`, `provenance`) are enumerated; the TEST_SPEC.md:128 "when the reason depends on them" reference is made accurate against the now-real DTO. Edit reported for Daniel's approve/update-locks commit.
- [ ] All new I-0004 unit modules (from T-0034..T-0038) are wired into `CURRENT_TEST_MODULES` in protected `tools/run_tests.py` — ADD-ONLY, same pattern as commit 1a786a6; the PR gate test count increases accordingly and is stated in the completion report.
- [ ] PR gate, smoke gate, AND `--future-contract` gate all green (initiative close-out chunk per HANDOFF loop step 5).
- [ ] Mutation probes documented in the task's Status Updates: reverting a representative honesty mechanism (e.g. the title ladder) makes the suite fail — proof the suite is not vacuous.
- [ ] No weakening of any existing assertion anywhere; all protected edits strengthen-only under RKIT-A-0006, accumulated and reported for the single approve/update-locks commit before the PR to main.

## Test Cases

### Test Case 1: Novel fabrication rejection (general mechanism)
- **Preconditions**: T-0036 general honesty mechanisms landed; `_GUARDED_TERMS` demoted.
- **Steps**: Validate operations/resumes carrying fabricated claims never seen in fixtures (e.g. "Reduced costs by 80 percent", "Distinguished Engineer", "Terraform expert") with no supporting facts.
- **Expected Results**: Each rejected on GROUNDING/honesty findings via the general path.

### Test Case 2: Truthful variant acceptance
- **Preconditions**: `user_verified` fact "6 years of AWS" present.
- **Steps**: Validate a claim "AWS, six years"; separately validate an unrelated "10 years of Java" claim against an AWS-years requirement.
- **Expected Results**: First accepted; second does not satisfy the AWS threshold.

### Test Case 3: Lifecycle matrix
- **Preconditions**: T-0034 landed.
- **Steps**: Drive every status transition pair and every mandatory-field omission through validateChange/applyChange.
- **Expected Results**: Legal transitions succeed; illegal ones raise typed errors; each omission rejected with a per-field code.

## Implementation Notes

### Technical Approach

Mostly test authorship consolidating T-0034..T-0037 behaviors into named, spec-linked suites, plus two protected strengthen-only edits (TEST_SPEC.md wording, run_tests.py module list). Follow the 1a786a6 add-only wiring pattern exactly. Keep new modules in `tests/unit/` (gate-wired) with any E2E additions joining the existing e2e suite file.

### Dependencies

RKIT-T-0037 (all mechanisms final before the consolidated suite freezes their contracts). Warn-only pre-commit hook (verified working) for the protected edits.

### Risk Considerations

Protected-file edits accumulate CHECKSUM_MISMATCH warnings until Daniel's approve/update-locks commit — expected; list every touched protected file in the completion report. Ensure new tests are deterministic (no dict-order reliance) so gate counts are stable.

### Execution profile

Recommended Agent: opus + medium

Rationale: consolidation and spec work following established patterns; reasoning load is in adversarial case selection, not architecture.

## Status Updates

- 2026-08-14: Activated after T-0037 committed (guardrails_config.py + quality_warnings.py; driver probes confirmed typed unknown-key/flat-key errors, inferred floor under allow=true, generalized duplicates with duplicate_of pointers, multi-term stuffing). Codex launched with the task's protected-file exception scoped to exactly TEST_SPEC.md + run_tests.py (strengthen-only/add-only), mutation-probe requirement, and --future-contract required for close-out. Prompt at scratchpad t0038-prompt.md.
- 2026-08-14: Mutation probe completed for the adversarial honesty suite. Temporarily removed `percent`/`percentage` from `resume_core.honesty._QUANTITY_COUNT_SUBJECTS`; `python3 -m unittest tests.unit.test_adversarial_honesty_suite.AdversarialHonestySuiteTests.test_novel_fabrications_reject_without_guarded_term_lookup -v` failed on `name='cost_percent'` with `AssertionError: 'ok' != 'rejected'` and `guarded_claims: []` for "Reduced costs by 80 percent." Restored percentage quantity recognition; the same targeted command passed (`Ran 1 test ... OK`). Final verification: PR gate 344 tests OK (was 307), smoke OK, future-contract 351 tests OK, unit discovery 123 tests OK, e2e grounded-tailoring 6 tests OK, snapshot regeneration deterministic with only `fixtures/expected/valid-operations.json` changed.