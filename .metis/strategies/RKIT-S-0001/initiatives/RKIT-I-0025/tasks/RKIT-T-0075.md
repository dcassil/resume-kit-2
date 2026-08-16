---
id: integrity-verification-career
level: task
title: "Integrity verification: career-store surfaces, base-hash comparison, rejected-operation scan"
short_code: "RKIT-T-0075"
created_at: 2026-08-16T18:09:42.282493+00:00
updated_at: 2026-08-16T18:26:05.640427+00:00
parent: workflow-recovery-and-idempotency
blocked_by: [RKIT-T-0074]
archived: false

tags:
  - "#task"
  - "#phase/completed"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0025
---

# Integrity verification: career-store surfaces, base-hash comparison, rejected-operation scan

## Parent Initiative

[[RKIT-I-0025]]

## Objective **[REQUIRED]**

Implement the three real integrity verifications behind the structured contract RKIT-T-0074 introduced, so recovery PROVES the TEST_SPEC recovery assertions ("career DB remains transactionally valid", "base resume remains unchanged", "rejected operations stay rejected") instead of declaring them. After this task no integrity check returns `unverified` in the normal path.

## Acceptance Criteria

## Acceptance Criteria

## Acceptance Criteria **[REQUIRED]**

- [ ] **career_db**: recoverRun consults career-store's public `getMigrationState()` (career-store/career_store/store.py:916, MigrationState in schemas.py:198-204). `verified` requires: `status == "ok"` (no pending migrations) AND `schema_version` equals the run's recorded `careerDbVersion` schema version (the manifest field populated via workflow/versions.py). Mismatch or pending migrations → `failed` with a reason naming the discrepancy. Evidence ref records the consulted MigrationState summary. A store double reporting pending/invalid state MUST yield `failed` — the regression proving the store is actually consulted.
- [ ] **base_resume**: sha256 of the workspace base resume file compared to the run's recorded `base_resume_hash` (validated manifest field from RKIT-I-0022; persisted run state per workflow/__init__.py:798). Equal → `verified` with the hash as evidence; differing → `failed`; missing file or missing recorded hash → `failed` (honest), never `verified`.
- [ ] **rejected_operations**: scan the run's `operations.jsonl` (RKIT-I-0024 append-only log, see `_log_path_if_recorded` at workflow/__init__.py:730): any operation id with a `rejected` record that has a LATER `applied` record is an integrity failure naming the offending ids. Clean scan → `verified` with a log evidence ref. Missing log when operations were recorded → `failed`.
- [ ] `resumable` is false when any check reports `failed`; all-verified → true.
- [ ] Contract tests: (a) store double with pending migration → career_db failed; (b) tampered base.json → base_resume failed with hash mismatch; (c) synthetic operations.jsonl with rejected-then-applied id → rejected_operations failed listing the id; (d) clean run → all three verified with evidence refs; (e) careerDbVersion mismatch → failed.
- [ ] Career-store is consulted ONLY through its public API — no SQL, no private imports (career-store forbidden_public_api / must_not boundaries).
- [ ] `--pr` and `--smoke` gates green.

## Implementation Notes **[CONDITIONAL: Technical Task]**

### Technical Approach
- The store's transaction-validity surface per RKIT-A-0001 is `getMigrationState()` plus the store's own transactional discipline (BEGIN IMMEDIATE substrate from RKIT-I-0005 guarantees no partial commits); recovery does NOT reimplement store checks — it consults and reports. If a richer validity surface is absent, `getMigrationState().status` + version match IS the decided consultation; do not add store-side code in this task.
- Database path / store handle: follow how the smoke/CLI wires career-store into workflow runs (see resume-cli usage of workspace paths); the run state records `careerDbVersion` — verification compares against a freshly consulted state.
- Inject the store consultation so tests can double it (parameter or workspace-derived factory — match existing workflow injection idioms; no global monkeypatch-only seam).
- Recommended Agent: opus + high

### Dependencies
RKIT-T-0074 (structured integrity contract). Serial with all I-0025 tasks (same file).

### Risk Considerations
- Protected files forbidden (tools/*, tests/boundary/*) — defer any gate wiring to the approval batch.
- Do not import career_store internals (`store_support`, `migrations`) into workflow — public surface only; workflow must not become an alternate truth owner (CONTRACT_SURFACE_ALIGNMENT.md:43).

## Status Updates **[REQUIRED]**

- 2026-08-16: T-0074 landed (workflow/recovery.py delegation, structured integrity placeholders, UnknownRunError; committed, gates 387/smoke green). Codex launched on this task: real career_db (getMigrationState via injectable seam mirroring versions.py), base_resume sha256 vs recorded base_resume_hash, rejected-then-applied scan over operations.jsonl. career_db_not_configured runs report unverified honestly, never verified.