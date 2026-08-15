---
id: grounded-evidenceref-model
level: task
title: "Grounded EvidenceRef model, advanceCheckpoint verification, computed blocking_reasons"
short_code: "RKIT-T-0061"
created_at: 2026-08-15T03:11:05.319879+00:00
updated_at: 2026-08-15T03:11:05.319879+00:00
parent: workflow-deterministic-checkpoint
blocked_by: []
archived: false

tags:
  - "#task"
  - "#phase/todo"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0023
---

# Grounded EvidenceRef model, advanceCheckpoint verification, computed blocking_reasons

## Parent Initiative

[[RKIT-I-0023]]

## Objective

Replace honor-system evidence with the grounded EvidenceRef model and make getNextCheckpoint compute real blockers (RKIT-I-0023 Requirements 1-2, 5; Detailed Design "Grounded evidence model"/"Blocking reasons"): advanceCheckpoint verifies typed refs against persisted state, validated DTOs, or hash-matched artifacts before any transition; bare booleans are typed rejections; blocking_reasons names each unmet requirement.

## Acceptance Criteria

- [ ] Evidence is typed refs, not dict[str, bool]: `{'kind': 'artifact', path, sha256}` (file exists + hash matches), `{'kind': 'dto', schema_id, payload}` (validates against the named schema), `{'kind': 'run_state', key}` (exists in persisted run state written by a prior recorded checkpoint result). Each checkpoint declares its required evidence as typed refs.
- [ ] advanceCheckpoint verifies EVERY required ref before transitioning and persists the verified refs into run state (downstream gates and audit read the same grounding). A caller passing literal booleans (the old `{'config_validated': True}`) is rejected with a typed error — the audit's bare-boolean advance is a named regression.
- [ ] getNextCheckpoint computes blocking_reasons as the NAMED unmet evidence requirements of the next checkpoint plus policy-gate holds; the unconditional `blocking_reasons: []` is gone; an advance blocked for reason R surfaces R by name (contract test).
- [ ] Migration honesty: existing persisted runs holding boolean evidence maps are treated as UNGROUNDED and cannot advance without re-supplying grounded evidence — no silent upgrade (tested).
- [ ] The contract tests currently advancing with literal booleans (old test_workflow_contract.py:113-131 region) are REWRITTEN to fail-then-pass with real refs (RKIT-A-0006 strengthen-only; full spec pass is T-0064).
- [ ] PR + smoke gates green; producers (CLI/workflow internal drivers) migrated to supply real refs minimally; no weakening of any existing assertion.

## Implementation Notes

### Technical Approach

EvidenceRef verification in a small workflow module (reuse the T-0059 stdlib schema walker for dto-kind refs; hashlib for artifact refs). Checkpoint→required-evidence declarations as a module-level table. Smoke's driver must produce grounded refs for the canonical path — expect the bulk of producer work there.

### Dependencies

RKIT-I-0022 complete (validated manifests, run identity). First task of the I-0023 serial chain.

### Risk Considerations

Highest-blast-radius chunk: every advance in smoke/CLI paths must now ground. Fix producers to record real outputs; never soften verification. workflow_guardrails.py (protected) may pin old shapes — deferral discipline with line refs.

### Execution profile

Recommended Agent: opus + high

Rationale: the enforcement model every later workflow initiative consumes; wrong ref semantics compound.

## Status Updates

*To be added during implementation*
