---
id: typed-recoverrun-contract
level: task
title: "Typed recoverRun contract: RunNotFound, structured integrity result, no invented state"
short_code: "RKIT-T-0074"
created_at: 2026-08-16T18:09:42.222770+00:00
updated_at: 2026-08-16T18:19:07.812394+00:00
parent: workflow-recovery-and-idempotency
blocked_by: []
archived: false

tags:
  - "#task"
  - "#phase/completed"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0025
---

# Typed recoverRun contract: RunNotFound, structured integrity result, no invented state

## Parent Initiative

[[RKIT-I-0025]]

## Objective **[REQUIRED]**

Convert `recoverRun` (workflow/__init__.py:383-402) from a fabricating, literal-returning stub into a typed recovery contract: unknown run ids raise the existing typed `UnknownRunError` (never fabricated `{'run_id', 'current_checkpoint': 'INIT'}` state — line 385 regression), and the result gains a structured `integrity` object with per-check `{status, evidence_ref}` entries replacing the bare `"transactional_integrity": "valid"` literal (line 401). This task delivers the CONTRACT SHAPE; the real verification logic behind each integrity check lands in RKIT-T-0075 — here each check may return `status: "unverified"` with an honest reason, never `"verified"` without proof.

## Acceptance Criteria

## Acceptance Criteria

## Acceptance Criteria **[REQUIRED]**

- [ ] `recoverRun(workspace, unknown_run_id)` raises `UnknownRunError` (REUSE the existing exception raised by `reconstructRunManifest` at workflow/__init__.py:372 — do NOT add a new public name; `__all__` is boundary-tested and `tools/workflow_guardrails.py` pins `ALLOWED_SURFACES` to exactly 7 functions).
- [ ] The fabrication branch at workflow/__init__.py:385 (`{"run_id": run_id, "current_checkpoint": "INIT"}` default) is deleted; recoverRun only ever reads persisted run state.
- [ ] The flat `"transactional_integrity": "valid"` literal (line 401) is deleted; the result carries `integrity: {career_db, base_resume, rejected_operations}` where each value is `{"status": "verified"|"failed"|"unverified", "evidence_ref": <ref-or-null>, "reason": <string>}` — never a bare string literal.
- [ ] In this task the three integrity checks return `status: "unverified"` with reason `"verification_not_implemented"` unless trivially provable; NO check may claim `"verified"` without real evidence (the audit's declared-not-checked pattern must not reappear in structured form).
- [ ] Result includes `resumable: bool` — false whenever any integrity check reports `failed` (unverified does not block in this task; T-0075 tightens).
- [ ] `workflow/workflow_surface.json` recoverRun declaration (~line 198) updated to the new response field set; function-name set unchanged (must stay equal to guardrail `ALLOWED_SURFACES`).
- [ ] Unit/contract tests: unknown-run raises `UnknownRunError`; result shape has structured integrity (no string literal); fabricated-state regression (nonexistent run file never yields a usable result).
- [ ] `python3 tools/run_gate.py --pr --root .` and `--smoke` green.

## Implementation Notes **[CONDITIONAL: Technical Task]**

### Technical Approach
- Keep the existing recovery-payload fields (already_* registries, resolution/render-overflow state, required_reruns) intact; `required_reruns` hardcoding is fixed by RKIT-T-0076, not here — leave line 387 semantics alone except as needed to preserve shape.
- `UnknownRunError(run_id, workspace_path)` construction pattern already exists at workflow/__init__.py:372.
- Evidence-ref shape should mirror the grounded EvidenceRef conventions from RKIT-I-0023 (see `_completion_gate_refs` usage) — refs into persisted run state / logs, not free text.
- Recommended Agent: opus + high

### Dependencies
None (first task of the initiative). RKIT-T-0075/0076/0077/0078 build on this contract.

### Risk Considerations
- Do NOT touch protected files: tools/run_gate.py, tools/run_tests.py, tools/run_smoke.py, tools/TEST_SPEC.md, tools/*_guardrails.py, tests/boundary/*. If a test module needs gate wiring, note it for the deferred approval batch instead.
- resume-cli smoke drives recoverRun indirectly — run `--smoke`, not just `--pr`, before declaring done.

## Status Updates **[REQUIRED]**

- 2026-08-16: Session resumed post-approval (straight-jacket verify clean, gates 382/smoke green at 6540f53). I-0025 decomposed into T-0074..0078 (serial chain, all touch workflow/__init__.py). Codex launched on this task with binding decisions: reuse UnknownRunError, structured integrity with "unverified"/verification_not_implemented placeholder statuses (T-0075 implements real checks), resumable flag, surface JSON update with unchanged function-name set. Protected files forbidden; gate wiring deferred to approval batch.