# Straight Jacket

A repo-native CLI, GitHub Action, and pre-commit hook for protecting files that
should only change with human approval.

## How it works

Straight Jacket starts by creating repository metadata in `.straight-jacket/`.
That metadata records which files are protected and which human-controlled keys
are allowed to approve changes.

During setup, you create two passwords:

- **Master password**: used to register trusted checkouts for this repository.
  It encrypts the repository registration key. Straight Jacket also derives a
  `STRAIGHT_JACKET_CI_KEY` from it; store that derived value as a GitHub Actions
  secret so CI can detect unauthorized metadata replacement.
- **Local password**: used on one checkout when you approve protected-file
  changes. It encrypts that checkout's local signer private key in
  `.straight-jacket/local/`.

When you run `straight-jacket add <file>`, Straight Jacket adds the file to a
signed JSON manifest with its path, size, timestamp, and SHA-256 checksum. Later,
`straight-jacket verify` hashes the current file contents and compares them to
the signed checksum. If the file changed without an approved
`straight-jacket update <file>`, verification fails.

The signatures protect the metadata itself. The manifest must be signed by a
registered local signer, and the signer registry must be signed by the
registration key. In CI, Straight Jacket checks the committed CI proof with:

```sh
straight-jacket verify --ci-key "$STRAIGHT_JACKET_CI_KEY"
```

That ties the current registration metadata back to the original master-derived
CI key.

See [`PRODUCT_VISION.md`](./PRODUCT_VISION.md) for the full rationale.

## Install via npm

```sh
npm i --save-dev straight-jacket
```

You can also install it globally:

```sh
npm i -g straight-jacket
```

## CLI quick guide

```sh
straight-jacket --help
straight-jacket setup --help

straight-jacket add <path | pattern>
straight-jacket add <path> <second path> ...
straight-jacket add <path> --reason "<optional description>"

straight-jacket update <path | pattern>
straight-jacket update <path> <second path> ...

straight-jacket remove <path | pattern>
```

## Setup

```sh
straight-jacket setup
```

This prompts for a master password and confirmation.

- If multiple contributors need to approve protected-file changes, choose a
  master password you are comfortable sharing with those trusted contributors.
- The master password lets Straight Jacket remain repo-based and team-friendly
  without depending on an external service.

Next, it prompts for a local password and confirmation. This is your personal
password for this checkout.

Do not paste either password into an AI chat, and do not store either password
anywhere an AI agent can read it.

`setup` also prints the `STRAIGHT_JACKET_CI_KEY` value needed by the GitHub
Action. Copy that value and save it for the branch protection setup below.

## Set up GitHub enforcement

The pre-commit hook is useful, but it is advisory: a user or agent can bypass it
with `git commit --no-verify`. For merge enforcement, install the GitHub Action
and require it through branch protection.

Run:

```sh
straight-jacket install-ci
```

Stage the generated metadata and workflow:

```sh
git add .straight-jacket
git add .github/workflows/straight-jacket.yml
```

Commit and push those changes to the branch you want to protect, or push them to
a temporary/development branch and open a PR to your protected branch.

```sh
git commit -m "Add Straight Jacket CI"
git push
```

This registers the workflow so GitHub can use it as a required status check.

On GitHub:

1. Go to repo settings -> Secrets and variables -> Actions.
2. Add the key printed by `straight-jacket setup` as `STRAIGHT_JACKET_CI_KEY`.
3. Go to repo settings -> Branches -> Add classic branch protection rule.
4. Set the branch name pattern you want to protect, such as `main`.
5. Enable "Require a pull request before merging".
6. Enable "Require status checks to pass before merging".
7. Search for and select the `verify` status check.
8. Save the rule.

For more detail, see
[`docs/features/github-protection.md`](./docs/features/github-protection.md).

## Install the pre-commit hook

The pre-commit hook helps humans and AI agents catch protected-file changes
before opening a PR.

```sh
straight-jacket install-hook
```

## Protect files

Add one file:

```sh
straight-jacket add <relative-path-to-file>
```

Add multiple files:

```sh
straight-jacket add <file1> <file2>
```

Add a pattern:

```sh
straight-jacket add 'guardrails/*.ts'
```

## Approve a protected-file change

If a protected file changes and the pre-commit hook is installed, the commit is
blocked with a checksum error and instructions to run:

```sh
straight-jacket update <file>
```

Run that only when you approve the new contents. It updates the signed manifest
to accept the current checksum.

If the GitHub Action is installed and required by branch protection, PRs to the
protected branch fail when a protected file changed without an approved
`straight-jacket update`.

## Remove a protected file

```sh
straight-jacket remove <file>
```

## Try it out

After setup is complete, and after installing the pre-commit hook and GitHub
Action if desired, create a test file:

```sh
touch test-straight-jacket.md
```

Protect it:

```sh
straight-jacket add test-straight-jacket.md --reason "Just a test file"
```

Now edit the file, add some text, and try to commit it:

```sh
git add test-straight-jacket.md
git commit -m "just a test"
```

The pre-commit hook should fail and tell you to run
`straight-jacket update test-straight-jacket.md` if you approve the change.

If you also set up the GitHub Action and branch protection, you can test remote
enforcement:

```sh
git commit -m "just a test" --no-verify
git push
```

That bypasses the local hook. Open a PR from this branch to your protected
branch. The merge should be blocked by the failed required status check, and the
check output will name the changed protected file.

## Teams and multiple workstations

After initial setup is pushed, additional developers can register their own
local signer by running `straight-jacket setup` in an up-to-date checkout.

- Make sure they have pulled a branch with Straight Jacket configured.
- If installed as a dev dependency, run `npm install`.
- If installed globally, run `npm install -g straight-jacket`.

Then run:

```sh
straight-jacket setup
```

In an already-initialized repository, this verifies the protected state, prompts
for the master password, then lets the developer create their own local
password. They should commit and push the signer registration so future
protected-file updates can verify their signer.

## Install the Claude Code plugin

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

Codex reads MCP servers from `~/.codex/config.toml`. After installing the CLI,
merge the snippet in [`codex/config.toml`](./codex/config.toml).

## Use with any MCP client

[`.mcp.json`](./.mcp.json) declares the server for generic MCP hosts:

```sh
straight-jacket-mcp
```

## Uninstall

To remove Straight Jacket from a repository:

- delete `.straight-jacket/`;
- remove Straight Jacket entries from `.githooks/pre-commit`;
- delete `.github/workflows/straight-jacket.yml`;
- remove the GitHub branch protection settings added during setup;
- remove the `STRAIGHT_JACKET_CI_KEY` GitHub secret.

## Development

```sh
npm test        # unit + contract + security + guardrails
npm run guardrails
```
