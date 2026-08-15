---
id: durable-audit-events-and-real
level: task
title: "Durable audit events and real checkpoint artifact refs; delete substring fabrication"
short_code: "RKIT-T-0065"
created_at: 2026-08-15T03:39:09.827790+00:00
updated_at: 2026-08-15T03:47:16.560052+00:00
parent: workflow-checkpoint-result
blocked_by: []
archived: false

tags:
  - "#task"
  - "#phase/completed"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0024
---

# Durable audit events and real checkpoint artifact refs; delete substring fabrication

## Parent Initiative

[[RKIT-I-0024]]

## Objective

Make the audit surface real (RKIT-I-0024 Requirements 1-3; Detailed Design "Audit-event persistence"/"Ref grounding"): every advanceCheckpoint decision — allowed AND blocked — appends a durable AuditEvent flushed at decision time; recordCheckpointResult writes the checkpoint payload to disk and returns only refs to files that exist with sha256 hashes; the substring 'validation'/'render' ref fabrication is deleted outright.

## Acceptance Criteria

## Acceptance Criteria

## Acceptance Criteria

- [ ] AuditEvent DTO {event_id, run_id, checkpoint, decision (advanced|blocked), blocking_reasons, evidence_refs, timestamp} appended to run_state.audit_events and flushed to durable JSON at DECISION time (not completion); blocked events carry the I-0023-computed blocking_reasons. Regression: a blocked advance persists exactly one event, and a process-restart simulation (fresh module load reading the run file) still finds it.
- [ ] recordCheckpointResult writes the checkpoint payload to `.workflow/runs/<run_id>/checkpoints/<checkpoint>.json`; returned artifact_refs point ONLY at files that exist, each with sha256. Contract test: every ref resolves and hash-matches.
- [ ] The substring ref fabrication (JSON-serialized-payload scan for 'validation'/'render', old workflow/__init__.py:145-146) is DELETED, not patched; validation/render refs come only from explicit typed refs supplied from recorded package outputs. Adversarial regression: a payload containing 'render'/'validation' in unrelated content yields NO refs.
- [ ] Timestamps respect the repo determinism law (frozen/injectable clock per existing conventions — check how the run files handle time; no naked wall-clock in ids).
- [ ] PR + smoke gates green; no weakening of any existing assertion; protected files untouched (run_smoke read-only; report needs).

## Implementation Notes

### Technical Approach

Extend the T-0061-established persistence (advanceCheckpoint already persists verified evidence — add the event append + flush in the same write). recordCheckpointResult gains the checkpoint-file write; explicit typed refs shape mirrors the EvidenceRef conventions.

### Dependencies

RKIT-I-0023 complete (blocking_reasons + grounded evidence are the persisted content). First task of the I-0024 serial chain.

### Risk Considerations

Every existing advance/record call path now writes files — keep paths under the run directory, deterministic names. Watch clock usage: run ids are clock-free by design; events may carry timestamps only if determinism tests tolerate (injectable clock exists in career-store openCareerStore(clock=...) precedent — mirror it).

### Execution profile

Recommended Agent: opus + high

Rationale: durable audit semantics + deletion of fabricated refs; the persisted shapes are what reconstruction (T-0066) and recovery (I-0025) read.

## Status Updates

- Implemented workflow durable advance audit events with event_id/run_id/checkpoint/decision/blocking_reasons/evidence_refs/timestamp, sequence-based event IDs, and injectable clocks.
- Implemented checkpoint payload writes under `.workflow/runs/<run_id>/checkpoints/<checkpoint>.json`; returned checkpoint/artifact/validation/render refs are verified artifact EvidenceRefs with sha256.
- Deleted validation/render substring fabrication by replacing it with explicit typed refs only.
- Added focused unit regressions; focused workflow tests and workflow contract suite are green.
- Straight Jacket verify had pre-existing protected-file checksum mismatches before this work (`tools/run_smoke.py`, `tools/run_tests.py`, `tools/TEST_SPEC.md`, `tools/pre-commit-resume-cli-guardrails.sh`), so final gate status may be affected.
- Final validation: `python3 tools/run_gate.py --pr --root .` passed (368 tests); `python3 tools/run_gate.py --smoke --root .` passed; `python3 -m unittest discover -s tests/unit -v` passed (194 tests). No protected tool files were edited by this task.