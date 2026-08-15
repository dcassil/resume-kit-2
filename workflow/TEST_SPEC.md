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

Simulate interruption after:

- job ingest,
- user verification,
- proposed operations,
- partially applied operation sequence,
- render overflow.

Assertions:

- run resumes from persisted deterministic state,
- career DB remains transactionally valid,
- base resume remains unchanged,
- already-applied operations are not applied twice,
- rejected operations stay rejected,
- final validation reruns after recovery before complete.

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
