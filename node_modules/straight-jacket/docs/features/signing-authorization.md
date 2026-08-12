# Signing And Authorization Spec

## Purpose

Signing separates readable verification from human-controlled mutation authority.

Implementation folder:

```text
src/signing/
```

## Security Model

- AI may read the manifest, signature, and public key.
- AI may run verification.
- AI must not get private signing material or password-derived signing authority.
- Mutations require a human password that unlocks local private signing material.
- Verification requires only public material.

## Algorithms

MVP:

- checksum: SHA-256
- manifest signature: Ed25519
- public-key fingerprint: SHA-256 over canonical public key metadata
- private-key encryption: password-based key derivation plus authenticated encryption

Node implementation options:

- Use `node:crypto` Ed25519 key generation.
- Use `scrypt` or `pbkdf2` for password-based key derivation.
- Use AES-256-GCM for encrypted private key payload.

Keep dependencies out of MVP unless Node's built-in crypto is insufficient.

## Private Key Storage

Preferred MVP storage:

```text
.straight-jacket/local/private-key.json
```

This path is ignored by `.gitignore`.

Encrypted payload shape:

```json
{
  "version": 1,
  "algorithm": "ed25519",
  "kdf": {
    "name": "scrypt",
    "salt": "base64url...",
    "cost": 16384,
    "blockSize": 8,
    "parallelization": 1,
    "keyLength": 32
  },
  "cipher": {
    "name": "aes-256-gcm",
    "iv": "base64url...",
    "tag": "base64url..."
  },
  "encryptedPrivateKey": "base64url...",
  "publicKeyFingerprint": "sha256:..."
}
```

Future option:

- OS keychain as a preferred storage backend
- `.straight-jacket/local/` as fallback

## Public Key Storage

Stored in repo:

```text
.straight-jacket/public-key.json
```

Public key is not secret. It is still security-relevant because replacing it can make a forged manifest verify locally. Strong mode must pin its fingerprint outside AI-editable files.

## Authorization Flow

Mutating operations:

1. Load encrypted private key.
2. Derive unlock key from password.
3. Decrypt private key.
4. Confirm public key fingerprint matches repo public key.
5. Validate current manifest signature before mutation.
6. Apply mutation.
7. Canonicalize and sign new manifest.
8. Wipe password/private key buffers where practical.

Failures:

- wrong password throws `INVALID_PASSWORD`
- missing private key throws `SIGNING_KEY_MISSING`
- public/private mismatch throws `SIGNING_KEY_MISMATCH`
- invalid current signature throws `MANIFEST_SIGNATURE_INVALID`

## Verification Flow

Read-only operations:

1. Read manifest bytes.
2. Read signature payload.
3. Read public key payload.
4. Optionally compare public-key fingerprint to externally pinned fingerprint.
5. Canonicalize parsed manifest.
6. Verify Ed25519 signature.

Failures return verification violations:

- `PUBLIC_KEY_MISSING`
- `PUBLIC_KEY_FINGERPRINT_MISMATCH`
- `MANIFEST_SIGNATURE_MISSING`
- `MANIFEST_SIGNATURE_INVALID`

## Password Source Rules

Allowed:

- interactive CLI prompt
- direct `password` parameter in core API tests and trusted calling code

Forbidden by default:

- `--password`
- `--password-file`
- repo-local password files
- default environment variables such as `STRAIGHT_JACKET_PASSWORD`
- MCP tool arguments that capture or forward passwords

This is enforced by both contract tests and boundary guardrails.

## Internal API

Suggested functions:

- `createSigningKey({ repoRoot, password })`
- `loadEncryptedPrivateKey(repoRoot)`
- `unlockPrivateKey({ repoRoot, password })`
- `writeEncryptedPrivateKey({ repoRoot, password, keyPair })`
- `exportPublicKey(keyPair)`
- `fingerprintPublicKey(publicKeyPayload)`
- `signManifest({ manifest, privateKey, now })`
- `verifyManifestSignature({ manifest, signature, publicKey })`
- `assertAuthorizedSigner({ repoRoot, password })`

## Test Mapping

Primary tests:

- password not stored during init
- wrong password rejection for remove/update
- manifest tampering detection
- public verifier replacement detection
- MCP secret-exposure rejection
- CLI password-source rejection
