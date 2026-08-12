# Straight Jacket

## Purpose

Use this skill when a repository contains Straight Jacket metadata or when the user mentions protected files. Straight Jacket marks files whose changes require human authorization.

## When To Use

- A repository contains `.straight-jacket/manifest.json`.
- A task may edit broad areas of a repository.
- A Straight Jacket verification command reports violations.

## Required First Checks

Run these before broad edits:

```sh
straight-jacket list --json
straight-jacket verify --json
```

If the CLI, MCP tools, or Straight Jacket repo metadata is unavailable, stop and give the user the relevant setup note from "Setup And Missing Configuration Guidance" before continuing.

## Setup And Missing Configuration Guidance

Use these notes whenever setup is missing or incomplete. Do not claim protected state was verified when any prerequisite is missing.

### CLI Missing

Detect this with `command -v straight-jacket`. If the command is unavailable, tell the user:

```text
Straight Jacket's CLI is not installed on PATH yet. To install it, open a terminal and run:

npm install -g github:dcassil/straight-jacket

Then confirm it works with:

straight-jacket status --json
```

If a local checkout is available, you may use `node /absolute/path/to/straight-jacket/bin/straight-jacket.mjs ...` only as a temporary fallback and must say that verification used the checkout-local CLI.

### Project Not Initialized

If `.straight-jacket/manifest.json` is missing, tell the user:

```text
Before using Straight Jacket, you need to initialize it in this project. Open a terminal in the project root and run:

straight-jacket init

After that, register files that should require human authorization:

straight-jacket add <path> --reason "Human-owned file"
```

Do not run mutating setup commands yourself unless the user explicitly asks you to and the command can prompt the human directly in their terminal.

### Metadata Or Config Incomplete

If `.straight-jacket/manifest.json`, `.straight-jacket/manifest.sig`, or `.straight-jacket/public-key.json` is missing while another one exists, tell the user:

```text
Straight Jacket metadata is incomplete. Restore the missing `.straight-jacket` files from version control, or if this project has no protected files yet, re-initialize it with:

straight-jacket init
```

Do not edit Straight Jacket metadata files by hand.

### MCP Not Connected

If the MCP tools are unavailable but the CLI exists, continue with the CLI and tell the user:

```text
The Straight Jacket MCP server is not connected in this host yet. CLI verification can still run locally. To connect MCP in Codex, add this to `~/.codex/config.toml`:

[mcp_servers.straight-jacket]
command = "straight-jacket-mcp"
args = []
```

## GitHub Protection Guidance

Local hooks are advisory. `git commit --no-verify` can bypass local hook checks, and ordinary feature branches may still accept bad commits. Strong GitHub enforcement requires remote branch protection or rulesets.

When the user asks to set up GitHub protection, use the GitHub UI/API or `gh` CLI to configure and verify:

- `main` requires a pull request before merging.
- `main` requires the `verify` status check.
- required status checks are strict/up-to-date before merge.
- admins are included in enforcement.
- force pushes and deletions are disabled.
- `develop` exists if the repository uses a develop integration branch.
- `STRAIGHT_JACKET_PUBLIC_KEY_FINGERPRINT` is set as a repository variable for the verifier workflow.

If using `gh`, the setup guide is:

```text
docs/features/github-protection.md
```

After changing GitHub settings, read back branch protection before claiming success:

```sh
gh api "repos/OWNER/REPO/branches/main/protection"
```

Do not claim protected-file changes are merge-blocked unless the remote readback confirms required PRs and required `verify` on `main`.

## Protected-File Editing Policy

Avoid editing protected paths. If a protected file must change, make the content change only when the user explicitly asks for it, then ask the human to run the appropriate command locally:

```sh
straight-jacket update <path>
straight-jacket remove <path>
straight-jacket rename <old-path> <new-path>
```

## Verification Policy

Run `straight-jacket verify --json` before final response when Straight Jacket metadata exists and the CLI is available. Treat violations as blocking until the human authorizes or resolves them.

## Human Update Flow

Explain what changed and which human command is needed. Do not request secrets or signing authority in chat.

## Forbidden Actions

- edit .straight-jacket/manifest.json
- edit .straight-jacket/manifest.sig
- edit .straight-jacket/public-key.json
- ask user for password in chat
- commit with --no-verify to bypass checks
- delete hooks to bypass checks
- call or invent MCP mutation tools without host-mediated human confirmation

## Plugin Packaging Notes

Package the CLI, read-only MCP helpers, this skill, and hook/CI templates. The plugin must not include a daemon, secret forwarding, password capture, or private-key export path.
