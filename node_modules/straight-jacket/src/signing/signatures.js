import { sign, verify } from "node:crypto";
import { importPublicKey } from "./keys.js";

export async function signPayload({ payload, privateKey, keyId, now }) {
  const signature = sign(null, Buffer.from(payload, "utf8"), privateKey);

  return {
    version: 1,
    algorithm: "ed25519",
    keyId,
    signedAt: timestampFrom(now),
    signature: signature.toString("base64url")
  };
}

export async function verifyPayloadSignature({ payload, signature, publicKey }) {
  if (!signature || signature.algorithm !== "ed25519") {
    return false;
  }

  try {
    return verify(
      null,
      Buffer.from(payload, "utf8"),
      importPublicKey(publicKey),
      Buffer.from(signature.signature, "base64url")
    );
  } catch {
    return false;
  }
}

function timestampFrom(now) {
  if (now instanceof Date) {
    return now.toISOString();
  }
  if (typeof now === "string") {
    return new Date(now).toISOString();
  }
  return new Date().toISOString();
}
