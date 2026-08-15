---
id: transaction-substrate-atomic
level: task
title: "Transaction substrate: atomic detect+write, TransactionResult, interruption recovery"
short_code: "RKIT-T-0042"
created_at: 2026-08-14T23:56:07.530441+00:00
updated_at: 2026-08-15T00:31:53.272518+00:00
parent: durable-career-store-package-and
blocked_by: [RKIT-T-0041]
archived: false

tags:
  - "#task"
  - "#phase/completed"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0005
---

# Transaction substrate: atomic detect+write, TransactionResult, interruption recovery

## Parent Initiative

[[RKIT-I-0005]]

## Objective

Build the store-owned transaction substrate (RKIT-I-0005 Requirement 6, moved forward from RKIT-I-0008 by deliberate re-sequencing): a context-managed single-connection transaction helper; `upsertFact` conflict detection and fact/evidence writes execute atomically in ONE transaction (fixing the separate-connections defect at store.py:245-247); the never-used `TransactionResult` DTO (schemas.py:81-88) is constructed and returned; interruption mid-operation leaves no partial rows.

## Acceptance Criteria

## Acceptance Criteria

## Acceptance Criteria

- [ ] A store-owned transaction helper exists (context manager over a single connection with an immediate transaction); store mutation paths that pair reads with writes run inside it.
- [ ] `upsertFact` performs conflict-detection reads and fact/evidence writes on the SAME connection inside the SAME transaction — the store.py:245-247 separate-connection pattern is gone.
- [ ] `TransactionResult` (schemas.py:81-88) is constructed and returned by transactional mutations: committed vs rolled_back plus touched row identity for the audit trail.
- [ ] Atomicity regression test: an injected failure between conflict detection and write leaves ZERO partial rows (facts, evidence, conflicts all absent) and returns/raises with a rolled_back TransactionResult — codifying the audited defect.
- [ ] Evidence append-only and deterministic-ID invariants preserved under the new transaction path (existing tests keep passing unmodified or strengthened).
- [ ] PR + smoke gates green; no weakening of any existing assertion; protected files untouched (report if a boundary guardrail edit seems needed).

## Implementation Notes

### Technical Approach

Helper in store.py (or a small `career_store/transactions.py`): `with store.transaction() as txn:` yielding the connection; BEGIN IMMEDIATE; commit/rollback recorded into a TransactionResult. Refactor `upsertFact` (and any sibling mutation doing read-then-write across connections) onto it. Failure injection via a test hook or monkeypatched write step. Registry migrations from T-0039..T-0041 already run transactionally — reuse, don't duplicate.

### Dependencies

RKIT-T-0041 (enum-validated write paths are final before wrapping them transactionally).

### Risk Considerations

SQLite connection semantics: the store currently opens per-call connections; consolidating to a shared transaction connection must not break concurrent-open tests or reopen idempotence. Keep result shapes additive for career-mcp consumers.

### Execution profile

Recommended Agent: opus + high

Rationale: concurrency/atomicity semantics with data-integrity stakes; I-0006's fact/evidence lifecycle builds directly on this substrate.

## Status Updates

*To be added during implementation*

- 2026-08-14: Started implementation. Confirmed `upsertFact` still detects conflicts before opening its write connection; sibling read-then-write mutation paths identified for transaction helper coverage: `verifyFact`, `addEvidence`, `addRelationship`, and `recordJobMatch`.
- 2026-08-14: Implemented private `BEGIN IMMEDIATE` transaction scope with `TransactionResult` capture. Moved `upsertFact`, `verifyFact`, `addEvidence`, `addRelationship`, and `recordJobMatch` read+write work onto transaction-owned connections; added focused unit coverage for rollback, result embedding, and evidence append-only deterministic IDs.
- 2026-08-14: Validation passed after splitting private helpers to keep `store.py` under the architecture line cap: PR gate 350 tests OK, smoke OK, unit discovery 131 tests OK, migration checks OK. Protected files and `career-store/store_surface.json` were not edited.