# Straight Jacket API Contract

This document defines the executable contract covered by the test suite.

The implementation should expose three surfaces:

- core library: `src/index.js`
- CLI: `src/cli.js`
- MCP server helpers: `src/mcp.js`

## Core Library

### `initRepository(input)`

Creates Straight Jacket metadata for a Git repository.

Input:

```js
{
  repoRoot: "/absolute/path/to/repo",
  password: "human supplied password",
  now: "2026-08-12T00:00:00.000Z"
}
```

Expected output:

```js
{
  ok: true,
  manifestPath: "/repo/.straight-jacket/manifest.json",
  signaturePath: "/repo/.straight-jacket/manifest.sig",
  publicKeyPath: "/repo/.straight-jacket/public-key.json",
  fingerprint: "sha256:..."
}
```

Rules:

- creates `.straight-jacket/manifest.json`
- creates `.straight-jacket/manifest.sig`
- creates `.straight-jacket/public-key.json`
- creates local private signing material outside tracked files, or under `.straight-jacket/local/`
- never stores the password in repo files
- manifest starts with an empty `entries` array

### `addProtectedFile(input)`

Registers a file path plus checksum.

Input:

```js
{
  repoRoot: "/absolute/path/to/repo",
  path: "docs/policy.md",
  password: "human supplied password",
  reason: "Human-owned policy file",
  now: "2026-08-12T00:00:00.000Z"
}
```

Expected output:

```js
{
  ok: true,
  entry: {
    path: "docs/policy.md",
    name: "policy.md",
    checksum: "sha256:...",
    size: 1234,
    registeredAt: "2026-08-12T00:00:00.000Z",
    reason: "Human-owned policy file"
  }
}
```

Rules:

- rejects absolute paths
- rejects parent-directory escapes
- rejects symlink targets by default
- rejects duplicate paths
- rejects paths that collide only by case
- re-signs the manifest after mutation

### `removeProtectedFile(input)`

Removes a registered entry.

Input:

```js
{
  repoRoot: "/absolute/path/to/repo",
  path: "docs/policy.md",
  password: "human supplied password"
}
```

Expected output:

```js
{
  ok: true,
  removedPath: "docs/policy.md"
}
```

Rules:

- requires human authorization
- fails if the manifest signature is invalid before mutation
- re-signs the manifest after mutation

### `updateProtectedFile(input)`

Accepts the current content of an already registered file as the new protected checksum.

Input:

```js
{
  repoRoot: "/absolute/path/to/repo",
  path: "docs/policy.md",
  password: "human supplied password",
  now: "2026-08-12T00:00:00.000Z"
}
```

Expected output:

```js
{
  ok: true,
  entry: {
    path: "docs/policy.md",
    checksum: "sha256:..."
  }
}
```

Rules:

- requires human authorization
- preserves path identity
- re-signs the manifest after mutation

### `renameProtectedFile(input)`

Authorizes a path change for a protected file.

Input:

```js
{
  repoRoot: "/absolute/path/to/repo",
  from: "docs/policy.md",
  to: "docs/policy-renamed.md",
  password: "human supplied password",
  now: "2026-08-12T00:00:00.000Z"
}
```

Expected output:

```js
{
  ok: true,
  from: "docs/policy.md",
  to: "docs/policy-renamed.md"
}
```

Rules:

- requires human authorization
- rejects implicit moves discovered during verification
- re-signs the manifest after mutation

### `verifyRepository(input)`

Verifies manifest authenticity and protected file integrity.

Input:

```js
{
  repoRoot: "/absolute/path/to/repo",
  scope: "working-tree"
}
```

Expected success:

```js
{
  ok: true,
  checked: 1,
  violations: []
}
```

Expected failure:

```js
{
  ok: false,
  checked: 1,
  violations: [
    {
      code: "CHECKSUM_MISMATCH",
      path: "docs/policy.md",
      message: "docs/policy.md checksum changed",
      expected: "sha256:...",
      actual: "sha256:..."
    }
  ]
}
```

Rules:

- read-only
- never asks for a password
- fails closed for missing, unsigned, ambiguous, or tampered state
- supports `scope: "working-tree"` and `scope: "staged"`
- may accept `trustedPublicKeyFingerprint` for externally pinned strong-mode verification
- may accept `skipSignatureForDiagnostics` only from core-level tests/internal diagnostics; CLI, MCP, hooks, and plugin surfaces must never expose it

### `listProtectedFiles(input)`

Returns protected entries without requiring private signing material.

Input:

```js
{
  repoRoot: "/absolute/path/to/repo"
}
```

Expected output:

```js
{
  ok: true,
  entries: [
    {
      path: "docs/policy.md",
      name: "policy.md",
      checksum: "sha256:...",
      size: 1234,
      reason: "Human-owned policy file"
    }
  ]
}
```

Rules:

- read-only
- verifies manifest signature before returning entries
- never includes passwords or private key material

### `getRepositoryStatus(input)`

Returns repository, manifest, hook, and enforcement posture.

Input:

```js
{
  repoRoot: "/absolute/path/to/repo"
}
```

Expected output:

```js
{
  ok: true,
  hook: {
    installed: false,
    path: "/repo/.git/hooks/pre-commit"
  },
  enforcement: {
    localHookAdvisory: true,
    requiresExternalVerifierForStrongMode: true
  }
}
```

Rules:

- read-only
- never claims local hooks are the strong security boundary

### `installHook(input)`

Installs or updates the local pre-commit hook.

Input:

```js
{
  repoRoot: "/absolute/path/to/repo"
}
```

Expected output:

```js
{
  ok: true,
  hook: {
    installed: true,
    path: "/repo/.git/hooks/pre-commit"
  }
}
```

Rules:

- does not require a password
- installs a hook that runs `straight-jacket verify --staged`
- remains advisory unless paired with CI or server-side enforcement

### `installCi(input)`

Installs or prints a CI verifier template.

Input:

```js
{
  repoRoot: "/absolute/path/to/repo",
  provider: "github-actions"
}
```

Expected output:

```js
{
  ok: true,
  provider: "github-actions",
  path: ".github/workflows/straight-jacket.yml"
}
```

Rules:

- does not require a password
- must document external public-key fingerprint pinning for strong mode
- must not silently configure repository branch protection

## CLI

The CLI should map to the core contract.

Read-only commands:

```text
straight-jacket list --json
straight-jacket status --json
straight-jacket verify --json
straight-jacket verify --staged --json
```

Mutating commands:

```text
straight-jacket init
straight-jacket add <path> --reason "..."
straight-jacket remove <path>
straight-jacket update <path>
straight-jacket rename <old-path> <new-path>
straight-jacket install-hook
straight-jacket install-ci
```

Rules:

- read-only commands exit `0` on success
- verification exits non-zero on violations
- manifest-mutating commands require interactive human authorization
- `install-hook` and `install-ci` do not mutate the signed manifest and do not require a password
- mutating commands must not accept passwords from repo files
- JSON mode emits machine-readable output with stable `ok`, `violations`, and `entries` fields

## MCP

MCP should be read-only by default.

Required tools:

- `straight_jacket_list_protected_files`
- `straight_jacket_verify`
- `straight_jacket_explain_violation`

Forbidden by default:

- silent `add`
- silent `remove`
- silent `update`
- silent `rename`
- password capture
- private key export

Optional human-gated tools may exist only as request flows:

- `straight_jacket_request_update`
- `straight_jacket_request_unlock`

They must return instructions for human authorization, not perform silent mutation.
