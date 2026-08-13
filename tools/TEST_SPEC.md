# tools Test Spec

## Contract

`tools` contains local developer and release utilities that enforce the product contract. Tools may run tests, validate fixtures, inspect architecture boundaries, check manifests, and generate reports. They must not become hidden business logic.

## Expected Structure

Future utilities may include:

- test runners,
- fixture validators,
- snapshot review helpers,
- architecture import checkers,
- migration checkers,
- release checks,
- audit validators,
- render parse-back validators.

## Tool Test Cases

### Test runner wrappers

- Run PR gate with unit, contract, boundary, deterministic scoring, and hallucination fixtures.
- Run future contract gate with full package contracts plus package boundary guardrails.
- Run main gate with smoke tests.
- Run release gate with E2E, renderer parse-back, and migration upgrade tests.
- Return non-zero on any release-blocking failure.
- Print enough command output for debugging without leaking sensitive fixture contact data.

### Fixture validators

- Validate fixture presence and schema.
- Validate that resume fixture does not accidentally include AWS/GraphQL/Staff/unsupported metrics.
- Validate invalid operation fixtures remain unsupported by evidence.
- Validate expected snapshots include schema/config/version metadata.

### Architecture checkers

- Detect forbidden imports between packages.
- Detect plugin-owned domain algorithms.
- Detect renderer imports of career-store/MCP.
- Detect MCP raw SQL tools.
- Detect CLI direct DB writes or direct resume mutation bypassing core.

### Migration checkers

- Create fresh DB and migrate.
- Re-run migrations idempotently.
- Upgrade from previous schema fixture when available.
- Record schema version.
- Fail on destructive migration without explicit audited policy.

### Release check

Release check should require:

- build/package import success,
- all PR gate tests,
- full smoke test,
- hallucination rejection,
- base immutability,
- deterministic scoring,
- render validation,
- audit completeness.

Release candidate should additionally require:

- full E2E,
- Job B persistent learning,
- recovery tests,
- migration upgrade tests.

## Boundary Tests

- Fail if tools implement scoring, validation, or mutation logic that packages do not own.
- Fail if tests pass only through tool-specific behavior not available through public APIs.
- Fail if tool output becomes an unversioned source of product truth.

## Documentation Requirements

Every tool should document:

- what gate it supports,
- which package surfaces it invokes,
- whether it is safe for PR/main/release,
- what files it reads/writes,
- what failures are release-blocking.
