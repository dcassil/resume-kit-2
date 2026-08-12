# Manifest Implementation Spec

## Purpose

`src/manifest/` owns manifest shape, canonical JSON, entry sorting, and validation. It should be deterministic and strict.

## Expected Files

```text
src/manifest/canonical-json.js
src/manifest/entries.js
src/manifest/validation.js
src/manifest/read-write.js
```

## Required Exports

From `canonical-json.js`:

- `canonicalizeJson(value)`

From `entries.js`:

- `sortEntries(entries)`
- `createProtectedEntry({ repoRoot, path, reason, now })`

From `validation.js`:

- `validateManifestShape(manifest)`
- `validateEntry(entry)`
- `validateEntrySet(entries)`

From `read-write.js`:

- `readManifest(repoRoot)`
- `writeManifest(repoRoot, manifest)`
- `readSignature(repoRoot)`
- `writeSignature(repoRoot, signature)`
- `readPublicKey(repoRoot)`
- `writePublicKey(repoRoot, publicKey)`

## Canonical JSON Rules

- Sort object keys lexicographically.
- Preserve array order.
- Reject `undefined`, functions, symbols, bigint, `NaN`, and infinities.
- Return compact JSON with no trailing newline.
- Throw `CANONICAL_JSON_UNSUPPORTED_VALUE` for unsupported values.

## Manifest Rules

- Write camelCase fields.
- Accept snake_case only as compatibility input if needed by early tests.
- Support only `version: 1`.
- Support only `hashAlgorithm: "sha256"`.
- Support only `signatureAlgorithm: "ed25519"`.
- Reject policy downgrades.
- Reject duplicate exact paths.
- Reject case-insensitive path collisions.

## Entry Rules

Each entry must include:

- `path`
- `name`
- `checksum`
- `size`
- `registeredAt`
- optional `reason`

`path` must be repo-relative and slash-separated.

## Test Targets

Primary:

```text
test/unit/manifest.test.mjs
test/security/tamper-vectors.contract.test.mjs
```
