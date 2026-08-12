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
- repository rule that pins trusted public-key fingerprint
- protected branch configuration

Straight Jacket must never claim local hooks are impossible to bypass.

## Pre-Commit Hook

Template path:

```text
templates/hooks/pre-commit
```

Installed target:

```text
.git/hooks/pre-commit
```

Hook content:

```sh
#!/bin/sh
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
2. Locate `.git/hooks/pre-commit`.
3. If no hook exists, write Straight Jacket hook.
4. If a hook exists and already contains Straight Jacket block, no-op.
5. If a hook exists without Straight Jacket block, append a clearly marked block.
6. Mark hook executable.
7. Return hook path and status.

Output:

```js
{
  "ok": true,
  "hook": {
    "installed": true,
    "path": "/repo/.git/hooks/pre-commit"
  }
}
```

## Hook Marker

Use stable markers for idempotent install:

```sh
# straight-jacket:start
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
      - run: straight-jacket verify --json
```

Strong mode should include a pinned fingerprint supplied by repository settings or CI variables:

```sh
straight-jacket verify --trusted-public-key-fingerprint "$STRAIGHT_JACKET_PUBLIC_KEY_FINGERPRINT"
```

The fingerprint variable must be controlled by humans or repository administrators.

## Server-Side Hook Template

Future template:

```text
templates/ci/pre-receive
```

Behavior:

- verify incoming tree state
- reject invalid manifests, tampered protected files, and public-key replacement
- read trusted public-key fingerprint from server-controlled config

## Test Mapping

Primary tests:

- CLI `install-hook`
- CLI `status`
- staged tamper-vector tests

Future tests:

- existing hook append/idempotency
- executable bit
- hook invokes `straight-jacket verify` and `straight-jacket verify --staged`
- CI template includes external fingerprint guidance
