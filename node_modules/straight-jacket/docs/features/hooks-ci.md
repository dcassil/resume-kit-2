# Hooks And CI Spec

## Purpose

Hooks and CI run verification at the points where protected files could otherwise be committed or merged.

Implementation folders:

```text
src/hooks/
templates/hooks/
templates/ci/
```

## Security Posture

Local pre-commit hooks are useful but advisory.

Strong enforcement requires at least one verifier outside the AI-editable working tree:

- required CI check
- server-side Git hook
- CI proof verification with a human-controlled `STRAIGHT_JACKET_CI_KEY` secret
- protected branch configuration

Straight Jacket must never claim local hooks are impossible to bypass.

For GitHub repositories, the recommended merge gate is documented in
[GitHub Protection Setup](./github-protection.md): require PRs on `main`, require
the `verify` check, require up-to-date branches, enforce admins, and disable force
pushes/deletions.

## Pre-Commit Hook

Template path:

```text
templates/hooks/pre-commit
```

Installed target:

```text
.githooks/pre-commit
```

Local Git config:

```text
core.hooksPath=.githooks
```

Hook content:

```sh
#!/bin/sh
if [ -f ".straight-jacket/manifest.json" ]; then
  if ! straight-jacket setup --check >/dev/null 2>&1; then
    echo "Straight Jacket local setup is missing or incomplete."
    echo "Run: straight-jacket setup"
    exit 1
  fi
fi
straight-jacket verify && straight-jacket verify --staged
```

Implementation may use an absolute path to the current CLI binary if needed for local development, but package output should prefer the executable on `PATH`.

## `installHook`

Core/helper function:

```js
installHook({ repoRoot })
```

Behavior:

1. Verify `repoRoot` is a Git repo root.
2. Locate `.githooks/pre-commit`.
3. If no hook exists, write Straight Jacket hook.
4. If a hook exists and already contains Straight Jacket block, no-op.
5. If a hook exists without Straight Jacket block, append a clearly marked block.
6. Mark hook executable.
7. Configure `git config core.hooksPath .githooks`.
8. Return hook path and status.

Output:

```js
{
  "ok": true,
  "hook": {
    "installed": true,
    "path": "/repo/.githooks/pre-commit",
    "hooksPath": ".githooks",
    "configuredHooksPath": ".githooks"
  }
}
```

## Hook Marker

Use stable markers for idempotent install:

```sh
# straight-jacket:start
straight-jacket setup --check
straight-jacket verify && straight-jacket verify --staged
# straight-jacket:end
```

## CI Template

Template path:

```text
templates/ci/github-action.yml
```

Suggested workflow:

```yaml
name: Straight Jacket

on:
  pull_request:
  push:
    branches: [main]

jobs:
  verify:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 20
      - run: npm install -g straight-jacket
      - run: straight-jacket verify
```

Strong mode should include the CI key generated from the master password during `straight-jacket setup`.

```sh
straight-jacket verify --ci-key "$STRAIGHT_JACKET_CI_KEY"
```

The CI key is not the master password and cannot unlock signing keys. It must still be controlled by humans or repository administrators, never by an AI agent.

For GitHub Actions, store it as a repository secret named `STRAIGHT_JACKET_CI_KEY`.

## Server-Side Hook Template

Future template:

```text
templates/ci/pre-receive
```

Behavior:

- verify incoming tree state
- reject invalid manifests, tampered signer registries, tampered protected files, and registration public-key replacement
- read trusted CI key from server-controlled config

## Test Mapping

Primary tests:

- CLI `install-hook`
- CLI `status`
- staged tamper-vector tests

Future tests:

- existing hook append/idempotency
- executable bit
- hook invokes `straight-jacket setup --check`, `straight-jacket verify`, and `straight-jacket verify --staged`
- CI template includes CI key secret guidance
