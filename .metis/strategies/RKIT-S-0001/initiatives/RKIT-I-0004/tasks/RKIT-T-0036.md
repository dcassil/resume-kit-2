---
id: generalized-honesty-heuristics
level: task
title: "Generalized honesty heuristics: quantity normalization, title ladder, scoped years, structured negation"
short_code: "RKIT-T-0036"
created_at: 2026-08-14T22:54:23.858954+00:00
updated_at: 2026-08-14T22:54:23.858954+00:00
parent: resume-core-grounded-change
blocked_by: ["RKIT-T-0035"]
archived: false

tags:
  - "#task"
  - "#phase/todo"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0004
---

# Generalized honesty heuristics: quantity normalization, title ladder, scoped years, structured negation

## Parent Initiative

[[RKIT-I-0004]]

## Objective

Generalize the honesty gate from fixture enumeration to mechanism (RKIT-I-0004 Requirements 2, 3, 4, and 8's negation piece): ANY ungrounded claim is rejected by default-deny over the T-0035 claim walk; `_GUARDED_TERMS` (domain.py:47-53, 1103-1105) is demoted from mechanism to regression fixture; title inflation uses a seniority ladder; years claims normalize number words and scope evidence to the claim's subject; negation checks compare structured fact fields.

## Acceptance Criteria

- [ ] The audit's three empirically passing fabrications are rejected by the GENERAL mechanism (with `_GUARDED_TERMS` neutralized in the test to prove it's not the lookup): "Served 50 million users daily", "Principal Engineer leading 100 people", "Kubernetes expert".
- [ ] Quantity claims (digit or number-word scale statements) require a fact asserting a compatible quantity after word↔digit normalization; incompatible or absent quantities are rejected.
- [ ] Title-inflation checking uses the seniority ladder (engineer < senior < staff < principal < distinguished) against the highest evidenced title (replaces the single-word "staff" guard at domain.py:1136-1143); "Principal Software Engineer" inflation over a Senior-evidenced history is rejected; a truthful title at or below the evidenced rung passes.
- [ ] Years-claim support normalizes number words and digits and scopes evidence to the claim's subject: truthful "AWS, six years" matches a `user_verified` "6 years of AWS" fact (fixes domain.py:989-995, 1146-1161); an unrelated "10 years" elsewhere in the resume cannot satisfy a requirement threshold (fixes the max-anywhere `_years_met`, domain.py:799-812).
- [ ] `_fact_negates_claim` moves from naive substring scanning (domain.py:1126-1133) to structured comparison against fact fields; a negating fact rejects the claim, a non-negating fact containing the word "not" incidentally does not false-positive.
- [ ] All five original `_GUARDED_TERMS` fixture behaviors (aws, graphql, staff title, "20 million", "30 engineers") still rejected — now through the general path; the lookup table is retained only as regression-fixture data or deleted with its cases re-expressed as tests.
- [ ] Deterministic and stdlib-only (no LLM, per the initiative's Alternatives Considered); unit tests in `tests/unit/`; PR + smoke gates green; snapshot no-drift proof run and diffs reviewed.
- [ ] No weakening of any existing assertion; protected edits strengthen-only under RKIT-A-0006 and reported.

## Implementation Notes

### Technical Approach

Build on T-0035's per-claim walk: classification of claim kinds (quantity, title, skill, years) happens per claim, then each kind gets a deterministic admissibility check against linked facts. Word↔digit normalization is a small stdlib table (units/tens/scales — "six"↔6, "50 million"↔50_000_000). The title ladder is a module constant with rank comparison; highest evidenced title comes from facts/base resume fields. Years scoping keys evidence to the claim subject term (reuse JobTerm/term-normalization substrate from I-0002 where applicable). Negation compares structured fields (e.g. fact.negated / explicit quantity contradiction), not substrings.

### Dependencies

RKIT-T-0035 (claim-level walk is the substrate these checks run on). I-0002 term substrate for subject scoping (done).

### Risk Considerations

Highest-blast-radius chunk: default-deny over all claims can reject currently-passing fixture resumes whose claims lack linked facts. Expect and review snapshot churn; where a fixture claim is truthful but unlinked, the fix is linking the fixture's facts (fixture truth content unchanged per A-0006), never loosening the gate. Watch smoke: CLI/workflow paths feed resumes through this gate.

### Execution profile

Recommended Agent: opus + high

Rationale: the initiative's keystone honesty semantics; open-world default-deny design with cross-cutting effects on every downstream validation consumer.

## Status Updates

*To be added during implementation*
