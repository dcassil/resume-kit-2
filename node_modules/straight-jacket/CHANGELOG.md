# Changelog

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
