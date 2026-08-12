# Core Library Spec

## Purpose

The core library is the authoritative domain API. It owns product behavior and coordinates manifest, signing, Git, and filesystem modules.

Public entrypoint:

```text
src/index.js
```

Internal implementation folder:

```text
src/core/
```

## Public API

Export these async functions from `src/index.js`:

- `initRepository(input)`
- `addProtectedFile(input)`
- `addProtectedFiles(input)`
- `removeProtectedFile(input)`
- `removeProtectedFiles(input)`
- `updateProtectedFile(input)`
- `renameProtectedFile(input)`
- `verifyRepository(input)`
- `listProtectedFiles(input)`
- `getRepositoryStatus(input)`
- `installHook(input)`
- `installCi(input)`

The first six are required by core contract tests. The remaining support CLI, MCP, hook, and CI surfaces.

## Inputs

Every public function takes a single object argument.

Shared fields:

- `repoRoot`: absolute path to a Git repository root
- `now`: ISO timestamp override for deterministic tests
- `scope`: `"working-tree"` or `"staged"` for verification
- `trustedPublicKeyFingerprint`: optional external trust pin for strong-mode verification

Mutating fields:

- `password`: human-entered password
- `path`: repo-relative protected path
- `paths`: repo-relative protected paths and/or glob patterns
- `from`: repo-relative old path for rename
- `to`: repo-relative new path for rename
- `reason`: optional human-readable explanation

## Outputs

Successful operations return plain JSON-serializable objects with `ok: true`.

Verification returns:

```js
{
  ok: true,
  checked: 1,
  violations: []
}
```

or:

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

Mutating failures should throw typed errors whose messages include a stable code, such as `INVALID_PASSWORD` or `DUPLICATE_PROTECTED_PATH`.

Verification failures should return violations instead of throwing when possible. Throw only for programmer errors, such as missing `repoRoot`.

## Responsibilities

Core library should:

- validate top-level inputs
- resolve and verify the Git repo root
- call manifest validation before any mutation
- call signing authorization for mutations
- compute protected file metadata through manifest/path helpers
- return stable violation objects
- avoid direct prompt or terminal interaction
- avoid environment-variable password sources

Core library should not:

- parse CLI flags
- print to stdout/stderr
- expose MCP protocol details
- store plaintext passwords
- decide whether CI branch protection is enabled

## Function Details

### `initRepository`

Flow:

1. Validate `repoRoot` is absolute and is a Git repo root.
2. Create `.straight-jacket/`.
3. Create `.straight-jacket/local/` for encrypted local private signing material.
4. Create or unlock signing key with password.
5. Build empty manifest with version, repo identity, hash algorithm, policy, and empty entries.
6. Canonicalize and sign manifest.
7. Write manifest, signature, and public key.
8. Return paths and fingerprint.

Idempotency:

- Running init twice should fail if an initialized repo already exists unless `force` is added in a future contract.
- Do not overwrite an existing signing key silently.

### `addProtectedFile`

Flow:

1. Load and verify manifest signature.
2. Validate repo-relative path.
3. Reject symlink target.
4. Reject duplicate path and case collision.
5. Read file content and metadata.
6. Create entry with path, name, checksum, size, timestamp, and reason.
7. Append entry in deterministic order.
8. Re-sign manifest.
9. Return the new entry.

Sorting:

- Store entries sorted by normalized lowercase path, then exact path.
- Deterministic sorting prevents avoidable signature churn.

### `removeProtectedFile`

Flow:

1. Load and verify manifest signature.
2. Require password authorization.
3. Remove exact path entry.
4. Fail if path is not registered.
5. Re-sign manifest.

### `addProtectedFiles`

Flow:

1. Expand exact paths and glob patterns against the repository working tree.
2. Load and verify manifest signature.
3. Validate the combined set for duplicates and case collisions.
4. Require password authorization once.
5. Create entries for every expanded path.
6. Append entries in deterministic order.
7. Re-sign manifest once.

### `removeProtectedFiles`

Flow:

1. Load and verify manifest signature.
2. Expand exact paths and glob patterns against registered manifest paths.
3. Fail if an exact path is not registered or a pattern matches no entries.
4. Require password authorization once.
5. Remove every matched entry.
6. Re-sign manifest once.

### `updateProtectedFile`

Flow:

1. Load and verify manifest signature.
2. Require password authorization.
3. Find exact registered path.
4. Validate path still points to a regular file.
5. Replace checksum, size, timestamp.
6. Preserve path identity and reason unless a future flag changes it.
7. Re-sign manifest.

### `renameProtectedFile`

Flow:

1. Load and verify manifest signature.
2. Require password authorization.
3. Validate old path exists in manifest.
4. Validate new path is repo-relative and regular.
5. Reject duplicate and case-collision target.
6. Update path, name, checksum, size, timestamp.
7. Re-sign manifest.

Renames are explicit only. `verifyRepository` should never auto-accept a moved file.

### `verifyRepository`

Flow:

1. Load manifest, signature, and public key.
2. If any are missing, return fail-closed violation.
3. If external fingerprint is provided, verify public key fingerprint first.
4. Validate manifest shape and policy.
5. Verify manifest signature unless diagnostic mode is explicitly requested.
6. Validate each entry path.
7. For working-tree scope, inspect filesystem state.
8. For staged scope, inspect Git index state.
9. Return every detected violation, not only the first one.

Diagnostic mode:

- `skipSignatureForDiagnostics` may exist for tests and internal debug only.
- It must never be reachable from CLI, MCP, hooks, or plugin surfaces.

### Support Functions

`listProtectedFiles`:

- load and verify the signed manifest
- return public entry metadata only
- omit passwords, encrypted private key payloads, and private key material
- return violations or throw a stable configuration error if the manifest cannot be trusted

`getRepositoryStatus`:

- report manifest presence and verification health
- report pre-commit hook status
- include `localHookAdvisory: true`
- include `requiresExternalVerifierForStrongMode: true`
- never require a password

`installHook`:

- install or update `.git/hooks/pre-commit`
- use stable Straight Jacket markers for idempotency
- run `straight-jacket verify --staged`
- never require a password

`installCi`:

- create `.github/workflows/straight-jacket.yml` for `provider: "github-actions"`
- include `straight-jacket verify`
- include guidance or command wiring for `STRAIGHT_JACKET_PUBLIC_KEY_FINGERPRINT`
- never require a password
- never claim it configured branch protection automatically

## Violation Codes

Core should centralize violation codes:

- `MANIFEST_MISSING`
- `MANIFEST_SIGNATURE_MISSING`
- `MANIFEST_SIGNATURE_INVALID`
- `PUBLIC_KEY_MISSING`
- `PUBLIC_KEY_FINGERPRINT_MISMATCH`
- `HASH_ALGORITHM_NOT_ALLOWED`
- `POLICY_DOWNGRADE_NOT_ALLOWED`
- `INVALID_PATH_ABSOLUTE`
- `INVALID_PATH_ESCAPE`
- `DUPLICATE_PROTECTED_PATH`
- `PATH_CASE_COLLISION`
- `SYMLINK_NOT_ALLOWED`
- `PROTECTED_FILE_MISSING`
- `CHECKSUM_MISMATCH`
- `LIKELY_RENAME_OR_MOVE`
- `STAGED_PROTECTED_FILE_DELETED`
- `STAGED_MANIFEST_SIGNATURE_INVALID`

## Test Mapping

Primary tests:

- `test/contract/core-api.contract.test.mjs`
- `test/security/tamper-vectors.contract.test.mjs`

The first green milestone should be `initRepository creates signed repo-readable verification metadata without storing the password`.
