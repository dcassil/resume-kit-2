import { canonicalizeJson } from "../manifest/canonical-json.js";
import { readManifest, readSignature, writeManifest, writeSignature } from "../manifest/read-write.js";
import { validateManifestShape } from "../manifest/validation.js";
import { signPayload, verifyPayloadSignature } from "../signing/signatures.js";
import { findActiveSigner, loadVerifiedSignerRegistry, publicKeyFromSigner } from "../signing/signer-registry.js";
import { createCodedError } from "./errors.js";

export async function loadVerifiedManifest(repoRoot) {
  const [manifest, signature, signerRegistry] = await Promise.all([
    readManifest(repoRoot),
    readSignature(repoRoot),
    loadVerifiedSignerRegistry(repoRoot)
  ]);

  const shapeViolations = validateManifestShape(manifest);
  if (shapeViolations.length > 0) {
    throw createCodedError(shapeViolations[0].code, "Manifest shape is invalid", { violations: shapeViolations });
  }

  const signer = findActiveSigner(signerRegistry.registry, signature.keyId ?? manifest.keyId);
  if (!signer || manifest.keyId !== signer.keyId) {
    throw createCodedError("MANIFEST_SIGNER_NOT_REGISTERED", "Manifest signer is not registered");
  }

  const validSignature = await verifyPayloadSignature({
    payload: canonicalizeJson(manifest),
    signature,
    publicKey: publicKeyFromSigner(signer)
  });
  if (!validSignature) {
    throw createCodedError("MANIFEST_SIGNATURE_INVALID", "Manifest signature is invalid");
  }

  return { manifest, signature, publicKey: publicKeyFromSigner(signer), signerRegistry };
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
