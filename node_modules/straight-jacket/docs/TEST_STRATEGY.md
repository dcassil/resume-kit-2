# Straight Jacket Test Strategy

The test suite is contract-first. It defines expected behavior before implementation.

## Test Layers

- `test/unit/*.test.mjs` defines internal module boundaries for each major `src/` piece.
- `test/contract/core-api.contract.test.mjs` defines the core JavaScript API.
- `test/contract/cli.contract.test.mjs` defines CLI commands, outputs, and exit codes.
- `test/contract/mcp.contract.test.mjs` defines MCP tools and forbidden capabilities.
- `test/security/tamper-vectors.contract.test.mjs` defines tamper detection behavior.
- `test/guardrails/guardrails.test.mjs` keeps guardrail scripts executable.

Detailed implementation specs live in `docs/features/`.

## TDD Flow

1. Run `npm test`.
2. Observe the red contract failures.
3. Implement the smallest core behavior that satisfies one failing test.
4. Keep the public output contract stable.
5. Add a new failing test before widening the behavior.

## Strongest Security Assertions

The suite distinguishes local friction from real enforcement.

- Pre-commit hook tests prove the local hook calls verification.
- Tamper-vector tests prove local detection.
- Public-key pinning tests prove the design can support external enforcement.
- No test should imply that a repo-local hook alone is impossible to bypass.
