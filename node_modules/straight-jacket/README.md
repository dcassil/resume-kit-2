# Straight Jacket

A tiny MCP, CLI, and plugin for **human-protected repo files**. Straight Jacket
marks files whose changes require human authorization and gives coding agents a
read-only way to verify protected state — without any path to bypass, secret
capture, or private-key export.

See [`PRODUCT_VISION.md`](./PRODUCT_VISION.md) for the full rationale.

## Install as a Claude Code plugin

The plugin ships:

- a read-only MCP server (`bin/straight-jacket-mcp.mjs`) exposing
  `list_protected_files`, `verify`, and `explain_violation`;
- the `straight-jacket` skill (protected-file editing policy + forbidden bypass actions);
- the `straight-jacket` CLI.

Plugin manifest: [`.claude-plugin/plugin.json`](./.claude-plugin/plugin.json).
Marketplace manifest: [`.claude-plugin/marketplace.json`](./.claude-plugin/marketplace.json).
Add this repo as a marketplace or a local plugin, e.g.:

```sh
/plugin marketplace add dcassil/straight-jacket
/plugin install straight-jacket@straight-jacket
```

Or reference it directly as a local plugin during development.

## Use with Codex

Codex reads MCP servers from `~/.codex/config.toml`. Merge the snippet in
[`codex/config.toml`](./codex/config.toml) after installing the CLI.

## Use with any MCP client

[`.mcp.json`](./.mcp.json) declares the server for generic MCP hosts:

```sh
straight-jacket-mcp
```

## CLI

```sh
straight-jacket --help
straight-jacket init --help
straight-jacket init
node bin/straight-jacket.mjs list --json
node bin/straight-jacket.mjs verify --json
```

## Development

```sh
npm test        # unit + contract + security + guardrails
npm run guardrails
```
