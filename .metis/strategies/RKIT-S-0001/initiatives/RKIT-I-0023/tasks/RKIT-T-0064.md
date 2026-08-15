---
id: contract-test-rewrite-test-spec
level: task
title: "Contract-test rewrite, TEST_SPEC grounding obligations, skip-guardrail finding; I-0023 close-out"
short_code: "RKIT-T-0064"
created_at: 2026-08-15T03:11:05.482223+00:00
updated_at: 2026-08-15T03:11:05.482223+00:00
parent: workflow-deterministic-checkpoint
blocked_by: ["RKIT-T-0063"]
archived: false

tags:
  - "#task"
  - "#phase/todo"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0023
---

# Contract-test rewrite, TEST_SPEC grounding obligations, skip-guardrail finding; I-0023 close-out

## Parent Initiative

[[RKIT-I-0023]]

## Objective

Close out RKIT-I-0023 (Requirement 5 + Testing Strategy): finish the strengthen-only contract-test rewrite, rephrase workflow/TEST_SPEC.md:50-61 state-machine cases as grounding obligations and add the :57 loop-termination case, produce the structural skip-guardrail replacement finding for the protected tools/workflow_guardrails.py keyword blocklist, and run the three-gate close-out with a mutation probe.

## Acceptance Criteria

- [ ] Gap check: every Testing Strategy item has a named test — boolean-advance rejection + grounded-ref advances (T-0061), non-empty blocking_reasons naming unmet requirements (T-0061), loop-termination/BUILD_SELECTION_PLAN reachability (T-0062), hallucination-gate cases (T-0063); add anything missing.
- [ ] workflow/TEST_SPEC.md:50-61 rephrased as grounding obligations (evidence resolves against persisted artifacts/DTOs/run state, not presence-only); the :57 loop-termination case added — strengthen-only, guardrail-compatibility checked first.
- [ ] The protected tools/workflow_guardrails.py checkpoint-skip keyword blocklist (~:87-102) CANNOT be edited (approvals deferred): write the exact structural replacement (no path reaches a checkpoint's successor without a recorded grounded transition) as a ready-to-apply patch snippet in the task doc/report, AND add an UNPROTECTED unit test enforcing the same structural invariant so coverage exists now.
- [ ] Mutation probe documented: re-accepting bare-boolean evidence (or removing a required-evidence declaration) fails the suite; restored green.
- [ ] New workflow unit modules (if any) listed for the protected run_tests.py batch.
- [ ] Close-out gates ALL green: --pr, --smoke, --future-contract; counts reported; no weakening of any existing assertion.

## Implementation Notes

### Technical Approach

Established close-out pattern. The skip-guardrail structural check as an unprotected test: walk the state machine's transition recording and assert every reached checkpoint has a recorded grounded transition behind it.

### Dependencies

RKIT-T-0063 (all mechanisms final).

### Risk Considerations

workflow_guardrails.py parsing of TEST_SPEC — check before spec edits; deferral discipline with line refs.

### Execution profile

Recommended Agent: opus + medium

Rationale: consolidation with one protected-patch authoring piece.

## Status Updates

*To be added during implementation*
