import { createCodedError } from "../core/errors.js";
import { readPublicKey } from "../manifest/read-write.js";
import { fingerprintPublicKey } from "./keys.js";
import { decryptPrivateKey, readEncryptedPrivateKey } from "./private-key-store.js";

export async function assertAuthorizedSigner({ repoRoot, password }) {
  const encrypted = await readEncryptedPrivateKey(repoRoot).catch((error) => {
    if (error.code === "ENOENT") {
      throw createCodedError("SIGNING_KEY_MISSING", "Encrypted signing key is missing");
    }
    throw error;
  });
  const privateKey = await decryptPrivateKey({ encrypted, password });
  const publicKey = await readPublicKey(repoRoot);
  const publicKeyFingerprint = fingerprintPublicKey(publicKey);

  if (encrypted.publicKeyFingerprint !== publicKeyFingerprint) {
    throw createCodedError("SIGNING_KEY_MISMATCH", "Signing key does not match public verifier");
  }

  return {
    privateKey,
    publicKey,
    keyId: publicKey.keyId
  };
}
