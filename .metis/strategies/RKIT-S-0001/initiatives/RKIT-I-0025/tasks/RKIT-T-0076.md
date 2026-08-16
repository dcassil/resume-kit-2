---
id: computed-rerun-sets-per
level: task
title: "Computed rerun sets per interruption checkpoint + completion-gate enforcement"
short_code: "RKIT-T-0076"
created_at: 2026-08-16T18:09:42.338523+00:00
updated_at: 2026-08-16T18:26:05.959755+00:00
parent: workflow-recovery-and-idempotency
blocked_by: [RKIT-T-0074, RKIT-T-0075]
archived: false

tags:
  - "#task"
  - "#phase/active"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0025
---

# Computed rerun sets per interruption checkpoint + completion-gate enforcement

## Parent Initiative

[[RKIT-I-0025]]

## Objective **[REQUIRED]**

Replace the hardcoded FINAL_MATCH-only `required_reruns` (workflow/__init__.py:387) with a deterministic checkpoint→rerun-set map persisted into run state at recovery time, and give `assertCanComplete` a recovery gate so COMPLETE is structurally unreachable until every computed rerun has a fresh post-recovery recorded result. Reruns become enforced, not advisory (the workflow/__init__.py:198-212-era unenforced-rerun audit finding).

## Acceptance Criteria

## Acceptance Criteria **[REQUIRED]**

- [ ] A module-level deterministic map from interruption checkpoint to rerun set covering ALL 18 checkpoints (REQUIRED_CHECKPOINTS in tools/workflow_guardrails.py:28-47 — read-only reference). Binding minimums: `APPLY_CHANGES` (partially applied operation sequence) → {GROUNDING_AUDIT, FINAL_MATCH}; `RENDER`/`RENDER_VALIDATION` (render overflow) → {RENDER, RENDER_VALIDATION}; `FINAL_MATCH` → {FINAL_MATCH}; `GROUNDING_AUDIT` → {GROUNDING_AUDIT, FINAL_MATCH}; `ATS_STRUCTURE_VALIDATION` → {ATS_STRUCTURE_VALIDATION}; pre-APPLY checkpoints (INIT..VALIDATE_CHANGES) → {} (their stages simply resume). Document the rationale per non-empty entry in code.
- [ ] recoverRun computes `required_reruns` from the map, includes them in its result, AND persists a recovery event into run state: `{recovered_at_checkpoint, required_reruns, recovery_sequence}` (monotonic counter — remember Date-free determinism: use sequence numbers/log positions, not wall-clock, as the ordering authority).
- [ ] `assertCanComplete` gains a `recovery_reruns` gate: for the latest recovery event, every required rerun checkpoint must have a recorded result ordered AFTER that recovery event (recorded via recordCheckpointResult ordering/sequence). Missing/stale rerun → gate fails with the missing checkpoints named in `failed_gate_reasons`.
- [ ] Runs with no recovery event pass the new gate vacuously (no regression for uninterrupted runs — all existing completion tests stay green).
- [ ] Contract tests: (a) recover at APPLY_CHANGES → reruns {GROUNDING_AUDIT, FINAL_MATCH} and COMPLETE blocked until both re-record post-recovery; (b) pre-recovery recorded results do NOT satisfy the gate; (c) recover at INGEST_JOB → empty rerun set, gate vacuous; (d) two successive recoveries — the LATEST recovery event governs; (e) hardcoded-set regression: recovery at RENDER must NOT yield bare ['FINAL_MATCH'].
- [ ] `--pr` and `--smoke` green.

## Implementation Notes **[CONDITIONAL: Technical Task]**

### Technical Approach
- Follow the existing completion-gate idiom in `assertCanComplete` (workflow/__init__.py:405-443): add to `required_gates` / `failed_gate_reasons`, keep the response shape stable (add-only).
- Ordering authority: recordCheckpointResult already appends into persisted state; use its position/sequence relative to the persisted recovery event — do not introduce wall-clock comparisons (scripts and tests are deterministic; the codebase avoids nondeterministic time as gate input).
- Recommended Agent: opus + medium

### Dependencies
RKIT-T-0074 (recoverRun contract), RKIT-T-0075 (integrity results feed `resumable`). Serial chain.

### Risk Considerations
- tools/workflow_guardrails.py is protected and pins manifest fields — persist the recovery event inside run state (and `recovery_markers`, already a manifest field per workflow/__init__.py:360) rather than adding new manifest fields; if a new manifest field is genuinely needed, DEFER the manifest/guardrail edit to the approval batch and keep gates green.
- Keep `workflow_surface.json` recoverRun/assertCanComplete declarations in sync (unprotected).

## Status Updates **[REQUIRED]**

- 2026-08-16: T-0074/0075 landed and committed (gates 391/smoke/verify green; store-consultation mutation-probed by driver). Codex launched: 18-checkpoint rerun map, recovery events with monotonic recovery_sequence in run state (no new manifest fields — recovery_markers mirror only), recordCheckpointResult ordering stamp, recovery_reruns gate in assertCanComplete (vacuous without recovery).