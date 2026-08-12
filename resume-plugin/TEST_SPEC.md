# resume-plugin Test Spec

## Contract

`resume-plugin` is an optional delivery adapter. It registers host tools/skills, maps host conversations into CLI/domain workflows, presents confirmation requests, diffs, and reports, and keeps all domain behavior in reusable packages.

It must not own scoring, SQLite schema, ATS sanitation, mutation logic, canonical schemas, rendering truth, or career-learning behavior.

## Expected Structure

Tests should expect adapter-only concerns:

- host/plugin manifests
- skill/instruction text
- command mapping
- confirmation presentation
- diff/report presentation
- error/report formatting
- compatibility metadata

## Test Cases

### Manifest and registration

- Plugin manifests identify the adapter and exposed skill/tool entry points.
- Registered tools map to CLI/domain workflows rather than duplicating logic.
- Metadata changes remain synchronized across supported manifests if multiple host formats exist.

### Conversation mapping

- User requests for resume ingest map to CLI/domain ingest.
- User requests for job tailoring map to run/resolve/tailor workflows.
- User confirmation prompts preserve the code-selected unresolved requirement.
- User answers are passed to agent/store workflow as structured inputs, not direct DB writes.

### Presentation

- Shows match reports with resolved, missing, preferred, and unresolved requirements clearly separated.
- Shows diffs from `ResumeChangeOperation` records.
- Shows rejected operations and reasons.
- Shows audit summaries without leaking unnecessary sensitive data.
- Shows render/export results.

### Forbidden behavior

- No independent scoring algorithm.
- No independent SQLite schema or migration code.
- No independent ATS sanitizer.
- No independent mutation logic.
- No independent canonical resume/job schemas.
- No independent career-learning behavior.
- No host skill instruction that tells the agent it may bypass validation.

### Upgrade safety

- Plugin-only version changes do not alter resume truth semantics.
- Domain semantics change only when underlying package versions or config hashes change.
- Reports include underlying package/schema/config versions.

## Boundary Tests

- Fail if plugin imports private package internals instead of public CLI/domain APIs.
- Fail if plugin writes `resume/working.json` directly.
- Fail if plugin writes SQLite directly.
- Fail if plugin prompts include broader career DB context than needed.
- Fail if plugin exports internal provenance metadata in final resume files.

## Smoke Coverage

Plugin smoke is optional after core smoke, but when run it must prove:

- plugin can invoke the same local workflow,
- user confirmation can be presented and captured,
- reports/diffs/audits are displayed,
- no domain behavior differs from CLI result.

## E2E Coverage

Plugin E2E should reuse the same fixture expectations as CLI E2E. The plugin passes only if adapter presentation changes do not affect:

- score,
- requirement resolution,
- verification state,
- applied operations,
- final canonical resume,
- rendered semantic content,
- audit reconstruction.

