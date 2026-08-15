---
id: tailoring-tail-stage-evidence
level: task
title: "Tailoring-tail stage evidence declarations and grounded completion gates"
short_code: "RKIT-T-0071"
created_at: 2026-08-15T04:29:40.575022+00:00
updated_at: 2026-08-15T04:30:49.338364+00:00
parent: workflow-tailoring-validation
blocked_by: []
archived: false

tags:
  - "#task"
  - "#phase/active"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0027
---

# Tailoring-tail stage evidence declarations and grounded completion gates

## Parent Initiative

[[RKIT-I-0027]]

## Objective

Ground the tailoring tail (RKIT-I-0027 Requirements 3 + Detailed Design "Stage evidence declarations"/"Grounded completion"): each tail checkpoint (BUILD_SELECTION_PLAN through COMPLETE) declares grounded evidence per the I-0023 model, and every assertCanComplete gate maps to a persisted artifact/report ref per the I-0024 model — completion unreachable on missing or hash-mismatched refs, boolean gate evidence gone.

## Acceptance Criteria

## Acceptance Criteria

- [ ] Stage evidence declarations extended for the tail: BUILD_SELECTION_PLAN requires a persisted selection-plan artifact; proposal/validation/application checkpoints require operation ids in correct lifecycle states (resume-core-owned statuses); final checks require grounding + ATS report refs; the render checkpoint requires render output + measureLayout result; COMPLETE requires assertCanComplete.
- [ ] required_gates map to persisted refs: final_match→match report artifact, grounding→grounding audit artifact, ats→ATS report, render_validation→render validation report, audit_ref→I-0024 audit trail, hallucination_rejection→I-0023 gate, hard_requirements→policy state. COMPLETE unreachable while any ref is missing or hash-mismatched (both cases tested).
- [ ] Boolean-evidence completion tests that certified the honor system are REWRITTEN strengthen-only to real-artifact refs.
- [ ] Contract test: completion succeeds only with all real artifacts present; fails per-gate with named reasons on absence and on hash mismatch.
- [ ] PR + smoke gates green; smoke's grounded driver extended only via unprotected paths (run_smoke.py is protected — report if it must change).

## Implementation Notes

### Technical Approach

Extends the T-0061 checkpoint declaration table for the tail and rewires assertCanComplete's gate map onto artifact refs (T-0065's sha256 EvidenceRef verification). measureLayout evidence: the render checkpoint declaration references the recorded measureLayout result artifact — actually CALLING measureLayout in a driver path lands with T-0072's loop; here declare + accept its recorded output.

### Dependencies

RKIT-I-0026 complete. First task of the I-0027 serial chain.

### Risk Considerations

Contract tests must produce real artifacts (write files, hash them) — reuse T-0065/T-0066 test helpers. Producers that reached COMPLETE with booleans in tests get honest artifact fixtures, never gate loosening.

### Execution profile

Recommended Agent: opus + high

Rationale: completion-integrity semantics; the gate-to-ref map is what makes COMPLETE meaningful for the whole product.

## Status Updates

- 2026-08-15: Read task and parent initiative. Verified Straight Jacket state; only the four expected pre-existing protected checksum mismatches are present. Investigated workflow evidence verification, resume-render public render/measure/validation surfaces, and resume-core operation lifecycle statuses. Implementation plan: extend tail `_ADVANCE_REQUIREMENTS` to artifact/run-state evidence, make `assertCanComplete` verify persisted artifact refs and operation-policy gates, then rewrite old boolean/DTO completion tests to real hashed files.
- 2026-08-15: Implemented tail evidence declarations and grounded completion gates. Focused workflow tests passed, then requested PR, smoke, and unit discovery gates all passed. Smoke did not require protected-file changes.