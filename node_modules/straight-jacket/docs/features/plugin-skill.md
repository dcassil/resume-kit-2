# Plugin And Skill Spec

## Purpose

The plugin and skill help AI agents cooperate with Straight Jacket boundaries.

Folders:

```text
src/plugin/
src/plugin/skills/
src/plugin/mcp/
templates/plugin/
```

## Agent Behavior

The skill should instruct AI agents to:

- list protected files before broad edits
- avoid editing protected paths
- run `straight-jacket verify` before final response when Straight Jacket metadata exists
- distinguish advisory local hooks from remote merge enforcement
- verify GitHub branch protection before claiming protected-file changes cannot merge
- explain violations without trying to bypass them
- ask the human to run update/remove/rename commands when protected state must change
- never request, infer, store, or pass a human password

## Skill Triggers

Suggested triggers:

- user mentions Straight Jacket
- repo contains `.straight-jacket/manifest.json`
- task involves editing files in a repo with Straight Jacket installed
- pre-commit verification fails with Straight Jacket violation codes

## Skill Instructions

Template path:

```text
templates/plugin/SKILL.md
```

Expected sections:

- Purpose
- When to use
- Required first checks
- Protected-file editing policy
- Verification policy
- GitHub protection setup policy
- Human update flow
- Forbidden actions

## Required First Checks

When active in a repo:

```text
straight-jacket list --json
straight-jacket verify --json
```

If either command is missing because the tool is not installed, the agent should inspect `.straight-jacket/manifest.json` directly and warn that verification could not be run.

## Forbidden Agent Actions

The skill should forbid:

- editing `.straight-jacket/manifest.json`
- editing `.straight-jacket/manifest.sig`
- editing `.straight-jacket/signers.json`
- editing `.straight-jacket/signers.sig`
- editing `.straight-jacket/registration-public-key.json`
- editing `.straight-jacket/registration-key.enc.json`
- deleting hooks to bypass checks
- committing with `--no-verify` to bypass checks
- asking the user to share a password in chat
- using MCP mutation tools if any exist without host-mediated human confirmation

## Plugin Packaging

Future package should include:

- CLI binary
- MCP server or MCP helper definition
- skill instructions
- hook and CI templates

Keep plugin install lightweight. It should not require a daemon.

## MCP Relationship

The plugin may expose MCP tools, but they must match [MCP Spec](./mcp.md):

- read-only list
- read-only verify
- explain violation

Request-style mutation tools are future work only.

## Test Mapping

Current tests:

- MCP read-only tool tests
- forbidden MCP mutation tests

Future tests:

- skill template includes forbidden action list
- skill template includes verification-before-final-response policy
- plugin metadata references read-only MCP tools only
