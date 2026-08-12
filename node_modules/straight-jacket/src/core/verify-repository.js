import { createHash } from "node:crypto";
import { lstat, readFile } from "node:fs/promises";
import { resolveRepoPath } from "../git/paths.js";
import { scanForChecksum } from "../git/scan.js";
import { getStagedChanges, readStagedFile } from "../git/staged.js";
import { canonicalizeJson } from "../manifest/canonical-json.js";
import { readManifest, readPublicKey, readSignature } from "../manifest/read-write.js";
import { validateManifestShape } from "../manifest/validation.js";
import { fingerprintPublicKey } from "../signing/keys.js";
import { verifyPayloadSignature } from "../signing/signatures.js";
import { createViolation } from "./violations.js";
import { buildVerificationResult } from "./verification-result.js";

export async function verifyRepository({ repoRoot, scope = "working-tree", trustedPublicKeyFingerprint, skipSignatureForDiagnostics = false } = {}) {
  if (scope !== "working-tree") {
    if (scope === "staged") {
      return verifyStagedScope({ repoRoot });
    }
    return buildVerificationResult({ checked: 0, violations: [] });
  }

  const violations = [];
  const manifest = await readJsonOrViolation(repoRoot, "manifest");
  const signature = await readJsonOrViolation(repoRoot, "signature");
  const publicKey = await readJsonOrViolation(repoRoot, "publicKey");

  if (manifest.violation) {
    violations.push(manifest.violation);
  }
  if (signature.violation) {
    violations.push(signature.violation);
  }
  if (publicKey.violation) {
    violations.push(publicKey.violation);
  }

  if (violations.length > 0) {
    return buildVerificationResult({ checked: 0, violations });
  }

  if (trustedPublicKeyFingerprint) {
    const actualFingerprint = fingerprintPublicKeyOrNull(publicKey.value);
    if (actualFingerprint === null) {
      violations.push(createViolation("PUBLIC_KEY_INVALID"));
    } else if (actualFingerprint !== trustedPublicKeyFingerprint) {
      violations.push(createViolation("PUBLIC_KEY_FINGERPRINT_MISMATCH", {
        expected: trustedPublicKeyFingerprint,
        actual: actualFingerprint
      }));
    }
  }

  const manifestViolations = validateManifestShape(manifest.value).map((violation) => createViolation(violation.code, violation));
  violations.push(...manifestViolations);

  if (!skipSignatureForDiagnostics) {
    const signatureValid = await verifyPayloadSignature({
      payload: canonicalizeJson(manifest.value),
      signature: signature.value,
      publicKey: publicKey.value
    });
    if (!signatureValid) {
      violations.push(createViolation("MANIFEST_SIGNATURE_INVALID"));
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

async function verifyStagedScope({ repoRoot }) {
  const manifest = await readJsonOrViolation(repoRoot, "manifest");
  if (manifest.violation) {
    return buildVerificationResult({ checked: 0, violations: [manifest.violation] });
  }

  const changes = await getStagedChanges(repoRoot);
  const violations = [];
  const protectedPaths = new Set(manifest.value.entries.map((entry) => entry.path));

  for (const change of changes) {
    if ((change.status === "deleted" && protectedPaths.has(change.path)) ||
      (change.status === "renamed" && protectedPaths.has(change.oldPath))) {
      violations.push(createViolation("STAGED_PROTECTED_FILE_DELETED", {
        path: change.oldPath ?? change.path
      }));
    }
  }

  if (changes.some((change) => change.path === ".straight-jacket/manifest.json")) {
    const stagedManifestText = await readStagedFile(repoRoot, ".straight-jacket/manifest.json");
    const stagedSignatureText = await readStagedFile(repoRoot, ".straight-jacket/manifest.sig");
    const stagedPublicKeyText = await readStagedFile(repoRoot, ".straight-jacket/public-key.json");

    const stagedManifest = parseJsonOrNull(stagedManifestText);
    const stagedSignature = stagedSignatureText ? parseJsonOrNull(stagedSignatureText) : (await readJsonOrViolation(repoRoot, "signature")).value;
    const stagedPublicKey = stagedPublicKeyText ? parseJsonOrNull(stagedPublicKeyText) : (await readJsonOrViolation(repoRoot, "publicKey")).value;
    if (!stagedManifest || !stagedSignature || !stagedPublicKey) {
      violations.push(createViolation("STAGED_MANIFEST_SIGNATURE_INVALID", {
        path: ".straight-jacket/manifest.json"
      }));
      return buildVerificationResult({
        checked: manifest.value.entries.length,
        violations
      });
    }

    const signatureValid = await verifyPayloadSignature({
      payload: canonicalizeJson(stagedManifest),
      signature: stagedSignature,
      publicKey: stagedPublicKey
    });

    if (!signatureValid) {
      violations.push(createViolation("STAGED_MANIFEST_SIGNATURE_INVALID", {
        path: ".straight-jacket/manifest.json"
      }));
    }
  }

  return buildVerificationResult({
    checked: manifest.value.entries.length,
    violations
  });
}

async function verifyWorkingTreeEntries({ repoRoot, entries }) {
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
    return { value: await readPublicKey(repoRoot) };
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
  return "PUBLIC_KEY_MISSING";
}

function invalidCodeForKind(kind) {
  if (kind === "manifest") {
    return "MANIFEST_INVALID";
  }
  if (kind === "signature") {
    return "MANIFEST_SIGNATURE_INVALID";
  }
  return "PUBLIC_KEY_INVALID";
}

function fingerprintPublicKeyOrNull(publicKey) {
  try {
    return fingerprintPublicKey(publicKey);
  } catch {
    return null;
  }
}

function parseJsonOrNull(text) {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}
