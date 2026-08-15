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
- operation log
- question/answer log
- validation results
- render results
- recovery markers

## State Machine Test Cases

### Valid transitions

- INIT can move to resume ingest only after config validates.
- Resume ingest can move to base validation only after canonical output exists.
- Base validation must pass before career fact extraction persists final source-stated facts.
- Job ingest must pass normalization before matching.
- Match must run before gap resolution.
- Gap resolution must rerun match after new verified facts.
- Tailoring must build a selection plan before agent rewrite proposals.
- Changes must validate before application.
- Final validation must run before render/export completion.
- Render validation must run before complete.

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
