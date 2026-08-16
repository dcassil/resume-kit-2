---
id: idempotent-resumption-over
level: task
title: "Idempotent resumption over resolution/tailoring loop state via dedupe registries"
short_code: "RKIT-T-0077"
created_at: 2026-08-16T18:09:42.396807+00:00
updated_at: 2026-08-16T18:38:36.902318+00:00
parent: workflow-recovery-and-idempotency
blocked_by: [RKIT-T-0074, RKIT-T-0075, RKIT-T-0076]
archived: false

tags:
  - "#task"
  - "#phase/completed"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0025
---

# Idempotent resumption over resolution/tailoring loop state via dedupe registries

## Parent Initiative

[[RKIT-I-0025]]

## Objective **[REQUIRED]**

Make the dedupe registries (`already_asked_questions`, `already_written_facts`, `already_applied_operations` — workflow/__init__.py:126-128, 287-289) the ENFORCED recovery input for resumed execution: after recoverRun, resumed loop advancement must consult them before asking, writing, or applying, so no interruption point produces a duplicate question, fact write, or operation application. Today the registries are populated but nothing structurally prevents a resumed driver from re-doing recorded work.

## Acceptance Criteria

## Acceptance Criteria

## Acceptance Criteria **[REQUIRED]**

- [ ] A resumption surface (extending `getNextCheckpoint`/`advanceCheckpoint`/`recordCheckpointResult` semantics — NO new public function; guardrail pins 7 names) accepts/derives the recovery payload and filters: questions whose recovery refs are in `already_asked_questions` are not re-askable (the RKIT-I-0026 asked-question registry honors them on resume); fact ids in `already_written_facts` are not re-writable; operation ids in `already_applied_operations` are rejected for re-application with a typed duplicate-application result (detected, not silently skipped, satisfying "retried operation application is idempotent or safely detected" — workflow/TEST_SPEC.md Determinism cases).
- [ ] recordCheckpointResult after recovery MERGES into the registries (extend-unique semantics already at workflow/__init__.py:287-289) — never resets them.
- [ ] Resumed resolution loop (workflow/resolution_loop.py state via `_normalize_resolution_loop_state`) resumes from persisted `last_match_fact_watermark` and asked-question registry — recovery does not restart the loop from scratch.
- [ ] Resumed render-overflow loop (workflow/render_overflow.py via `_normalize_render_overflow_state`) resumes with its persisted iteration count — recovery does not grant a fresh `maxRenderOverflowIterations` budget.
- [ ] Contract tests: (a) recover mid-RESOLVE_GAPS → previously asked question ref is excluded from askable set; (b) recover after facts written → re-write attempt of same fact id is a no-op/typed-duplicate, registry unchanged; (c) recover mid-APPLY_CHANGES → re-applying an already-applied operation id yields the typed duplicate detection, not a second application; (d) render-overflow iteration count survives recovery; (e) registries only ever grow across recover→record cycles.
- [ ] `--pr` and `--smoke` green.

## Implementation Notes **[CONDITIONAL: Technical Task]**

### Technical Approach
- Prefer threading the recovery payload through existing checkpoint-advance paths (working run state) over new parameters on public functions; `_working_run_state` already normalizes persisted state.
- The typed duplicate-application result should mirror existing typed-rejection idioms (structured `{status, reason, operation_id}`), not an exception that aborts resumption.
- Recommended Agent: opus + medium

### Dependencies
RKIT-T-0074/0075/0076 (contract, integrity, recovery event). Serial chain — same files.

### Risk Considerations
- Do not change resolution_loop/render_overflow termination semantics (RKIT-I-0026/0027 contracts) — this task only makes their persisted state authoritative across recovery.
- Protected files forbidden; surface manifest updates limited to unprotected workflow/workflow_surface.json with the function-name set unchanged.

## Status Updates **[REQUIRED]**

- 2026-08-16: T-0076 landed and committed (PR 396/smoke/verify green; driver probed RENDER→{RENDER,RENDER_VALIDATION} + latest-recovery-governs end-to-end). Codex launched on this task: enforcement inside existing checkpoint paths (no new public names), typed duplicate detection for ops/facts, askable-set exclusion, loop-state continuity (watermark, render-overflow iteration budget). Note passed to codex: workflow/__init__.py at 1499/1500 guardrail line cap — new logic goes in private modules.