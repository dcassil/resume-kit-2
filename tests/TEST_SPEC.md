# tests Test Spec

## Contract

`tests` owns the executable suite layout and gating strategy. Tests are contract-first and must be in place before new implementation or port adaptation changes behavior.

The suite validates:

- contracts,
- expected output,
- gates,
- validation,
- determinism,
- package boundaries,
- persistence,
- honesty guardrails,
- rendering neutrality,
- auditability.

## Expected Test Layout

Future test files should be organized by gate:

```text
tests/
  unit/
  contract/
  boundary/
  integration/
  smoke/
  e2e/
  fixtures/
  snapshots/
```

## Required Gates

Canonical current command:

```sh
python3 tools/run_gate.py --pr --root .
```

This is the only canonical current gate. It installs the root package metadata in an isolated editable environment, verifies the runtime package layout, and runs the current executable contract, boundary, unit, honesty-fixture, and snapshot suite.

Forward-looking full package-contract gate:

```sh
python3 tools/run_gate.py --future-contract --root .
```

This distinct gate is a strict superset of `--pr`. It keeps every current-gate module and adds the full package-contract acceptance surfaces that are intentionally omitted from the PR gate.

### PR gate

Run:

- unit tests,
- contract tests,
- package-boundary tests,
- deterministic scoring fixtures,
- hallucination-rejection fixtures.

### Main gate

Run:

- full PR gate,
- full smoke test.

Command:

```sh
python3 tools/run_gate.py --main --root .
```

### Release-candidate gate

Run:

- full main gate,
- complete E2E test,
- renderer parse-back checks,
- migration upgrade tests from previous DB schema.

## Test Categories

### Unit tests

Validate pure functions and local behavior:

- schema parsing,
- ATS sanitation,
- date normalization,
- requirement normalization,
- scoring math,
- state transitions,
- change validation,
- relationship matching,
- config parsing.

### Contract tests

Validate public surfaces:

- core APIs accept/reject specified DTOs,
- store APIs preserve verification/evidence rules,
- MCP tools expose only allowed operations,
- agent outputs match schema and proposal-only boundary,
- renderer returns semantic-neutral outputs or layout constraints,
- CLI commands produce expected artifacts.

### Boundary tests

Validate dependency direction and forbidden behavior:

- core imports no CLI/MCP/plugin/renderer/store internals,
- store imports no CLI/agent/plugin host,
- MCP exposes no raw SQL,
- renderer imports no career-store/MCP,
- plugin contains no domain algorithms,
- CLI orchestrates through public APIs only.

### Integration tests

Validate package cooperation:

- resume ingest to core validation to store facts,
- job ingest to core normalization,
- match with store facts,
- resolve loop through agent proposals and store persistence,
- tailor through selection, rewrite proposals, validation, and application,
- render through validated canonical working resume.

### Smoke tests

Validate the install/build happy path plus release-blocking honesty checks using the smoke fixture.

Required smoke assertions:

- packages load/build,
- SQLite migration succeeds,
- resume/job schemas validate,
- base resume immutable,
- career facts persisted with evidence,
- MCP search works without raw SQL,
- score reproducible,
- user confirmation updates career model,
- agent outputs are proposals,
- grounded rewrite can be applied,
- hallucinated rewrite rejected,
- final grounding and ATS validation pass,
- Markdown and DOCX render targets succeed,
- audit explains the run.

### E2E tests

Validate the full product behavior:

- base resume to canonical resume,
- fact extraction without over-verification,
- job normalization,
- deterministic match,
- known-fact gap resolution,
- targeted questions,
- persistent confirmations,
- grounded rewrites,
- unsupported proposal rejection,
- structure constraints,
- base immutability,
- second-job reuse of career DB,
- audit reconstruction,
- failure recovery.

## Determinism Requirements

- Use isolated temp directories.
- Use isolated SQLite databases.
- Freeze time where IDs/timestamps affect output.
- Record package versions, schema versions, model config, config hash, and renderer template version.
- Run official scoring twice and assert identical results.
- Snapshot expected deterministic outputs.
- Keep language-model phrasing assertions tolerant, but keep structured fields strict.

## Pass/Fail Policy

Release is blocked by:

- fabricated skill, title, metric, years, responsibility, scale, or outcome in final output,
- inferred fact treated as verified,
- related fact treated as equivalent without modeled relationship,
- missing provenance for generated claim,
- nondeterministic official score,
- base resume mutation,
- raw SQL MCP exposure,
- renderer semantic mutation,
- lost learned facts between jobs,
- duplicate questions for verified facts without legitimate reason,
- false resolution of unresolved hard requirement.
