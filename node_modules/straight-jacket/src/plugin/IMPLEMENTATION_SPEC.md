# Plugin Implementation Spec

## Purpose

`src/plugin/` contains assets and helpers for packaging Straight Jacket as an AI-friendly plugin.

The plugin must help agents respect the boundary without granting mutation authority.

## Expected Folders

```text
src/plugin/skills/
src/plugin/mcp/
```

## Required Behavior

- Generate or package skill instructions.
- Reference only read-only MCP tools by default.
- Teach agents to list and verify protected files before broad edits.
- Teach agents never to request passwords in chat.
- Teach agents never to edit Straight Jacket metadata directly.

## Forbidden Behavior

- no silent add/remove/update/rename tools
- no password forwarding
- no private-key export
- no bypass instructions such as `git commit --no-verify`

## Test Targets

Primary:

```text
test/unit/plugin.test.mjs
```
