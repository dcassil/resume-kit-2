# MCP Spec

## Purpose

The MCP surface lets AI agents inspect and explain Straight Jacket state without giving them mutation authority.

Entrypoints:

```text
src/mcp.js
src/mcp/
src/plugin/mcp/
```

## Required Tools

### `straight_jacket_list_protected_files`

Input:

```json
{
  "repoRoot": "/absolute/path/to/repo"
}
```

Output:

```json
{
  "ok": true,
  "entries": [
    {
      "path": "docs/policy.md",
      "name": "policy.md",
      "checksum": "sha256:...",
      "size": 1234,
      "reason": "Human-owned policy file"
    }
  ]
}
```

Rules:

- read-only
- no password fields
- no private key fields
- safe to show to AI

### `straight_jacket_verify`

Input:

```json
{
  "repoRoot": "/absolute/path/to/repo",
  "scope": "working-tree"
}
```

Output:

```json
{
  "ok": false,
  "checked": 1,
  "violations": []
}
```

Rules:

- read-only
- no password
- no diagnostic signature bypass
- may accept CI proof state only through trusted host configuration, not by model-generated repo files

### `straight_jacket_explain_violation`

Input:

```json
{
  "violation": {
    "code": "CHECKSUM_MISMATCH",
    "path": "docs/policy.md"
  }
}
```

Output:

```json
{
  "ok": true,
  "message": "docs/policy.md changed. Ask the human to run: straight-jacket update docs/policy.md"
}
```

Rules:

- explain safe remediation
- never ask the AI for a password
- never reveal signing implementation details in a way that helps bypass

## Forbidden Tools

Do not expose by default:

- `straight_jacket_add`
- `straight_jacket_remove`
- `straight_jacket_update`
- `straight_jacket_rename`
- `straight_jacket_capture_password`
- `straight_jacket_export_private_key`

Calling a forbidden or unknown tool should reject with:

```text
TOOL_NOT_FOUND
```

or:

```text
MUTATION_NOT_ALLOWED
```

## Optional Future Request Tools

Allowed only if they do not mutate state silently:

- `straight_jacket_request_update`
- `straight_jacket_request_unlock`

These should return human instructions or a host-mediated confirmation request. They should not accept a password from the AI.

## Implementation Shape

Export two pure helpers for contract tests:

```js
export async function listTools()
export async function callTool(name, args)
```

Internal layout:

- `src/mcp/tools.js`
- `src/mcp/tool-schemas.js`
- `src/mcp/explain-violation.js`

## Tool Schemas

Each tool should define:

- `name`
- `description`
- JSON schema input
- JSON schema output, if supported by host

Descriptions should be explicit that tools are read-only.

## Test Mapping

Primary tests:

- `test/contract/mcp.contract.test.mjs`
- guardrail check for forbidden tool names
