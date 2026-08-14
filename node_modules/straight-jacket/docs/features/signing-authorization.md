# Signing And Authorization Spec

## Purpose

Signing separates readable verification from human-controlled mutation authority.

Implementation folder:

```text
src/signing/
```

## Security Model

- AI may read the manifest, signatures, signer registry, and registration public key.
- AI may run verification.
- AI must not get private signing material or password-derived signing authority.
- Registering new local users requires the master password, which unlocks only the encrypted registration key.
- Protected-file mutations require a local password that unlocks local private signing material.
- Verification requires only public material.

## Algorithms

MVP:

- checksum: SHA-256
- manifest signature: Ed25519
- CI proof: HMAC-SHA-256 over registration metadata using a CI-only key derived from the master password
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

## Registration Key Storage

Stored in repo:

```text
.straight-jacket/registration-public-key.json
.straight-jacket/registration-key.enc.json
```

The registration public key is not secret. The encrypted registration key is committed so fresh clones can register local signers with the master password, but the master password cannot sign protected-file manifest changes. Strong mode verifies committed registration metadata with `STRAIGHT_JACKET_CI_KEY`, which is derived from the master password and stored as a GitHub Actions secret.

## Signer Registry Storage

Stored in repo:

```text
.straight-jacket/signers.json
.straight-jacket/signers.sig
```

The signer registry lists active local signer public keys. Its signature is verified with `.straight-jacket/registration-public-key.json`.

## Authorization Flow

Mutating operations:

1. Load encrypted private key.
2. Derive unlock key from password.
3. Decrypt private key.
4. Confirm local public key fingerprint matches an active signer in `.straight-jacket/signers.json`.
5. Validate current signer-registry and manifest signatures before mutation.
6. Apply mutation.
7. Canonicalize and sign new manifest with the local signer.
8. Wipe password/private key buffers where practical.

Failures:

- wrong password throws `INVALID_PASSWORD`
- missing private key throws `SIGNING_KEY_MISSING`
- public/private mismatch throws `SIGNING_KEY_MISMATCH`
- unregistered local signer throws `SIGNER_NOT_REGISTERED`
- invalid current signature throws `MANIFEST_SIGNATURE_INVALID`

## Registration Flow

Fresh clone setup:

1. Verify current protected files and shared metadata.
2. Refuse setup if locked files have checksum violations.
3. Unlock `.straight-jacket/registration-key.enc.json` with the master password.
4. Generate a new local signer keypair.
5. Encrypt the local signer under `.straight-jacket/local/private-key.json` with the local password.
6. Add the local signer public key to `.straight-jacket/signers.json`.
7. Re-sign `.straight-jacket/signers.json` with the registration key.

Legacy setup:

1. If only `.straight-jacket/public-key.json` exists, verify the legacy manifest signature and locked file checksums first.
2. Create registration and local signer keys from the supplied master/local passwords.
3. Re-sign the manifest with the new local signer and write the signer registry, registration key, and CI proof metadata.
4. Remove the legacy public-key metadata.

## Verification Flow

Read-only operations:

1. Read manifest bytes.
2. Read signature payload.
3. Read signer registry, signer-registry signature, and registration public key.
4. If a CI key is supplied, verify `.straight-jacket/ci-proof.json` against registration metadata.
5. Verify the signer registry signature with the registration public key.
6. Find the active signer named by the manifest signature.
7. Canonicalize parsed manifest.
8. Verify manifest signature with the registered signer public key.

Failures return verification violations:

- `REGISTRATION_PUBLIC_KEY_MISSING`
- `SIGNERS_MISSING`
- `SIGNERS_SIGNATURE_INVALID`
- `CI_PROOF_INVALID`
- `CI_PROOF_MISSING`
- `MANIFEST_SIGNATURE_MISSING`
- `MANIFEST_SIGNATURE_INVALID`

## Password Source Rules

Allowed:

- interactive CLI prompt
- direct `password`, `masterPassword`, or `localPassword` parameters in core API tests and trusted calling code

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
- `setupRepository({ repoRoot, masterPassword, localPassword })`
- `checkRepositorySetup({ repoRoot })`
- `loadEncryptedPrivateKey(repoRoot)`
- `unlockPrivateKey({ repoRoot, password })`
- `writeEncryptedPrivateKey({ repoRoot, password, keyPair })`
- `exportPublicKey(keyPair)`
- `fingerprintPublicKey(publicKeyPayload)`
- `signManifest({ manifest, privateKey, now })`
- `verifyManifestSignature({ manifest, signature, publicKey })`
- `assertAuthorizedSigner({ repoRoot, password })`
- `loadVerifiedSignerRegistry(repoRoot)`
- `signAndWriteSignerRegistry({ repoRoot, registry, privateKey, keyId })`

## Test Mapping

Primary tests:

- password not stored during init
- master password cannot mutate protected-file manifest entries
- fresh clone setup registers a local signer
- wrong password rejection for remove/update
- manifest tampering detection
- registration public verifier replacement detection
- MCP secret-exposure rejection
- CLI password-source rejection
