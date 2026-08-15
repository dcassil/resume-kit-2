---
id: manifest-audit-field-additions-and
level: task
title: "Manifest audit-field additions and TEST_SPEC field-list strengthening; I-0022 close-out"
short_code: "RKIT-T-0060"
created_at: 2026-08-15T02:48:33.833144+00:00
updated_at: 2026-08-15T02:48:33.833144+00:00
parent: workflow-artifact-schemas-and-run
blocked_by: ["RKIT-T-0059"]
archived: false

tags:
  - "#task"
  - "#phase/todo"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0022
---

# Manifest audit-field additions and TEST_SPEC field-list strengthening; I-0022 close-out

## Parent Initiative

[[RKIT-I-0022]]

## Objective

Close out RKIT-I-0022 (Requirement 6 + Testing Strategy): RunManifest and RUN_MANIFEST_SCHEMA gain `question_answer_log_refs` and `unresolved_requirements` so the full Audit Gate reconstruction list (CONTRACT_SURFACE_ALIGNMENT.md:353-366) is representable; workflow/TEST_SPEC.md's manifest field list (:83-101) is strengthened to that set; three-gate close-out with mutation probe.

## Acceptance Criteria

- [ ] RunManifest dataclass + RUN_MANIFEST_SCHEMA gain `question_answer_log_refs` (refs into the run's question/answer log) and `unresolved_requirements` (requirement id, resolution state, reason) with matching schema entries; buildRunManifest carries them (honest empty defaults are acceptable here — the PRODUCERS land in RKIT-I-0024; the validated shape and schema obligation land now).
- [ ] workflow/TEST_SPEC.md's run-manifest field list (~:83-101) extended to the CONTRACT_SURFACE_ALIGNMENT.md:353-366 set — CHECK the straight-jacket protected list first: if workflow/TEST_SPEC.md is protected (only tools/TEST_SPEC.md is known-protected), defer with line refs; package specs have been editable so far.
- [ ] Contract tests assert the new fields exist in schema + manifest output and that RUN_MANIFEST_SCHEMA rejects a manifest missing them.
- [ ] Gap check against the initiative's Testing Strategy: distinct-run-id collision regression (landed 08-13), typed-empty-identity and no-placeholder tests (T-0059/T-0058), careerDbVersion equality (T-0058) — all present and named; add anything missing.
- [ ] Mutation probe documented: reverting careerDbVersion to a literal (or dropping manifest validation) fails the suite; restored green.
- [ ] Any new workflow unit modules listed for the protected run_tests.py batch (joining the eleven queued career-store modules).
- [ ] Close-out gates ALL green: --pr, --smoke, --future-contract; counts reported; no weakening of any existing assertion.

## Implementation Notes

### Technical Approach

Established close-out pattern. Schema additions are additive; TEST_SPEC edit follows the guardrail-compatibility check discipline (tools/workflow_guardrails.py may parse the spec — read it first).

### Dependencies

RKIT-T-0059 (validation layer final before schema additions freeze).

### Risk Considerations

workflow_guardrails.py (protected) may pin the manifest field list or spec framing — deferral discipline applies. Honest empty defaults for the new fields must be explicit (empty list) not missing.

### Execution profile

Recommended Agent: opus + medium

Rationale: additive schema/spec consolidation on decided shapes.

## Status Updates

*To be added during implementation*
