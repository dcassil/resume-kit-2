import { canonicalizeJson } from "../manifest/canonical-json.js";
import { readManifest, readPublicKey, readSignature, writeManifest, writeSignature } from "../manifest/read-write.js";
import { validateManifestShape } from "../manifest/validation.js";
import { signPayload, verifyPayloadSignature } from "../signing/signatures.js";
import { createCodedError } from "./errors.js";

export async function loadVerifiedManifest(repoRoot) {
  const [manifest, signature, publicKey] = await Promise.all([
    readManifest(repoRoot),
    readSignature(repoRoot),
    readPublicKey(repoRoot)
  ]);

  const shapeViolations = validateManifestShape(manifest);
  if (shapeViolations.length > 0) {
    throw createCodedError(shapeViolations[0].code, "Manifest shape is invalid", { violations: shapeViolations });
  }

  const validSignature = await verifyPayloadSignature({
    payload: canonicalizeJson(manifest),
    signature,
    publicKey
  });
  if (!validSignature) {
    throw createCodedError("MANIFEST_SIGNATURE_INVALID", "Manifest signature is invalid");
  }

  return { manifest, signature, publicKey };
}

export async function signAndWriteManifest({ repoRoot, manifest, privateKey, keyId, now }) {
  const signature = await signPayload({
    payload: canonicalizeJson(manifest),
    privateKey,
    keyId,
    now
  });

  await writeManifest(repoRoot, manifest);
  await writeSignature(repoRoot, signature);

  return signature;
}
