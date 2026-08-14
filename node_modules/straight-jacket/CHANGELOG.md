# Changelog

## 1.0.0 - 2026-08-13

- Replaced CI trust-root pinning with a master-password-derived `STRAIGHT_JACKET_CI_KEY` proof model.
- Added `.straight-jacket/ci-proof.json` and `straight-jacket verify --ci-key` for GitHub Actions enforcement.
- Updated setup output to print a CI-only key for humans to store as a GitHub Actions secret without exposing the master password.
- Restored the release workflow and converted verifier workflows to use `STRAIGHT_JACKET_CI_KEY`.

## 0.1.11 - 2026-08-13

- Added master-password registration authority and per-developer local signer registration.
- Added committed signer registry metadata, encrypted registration key support, and manifest verification against active registered signers.
- Added `straight-jacket setup` and `straight-jacket setup --check` for clean repo initialization and fresh clone registration.
- Moved hook installation to committed `.githooks/pre-commit` with `core.hooksPath=.githooks` and local setup checks.

## 0.1.10 - 2026-08-12

- Expanded human-readable verification failures with locked file lists and human authorization commands.
- Updated generated GitHub Actions workflows to use detailed human verification output instead of JSON logs.
- Fixed batch `remove` to skip shell-expanded unregistered paths while removing registered matches.

## 0.1.8 - 2026-08-12

- Added a `Release` workflow that publishes the npm package, tag, and GitHub release on every push to `main`.
- Updated the required `verify` workflow to block PRs whose package version is already published.
- Added repository agent rules requiring version/changelog bumps before merging to `main`.

## 0.1.7 - 2026-08-12

- Fixed batch `add` coverage for shell-expanded path lists such as `tools/pre-commit-alpha tools/pre-commit-beta`.
- Added batch `remove` support for multiple exact paths and registered-path glob patterns.
- Documented the `addProtectedFiles` and `removeProtectedFiles` contracts.

## 0.1.6 - 2026-08-12

- Updated the GitHub Actions verifier workflow to install Straight Jacket from the GitHub release tag.
- Wired `STRAIGHT_JACKET_PUBLIC_KEY_FINGERPRINT` from GitHub Actions repository variables.

## 0.1.5 - 2026-08-12

- Updated the pre-commit hook to run full working-tree verification before staged verification.
- This blocks commits while already-protected files are modified, even when the protected change was staged or committed earlier.

## 0.1.4 - 2026-08-12

- Added detailed CLI help for top-level usage and each command.
- Added support for `--help`, `-h`, `help <command>`, and no-argument help output.
- Added visible interactive terminal prompts for password-based commands.

## 0.1.3 - 2026-08-12

- Updated MCP config examples to use the installed `straight-jacket-mcp` binary.

## 0.1.2 - 2026-08-12

- Added plugin setup guidance for missing CLI, missing project initialization, incomplete metadata, and disconnected MCP config.

## 0.1.1 - 2026-08-12

- Fixed the MCP stdio server initialize response to report the package version.

## 0.1.0 - 2026-08-12

- Added the first public Straight Jacket CLI, core library, and read-only MCP server.
- Added signed manifest verification for human-protected repo files.
- Added interactive authorization flows for protected file add, update, remove, and rename operations.
- Added staged verification, advisory pre-commit hook installation, and GitHub Actions CI template generation.
- Added Claude plugin marketplace metadata and the Straight Jacket agent skill.
