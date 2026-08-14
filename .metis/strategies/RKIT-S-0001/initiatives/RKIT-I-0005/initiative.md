---
id: durable-career-store-package-and
level: initiative
title: "Durable Career-Store Package and Migration Foundation"
short_code: "RKIT-I-0005"
created_at: 2026-08-13T20:41:36.917160+00:00
updated_at: 2026-08-13T20:41:36.917160+00:00
parent: resume-kit-2-full-product-buildout
blocked_by: []
archived: false

tags:
  - "#initiative"
  - "#phase/discovery"


exit_criteria_met: false
estimated_complexity: M
strategy_id: RKIT-S-0001
initiative_id: NULL
---

# Durable Career-Store Package and Migration Foundation Initiative

## Context **[REQUIRED]**

Package: `career-store`, foundation initiative for the group (RKIT-I-0006/0007/0008 build on it). The package is no longer a scaffold: roughly 7,500 lines implement a durable SQLite service — all nine `store_surface.json` functions, deterministic content-hashed IDs and ordering, append-only evidence, persisted conflicts and job associations, and genuine boundary guardrails. Tables are created at open and data survives across store instances, so "durable schema initialization" already exists.

What is missing or fake at the foundation level, per the 2026-08-13 alignment audit:
- The "migration framework" is a single hardcoded CREATE TABLE block labeled `001_initial`: no registry, no version stamping, no incompatible-schema-version rejection. The `MigrationState` DTO is declared but never constructed (schemas.py:91-98).
- The `TransactionResult` DTO is declared but never used (schemas.py:81-88), and `upsertFact` runs conflict detection on separate connections before the write transaction (store.py:245-247), so detect+write is not atomic.
- Schema shape diverges from vision section 6 recommended tables with no recorded contract change: facts lack canonical_name/description/years/confidence, there is no `jobs` table (only free-string job_ids in job_matches, store.py:672-684), `job_fact_matches` lack match_type/confidence/user_confirmed, `fact_relationships` lack confidence (store.py:602-689).
- The store vocabulary carries the enum drift RKIT-A-0006 rules against: VerificationState drops `imported` and adds `explicitly_missing`/`conflicted`, ResolutionState drops `not_applicable` and adds `conflicted`, relationship types drop `parent`/`child` (store.py:16-35, store.py:25, store_surface.json:28-51).
- `career_store/matching.py` is a dead parallel matching implementation — unused, unexported, unimported anywhere — with semantics that diverge from store.py and Must-Not-Own scoring logic (`_match_score`, matching.py:497-508).

The passing 188-test gate reflects thin assertions, not compliance. Re-baselined 2026-08-13 against the alignment audit and decided ADRs.

## Goals & Non-Goals **[REQUIRED]**

**Goals:**
- A real ordered migration registry, schema-version stamping, and public `getMigrationState()` per RKIT-A-0001 item 1, so workflow run manifests read a true `careerDbVersion`.
- Typed incompatible-schema-version errors on open; no silent upgrade or downgrade.
- Schema realignment to the vision section 6 recommended tables under RKIT-A-0006's contracts-win ruling: facts columns, jobs table, job_fact_matches columns.
- Enum restoration per RKIT-A-0006 items 1, 2, and 5 in the store vocabulary and surface manifest.
- Transaction substrate (moved here from RKIT-I-0008): atomic detect+write on one connection with `TransactionResult` in actual use.
- Execute the decision on the dead parallel matching.py: remove it.

**Non-Goals:**
- Verification transition gating and confirmation semantics — RKIT-I-0006.
- Matching semantics, alias lookup, relationship confirmation enforcement — RKIT-I-0007 (this initiative only restores the enum values and columns that work needs).
- Conflict workflow, interactions table, preference APIs — RKIT-I-0008 (its migrations land through the registry built here).
- No retrieval-layer performance overhaul beyond what the transaction work requires.

## Requirements **[CONDITIONAL: Requirements-Heavy Initiative]**

### System Requirements
1. Migration registry: an ordered registry of identified migrations replaces the hardcoded CREATE TABLE block (which becomes registry entry `001_initial`). Fresh DB creation applies all migrations; re-open is idempotent; applied migration ids and timestamps persist.
2. `getMigrationState()` public API returns the `MigrationState` DTO — schema version, applied migration ids, pending migration ids — finally constructing the DTO declared but never built at schemas.py:91-98. `openStore` may embed the same DTO in its result; `getMigrationState()` is the contract surface (RKIT-A-0001 item 1).
3. Opening a database with an incompatible schema version fails with a typed error carrying found and supported versions (TEST_SPEC "Reject incompatible schema versions"; RKIT-A-0001 item 1). No silent upgrade/downgrade.
4. Section 6 schema realignment delivered as registry migrations: facts gain canonical_name, description, years, confidence; a `jobs` table (lightweight job identity/history) exists; `job_fact_matches` gain match_type, confidence, user_confirmed; `fact_relationships` gain confidence. Databases created during the 2026-08-12/13 waves migrate forward (RKIT-A-0006 consequence: migration handling for drifted persisted data).
5. Enum restoration per RKIT-A-0006 items 1, 2, 5 in store.py:16-35 and store_surface.json:28-51: VerificationState = source_stated/user_verified/imported/inferred/unknown; ResolutionState regains `not_applicable` and drops `conflicted`; relationship types become alias/related/parent/child/equivalent plus `contradicts` (retained as the A-0006-recorded extension). A data migration remaps persisted drifted values (drifted verification values migrate to `unknown`, preserving a conflict record where the prior state was `conflicted`).
6. Transaction substrate: a store-owned transaction helper executes detect+write atomically on a single connection — fixing store.py:245-247 — and returns `TransactionResult` (schemas.py:81-88, currently never used). Interruption mid-operation leaves no partial rows.
7. Remove `career_store/matching.py` (dead, unexported, divergent related→alias_match and user_verified→exact_match mappings, Must-Not-Own scoring at matching.py:497-508). Salvage its `_YEARS_RE` pattern for RKIT-I-0008's years-heuristic fix before deletion.
8. Manifest and protected contract-test edits use only the RKIT-A-0006 authorization: realign, never weaken assertion strength.

### Dependencies
- Resume-core contracts realignment for the shared enum definitions (resume-core/resume_core/schemas.py:32-49 carries the same drift); the store-side restoration must land against the restored shared DTOs.
- RKIT-A-0001 (decided): migration state exposure, typed incompatible-version error.
- RKIT-A-0006 (decided): enum sets, contracts-win ruling, protected-surface edit authorization.

### Blocked Status
- Not blocked. The former RKIT-A-0001 block is lifted — the ADR was decided 2026-08-13; this initiative implements its item 1 rather than waiting on it. RKIT-I-0006/0007/0008 are downstream consumers of the registry, transaction substrate, restored vocabulary, and section 6 columns.

## Detailed Design **[REQUIRED]**

- Migration registry: module-level ordered list of `(id, apply)` entries; a `schema_migrations` table records `(id, applied_at)`; a version stamp (`PRAGMA user_version` or equivalent meta row) identifies the schema. `openStore` compares the DB version to the supported range before applying anything; pending = registry ids minus applied ids.
- MigrationState DTO: `{schemaVersion, appliedMigrationIds, pendingMigrationIds}` per the declared shape, re-queryable at any time via `getMigrationState()` (RKIT-A-0001 explicitly rejected open-metadata-only exposure).
- Typed errors: `IncompatibleSchemaVersionError(found, supported)` distinct from `MigrationFailedError(migrationId, cause)`; both exported on the surface so career-mcp and workflow can map them.
- Transaction helper: context-managed single connection with an immediate transaction; `upsertFact` conflict-detection reads and fact/evidence writes execute inside the same transaction; `TransactionResult` reports committed vs rolled_back plus touched row identity for the audit trail.
- Schema migrations: `002` adds section 6 columns with NULL/default backfill; `003` creates `jobs` and derives job identities from existing free-string job_ids in job_matches; `004` remaps drifted enum values. Each is a forward-only registry entry.
- matching.py removal: delete the file and any references; add a guardrail assertion that the package exports no scoring-shaped function (scoring is Must-Not-Own for career-store, CONTRACT_SURFACE_ALIGNMENT.md:37).

## Testing Strategy **[CONDITIONAL: Separate Testing Initiative]**

- Contract tests: fresh-DB `getMigrationState()` shows all applied/none pending; reopen is idempotent; a DB stamped with an unsupported version fails open with the typed error — no executable case exercises this today even though TEST_SPEC names it.
- Migration tests: a wave-era fixture DB (drifted enums, missing columns) migrates forward with data intact; enum remap verified row-by-row.
- Atomicity regression: injected failure between conflict detection and write leaves zero partial rows and returns a rolled_back `TransactionResult`, codifying the store.py:245-247 defect.
- TEST_SPEC strengthening: realign career-store/TEST_SPEC.md's 6-value verification set (TEST_SPEC.md:66-72) and the shared DTO/store-surface contract tests to the section 4.4/4.6 sets under the A-0006 authorization — the drifted spec is currently certifying the drifted code.
- Add the missing `jobs` unit cases: TEST_SPEC lists `jobs` in Expected Structure (:29) with zero unit cases, the exact spec hole that let the table be omitted while appearing compliant.
- Boundary guardrail: nothing imports `career_store.matching` (removed).

## Alternatives Considered **[REQUIRED]**

- Version stamp without a registry (keep the single CREATE TABLE, record a version): rejected — RKIT-I-0006/0007/0008 all need additive migrations through a registry, and run manifests need applied/pending introspection; RKIT-A-0001 also rejected store-open-metadata-only exposure.
- Leave the transaction substrate in RKIT-I-0008 as originally sequenced: rejected — RKIT-I-0006's fact/evidence writes require atomic detect+write; parking foundational semantics at the end of the dependency chain forces rework of everything built on non-atomic writes (audit ordering finding).
- Reconcile and adopt matching.py instead of deleting it: rejected — its semantics diverge from store.py (related→alias_match, user_verified→exact_match) and it contains scoring the package must not own; two matching layers invite silent drift.

## Implementation Plan **[REQUIRED]**

Dependency-ordered chunks for later decomposition (no Metis tasks yet):
1. Migration registry + version stamping + typed errors + `getMigrationState()` (registry absorbs `001_initial`).
2. Section 6 schema realignment migrations (facts columns, jobs table, job_fact_matches/fact_relationships columns).
3. Enum restoration + persisted-value remap migration + store_surface.json/contract-test realignment under the A-0006 authorization.
4. Transaction substrate: atomic detect+write, `TransactionResult`, interruption-recovery tests.
5. Delete matching.py (salvaging `_YEARS_RE` for RKIT-I-0008) + guardrail test + TEST_SPEC realignment pass.
