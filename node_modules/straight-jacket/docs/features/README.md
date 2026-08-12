# Feature Specs

This folder breaks Straight Jacket into implementation pieces that match the project scaffold and contract tests.

## Pieces

- [Core Library](./core-library.md): public JavaScript API and orchestration.
- [Manifest Format](./manifest-format.md): signed payload shape, canonicalization, and validation.
- [Signing And Authorization](./signing-authorization.md): password-gated private key use and public verification.
- [Git Integration](./git-integration.md): repo-root detection, staged checks, hook health, and path state.
- [CLI](./cli.md): command behavior, prompts, JSON output, and exit codes.
- [MCP](./mcp.md): read-only tool surface and forbidden capabilities.
- [Hooks And CI](./hooks-ci.md): pre-commit hook, CI template, and strong enforcement posture.
- [Plugin And Skill](./plugin-skill.md): agent-facing behavior and install/help flows.
- [Guardrails](./guardrails.md): quality, boundary, and coverage checks.
- [Implementation Roadmap](./implementation-roadmap.md): suggested TDD build order.

## Design Rules

- The executable contract lives in `test/`.
- The API contract lives in `docs/API_CONTRACT.md`.
- These feature specs explain how to implement the contract without expanding scope.
- Source-adjacent implementation specs live in `src/**/IMPLEMENTATION_SPEC.md`.
- When specs and tests disagree, update the test first if the contract should change.

## Major Folders

```text
src/core       API orchestration and domain behavior
src/manifest   manifest parsing, canonicalization, validation
src/signing    key creation, password unlock, signing, verification
src/git        Git index/status/path helpers
src/hooks      hook installer and hook health checks
src/cli        command parsing and prompt handling
src/mcp        MCP tool definitions and tool dispatch
src/plugin     Codex/AI plugin assets and skill instructions
bin            package executable shim
templates      generated hook, CI, and plugin templates
```
