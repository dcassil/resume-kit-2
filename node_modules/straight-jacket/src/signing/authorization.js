import { createCodedError } from "../core/errors.js";
import { createPublicKey } from "node:crypto";
import { exportPublicKey } from "./keys.js";
import { decryptPrivateKey, readEncryptedPrivateKey } from "./private-key-store.js";
import { findActiveSigner, loadVerifiedSignerRegistry, publicKeyFromSigner } from "./signer-registry.js";

export async function assertAuthorizedSigner({ repoRoot, password }) {
  const encrypted = await readEncryptedPrivateKey(repoRoot).catch((error) => {
    if (error.code === "ENOENT") {
      throw createCodedError("SIGNING_KEY_MISSING", "Encrypted signing key is missing");
    }
    throw error;
  });
  const privateKey = await decryptPrivateKey({ encrypted, password });
  const publicKey = await exportPublicKey({ publicKey: createPublicKey(privateKey) });

  if (encrypted.publicKeyFingerprint !== publicKey.fingerprint) {
    throw createCodedError("SIGNING_KEY_MISMATCH", "Signing key does not match public verifier");
  }
  const { registry } = await loadVerifiedSignerRegistry(repoRoot);
  const signer = findActiveSigner(registry, publicKey.fingerprint);
  if (!signer) {
    throw createCodedError("SIGNER_NOT_REGISTERED", "Local signing key is not registered for this repository");
  }

  return {
    privateKey,
    publicKey: publicKeyFromSigner(signer),
    keyId: signer.keyId
  };
}

export async function checkLocalSigner({ repoRoot } = {}) {
  const encrypted = await readEncryptedPrivateKey(repoRoot).catch((error) => {
    if (error.code === "ENOENT") {
      throw createCodedError("LOCAL_SIGNER_MISSING", "Local Straight Jacket signer is not registered. Run straight-jacket setup.");
    }
    throw error;
  });
  const { registry } = await loadVerifiedSignerRegistry(repoRoot);
  const signer = findActiveSigner(registry, encrypted.publicKeyFingerprint);
  if (!signer) {
    throw createCodedError("LOCAL_SIGNER_NOT_REGISTERED", "Local Straight Jacket signer is not registered. Run straight-jacket setup.");
  }

  return {
    ok: true,
    signerKeyId: signer.keyId
  };
}
