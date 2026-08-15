---
id: azure-contract-test-replacement
level: task
title: "Azure contract-test replacement, TEST_SPEC strengthening; I-0007 close-out"
short_code: "RKIT-T-0053"
created_at: 2026-08-15T01:23:28.483508+00:00
updated_at: 2026-08-15T01:23:28.483508+00:00
parent: relationship-aware-matching-and
blocked_by: ["RKIT-T-0052"]
archived: false

tags:
  - "#task"
  - "#phase/todo"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0007
---

# Azure contract-test replacement, TEST_SPEC strengthening; I-0007 close-out

## Parent Initiative

[[RKIT-I-0007]]

## Objective

Close out RKIT-I-0007 (Requirement 7 + Testing Strategy): replace the vacuous Azure string-absence contract test with outcome assertions; consolidate confirmation/dictionary-removal/parent-child/searchFacts regressions; strengthen career-store/TEST_SPEC.md's relationship and match-type framing; run the three-gate close-out with a mutation probe.

## Acceptance Criteria

- [ ] tests/contract/test_career_store_contract.py's old :180-182 string-absence Azure assertion is REPLACED with outcome assertions: related Azure→AWS + allow_related_as_equivalent=False → Azure candidate at most related_match, AWS requirement unresolved, no exact_match/alias_match anywhere in the result (strengthen-only under RKIT-A-0006).
- [ ] Gap-fill named tests exist for every Testing Strategy item not already landed in T-0049..0052: unconfirmed-alias before/after confirmRelationship, dictionary-removal fixture pairs, parent/child directionality, contradicts signal, searchFacts filters + evidence minimization.
- [ ] career-store/TEST_SPEC.md strengthened (guardrail-compatible; check its parsing first): relationship set framing realigned per A-0006 item 5 (with the parent/child deferral note if the guardrail still pins the drifted set), match-type list aligned with section 4.4 incl. not_applicable, string-absence framing replaced with outcome-based case names for pollution + confirmation policy.
- [ ] Mutation probe documented: reintroducing term folding in the traversal (or the alias dictionary) fails the suite; restored green.
- [ ] All new I-0007 unit modules listed for the protected run_tests.py batch (joining the six queued career-store modules).
- [ ] Close-out gates ALL green: --pr, --smoke, --future-contract; counts reported; no weakening of any existing assertion.

## Implementation Notes

### Technical Approach

Follows the T-0038/T-0043/T-0048 close-out pattern: gap analysis over landed suites, spec text, contract-test replacement, mutation probe, three gates.

### Dependencies

RKIT-T-0052 (all mechanisms final).

### Risk Considerations

The protected guardrail parses TEST_SPEC relationship vocabulary — same deferral discipline as T-0043. Deterministic tests only.

### Execution profile

Recommended Agent: opus + medium

Rationale: consolidation over a decided mechanism set; judgment is in outcome-assertion strength.

## Status Updates

*To be added during implementation*
