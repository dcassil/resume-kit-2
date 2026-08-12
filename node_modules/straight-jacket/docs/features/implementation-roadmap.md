# Implementation Roadmap

## Goal

Build Straight Jacket test-first, keeping the product tiny and the security claims honest.

## Milestone 1: Manifest And Signing Foundation

Target tests:

- `initRepository creates signed repo-readable verification metadata without storing the password`

Implement:

- `src/index.js`
- `src/core/init-repository.js`
- `src/manifest/canonical-json.js`
- `src/manifest/read-write.js`
- `src/signing/keys.js`
- `src/signing/signatures.js`

Done when:

- `initRepository` writes manifest, signature, public key, and encrypted local private key
- manifest starts empty
- repo metadata does not contain the password
- public key fingerprint is stable

## Milestone 2: Add And Verify Happy Path

Target tests:

- `addProtectedFile registers path...`
- basic verify success tests

Implement:

- path normalization
- checksum calculation
- entry creation
- manifest re-signing
- basic working-tree verification

Done when:

- adding `docs/policy.md` produces expected entry fields
- `verifyRepository` returns `{ ok: true, checked: 1, violations: [] }`

## Milestone 3: Mutation Authorization

Target tests:

- remove wrong password rejection
- update wrong password rejection
- authorized remove/update
- authorized rename

Implement:

- password unlock
- signer mismatch checks
- remove/update/rename operations
- exact path identity preservation

Done when:

- every manifest mutation verifies current signature first
- wrong password cannot mutate state

## Milestone 4: Tamper Detection

Target tests:

- all `test/security/tamper-vectors.contract.test.mjs` working-tree tests

Implement:

- missing manifest/signature/public-key checks
- invalid signature checks
- public-key fingerprint pinning
- duplicate path detection
- case-collision detection
- absolute/escape rejection
- symlink rejection
- hash/policy downgrade detection
- likely move/rename scan

Done when:

- verification fails closed with stable violation codes
- multiple violations can be returned together

## Milestone 5: Staged Verification And Hooks

Target tests:

- staged protected-file deletion
- staged manifest tampering
- CLI `install-hook`
- CLI `install-ci`
- CLI `status`

Implement:

- Git staged blob helpers
- staged diff parsing
- hook installer
- hook health status
- pre-commit template
- GitHub Actions CI template installer

Done when:

- `verifyRepository({ scope: "staged" })` catches staged tampering
- status reports local hooks as advisory
- CI template includes external fingerprint pinning guidance

## Milestone 6: CLI Surface

Target tests:

- all `test/contract/cli.contract.test.mjs`

Implement:

- `src/cli.js`
- argument parser
- interactive prompt handling
- JSON output formatting
- exit-code mapping
- binary shim

Done when:

- CLI commands call core functions without duplicating domain logic
- forbidden password flags fail before touching repo state

## Milestone 7: MCP Surface

Target tests:

- all `test/contract/mcp.contract.test.mjs`

Implement:

- `src/mcp.js`
- tool registry
- read-only list/verify tools
- violation explainer
- forbidden tool rejection

Done when:

- MCP exposes only read-only tools by default
- MCP output never includes password/private key material

## Milestone 8: Plugin Skill And Templates

Target tests:

- new plugin template tests
- new hook/CI template tests

Implement:

- `templates/plugin/SKILL.md`
- `templates/hooks/pre-commit`
- `templates/ci/github-action.yml`
- plugin packaging notes

Done when:

- skill teaches agents to respect protected files
- CI template documents external fingerprint pinning

## Suggested Build Order

1. Run `npm test`.
2. Pick the first failing core test.
3. Implement only enough code to move that test green.
4. Run `npm run guardrails`.
5. Repeat through core, security, CLI, MCP, templates.

## Non-Goals During MVP

- cloud service
- daemon
- policy language
- silent MCP mutation
- password from environment variables
- fully preventing local hook bypass without CI/server enforcement
