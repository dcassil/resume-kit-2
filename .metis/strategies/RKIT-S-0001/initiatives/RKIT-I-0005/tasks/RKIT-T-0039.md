---
id: migration-registry-version
level: task
title: "Migration registry, version stamping, typed errors, getMigrationState"
short_code: "RKIT-T-0039"
created_at: 2026-08-14T23:56:07.382994+00:00
updated_at: 2026-08-14T23:58:02.712473+00:00
parent: durable-career-store-package-and
blocked_by: []
archived: false

tags:
  - "#task"
  - "#phase/active"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0005
---

# Migration registry, version stamping, typed errors, getMigrationState

## Parent Initiative

[[RKIT-I-0005]]

## Objective

Replace career-store's fake "migration framework" (a single hardcoded CREATE TABLE block labeled `001_initial`) with a real ordered migration registry, schema-version stamping, typed incompatible-version/migration-failure errors, and the public `getMigrationState()` API returning the never-constructed `MigrationState` DTO (RKIT-I-0005 Requirements 1-3; RKIT-A-0001 item 1).

## Acceptance Criteria

## Acceptance Criteria

- [ ] A module-level ordered registry of `(id, apply)` migration entries exists; the current hardcoded CREATE TABLE block becomes registry entry `001_initial` with identical resulting schema for fresh DBs.
- [ ] A `schema_migrations` table records `(id, applied_at)`; a version stamp (`PRAGMA user_version` or a meta row) identifies the schema version. Fresh DB creation applies all migrations; re-open is idempotent (no re-application, no errors, no duplicate rows).
- [ ] `getMigrationState()` is a public surface function returning the `MigrationState` DTO (schemas.py:91-98 shape): schema version, applied migration ids, pending migration ids — re-queryable at any time. `openStore` may embed the same DTO but `getMigrationState()` is the contract surface.
- [ ] Opening a DB stamped with an unsupported schema version fails with typed `IncompatibleSchemaVersionError` carrying found and supported versions; no silent upgrade/downgrade. `MigrationFailedError(migrationId, cause)` is distinct and both are exported on the surface.
- [ ] Contract tests: fresh-DB getMigrationState shows all-applied/none-pending; reopen idempotent; unsupported-version DB fails open with the typed error (TEST_SPEC names this case; no executable case exists today — add it).
- [ ] `store_surface.json` gains `getMigrationState` (camelCase per RKIT-A-0002); manifest edit is realign-only under RKIT-A-0006.
- [ ] PR gate (now 344) and smoke gate green; no weakening of any existing assertion; protected files untouched (career-store contract tests in tests/contract/ are NOT protected; boundary guardrails ARE — report if an edit seems needed).

## Implementation Notes

### Technical Approach

Registry in a new `career_store/migrations.py` (ordered list, apply callables taking a connection); `openStore` path: read version → reject unsupported → apply pending inside a transaction → stamp. `getMigrationState()` reads `schema_migrations` + registry to compute pending. Follow existing store.py conventions for error/result shapes (deterministic dicts). The DTO at schemas.py:91-98 is finally constructed here. Downstream chunks (T-0040 schema columns, T-0041 enum remap, and later I-0008 migrations) land as registry entries `002+` — design the registry so adding entries is a one-line append.

### Dependencies

None within the initiative — this is the foundation chunk. RKIT-A-0001 (decided) defines the exposure contract.

### Risk Considerations

`openStore` is called by career-mcp, workflow, and smoke paths — keep its success-result shape backward compatible (additive only). Watch `--smoke` for any consumer assuming the old single-block init.

### Execution profile

Recommended Agent: opus + high

Rationale: foundation substrate for all of I-0005..0008 — registry design choices (entry shape, stamping, error taxonomy) compound through every later migration.

## Status Updates

- 2026-08-14: Added `career_store/migrations.py` registry with `001_initial`, `schema_migrations`, PRAGMA `user_version` stamping, typed migration errors, `CareerStore.getMigrationState()`, package exports, manifest surface entry, and focused contract coverage for fresh state, idempotent reopen, and unsupported-version rejection. Focused `tests.contract.test_career_store_contract` passes locally.
- 2026-08-14: Verification: migration checks, smoke, and unit discovery pass. PR gate runs 347 tests and fails only because protected `tools/career_store_guardrails.py` / `tests/boundary/test_career_store_guardrails.py` still hard-code the pre-ADR public surface and require `audit` on the DTO-shaped `getMigrationState` output.
