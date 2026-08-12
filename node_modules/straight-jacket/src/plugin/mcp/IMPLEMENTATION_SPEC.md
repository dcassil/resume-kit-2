# Plugin MCP Implementation Spec

## Purpose

`src/plugin/mcp/` defines plugin-facing MCP metadata. It should describe only the read-only MCP tool set unless a future host-mediated human confirmation system exists.

## Expected Files

```text
src/plugin/mcp/manifest.js
```

## Required Exports

From `manifest.js`:

- `buildPluginMcpManifest()`

## Manifest Shape

`buildPluginMcpManifest()` should return:

```js
{
  tools: [
    { name: "straight_jacket_list_protected_files" },
    { name: "straight_jacket_verify" },
    { name: "straight_jacket_explain_violation" }
  ]
}
```

Descriptions and schemas may be added, but default tools must stay read-only.

## Forbidden Tool Names

Do not include:

- `straight_jacket_add`
- `straight_jacket_remove`
- `straight_jacket_update`
- `straight_jacket_rename`
- `straight_jacket_capture_password`
- `straight_jacket_export_private_key`

## Test Targets

Primary:

```text
test/unit/plugin.test.mjs
```
