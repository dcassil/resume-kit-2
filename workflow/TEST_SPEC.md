# workflow Test Spec

## Contract

`workflow` documents and tests the cross-package state machine, checkpoints, run manifest, audit trail, recovery behavior, and deterministic orchestration rules.

The canonical workflow is:

```text
INIT
  -> INGEST_RESUME
  -> VALIDATE_BASE
  -> EXTRACT/PERSIST CAREER FACTS
  -> INGEST_JOB
  -> NORMALIZE_JOB
  -> MATCH_BASE
  -> RESOLVE_GAPS if needed
  -> BUILD_SELECTION_PLAN
  -> PROPOSE_TAILORING CHANGES
  -> VALIDATE CHANGES
  -> APPLY CHANGES
  -> FINAL MATCH
  -> GROUNDING AUDIT
  -> ATS/STRUCTURE VALIDATION
  -> RENDER
  -> RENDER VALIDATION
  -> COMPLETE
```

No checkpoint may be skipped because an agent output appears plausible.

## Expected Structure

Tests should expect workflow artifacts around:

- shared run manifest DTO and JSON schema definitions in `workflow.schemas`
- run manifest
- stage state
- checkpoints
- config hash
- schema/package/template versions
- operation log (`.workflow/runs/<run_id>/operations.jsonl`) exists on disk with at least one JSONL record when operation status transitions are recorded
- question/answer log (`.workflow/runs/<run_id>/questions.jsonl`) exists on disk with at least one JSONL record when question/answer refs are recorded
- validation results
- render results
- recovery markers

## State Machine Test Cases

### Grounded transition obligations

- INIT can move to resume ingest only after a config-validation DTO resolves in the run state.
- Resume ingest can move to base validation only after the canonical resume artifact exists and its hash matches the EvidenceRef.
- Base validation can move to career fact extraction only after a validation DTO resolves against the declared workflow schema.
- Job ingest can move to normalization only after the ingested job artifact exists and its hash matches the EvidenceRef.
- Normalization can move to matching only after a normalization DTO resolves against the declared workflow schema.
- Match can move to gap resolution only after a match-result DTO resolves against the declared workflow schema.
- Gap resolution with new persisted verified facts beyond the last match watermark must rerun match exactly once for that fact batch; after the rerun records a covering watermark, the loop continues and BUILD_SELECTION_PLAN must be reachable with grounded run-state evidence.
- Gap resolution with exhausted unresolved non-hard gaps must advance to BUILD_SELECTION_PLAN and record unresolved_requirements entries in the run manifest source state.
- Gap resolution with an unresolved hard requirement and requireHardRequirementsResolved enabled must remain blocked and must not advance to BUILD_SELECTION_PLAN.
- Tailoring can move to agent rewrite proposals only after a selection-plan DTO resolves against the declared workflow schema.
- Changes can move to application only after change-validation DTO evidence resolves against the declared workflow schema.
- Final match can move to grounding audit only after operations-applied evidence resolves from persisted run state.
- Grounding audit, ATS/structure validation, render, render validation, and complete can advance only after their required DTO, artifact, or persisted run-state evidence resolves.
- A render checkpoint result from `measureLayout` with `status: overflow` and positive character-count `requiredReduction` must record a render-overflow constraint artifact; `getNextCheckpoint` must route back to BUILD_SELECTION_PLAN with both `selection_plan` and `render_overflow_constraints` required, and advancing through BUILD_SELECTION_PLAN must consume that exact constraint ref.
- Render overflow that exceeds `workflow.maxRenderOverflowIterations` must block at RENDER with persisted `render_overflow_bound_exhausted` reasons and must not reach COMPLETE silently.
- COMPLETE can advance only when each grounded completion gate has a resolving artifact ref with a matching hash: final match report, grounding audit, ATS/structure report, render validation report, and audit ref.
- COMPLETE must remain blocked for each grounded completion gate when that gate's ref is missing or when the referenced artifact hash does not match the current file bytes.

### Invalid transitions

- Cannot tailor before job ingest.
- Cannot apply operations before validation.
- Cannot render as complete before grounding audit.
- Cannot continue past unresolved hard requirements when policy requires resolution.
- Cannot skip career-store persistence for confirmed facts.
- Cannot mark run complete with failed hallucination rejection gate.

### Artifact rules

- `resume/base.json` is immutable after successful ingest unless explicitly re-ingested.
- `resume/working.json` is recreated from base for a new tailoring session unless config says otherwise.
- Change operations persist separately from resume files.
- Job model is versioned or replaced explicitly.
- Career DB persists across jobs.
- Audit artifacts record enough detail to reconstruct the run.

### Run manifest

Record:

- source resume identity,
- run ID,
- base resume ID/hash,
- job ID,
- config hash,
- schema/package/model/template versions,
- initial and final scores,
- unresolved requirements,
- user question/answer log refs,
- facts added/verified,
- proposed/rejected/applied operations,
- validation outcomes,
- output artifact paths.

## Determinism Test Cases

- Same state/config yields same workflow decision for next unresolved requirement.
- Same state/config yields same official match score.
- Same state/config yields same selection plan.
- Retried operation application is idempotent or safely detected.
- Recovered runs do not duplicate user questions or fact writes.

## Failure Recovery Test Cases

The recovery contract is covered by `tests/contract/test_workflow_recovery_matrix.py` and is executed by the current PR/future gates through `tests.contract.test_workflow_contract` until the runner list is approved to include the new module directly.

Each matrix case simulates interruption by driving `createRun` through public `advanceCheckpoint` / `recordCheckpointResult` calls to the target checkpoint, then calling `recoverRun` against persisted run state. Persistence is the interruption boundary; no process-kill machinery is required.

Five-point interruption matrix:

- Job ingest: `test_recovery_matrix_job_ingest_interruption` interrupts at `INGEST_JOB`, expects `required_reruns == []`, verifies `resume_from_checkpoint == "INGEST_JOB"`, verifies career DB/base resume/rejected-operation integrity with evidence, and confirms no question/fact/operation registries are duplicated.
- User verification: `test_recovery_matrix_user_verification_interruption` interrupts at `RESOLVE_GAPS`, expects `required_reruns == []`, verifies persisted resume state and all integrity checks with evidence, confirms the asked-question registry prevents re-asking the first topic, and confirms duplicate fact writes return typed duplicate results without growing the registry.
- Proposed operations: `test_recovery_matrix_proposed_operations_interruption` interrupts at `PROPOSE_TAILORING_CHANGES`, expects `required_reruns == []`, verifies persisted resume state and all integrity checks with evidence, confirms question/fact registries remain monotone, and confirms no applied-operation registry exists before application.
- Partially applied operation sequence: `test_recovery_matrix_partially_applied_operation_sequence_interruption` interrupts at `APPLY_CHANGES`, expects `required_reruns == ["GROUNDING_AUDIT", "FINAL_MATCH"]`, verifies persisted resume state and all integrity checks with evidence, confirms duplicate fact writes and duplicate operation application are typed duplicates, and confirms `assertCanComplete` stays blocked by `recovery_reruns` until fresh post-recovery `GROUNDING_AUDIT` and `FINAL_MATCH` results are recorded.
- Render overflow: `test_recovery_matrix_render_overflow_interruption` interrupts at `RENDER` after an overflow result, expects `required_reruns == ["RENDER", "RENDER_VALIDATION"]`, verifies persisted render-overflow state and all integrity checks with evidence, confirms duplicate fact writes and duplicate operation application are typed duplicates, and confirms `assertCanComplete` stays blocked by `recovery_reruns` until fresh post-recovery `RENDER` and `RENDER_VALIDATION` results are recorded.

Recovery regressions are covered by `tests/contract/test_workflow_contract.py`: invalid store-double state fails career DB integrity (`test_recover_run_career_db_pending_schema_update_fails_via_store_double`), unknown runs raise `UnknownRunError` (`test_recover_run_unknown_run_raises_unknown_run_error` and `test_recover_run_never_fabricates_payload_for_missing_run_file`), completion remains blocked until required post-recovery reruns (`test_recovery_at_apply_changes_requires_grounding_and_final_match_reruns_before_completion`), and rejected-then-applied operation scans fail recovery (`test_recover_run_rejected_then_applied_operation_fails_and_lists_id`).

## Smoke Coverage

The smoke workflow must prove the happy path and critical honesty guardrails from init through audit.

## E2E Coverage

The E2E workflow must prove:

- complete Job A run,
- targeted interview,
- valid tailoring,
- adversarial rejection,
- render validation,
- audit reconstruction,
- second Job B run using same career DB,
- optional preference learning boundaries,
- interruption recovery.
