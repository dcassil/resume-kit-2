---
id: req-002-execute-all-five-honesty
level: task
title: "REQ-002: Execute all five honesty fixtures through validateChange"
short_code: "RKIT-T-0015"
created_at: 2026-08-14T03:14:05.590586+00:00
updated_at: 2026-08-14T17:59:01.886711+00:00
parent: executable-release-gate-e2e
blocked_by: []
archived: false

tags:
  - "#task"
  - "#task"
  - "#phase/completed"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0051
---

# REQ-002: Execute all five honesty fixtures through validateChange

## Parent Initiative

[[RKIT-I-0051]]

## Objective

Wire all five `fixtures/operations/invalid-*.json` honesty fixtures through `resume_core.validateChange` in the PR gate tier so each is asserted rejected, closing the confirmed gap that ZERO of the honesty fixtures currently execute through `validateChange`. This delivers an executable, deterministic honesty-rejection contract that proves the core actually blocks the fabrication scenarios it claims to guard against — the difference between a claimed guarantee and a demonstrated one.

## Acceptance Criteria

## Acceptance Criteria

## Acceptance Criteria

- [ ] All 5 fixtures (unsupported-scale, unsupported-management, title-inflation, years-inflation, related-skill-overreach) are loaded from `fixtures/operations/` and run through `resume_core.validateChange` — no inline hand-built operations substitute for the fixtures.
- [ ] Four fixtures assert a hard rejection (status in {rejected,error}) with a reason matching `expected_reason` (unsupported_scale, unsupported_management_scope, title_inflation, years_inflation).
- [ ] The related-skill-overreach (Azure→AWS) case: if it rejects today, assert rejection; if it does NOT, it is marked xfail/expectedFailure with a comment naming the owning package initiative (RKIT-I-0004 grounded-change lifecycle or the store initiative that supplies AWS-not-Azure facts) so the red baseline is executable and the PR gate stays green.
- [ ] The adapter is deterministic (no LLM/network) and reused by all five cases.
- [ ] The new module is in the PR gate's executed set and maps to `suite_manifest` hallucination_rejection_fixtures; `python3 tools/run_gate.py --pr --root .` executes it and stays green (xfail counts as expected).
- [ ] No fixture truth is altered to force a pass.

## Implementation Notes

### Execution Profile

Recommended Agent: opus + high

Codex-exec autonomously implementable: no — the task requires cross-package reasoning about the validateChange operation contract, the fixture-to-operation adapter shape mismatch, and a nuanced red-baseline (xfail) decision that hinges on runtime behavior; a wrong call weakens an honesty guarantee, so it needs high-reasoning judgment rather than mechanical execution.

### Technical Approach

Wire all five `fixtures/operations/invalid-*.json` through `resume_core.validateChange` in the PR tier so each is asserted rejected — closing the confirmed gap that ZERO (not one) of the honesty fixtures currently execute through `validateChange`.

This requires an adapter because the fixture shape (`target_path`/`before`/`after`/`expected_reason`) differs from the `validateChange` operation shape (`path`/`operation_id`/`op`/`linked_requirement_ids`/`linked_fact_ids`):

- Write a deterministic fixture→operation adapter that maps `target_path`→`path`, passes `before`/`after` through, and supplies the canonical resume + job model + career facts (reuse the fixture resume/job or the test constants).
- For each fixture, assert `validateChange` returns status in {rejected,error} and that the rejection reason corresponds to `expected_reason`.
- Place the test in the `hallucination_rejection` category so it maps to a real module (feeds REQ-009's category-mapping goal).

APPROVED DECISION (red baselines) — binding: the Azure-as-AWS `related_skill_overreach` fixture is the KNOWN red-baseline. If current `validateChange` does NOT reject it, land that one case as an xfail/expectedFailure annotated with the owning package-initiative id (RKIT-I-0007 store / RKIT-I-0004 lifecycle) so the red TDD signal is executable and discoverable while the PR gate stays green. Do NOT weaken the fixture to make it pass. Correction to prior assumptions: ZERO of the 5 currently execute through `validateChange` — only truly-passing fixtures go in the blocking `hallucination_rejection` category; the overreach case rides as xfail until its owning initiative supplies the AWS-not-Azure grounding facts.

### Files

- `tests/contract/test_honesty_fixtures_validate_change.py` (new — NON-protected; loads all 5 fixtures, adapts, runs validateChange, asserts rejection)
- `tests/support/operation_fixture_adapter.py` (new — fixture→validateChange operation mapping + linked facts)
- `tests/suite_manifest.json` (map hallucination_rejection_fixtures category to the new module; NON-protected)

### Dependencies

- No task dependencies — startable once the initiative is active.
- Cross-initiative/semantic link: the related-skill-overreach xfail must be annotated with its owning package initiative — RKIT-I-0007 (store, which supplies the AWS-not-Azure career facts) or RKIT-I-0004 (grounded-change lifecycle) — so the red baseline is traceable to the work that will eventually make it green.
- Downstream: this task feeds REQ-009's category-mapping goal by placing the module under the `hallucination_rejection` suite category.

### Risk Considerations

- Protected-surface constraint: all three touched files are NON-protected test/manifest files; `resume_core.validateChange` itself is a protected core surface and MUST NOT be modified to make a fixture pass — the adapter and assertions live entirely in test-side code.
- Straight-jacket / honesty-integrity risk: the strongest failure mode is weakening a fixture (altering `target_path`/`after`/`expected_reason`) to force green. This is explicitly disallowed — the overreach case must ride as xfail rather than be softened.
- Cross-package blast radius: supplying the canonical resume + job model + career facts pulls in the store/lifecycle contract; if those facts don't yet prove AWS-not-Azure, the case correctly stays red (xfail) rather than being coerced.
- Determinism: the adapter must be pure (no LLM/network) and reused identically across all five cases so the gate result is reproducible.
- Scope-boundary bleed: keep the work to loading/adapting/asserting fixtures and the manifest mapping; do not drift into fixing validateChange behavior for the overreach case — that belongs to the owning package initiative.

## Verification Steps

1. `python3 -m unittest tests.contract.test_honesty_fixtures_validate_change` (4 rejections pass; overreach xfail or passes)
2. `python3 tools/run_gate.py --pr --root .` (green; xfail visible)
3. Confirm via grep that each fixture_id is loaded from `fixtures/operations/` (not inline): `grep -n target_path tests/support/operation_fixture_adapter.py`

## Status Updates

- 2026-08-14: Codex-driven implementation reviewed + committed. All FIVE fixtures reject today — including Azure→AWS related-skill-overreach (no xfail needed; the runtime-probe xfail scaffold is in place if it ever regresses). Reason correspondence is honest: `expected_reason` maps to core error vocabulary (`unsupported_guarded_claim` + specific claim in details, `unsupported_years_claim` for years_inflation). Files: `tests/contract/test_honesty_fixtures_validate_change.py`, `tests/support/operation_fixture_adapter.py`, `suite_manifest.json` mapping under hallucination_rejection_fixtures. New tests 5/5 green standalone; PR 198 + smoke green.
- OPEN CRITERION (task stays active): "module in PR gate's executed set" — `tools/run_tests.py` hard-codes CURRENT_TEST_MODULES and is straight-jacket protected. Adding `tests.contract.test_honesty_fixtures_validate_change` is batched with T-0021's unit-tier wiring for one Daniel password session (A-0006 strengthen-only realignment).
- 2026-08-14 RESOLVED: T-0021's run_tests.py edit added `tests.contract.test_honesty_fixtures_validate_change` to CURRENT_TEST_MODULES; Daniel re-registered straight-jacket and the batch landed as commit 84503f9. PR gate (257) executes the module. All criteria met; completed.