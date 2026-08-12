# Straight Jacket Guardrails

These guardrails keep the project aligned with its trust boundary.

## Boundary Guardrails

- Verification is read-only and never requires a password.
- Mutation requires human authorization and a signing flow.
- MCP tools are read-only by default.
- The manifest is repo-readable but not trusted unless its signature verifies.
- Public-key replacement is a violation unless an external pinned fingerprint approves it.
- Local hooks are advisory; strong enforcement belongs in CI or server-side Git hooks.
- Private signing material must not be committed.
- Passwords must never be accepted from repo files or default environment variables.
- CLI code may mention forbidden password flags only to reject them before touching repo state.

## Quality Guardrails

- Every tamper vector named in the product vision must have a contract test.
- Every public CLI command must have an expected exit code and JSON output contract.
- Every MCP tool must be covered by a surface test.
- Path handling must be tested against absolute paths, parent escapes, symlinks, and case collisions.
- Failure outputs must include stable violation codes.
- Tests should prefer isolated temporary Git repositories.
- New security behavior should be added test-first.

## Implementation Guardrails

- Keep dependencies minimal.
- Prefer Ed25519 signatures and SHA-256 checksums for MVP.
- Use deterministic JSON canonicalization for signed payloads.
- Keep core logic independent from CLI prompt handling.
- Keep MCP mutation flows request-only unless a human confirmation mechanism exists outside AI control.
- Fail closed on missing, malformed, duplicated, or ambiguous state.
