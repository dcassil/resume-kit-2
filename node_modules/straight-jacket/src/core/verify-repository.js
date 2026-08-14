import { createHash } from "node:crypto";
import { lstat, readFile } from "node:fs/promises";
import { resolveRepoPath } from "../git/paths.js";
import { scanForChecksum } from "../git/scan.js";
import { getStagedChanges, readStagedFile } from "../git/staged.js";
import { canonicalizeJson } from "../manifest/canonical-json.js";
import {
  CI_PROOF_PATH,
  MANIFEST_PATH,
  REGISTRATION_PUBLIC_KEY_PATH,
  REGISTRATION_KEY_PATH,
  SIGNATURE_PATH,
  SIGNERS_PATH,
  SIGNERS_SIGNATURE_PATH,
  readCiProof,
  readManifest,
  readRegistrationKey,
  readRegistrationPublicKey,
  readSignature,
  readSigners,
  readSignersSignature
} from "../manifest/read-write.js";
import { validateManifestShape } from "../manifest/validation.js";
import { verifyCiProof } from "../signing/ci-proof.js";
import { verifyPayloadSignature } from "../signing/signatures.js";
import { findActiveSigner, publicKeyFromSigner, validateSignerRegistry } from "../signing/signer-registry.js";
import { createViolation } from "./violations.js";
import { buildVerificationResult } from "./verification-result.js";

const METADATA_PATHS = new Set([
  MANIFEST_PATH,
  SIGNATURE_PATH,
  SIGNERS_PATH,
  SIGNERS_SIGNATURE_PATH,
  REGISTRATION_PUBLIC_KEY_PATH,
  REGISTRATION_KEY_PATH,
  CI_PROOF_PATH
]);

export async function verifyRepository({ repoRoot, scope = "working-tree", ciKey, skipSignatureForDiagnostics = false } = {}) {
  if (scope !== "working-tree") {
    if (scope === "staged") {
      return verifyStagedScope({ repoRoot, ciKey });
    }
    return buildVerificationResult({ checked: 0, violations: [] });
  }

  const violations = [];
  const metadata = await readMetadataOrViolations(repoRoot);
  const { manifest, signature, signers, signersSignature, registrationPublicKey, registrationKey, ciProof } = metadata;

  violations.push(...metadata.violations);

  if (violations.length > 0) {
    return buildVerificationResult({ checked: 0, violations });
  }

  if (ciKey !== undefined) {
    if (registrationKey.violation) {
      violations.push(registrationKey.violation);
    }
    if (ciProof.violation) {
      violations.push(ciProof.violation);
    }
  }

  if (violations.length > 0) {
    return buildVerificationResult({ checked: 0, violations });
  }

  const manifestViolations = validateManifestShape(manifest.value).map((violation) => createViolation(violation.code, violation));
  violations.push(...manifestViolations);
  const signerViolations = validateSignerRegistry(signers.value).map((violation) => createViolation(violation.code, violation));
  violations.push(...signerViolations);

  if (violations.length === 0) {
    const signersSignatureValid = await verifyPayloadSignature({
      payload: canonicalizeJson(signers.value),
      signature: signersSignature.value,
      publicKey: registrationPublicKey.value
    });
    if (!signersSignatureValid) {
      violations.push(createViolation("SIGNERS_SIGNATURE_INVALID"));
    }
  }

  if (ciKey !== undefined && violations.length === 0) {
    try {
      if (!verifyCiProof({
        ciKey,
        proof: ciProof.value,
        registrationPublicKey: registrationPublicKey.value,
        registrationKey: registrationKey.value,
        signerRegistry: signers.value,
        signerRegistrySignature: signersSignature.value
      })) {
        violations.push(createViolation("CI_PROOF_INVALID"));
      }
    } catch {
      violations.push(createViolation("CI_KEY_INVALID"));
    }
  }

  if (!skipSignatureForDiagnostics && violations.length === 0) {
    const signer = findActiveSigner(signers.value, signature.value.keyId ?? manifest.value.keyId);
    if (!signer || manifest.value.keyId !== signer.keyId) {
      violations.push(createViolation("MANIFEST_SIGNER_NOT_REGISTERED"));
    } else {
      const signatureValid = await verifyPayloadSignature({
        payload: canonicalizeJson(manifest.value),
        signature: signature.value,
        publicKey: publicKeyFromSigner(signer)
      });
      if (!signatureValid) {
        violations.push(createViolation("MANIFEST_SIGNATURE_INVALID"));
      }
    }
  }

  if (violations.length === 0) {
    violations.push(...await verifyWorkingTreeEntries({ repoRoot, entries: manifest.value.entries }));
  }

  return buildVerificationResult({
    checked: Array.isArray(manifest.value?.entries) ? manifest.value.entries.length : 0,
    violations
  });
}

async function verifyStagedScope({ repoRoot, ciKey }) {
  const workingMetadata = await readMetadataOrViolations(repoRoot);
  if (workingMetadata.manifest?.violation) {
    return buildVerificationResult({ checked: 0, violations: [workingMetadata.manifest.violation] });
  }

  const changes = await getStagedChanges(repoRoot);
  const violations = [];
  const stagedMetadata = await readStagedMetadataOrViolations(repoRoot);
  const manifestForProtectedPaths = stagedMetadata.manifest?.value ?? workingMetadata.manifest.value;
  const protectedPaths = new Set(manifestForProtectedPaths.entries.map((entry) => entry.path));

  for (const change of changes) {
    if ((change.status === "deleted" && protectedPaths.has(change.path)) ||
      (change.status === "renamed" && protectedPaths.has(change.oldPath))) {
      violations.push(createViolation("STAGED_PROTECTED_FILE_DELETED", {
        path: change.oldPath ?? change.path
      }));
    }
  }

  if (changes.some((change) => METADATA_PATHS.has(change.path) || METADATA_PATHS.has(change.oldPath))) {
    const metadataViolations = await verifyMetadataValues(stagedMetadata, { ciKey });
    if (metadataViolations.length > 0) {
      violations.push(createViolation("STAGED_MANIFEST_SIGNATURE_INVALID", {
        path: MANIFEST_PATH
      }));
    }
  }

  return buildVerificationResult({
    checked: manifestForProtectedPaths.entries.length,
    violations
  });
}

export async function verifyWorkingTreeEntries({ repoRoot, entries }) {
  const violations = [];

  for (const entry of entries) {
    try {
      const filePath = resolveRepoPath(repoRoot, entry.path);
      const stats = await lstat(filePath);
      if (stats.isSymbolicLink()) {
        violations.push(createViolation("SYMLINK_NOT_ALLOWED", { path: entry.path }));
        continue;
      }
      const content = await readFile(filePath);
      const actual = `sha256:${createHash("sha256").update(content).digest("hex")}`;
      if (actual !== entry.checksum) {
        violations.push(createViolation("CHECKSUM_MISMATCH", {
          path: entry.path,
          expected: entry.checksum,
          actual
        }));
      }
    } catch (error) {
      if (error.code === "ENOENT") {
        violations.push(createViolation("PROTECTED_FILE_MISSING", { path: entry.path }));
        const likelyMoves = await scanForChecksum(repoRoot, entry.checksum, {
          ignoredDirectories: [".straight-jacket"]
        });
        for (const likelyMove of likelyMoves.filter((match) => match.path !== entry.path)) {
          violations.push(createViolation("LIKELY_RENAME_OR_MOVE", { path: likelyMove.path, expectedPath: entry.path }));
        }
        continue;
      }
      throw error;
    }
  }

  return violations;
}

async function readJsonOrViolation(repoRoot, kind) {
  try {
    if (kind === "manifest") {
      return { value: await readManifest(repoRoot) };
    }
    if (kind === "signature") {
      return { value: await readSignature(repoRoot) };
    }
    if (kind === "signers") {
      return { value: await readSigners(repoRoot) };
    }
    if (kind === "signersSignature") {
      return { value: await readSignersSignature(repoRoot) };
    }
    if (kind === "registrationKey") {
      return { value: await readRegistrationKey(repoRoot) };
    }
    if (kind === "ciProof") {
      return { value: await readCiProof(repoRoot) };
    }
    return { value: await readRegistrationPublicKey(repoRoot) };
  } catch (error) {
    if (error.code === "ENOENT") {
      return { violation: createViolation(missingCodeForKind(kind)) };
    }
    if (error instanceof SyntaxError) {
      return { violation: createViolation(invalidCodeForKind(kind)) };
    }
    throw error;
  }
}

function missingCodeForKind(kind) {
  if (kind === "manifest") {
    return "MANIFEST_MISSING";
  }
  if (kind === "signature") {
    return "MANIFEST_SIGNATURE_MISSING";
  }
  if (kind === "signers") {
    return "SIGNERS_MISSING";
  }
  if (kind === "signersSignature") {
    return "SIGNERS_SIGNATURE_MISSING";
  }
  if (kind === "registrationKey") {
    return "REGISTRATION_KEY_MISSING";
  }
  if (kind === "ciProof") {
    return "CI_PROOF_MISSING";
  }
  return "REGISTRATION_PUBLIC_KEY_MISSING";
}

function invalidCodeForKind(kind) {
  if (kind === "manifest") {
    return "MANIFEST_INVALID";
  }
  if (kind === "signature") {
    return "MANIFEST_SIGNATURE_INVALID";
  }
  if (kind === "signers") {
    return "SIGNERS_INVALID";
  }
  if (kind === "signersSignature") {
    return "SIGNERS_SIGNATURE_INVALID";
  }
  if (kind === "registrationKey") {
    return "REGISTRATION_KEY_INVALID";
  }
  if (kind === "ciProof") {
    return "CI_PROOF_INVALID";
  }
  return "REGISTRATION_PUBLIC_KEY_INVALID";
}

function parseJsonOrNull(text) {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

async function readMetadataOrViolations(repoRoot) {
  const [manifest, signature, signers, signersSignature, registrationPublicKey, registrationKey, ciProof] = await Promise.all([
    readJsonOrViolation(repoRoot, "manifest"),
    readJsonOrViolation(repoRoot, "signature"),
    readJsonOrViolation(repoRoot, "signers"),
    readJsonOrViolation(repoRoot, "signersSignature"),
    readJsonOrViolation(repoRoot, "registrationPublicKey"),
    readJsonOrViolation(repoRoot, "registrationKey"),
    readJsonOrViolation(repoRoot, "ciProof")
  ]);

  return {
    manifest,
    signature,
    signers,
    signersSignature,
    registrationPublicKey,
    registrationKey,
    ciProof,
    violations: [manifest, signature, signers, signersSignature, registrationPublicKey]
      .flatMap((item) => item.violation ? [item.violation] : [])
  };
}

async function readStagedMetadataOrViolations(repoRoot) {
  const [manifest, signature, signers, signersSignature, registrationPublicKey, registrationKey, ciProof] = await Promise.all([
    readStagedJsonOrWorking(repoRoot, "manifest"),
    readStagedJsonOrWorking(repoRoot, "signature"),
    readStagedJsonOrWorking(repoRoot, "signers"),
    readStagedJsonOrWorking(repoRoot, "signersSignature"),
    readStagedJsonOrWorking(repoRoot, "registrationPublicKey"),
    readStagedJsonOrWorking(repoRoot, "registrationKey"),
    readStagedJsonOrWorking(repoRoot, "ciProof")
  ]);

  return {
    manifest,
    signature,
    signers,
    signersSignature,
    registrationPublicKey,
    registrationKey,
    ciProof,
    violations: [manifest, signature, signers, signersSignature, registrationPublicKey]
      .flatMap((item) => item.violation ? [item.violation] : [])
  };
}

async function readStagedJsonOrWorking(repoRoot, kind) {
  const text = await readStagedFile(repoRoot, pathForKind(kind));
  if (text === null) {
    return readJsonOrViolation(repoRoot, kind);
  }

  const value = parseJsonOrNull(text);
  if (!value) {
    return { violation: createViolation(invalidCodeForKind(kind)) };
  }
  return { value };
}

async function verifyMetadataValues(metadata, { ciKey } = {}) {
  const violations = [...metadata.violations];
  if (ciKey !== undefined) {
    if (metadata.registrationKey.violation) {
      violations.push(metadata.registrationKey.violation);
    }
    if (metadata.ciProof.violation) {
      violations.push(metadata.ciProof.violation);
    }
  }
  if (violations.length > 0) {
    return violations;
  }

  violations.push(...validateManifestShape(metadata.manifest.value).map((violation) => createViolation(violation.code, violation)));
  violations.push(...validateSignerRegistry(metadata.signers.value).map((violation) => createViolation(violation.code, violation)));
  if (violations.length > 0) {
    return violations;
  }

  const signersSignatureValid = await verifyPayloadSignature({
    payload: canonicalizeJson(metadata.signers.value),
    signature: metadata.signersSignature.value,
    publicKey: metadata.registrationPublicKey.value
  });
  if (!signersSignatureValid) {
    violations.push(createViolation("SIGNERS_SIGNATURE_INVALID"));
    return violations;
  }

  const signer = findActiveSigner(metadata.signers.value, metadata.signature.value.keyId ?? metadata.manifest.value.keyId);
  if (!signer || metadata.manifest.value.keyId !== signer.keyId) {
    violations.push(createViolation("MANIFEST_SIGNER_NOT_REGISTERED"));
    return violations;
  }

  const manifestSignatureValid = await verifyPayloadSignature({
    payload: canonicalizeJson(metadata.manifest.value),
    signature: metadata.signature.value,
    publicKey: publicKeyFromSigner(signer)
  });
  if (!manifestSignatureValid) {
    violations.push(createViolation("MANIFEST_SIGNATURE_INVALID"));
  }

  if (ciKey !== undefined) {
    try {
      if (!verifyCiProof({
        ciKey,
        proof: metadata.ciProof.value,
        registrationPublicKey: metadata.registrationPublicKey.value,
        registrationKey: metadata.registrationKey.value,
        signerRegistry: metadata.signers.value,
        signerRegistrySignature: metadata.signersSignature.value
      })) {
        violations.push(createViolation("CI_PROOF_INVALID"));
      }
    } catch {
      violations.push(createViolation("CI_KEY_INVALID"));
    }
  }

  return violations;
}

function pathForKind(kind) {
  if (kind === "manifest") {
    return MANIFEST_PATH;
  }
  if (kind === "signature") {
    return SIGNATURE_PATH;
  }
  if (kind === "signers") {
    return SIGNERS_PATH;
  }
  if (kind === "signersSignature") {
    return SIGNERS_SIGNATURE_PATH;
  }
  if (kind === "registrationKey") {
    return REGISTRATION_KEY_PATH;
  }
  if (kind === "ciProof") {
    return CI_PROOF_PATH;
  }
  return REGISTRATION_PUBLIC_KEY_PATH;
}
