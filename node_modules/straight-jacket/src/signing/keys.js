import { createHash, generateKeyPair, createPublicKey } from "node:crypto";
import { promisify } from "node:util";
import { canonicalizeJson } from "../manifest/canonical-json.js";

const generateKeyPairAsync = promisify(generateKeyPair);

export async function createSigningKey() {
  return generateKeyPairAsync("ed25519");
}

export async function exportPublicKey(keyPair) {
  const publicKeyDer = keyPair.publicKey.export({ format: "der", type: "spki" });
  const publicKey = {
    version: 1,
    algorithm: "ed25519",
    publicKey: publicKeyDer.toString("base64url")
  };
  const fingerprint = fingerprintPublicKey(publicKey);

  return {
    ...publicKey,
    keyId: fingerprint,
    fingerprint
  };
}

export function fingerprintPublicKey(publicKeyPayload) {
  const canonicalPublicKey = canonicalizeJson({
    algorithm: publicKeyPayload.algorithm,
    publicKey: publicKeyPayload.publicKey,
    version: publicKeyPayload.version ?? 1
  });

  return `sha256:${createHash("sha256").update(canonicalPublicKey).digest("hex")}`;
}

export function importPublicKey(publicKeyPayload) {
  return createPublicKey({
    key: Buffer.from(publicKeyPayload.publicKey, "base64url"),
    format: "der",
    type: "spki"
  });
}
