# Guardrails Spec

## Purpose

Guardrails catch design drift before implementation weakens the trust boundary.

Folders:

```text
scripts/guardrails/
test/guardrails/
docs/GUARDRAILS.md
```

## Current Guardrail Scripts

### `boundary-check.mjs`

Checks implementation source for forbidden boundary shortcuts.

Current checks:

- no default password environment variables
- no repo-file password source plumbing
- no password-file reads
- no forbidden silent MCP mutation tools

Future checks:

- `verifyRepository` does not import prompt helpers
- MCP does not import signing unlock helpers
- CLI does not expose diagnostic signature bypass
- no source file writes private keys outside allowed local path

### `coverage-check.mjs`

Checks that every named tamper vector has contract coverage.

Current required vectors:

- content modification
- deletion
- move or rename
- manifest checksum editing
- manifest deletion
- signature deletion
- public verifier replacement
- duplicate paths
- case collisions
- absolute paths
- parent escapes
- symlink replacement
- hash downgrade
- policy downgrade
- staged protected-file deletion
- staged manifest tampering

Future checks:

- every violation code has at least one test
- every CLI command has at least one contract test
- every MCP tool has one positive and one negative test

### `quality-check.mjs`

Checks project shape and committed-file hygiene.

Current checks:

- required docs exist
- required tests exist
- private signing material is not committed
- test password fixture is not leaked outside tests/guardrail logic

Future checks:

- templates exist once implementation reaches hook/plugin stage
- package binary exists once CLI is implemented
- docs mention external verifier whenever strong mode is discussed

## Guardrail Test

`test/guardrails/guardrails.test.mjs` executes each script as a test, so `npm test` includes guardrail health.

## Boundary Rules To Preserve

- Verification is read-only.
- Mutation requires signing authorization.
- MCP is read-only by default.
- Passwords are interactive-only in CLI.
- Manifest trust requires signature verification.
- Registration metadata replacement requires a valid CI proof checked with `STRAIGHT_JACKET_CI_KEY`.
- Local hooks are advisory.

## Updating Guardrails

When adding a new security behavior:

1. Add a failing contract/security test.
2. Add a guardrail if the behavior can drift through future source changes.
3. Update this document.
4. Implement the smallest code that passes both.

Guardrails should be strict where the boundary is strict, and quiet where implementation choices are still legitimately open.
