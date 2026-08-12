# Manifest Format Spec

## Purpose

The manifest is the repo-readable protected-file registry. It is editable as a file, but only trusted when its signature verifies.

Files:

```text
.straight-jacket/manifest.json
.straight-jacket/manifest.sig
.straight-jacket/public-key.json
```

Implementation folder:

```text
src/manifest/
```

## Manifest Shape

Canonical manifest payload:

```json
{
  "version": 1,
  "repoId": "sha256:...",
  "hashAlgorithm": "sha256",
  "signatureAlgorithm": "ed25519",
  "keyId": "sha256:...",
  "policy": {
    "allowSymlinks": false,
    "requireHumanAuthorization": true,
    "failClosed": true
  },
  "entries": [
    {
      "path": "docs/policy.md",
      "name": "policy.md",
      "checksum": "sha256:...",
      "size": 1234,
      "registeredAt": "2026-08-12T00:00:00.000Z",
      "reason": "Human-owned policy file"
    }
  ]
}
```

The API contract accepts either camelCase or snake_case for early compatibility in tests, but implementation should write camelCase.

## Signature Shape

Suggested `.straight-jacket/manifest.sig`:

```json
{
  "version": 1,
  "algorithm": "ed25519",
  "keyId": "sha256:...",
  "signedAt": "2026-08-12T00:00:00.000Z",
  "signature": "base64url..."
}
```

The signature signs the canonical JSON bytes of the manifest payload only.

## Public Key Shape

Suggested `.straight-jacket/public-key.json`:

```json
{
  "version": 1,
  "algorithm": "ed25519",
  "keyId": "sha256:...",
  "fingerprint": "sha256:...",
  "publicKey": "base64url..."
}
```

The public-key fingerprint is computed from canonical public key metadata, not from mutable manifest entries.

## Canonicalization

Signing must use deterministic JSON canonicalization.

MVP canonicalization rules:

- recursively sort object keys lexicographically
- preserve array order after manifest module sorts entries
- represent strings exactly as UTF-8
- reject `undefined`, functions, non-finite numbers, and comments
- write final manifest with two-space pretty JSON for humans
- sign compact canonical JSON bytes

Implementation targets:

- `src/manifest/canonical-json.js`
- `src/manifest/read-write.js`

## Entry Validation

Each entry must validate:

- `path` is a non-empty string
- `path` uses `/` separators
- `path` is not absolute
- `path` does not contain `..` segments
- `path` resolves under repo root
- `name` equals basename of `path`
- `checksum` matches `sha256:<64 lowercase hex>`
- `size` is a non-negative integer
- `registeredAt` is an ISO timestamp
- `reason`, if present, is a string

Entry set validation:

- no duplicate exact paths
- no paths equal after lowercase normalization
- entries sorted deterministically on write
- no unknown downgrade policy is allowed to weaken security

## Policy Validation

Allowed MVP policy:

```json
{
  "allowSymlinks": false,
  "requireHumanAuthorization": true,
  "failClosed": true
}
```

Violation behavior:

- `allowSymlinks: true` returns `POLICY_DOWNGRADE_NOT_ALLOWED`
- `requireHumanAuthorization: false` returns `POLICY_DOWNGRADE_NOT_ALLOWED`
- `failClosed: false` returns `POLICY_DOWNGRADE_NOT_ALLOWED`
- unknown policy keys should be rejected until there is a versioned policy extension mechanism

## Hash Algorithm

MVP supports only:

```text
sha256
```

Any other manifest algorithm returns `HASH_ALGORITHM_NOT_ALLOWED`.

## Repo Identity

`repoId` should bind the manifest to a repository.

MVP options:

- derive from `git rev-parse --show-toplevel` plus initial public-key fingerprint
- generate random bytes during `initRepository`

Recommendation:

- generate a random repo id during init
- include it in the signed manifest
- never use path-only identity because repo folders can move

## Read/Write API

Internal functions:

- `createEmptyManifest({ repoId, keyId, now })`
- `readManifest(repoRoot)`
- `writeManifest(repoRoot, manifest)`
- `readSignature(repoRoot)`
- `writeSignature(repoRoot, signature)`
- `readPublicKey(repoRoot)`
- `writePublicKey(repoRoot, publicKey)`
- `canonicalizeManifest(manifest)`
- `validateManifestShape(manifest)`
- `validateEntry(entry, repoRoot)`
- `sortEntries(entries)`
- `createViolation(code, fields)`

## Test Mapping

Primary tests:

- manifest creation in `core-api.contract.test.mjs`
- direct manifest tampering in `tamper-vectors.contract.test.mjs`
- duplicate/case/absolute/escape/downgrade tests in `tamper-vectors.contract.test.mjs`
