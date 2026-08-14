# Source Implementation Spec

## Purpose

`src/` contains the implementation for Straight Jacket's three public surfaces:

- core library API
- CLI executable
- MCP helper surface

The implementation should remain small and modular. Security-sensitive behavior belongs in focused modules with tests, not in CLI or MCP glue.

## Public Entrypoints

Expected files:

```text
src/index.js
src/cli.js
src/mcp.js
```

`src/index.js` exports the core API:

- `initRepository`
- `addProtectedFile`
- `removeProtectedFile`
- `updateProtectedFile`
- `updateProtectedFiles`
- `renameProtectedFile`
- `verifyRepository`
- `listProtectedFiles`
- `getRepositoryStatus`
- `installHook`
- `installCi`

`src/cli.js` runs CLI command dispatch.

`src/mcp.js` exports MCP test helpers:

- `listTools`
- `callTool`

## Dependency Direction

Allowed direction:

```text
cli -> core
mcp -> core
core -> manifest/signing/git/hooks
hooks -> git
manifest -> core violation helpers only if needed
signing -> manifest canonicalization only if needed
```

Forbidden direction:

```text
core -> cli
core -> mcp
manifest -> cli
signing -> cli
mcp -> signing private-key unlock helpers
```

## Boundary Rules

- Verification is read-only.
- Manifest mutation requires signing authorization.
- CLI prompts are not part of core logic.
- MCP is read-only by default.
- Diagnostic bypasses must never be reachable from CLI, MCP, hooks, or plugin surfaces.

## Test Targets

Run during implementation:

```text
npm run guardrails
npm run test:unit
npm run test:contract
```

The implementation should make unit tests green first, then contract and security tests.
