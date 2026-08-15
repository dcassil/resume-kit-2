---
id: appeasement-removal-idempotency
level: task
title: "Appeasement removal, idempotency hardening, TEST_SPEC pass; I-0008 close-out"
short_code: "RKIT-T-0057"
created_at: 2026-08-15T02:07:49.816212+00:00
updated_at: 2026-08-15T02:46:30.117102+00:00
parent: conflict-audit-recovery-and
blocked_by: [RKIT-T-0056]
archived: false

tags:
  - "#task"
  - "#phase/completed"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0008
---

# Appeasement removal, idempotency hardening, TEST_SPEC pass; I-0008 close-out

## Parent Initiative

[[RKIT-I-0008]]

## Objective

Close out RKIT-I-0008 (Requirements 7-8 + Testing Strategy): remove the `_clean_result`/`_FORBIDDEN_RESULT_KEYS` stripping of never-produced keys with real-output assertions replacing any dependent expectations; idempotency hardening across the new interaction/conflict tables; TEST_SPEC strengthening; three-gate close-out with mutation probe.

## Acceptance Criteria

## Acceptance Criteria

## Acceptance Criteria

- [ ] `_clean_result`/`_FORBIDDEN_RESULT_KEYS` stripping of keys no code path produces is removed; any manifest/test expectation that depended on the stripping is replaced with assertions about outputs the store ACTUALLY produces (strengthen-only under A-0006). If a protected boundary test pins the stripping, STOP that piece and report it for the approval batch.
- [ ] Idempotency: duplicate replays of recordInteraction, conflict creation, and adjudicateConflict produce single rows / stable outcomes; interrupted operations recover cleanly via the TransactionResult substrate (injected-failure test on at least one new path).
- [ ] career-store/TEST_SPEC.md strengthened: "Interaction and preference history" gains executable case names (currently zero); conflict-workflow cases (resolve/dismiss/adjudicate/no-overwrite/engine-routing); heuristic regression cases; never-produced-key expectations replaced with real-output case names. Guardrail-compatible; defer with line refs where pinned.
- [ ] Mutation probe documented (e.g. re-adding bare-digit years sniffing or an interactions→verification write path fails the suite; restored green).
- [ ] All new I-0008 unit modules listed for the protected run_tests.py batch (joining the eight queued career-store modules).
- [ ] Close-out gates ALL green: --pr, --smoke, --future-contract; counts reported; no weakening of any existing assertion.

## Implementation Notes

### Technical Approach

Follows the established close-out pattern (T-0038/T-0043/T-0048/T-0053): removal + gap-fill + spec + probe + three gates.

### Dependencies

RKIT-T-0056 (all mechanisms final).

### Risk Considerations

The `_FORBIDDEN_RESULT_KEYS` removal may interact with protected boundary guardrails that assert the absence of those keys — verify whether the guardrail asserts key-absence in OUTPUT (fine — outputs still lack them) or the STRIPPING MECHANISM (deferral case). Deterministic tests only.

### Execution profile

Recommended Agent: opus + medium

Rationale: consolidation with one delicate removal whose blast radius is checked against protected expectations.

## Status Updates

*To be added during implementation*