---
id: replace-warn-only-date-handling
level: task
title: "Replace warn-only date handling with canonicalization and typed rejection"
short_code: "RKIT-T-0007"
created_at: 2026-08-14T03:12:22.590745+00:00
updated_at: 2026-08-14T16:00:37.634928+00:00
parent: resume-core-canonical-contracts
blocked_by: []
archived: false

tags:
  - "#task"
  - "#task"
  - "#phase/completed"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0001
---

# Replace warn-only date handling with canonicalization and typed rejection

## Parent Initiative

[[RKIT-I-0001]]

## Objective

Replace the current regex warn-only date path in `resume-core` with the A-0006 / REQ-6 canonicalization-and-typed-rejection behavior, so date handling becomes a first-class part of the canonical contracts instead of silently coercing bad input. This task delivers stable `YYYY[-MM]` canonical keys for the four accepted input shapes, adds typed rejection for impossible dates and reversed ranges (new behavior), and preserves ambiguous-but-possible normalization as a warning — giving downstream consumers a deterministic, trustworthy date contract.

## Acceptance Criteria

## Acceptance Criteria

## Acceptance Criteria

- [ ] `'Jan 2019'` and `'01/2019'` canonicalize to `'2019-01'` (parsed key `(2019,1)`) and produce a warning, not an error, not a silent drop.
- [ ] `'2019-13'` produces a typed `invalid_date` error (severity error), NOT an ambiguous warning and NOT silent `None` coercion.
- [ ] `start_date` after `end_date` produces a typed `reversed_range` error.
- [ ] Bare `'YYYY'` and `'YYYY-MM'` remain accepted with no warning; `'present'`/`'current'` end sentinel still parses as open-ended with no error.
- [ ] A genuinely unparseable string (e.g. `'sometime in spring'`) still produces an `ambiguous_start_date`/`ambiguous_end_date` warning, not an error.

## Implementation Notes

### Execution Profile

Recommended Agent: opus + medium

Codex-exec autonomously implementable: yes — the change is confined to a single module (`domain.py`) with fully enumerated input/output cases and a deterministic, provider-free scope, making it a well-bounded implementation with clear test oracles.

### Technical Approach

Replace the regex warn-only date path (`domain.py:698-721`: `_check_dates` and `_date_key`) with the A-0006 / REQ-6 behavior:

- Canonicalize the four accepted input shapes into a stable `YYYY[-MM]` key:
  - `YYYY`
  - `YYYY-MM`
  - `'Mon YYYY'` (e.g. `'Jan 2019'`)
  - `MM/YYYY` (e.g. `'01/2019'`)
- Ambiguous-but-possible formats (`'Jan 2019'` / `'01/2019'`) normalize WITH a warning — keep the warning, do NOT reject and do NOT silently drop. Per the approved decision, these ambiguous-but-possible formats canonicalize with a warning, never an error.
- IMPOSSIBLE dates (month > 12 or month < 1, e.g. `2019-13`) must be REJECTED with a typed `invalid_date` error. This is NEW behavior: today `_date_key` silently coerces an out-of-range month to `None` (`domain.py:719`), so it only surfaces as the generic ambiguous warning. Per the approved decision, the implementation MUST SPLIT the "regex matched but out of range" branch from the "regex did not match" branch rather than tweak a threshold — the matched-but-out-of-range branch emits `invalid_date` (error), while the did-not-match branch keeps the ambiguous warning.
- Reversed ranges (start > end) must be REJECTED with a typed `reversed_range` error. Rename/retype the existing `reversed_date_range` error to the documented `reversed_range` code, or add `reversed_range` while keeping compatibility per TEST_SPEC.
- Unparseable/other formats remain a warning (`ambiguous_start_date` / `ambiguous_end_date`), NOT a rejection.
- Add a month-name lookup table (Jan..Dec, stdlib only) for `'Mon YYYY'` parsing.
- Preserve the present/current sentinel handling (open-ended end date, no error).

### Files

- `/Users/danielcassil/Code/resume-kit-2/resume-core/resume_core/domain.py`

### Dependencies

No task dependencies — startable once the initiative is active. Note the semantic downstream link: the typed `invalid_date` / `reversed_range` errors introduced here become part of the canonical contract that RKIT-I-0004 (final-resume validation / applied-operations) consumes, so the error codes must match the documented TEST_SPEC names. Any `xfail` markers relating to date behavior are owned by the package-owning initiative's test suite and should be reconciled there, not silently flipped here.

### Risk Considerations

- **New rejection behavior / blast radius**: Rejecting `2019-13` and reversed ranges is genuinely new behavior. Callers that previously received a silently-coerced `None` (or only a warning) will now see a typed error. Splitting the matched-but-out-of-range branch cleanly from the did-not-match branch is essential to avoid over-rejecting genuinely unparseable strings that should stay warnings.
- **Protected-surface / straight-jacket constraints**: `domain.py` is a canonical-contracts surface; changes must stay within the enumerated scope and not alter unrelated validation semantics or the public error-emission shape beyond the documented codes.
- **Determinism**: Canonicalization and the month-name lookup must be stdlib-only and fully deterministic — no locale-dependent month parsing, no provider calls.
- **Scope-boundary bleed**: Keep the change to date handling only. Do not retune adjacent thresholds or touch the present/current sentinel logic beyond preserving it.
- **Error-code compatibility**: The `reversed_date_range` → `reversed_range` rename must follow TEST_SPEC exactly (rename or add-with-compat) so downstream consumers and test suites see the documented code.

## Verification Steps

1. Unit test each case: `'Jan 2019'` (warn+canonical), `'01/2019'` (warn+canonical), `'2019'` (clean), `'2019-05'` (clean), `'2019-13'` (`invalid_date` error), `start='2020'` `end='2019'` (`reversed_range` error), `end='present'` (clean), `'spring'` (ambiguous warning).
2. `grep -n 'invalid_date\|reversed_range' resume-core/resume_core/domain.py` : both typed codes present.
3. `python3 tools/run_gate.py --pr --root .` : PR gate green, including TEST_SPEC date suites.

## Status Updates

- 2026-08-14: Implemented date parsing/canonicalization with typed `invalid_date` and `reversed_range` validation. Added focused unit coverage for ambiguous-but-possible dates, impossible months, reversed ranges, canonical clean dates, present/current sentinels, and unparseable strings. Verified `python3 tools/run_gate.py --pr --root .` passes with `Ran 194 tests in 6.744s OK`.