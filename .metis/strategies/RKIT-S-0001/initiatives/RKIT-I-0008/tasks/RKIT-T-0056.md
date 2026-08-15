---
id: honest-years-title-conflict
level: task
title: "Honest years/title conflict heuristics and dead-branch removal"
short_code: "RKIT-T-0056"
created_at: 2026-08-15T02:07:49.766969+00:00
updated_at: 2026-08-15T02:38:30.272772+00:00
parent: conflict-audit-recovery-and
blocked_by: [RKIT-T-0055]
archived: false

tags:
  - "#task"
  - "#phase/completed"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0008
---

# Honest years/title conflict heuristics and dead-branch removal

## Parent Initiative

[[RKIT-I-0008]]

## Objective

Replace the fixture-tuned conflict heuristics (RKIT-I-0008 Requirements 4-6): `_year_claim`'s bare-digit sniffing replaced with the salvaged `_YEARS_RE` explicit-pattern extraction (in the initiative doc, verbatim); `_title_claim`'s hardcoded 5-title list replaced with a general structured-claim title model; the dead identical if/else in `_detect_conflicts` removed and the same-fact contract scenario rewritten to real semantics.

## Acceptance Criteria

## Acceptance Criteria

## Acceptance Criteria

- [ ] Years claims come ONLY from explicit patterns ("N years", "N+ years", number words through twenty per the salvaged `_YEARS_RE` in the initiative doc's "Salvaged" section). AUDIT REGRESSIONS: "React 18" vs "React 17 migration" produces NO years conflict; "5 years" vs "8 years" for the same concept still conflicts; number words above ten (e.g. "twelve years") parse.
- [ ] Title claims come from structured claim fields (canonical_name/description from I-0005), not free-text sniffing against the 5-title list; arbitrary titles (e.g. "Engineering Manager" vs "Director of Engineering") conflict when competing for the same role slot; the old list is deleted.
- [ ] The dead identical if/else in `_detect_conflicts` is removed; a claim carrying its own fact_id is NOT conflict-checked against itself; the contract test that passed via the dead branch is rewritten to assert real conflict semantics (strengthen-only).
- [ ] Comparison happens on typed (concept, years) and (role, title) tuples per the Detailed Design, not raw strings.
- [ ] PR + smoke gates green; migration checks green; no weakening of any existing assertion.

## Implementation Notes

### Technical Approach

`_YEARS_RE` verbatim from the initiative doc (salvaged from deleted matching.py). Concept scoping can reuse the term-normalization substrate. Title model: extract role/title tuples from structured fields; conflict when same role slot + different title rank/value.

### Dependencies

RKIT-T-0055 (conflict rows final shape before heuristics regenerate them).

### Risk Considerations

Fixture conflicts may change (fewer false positives) — review any expected-output/fixture diffs as strictly-more-honest. Existing honesty-fixture conflicts (Staff title) must still be detected via the general model.

### Execution profile

Recommended Agent: opus + medium

Rationale: well-specified extraction rework with the regex already supplied; judgment is in tuple scoping and the contract-test rewrite.

## Status Updates

*To be added during implementation*

- 2026-08-15: Implemented explicit `_YEARS_RE` parsing, typed `(concept, years)` and `(role, title)` conflict comparisons, self-fact skip in `_detect_conflicts`, and focused regression tests for React version numbers, digit/word years, structured arbitrary titles, Staff title fixture, and self-conflict semantics. Focused heuristic and rewritten contract tests pass locally.