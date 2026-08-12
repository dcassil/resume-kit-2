# MCP Implementation Spec

## Purpose

`src/mcp/` exposes read-only AI-facing tools. It must not expose signing authority, password capture, or silent manifest mutation.

## Expected Files

```text
src/mcp/tools.js
src/mcp/tool-schemas.js
src/mcp/explain-violation.js
src/mcp.js
```

## Required Exports

From `tools.js`:

- `createToolRegistry(core)`

From `tool-schemas.js`:

- `toolSchemas`

From `explain-violation.js`:

- `explainViolation(violation)`

From `src/mcp.js`:

- `listTools()`
- `callTool(name, args)`

## Default Tools

Only these tools are allowed by default:

- `straight_jacket_list_protected_files`
- `straight_jacket_verify`
- `straight_jacket_explain_violation`

Forbidden by default:

- `straight_jacket_add`
- `straight_jacket_remove`
- `straight_jacket_update`
- `straight_jacket_rename`
- `straight_jacket_capture_password`
- `straight_jacket_export_private_key`

## Schema Rules

Tool schemas must not include fields containing:

- `password`
- `privateKey`
- `private_key`

## Test Targets

Primary:

```text
test/unit/mcp.test.mjs
test/contract/mcp.contract.test.mjs
```
