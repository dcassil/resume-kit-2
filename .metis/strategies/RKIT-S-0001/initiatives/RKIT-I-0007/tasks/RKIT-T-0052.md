---
id: searchfacts-concept-terms-alias
level: task
title: "searchFacts concept/terms/alias filtering and evidence minimization"
short_code: "RKIT-T-0052"
created_at: 2026-08-15T01:23:28.435082+00:00
updated_at: 2026-08-15T01:49:53.512428+00:00
parent: relationship-aware-matching-and
blocked_by: [RKIT-T-0051]
archived: false

tags:
  - "#task"
  - "#phase/active"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0007
---

# searchFacts concept/terms/alias filtering and evidence minimization

## Parent Initiative

[[RKIT-I-0007]]

## Objective

Bring searchFacts up to TEST_SPEC:83-84 (RKIT-I-0007 Requirement 5): accept concept, normalized-terms, alias (via stored relationships), and verification_state filters; include_evidence returns the minimum-necessary evidence rows for the match rather than all rows.

## Acceptance Criteria

## Acceptance Criteria

- [ ] searchFacts accepts concept, terms (normalized), alias, and verification_state filters, composable; alias filtering expands through STORED relationships only (one relationship join per the Detailed Design) honoring the T-0050 confirmation policy (unconfirmed aliases do not expand under allowUnverifiedAliasCreation:false).
- [ ] include_evidence returns only evidence rows referenced by the matched terms/filters (minimum-necessary), not all rows; a test counts rows for a fact with mixed relevant/irrelevant evidence.
- [ ] Redirected (merged-away) facts do not appear as independent results (T-0047 invariant preserved under the new filters).
- [ ] Deterministic result ordering; filters on absent columns/values return empty rather than erroring; typed error for malformed filter shapes.
- [ ] PR + smoke gates green; no weakening of any existing assertion.

## Implementation Notes

### Technical Approach

SQL-side filtering on the I-0005 columns (canonical_name/description support concept search) plus one relationship join for alias expansion. Evidence minimization keys evidence rows to matched terms via the existing normalized_terms linkage.

### Dependencies

RKIT-T-0051 (policy + traversal final so alias expansion honors confirmation).

### Risk Considerations

Keep SQL private (guardrail scans for raw-SQL public APIs). career-mcp/CLI consumers of searchFacts must keep working — filters are additive.

### Execution profile

Recommended Agent: opus + medium

Rationale: well-specified query work on an established schema; the only judgment is evidence-minimization keying.

## Status Updates

- 2026-08-15: Implemented private searchFacts filter normalization and SQL-backed candidate ID filtering for verification_state/type, normalized terms, concept text, and confirmed alias/equivalent expansion. Added minimum-necessary evidence loading keyed by matched search/filter terms. Focused search/merge/relationship unit tests pass.
- 2026-08-15: Required verification completed: PR gate, smoke gate, full unit discovery, and migration checks all pass. Straight Jacket verification still reports pre-existing protected-file checksum mismatches in tools/pre-commit-resume-cli-guardrails.sh, tools/run_tests.py, and tools/TEST_SPEC.md.
