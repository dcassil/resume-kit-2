---
id: section-6-schema-realignment
level: task
title: "Section 6 schema realignment migrations: facts columns, jobs table, match/relationship columns"
short_code: "RKIT-T-0040"
created_at: 2026-08-14T23:56:07.436663+00:00
updated_at: 2026-08-15T00:07:40.660638+00:00
parent: durable-career-store-package-and
blocked_by: [RKIT-T-0039]
archived: false

tags:
  - "#task"
  - "#phase/active"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0005
---

# Section 6 schema realignment migrations: facts columns, jobs table, match/relationship columns

## Parent Initiative

[[RKIT-I-0005]]

## Objective

Deliver the vision section 6 recommended-table realignment as registry migrations on the T-0039 substrate (RKIT-I-0005 Requirement 4): facts gain canonical_name/description/years/confidence; a lightweight `jobs` table replaces free-string-only job identity; `job_fact_matches` gain match_type/confidence/user_confirmed; `fact_relationships` gain confidence. Wave-era databases migrate forward with data intact.

## Acceptance Criteria

## Acceptance Criteria

- [ ] Registry migration `002` (or split entries) adds the section 6 columns with NULL/default backfill: facts.canonical_name, facts.description, facts.years, facts.confidence; job_fact_matches.match_type, .confidence, .user_confirmed; fact_relationships.confidence.
- [ ] A `jobs` table exists (lightweight job identity/history) created by a registry migration; job identities are derived/backfilled from existing free-string job_ids in job_matches (store.py:672-684 era data), preserving every existing association.
- [ ] Store write/read paths populate and return the new columns where the current API surface carries them (additive; downstream semantic use belongs to I-0006/0007).
- [ ] Migration test: a wave-era fixture DB (built with the pre-realignment schema) migrates forward with row counts and key data verified intact; migration ids/timestamps recorded; getMigrationState reflects the new entries applied.
- [ ] The missing `jobs` unit cases named by the initiative's Testing Strategy exist (TEST_SPEC Expected Structure line ~29 currently has zero unit cases for `jobs` — the spec hole that let the table be omitted).
- [ ] Fresh-DB creation and reopen remain idempotent; PR + smoke gates green; no weakening of any existing assertion.

## Implementation Notes

### Technical Approach

Build fixture DB in-test using the `001_initial`-only schema (registry lets you apply a prefix), insert representative rows, then open through the full registry and assert survival. SQLite ALTER TABLE ADD COLUMN for the additive columns; `jobs` backfill via INSERT..SELECT DISTINCT from job_matches job_ids. Keep career-store's deterministic content-hashed ID conventions for new jobs rows.

### Dependencies

RKIT-T-0039 (registry + stamping + state introspection).

### Risk Considerations

Backfill must be deterministic (ordered SELECT DISTINCT) so repeated migrations on identical data produce identical DBs. Don't let new NOT NULL constraints break existing insert paths — additive columns are nullable/defaulted.

### Execution profile

Recommended Agent: opus + medium

Rationale: substantive schema work but the registry pattern and column list are fully specified; reasoning is mostly in backfill determinism and fixture design.

## Status Updates

*To be added during implementation*