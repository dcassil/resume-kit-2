# Signing Implementation Spec

## Purpose

`src/signing/` owns human authorization, key material, signatures, and password-protected private key storage.

Verification must require only public material. Mutation must require private signing authority unlocked by a human password.

## Expected Files

```text
src/signing/keys.js
src/signing/signatures.js
src/signing/private-key-store.js
src/signing/authorization.js
```

## Required Exports

From `keys.js`:

- `createSigningKey()`
- `exportPublicKey(keyPair)`
- `fingerprintPublicKey(publicKeyPayload)`

From `signatures.js`:

- `signPayload({ payload, privateKey, keyId, now })`
- `verifyPayloadSignature({ payload, signature, publicKey })`

From `private-key-store.js`:

- `encryptPrivateKey({ privateKey, password, publicKeyFingerprint })`
- `decryptPrivateKey({ encrypted, password })`
- `readEncryptedPrivateKey(repoRoot)`
- `writeEncryptedPrivateKey(repoRoot, encrypted)`

From `authorization.js`:

- `assertAuthorizedSigner({ repoRoot, password })`

## Algorithms

MVP choices:

- Ed25519 signatures
- SHA-256 fingerprints
- scrypt password derivation
- AES-256-GCM encrypted private key payload

Use Node built-in `node:crypto` before adding dependencies.

## Storage Rules

Repo-readable:

```text
.straight-jacket/public-key.json
```

Ignored local private material:

```text
.straight-jacket/local/private-key.json
```

Never store plaintext passwords or unencrypted private keys.

## Error Codes

Throw coded errors for:

- `INVALID_PASSWORD`
- `SIGNING_KEY_MISSING`
- `SIGNING_KEY_MISMATCH`
- `SIGNING_FAILED`

## Test Targets

Primary:

```text
test/unit/signing.test.mjs
test/contract/core-api.contract.test.mjs
```
