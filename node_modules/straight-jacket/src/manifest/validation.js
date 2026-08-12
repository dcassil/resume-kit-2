import nodePath from "node:path";

const HASH_PATTERN = /^sha256:[a-f0-9]{64}$/;
const MVP_POLICY = {
  allowSymlinks: false,
  requireHumanAuthorization: true,
  failClosed: true
};

export function validateManifestShape(manifest) {
  const violations = [];

  if (!manifest || typeof manifest !== "object" || Array.isArray(manifest)) {
    return [createManifestViolation("MANIFEST_INVALID")];
  }

  if (manifest.version !== 1) {
    violations.push(createManifestViolation("MANIFEST_VERSION_UNSUPPORTED"));
  }

  if (manifest.hashAlgorithm !== "sha256") {
    violations.push(createManifestViolation("HASH_ALGORITHM_NOT_ALLOWED"));
  }

  if (manifest.signatureAlgorithm !== "ed25519") {
    violations.push(createManifestViolation("SIGNATURE_ALGORITHM_NOT_ALLOWED"));
  }

  if (!HASH_PATTERN.test(manifest.repoId ?? "")) {
    violations.push(createManifestViolation("REPO_ID_INVALID"));
  }

  if (!HASH_PATTERN.test(manifest.keyId ?? "")) {
    violations.push(createManifestViolation("KEY_ID_INVALID"));
  }

  if (isPolicyDowngraded(manifest.policy)) {
    violations.push(createManifestViolation("POLICY_DOWNGRADE_NOT_ALLOWED"));
  }

  const entries = Array.isArray(manifest.entries) ? manifest.entries : [];
  if (!Array.isArray(manifest.entries)) {
    violations.push(createManifestViolation("MANIFEST_ENTRIES_INVALID"));
  }

  violations.push(...entries.flatMap((entry) => validateEntry(entry)));
  violations.push(...validateEntrySet(entries));

  return uniqueViolations(violations);
}

export function validateEntry(entry) {
  const violations = [];

  if (!entry || typeof entry !== "object" || Array.isArray(entry)) {
    return [createManifestViolation("MANIFEST_ENTRY_INVALID")];
  }

  const pathViolationCode = invalidPathCode(entry.path);
  if (pathViolationCode) {
    violations.push(createManifestViolation(pathViolationCode, { path: entry.path }));
  } else if (entry.name !== nodePath.posix.basename(entry.path)) {
    violations.push(createManifestViolation("PROTECTED_ENTRY_NAME_INVALID", { path: entry.path }));
  }

  if (!HASH_PATTERN.test(entry.checksum ?? "")) {
    violations.push(createManifestViolation("PROTECTED_ENTRY_CHECKSUM_INVALID", { path: entry.path }));
  }

  if (!Number.isSafeInteger(entry.size) || entry.size < 0) {
    violations.push(createManifestViolation("PROTECTED_ENTRY_SIZE_INVALID", { path: entry.path }));
  }

  if (typeof entry.registeredAt !== "string" || Number.isNaN(Date.parse(entry.registeredAt))) {
    violations.push(createManifestViolation("PROTECTED_ENTRY_TIMESTAMP_INVALID", { path: entry.path }));
  }

  if (entry.reason !== undefined && typeof entry.reason !== "string") {
    violations.push(createManifestViolation("PROTECTED_ENTRY_REASON_INVALID", { path: entry.path }));
  }

  return violations;
}

export function validateEntrySet(entries) {
  const violations = [];
  const exactPaths = new Set();
  const lowerCasePaths = new Map();

  for (const entry of entries) {
    if (!entry || typeof entry.path !== "string") {
      continue;
    }

    if (exactPaths.has(entry.path)) {
      violations.push(createManifestViolation("DUPLICATE_PROTECTED_PATH", { path: entry.path }));
    }
    exactPaths.add(entry.path);

    const lowerCasePath = entry.path.toLowerCase();
    const firstPath = lowerCasePaths.get(lowerCasePath);
    if (firstPath !== undefined && firstPath !== entry.path) {
      violations.push(createManifestViolation("PATH_CASE_COLLISION", { path: entry.path, existingPath: firstPath }));
    }
    lowerCasePaths.set(lowerCasePath, entry.path);
  }

  return uniqueViolations(violations);
}

function isPolicyDowngraded(policy) {
  if (!policy || typeof policy !== "object" || Array.isArray(policy)) {
    return true;
  }

  const policyKeys = Object.keys(policy);
  const allowedKeys = Object.keys(MVP_POLICY);
  if (policyKeys.some((key) => !allowedKeys.includes(key))) {
    return true;
  }

  return allowedKeys.some((key) => policy[key] !== MVP_POLICY[key]);
}

function invalidPathCode(manifestPath) {
  if (typeof manifestPath !== "string" || manifestPath.length === 0) {
    return "PROTECTED_PATH_INVALID";
  }

  if (nodePath.isAbsolute(manifestPath)) {
    return "INVALID_PATH_ABSOLUTE";
  }

  if (manifestPath.split("/").includes("..")) {
    return "INVALID_PATH_ESCAPE";
  }

  if (manifestPath.includes("\\")) {
    return "PROTECTED_PATH_INVALID";
  }

  const normalized = nodePath.posix.normalize(manifestPath);
  if (normalized !== manifestPath || normalized === "." || normalized.startsWith("../")) {
    return "INVALID_PATH_ESCAPE";
  }

  return null;
}

function createManifestViolation(code, fields = {}) {
  return { code, ...fields };
}

function uniqueViolations(violations) {
  const seen = new Set();
  const unique = [];

  for (const violation of violations) {
    const key = `${violation.code}:${violation.path ?? ""}:${violation.existingPath ?? ""}`;
    if (!seen.has(key)) {
      seen.add(key);
      unique.push(violation);
    }
  }

  return unique;
}
