---
id: req-007a-migration-fixture-content
level: task
title: "REQ-007a: Migration fixture content spec and previous-schema career.db fixture"
short_code: "RKIT-T-0019"
created_at: 2026-08-14T03:14:05.754884+00:00
updated_at: 2026-08-14T16:54:14.342552+00:00
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

# REQ-007a: Migration fixture content spec and previous-schema career.db fixture

## Parent Initiative

[[RKIT-I-0051]]

## Objective

Replace the README-only `fixtures/migrations/` placeholder with the migration-fixture content spec and the actual fixture data the migration checker will consume. This task authors both the documentation (in `fixtures/TEST_SPEC.md`) that maps the four migration cases to concrete inputs/outputs and the deterministic previous-schema `career.db` fixture (plus its expected post-migration state) that makes the "upgrade-from-previous" migration path a real, exercisable test rather than an empty directory.

## Acceptance Criteria

## Acceptance Criteria

## Acceptance Criteria

- [ ] `fixtures/TEST_SPEC.md` documents the previous-schema fixture, the expected post-migration state, and maps the four migration cases (fresh, idempotent, upgrade-from-previous, destructive-failure) to concrete fixture inputs/expected outputs.
- [ ] A deterministic previous-schema fixture exists (checked-in DB or a no-network generator producing a byte-stable DB) plus an expected-post-migration state artifact.
- [ ] The chosen previous schema version is older than the current career-store schema so upgrade-from-previous exercises a real migration.
- [ ] `fixtures/migrations/` still exists and passes `fixtures_guardrails` REQUIRED_DIRS.
- [ ] PR gate green.

## Implementation Notes

### Execution Profile

Recommended Agent: opus + medium

Codex-exec autonomously implementable: no — this task requires cross-referencing the current career-store schema to pick a valid older version and reasoning about migration semantics and determinism guarantees, which exceeds mechanical find/replace autonomy (proposal codexSuitable: false).

### Technical Approach

Replace the README-only `fixtures/migrations/` placeholder with real fixture content plus its content spec:

- Add to `fixtures/TEST_SPEC.md` a migration-fixture content section defining: a previous-schema `career.db` (or a deterministic seed script that produces one) and the expected post-migration state, plus the four cases enumerated in `tools/TEST_SPEC.md` lines 47-52 — fresh migrate, idempotent re-run, upgrade-from-previous, and destructive-migration failure. Map each case to concrete fixture inputs and expected outputs.
- Produce the fixture artifact(s) under `fixtures/migrations/`: either a checked-in previous-schema DB snapshot or a deterministic generator script paired with an expected-state JSON.
- Coordinate the schema version choice with the current career-store schema so "upgrade-from-previous" is meaningful.

Binding approved decision (weave into the above): the fixture MUST be deterministic — a checked-in DB, or a no-network generator that produces a byte-stable DB — paired with an explicit expected-post-migration state artifact. The chosen previous schema version MUST be OLDER than the current career-store schema so upgrade-from-previous is a genuine migration. Keep `fixtures/migrations/` present at all times, since its existence is enforced by `fixtures_guardrails` REQUIRED_DIRS.

### Files

- `fixtures/TEST_SPEC.md` — add migration fixture content spec: previous-schema DB, expected post-migration state, four cases.
- `fixtures/migrations/previous-schema-career.db` OR `fixtures/migrations/seed_previous_schema.py` — new fixture artifact / deterministic generator.
- `fixtures/migrations/expected-post-migration.json` — new; expected post-upgrade state.
- `fixtures/migrations/README.md` — update from placeholder to describe the fixtures.

### Dependencies

No task dependencies — startable once the initiative is active (proposal dependsOn: []). Semantically, the fixtures authored here are consumed downstream by the migration checker work and are coordinated against the current career-store schema (owned by the career-store package initiative); the "upgrade-from-previous" case and any xfail handling belong to that consuming/owning surface. Downstream applied-operations validation work (RKIT-I-0004) may also rely on these fixtures being present and deterministic.

### Risk Considerations

- **Determinism**: A non-byte-stable generator (timestamps, autoincrement ordering, insertion nondeterminism) would break reproducibility; the generator must run with no network and produce identical DB bytes across runs.
- **Schema-version coupling / cross-package blast radius**: Picking a previous schema version that is not strictly older than — or is incompatible with — the current career-store schema would make upgrade-from-previous vacuous or break the consuming checker. The version choice reaches into the career-store package surface and must be coordinated there.
- **Protected-surface / straight-jacket constraints**: `fixtures/migrations/` is enforced by `fixtures_guardrails` REQUIRED_DIRS; the directory must never be removed or emptied, or the guardrail fails.
- **Scope-boundary bleed**: This task authors fixtures and their spec only — it must not implement or modify the migration runner/checker logic itself, which lives in the consuming initiative.

## Verification Steps

1. `python3 tools/fixtures_guardrails.py --root .` — green; directory present.
2. If a generator is used: run `python3 fixtures/migrations/seed_previous_schema.py` twice and confirm identical DB bytes (determinism).
3. `python3 tools/run_gate.py --pr --root .`

## Status Updates

- 2026-08-14: Codex-driven implementation reviewed + verified. Previous schema `career-store.v0` (migrations/facts/evidence only; no relationships/conflicts/job_matches) vs current `career-store.v1` (from store.py SCHEMA_VERSION) — genuinely older. Byte-stable seed generator (fixed timestamps, no autoincrement, canonical JSON, double-run hash identical: a7d86ce). `expected-post-migration.json` cross-checked against an actual fixed-clock CareerStore upgrade (EXPECTED_MATCH). TEST_SPEC.md maps all four checker cases. fixtures_guardrails green, PR 198 green, smoke green. All acceptance criteria met; committing and marking completed.