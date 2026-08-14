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
  masterPassword: "human supplied registration password",
  localPassword: "human supplied local password",
  now: "2026-08-12T00:00:00.000Z"
}
```

Expected output:

```js
{
  ok: true,
  manifestPath: "/repo/.straight-jacket/manifest.json",
  signaturePath: "/repo/.straight-jacket/manifest.sig",
  signersPath: "/repo/.straight-jacket/signers.json",
  signersSignaturePath: "/repo/.straight-jacket/signers.sig",
  registrationPublicKeyPath: "/repo/.straight-jacket/registration-public-key.json",
  registrationKeyPath: "/repo/.straight-jacket/registration-key.enc.json",
  ciProofPath: "/repo/.straight-jacket/ci-proof.json",
  fingerprint: "sha256:...",
  localSignerKeyId: "sha256:...",
  ci: {
    secretName: "STRAIGHT_JACKET_CI_KEY",
    ciKey: "sjci_v1_...",
    warning: "Never give an AI agent your master password..."
  }
}
```

Rules:

- creates `.straight-jacket/manifest.json`
- creates `.straight-jacket/manifest.sig`
- creates `.straight-jacket/signers.json`
- creates `.straight-jacket/signers.sig`
- creates `.straight-jacket/registration-public-key.json`
- creates `.straight-jacket/registration-key.enc.json`
- creates `.straight-jacket/ci-proof.json`
- creates local private signing material under ignored `.straight-jacket/local/`
- never stores plaintext passwords in repo files
- never stores the CI key in repo files
- the master password unlocks only registration authority
- the CI key is derived from the master password but cannot unlock signing keys
- the local password unlocks protected-file mutation authority
- manifest starts with an empty `entries` array

### `setupRepository(input)`

Initializes a clean repository or registers this checkout's local signer in an already-initialized repository.

Input for an initialized repository:

```js
{
  repoRoot: "/absolute/path/to/repo",
  masterPassword: "human supplied registration password",
  localPassword: "new local password",
  now: "2026-08-12T00:00:00.000Z"
}
```

Expected registration output:

```js
{
  ok: true,
  registered: true,
  signerKeyId: "sha256:...",
  ci: {
    secretName: "STRAIGHT_JACKET_CI_KEY",
    ciKey: "sjci_v1_..."
  }
}
```

Rules:

- verifies protected files before prompting for registration authority at the CLI layer
- returns verification violations and does not write local signing material when locked files are dirty
- unlocks `.straight-jacket/registration-key.enc.json` with the master password
- writes only this checkout's encrypted local signer under `.straight-jacket/local/`
- appends the new signer to `.straight-jacket/signers.json` and re-signs it with the registration key
- updates `.straight-jacket/ci-proof.json` because signer registry changes are registration metadata changes
- upgrades legacy `.straight-jacket/public-key.json` repositories after verifying protected files
- `checkRepositorySetup` is read-only and reports whether the local encrypted signer matches an active signer

### `addProtectedFile(input)`

Registers a file path plus checksum.

Input:

```js
{
  repoRoot: "/absolute/path/to/repo",
  path: "docs/policy.md",
  password: "human supplied local password",
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

### `addProtectedFiles(input)`

Registers multiple file paths and/or glob-pattern matches with one authorization and one manifest signature update.

Input:

```js
{
  repoRoot: "/absolute/path/to/repo",
  paths: ["tools/pre-commit-alpha", "tools/pre-commit-beta"],
  password: "human supplied local password",
  reason: "Hook scripts",
  now: "2026-08-12T00:00:00.000Z"
}
```

Expected output:

```js
{
  ok: true,
  entries: [
    {
      path: "tools/pre-commit-alpha",
      checksum: "sha256:..."
    },
    {
      path: "tools/pre-commit-beta",
      checksum: "sha256:..."
    }
  ]
}
```

Rules:

- accepts shell-expanded path lists such as `tools/pre-commit-alpha tools/pre-commit-beta`
- expands quoted glob patterns repo-relative
- prompts/unlocks once at the CLI layer
- rejects unmatched patterns
- rejects duplicate or case-colliding paths as one set
- re-signs the manifest once after all entries are created

### `removeProtectedFile(input)`

Removes a registered entry.

Input:

```js
{
  repoRoot: "/absolute/path/to/repo",
  path: "docs/policy.md",
  password: "human supplied local password"
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

### `removeProtectedFiles(input)`

Removes multiple registered entries by exact path and/or glob pattern with one authorization and one manifest signature update.

Input:

```js
{
  repoRoot: "/absolute/path/to/repo",
  paths: ["tools/pre-commit-*"],
  password: "human supplied local password"
}
```

Expected output:

```js
{
  ok: true,
  removedPaths: [
    "tools/pre-commit-alpha",
    "tools/pre-commit-beta"
  ]
}
```

Rules:

- matches patterns against registered manifest paths, not the working tree
- accepts shell-expanded path lists and quoted glob patterns
- requires human authorization once
- ignores unregistered exact paths when at least one registered path matches, which allows shell-expanded broader globs to include unrelated files
- fails if no registered protected path matches
- fails if a pattern does not match any registered protected path
- re-signs the manifest once after all matching entries are removed

### `updateProtectedFile(input)`

Accepts the current content of an already registered file as the new protected checksum.

Input:

```js
{
  repoRoot: "/absolute/path/to/repo",
  path: "docs/policy.md",
  password: "human supplied local password",
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

### `updateProtectedFiles(input)`

Accepts the current content of multiple already registered files as the new protected checksums.

Input:

```js
{
  repoRoot: "/absolute/path/to/repo",
  paths: ["docs/policy.md", "prompts/system.md"],
  password: "human supplied local password",
  now: "2026-08-12T00:00:00.000Z"
}
```

Expected output:

```js
{
  ok: true,
  entries: [
    {
      path: "docs/policy.md",
      checksum: "sha256:..."
    },
    {
      path: "prompts/system.md",
      checksum: "sha256:..."
    }
  ]
}
```

Rules:

- requires human authorization once
- preserves path identity
- fails if any path is not registered
- re-signs the manifest once after all entries are updated

### `renameProtectedFile(input)`

Authorizes a path change for a protected file.

Input:

```js
{
  repoRoot: "/absolute/path/to/repo",
  from: "docs/policy.md",
  to: "docs/policy-renamed.md",
  password: "human supplied local password",
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
- may accept `ciKey` for CI proof verification against committed registration metadata
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
    path: "/repo/.githooks/pre-commit",
    hooksPath: ".githooks",
    configuredHooksPath: null
  },
  setup: {
    localSignerRegistered: true,
    signerKeyId: "sha256:..."
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

Installs or updates the committed pre-commit hook path.

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
    path: "/repo/.githooks/pre-commit",
    hooksPath: ".githooks",
    configuredHooksPath: ".githooks"
  }
}
```

Rules:

- does not require a password
- writes `.githooks/pre-commit` and configures `core.hooksPath` to `.githooks`
- installs a hook that runs `straight-jacket setup --check`, `straight-jacket verify`, and `straight-jacket verify --staged`
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
- must document `STRAIGHT_JACKET_CI_KEY` setup for strong mode
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
straight-jacket setup
straight-jacket add <path> --reason "..."
straight-jacket remove <path>
straight-jacket update <path>...
straight-jacket rename <old-path> <new-path>
straight-jacket install-hook
straight-jacket install-ci
```

Rules:

- read-only commands exit `0` on success
- verification exits non-zero on violations
- `init` prompts for master and local passwords
- `setup` prompts for the master password and a new local password when registering a clone
- manifest-mutating commands require the local password
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
