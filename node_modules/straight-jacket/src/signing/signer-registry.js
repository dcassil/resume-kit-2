import { createPublicKey } from "node:crypto";
import { canonicalizeJson } from "../manifest/canonical-json.js";
import {
  readRegistrationKey,
  readRegistrationPublicKey,
  readSigners,
  readSignersSignature,
  writeSigners,
  writeSignersSignature
} from "../manifest/read-write.js";
import { createCodedError } from "../core/errors.js";
import { decryptPrivateKey } from "./private-key-store.js";
import { exportPublicKey, fingerprintPublicKey } from "./keys.js";
import { signPayload, verifyPayloadSignature } from "./signatures.js";

const HASH_PATTERN = /^sha256:[a-f0-9]{64}$/;

export function createSignerRegistry({ repoId, registrationKeyId, signers = [] }) {
  return {
    version: 1,
    repoId,
    registrationKeyId,
    signers: sortSigners(signers)
  };
}

export function createSignerRecord({ publicKey, registeredAt, label, active = true }) {
  const record = {
    version: publicKey.version ?? 1,
    algorithm: publicKey.algorithm,
    keyId: publicKey.keyId,
    fingerprint: publicKey.fingerprint ?? fingerprintPublicKey(publicKey),
    publicKey: publicKey.publicKey,
    registeredAt: registeredAt ?? new Date().toISOString(),
    active
  };

  if (label) {
    record.label = label;
  }

  return record;
}

export function validateSignerRegistry(registry) {
  const violations = [];
  if (!registry || typeof registry !== "object" || Array.isArray(registry)) {
    return [{ code: "SIGNERS_INVALID" }];
  }

  if (registry.version !== 1) {
    violations.push({ code: "SIGNERS_VERSION_UNSUPPORTED" });
  }
  if (!HASH_PATTERN.test(registry.repoId ?? "")) {
    violations.push({ code: "SIGNERS_REPO_ID_INVALID" });
  }
  if (!HASH_PATTERN.test(registry.registrationKeyId ?? "")) {
    violations.push({ code: "SIGNERS_REGISTRATION_KEY_INVALID" });
  }
  if (!Array.isArray(registry.signers)) {
    violations.push({ code: "SIGNERS_LIST_INVALID" });
    return violations;
  }

  const keyIds = new Set();
  for (const signer of registry.signers) {
    if (!signer || typeof signer !== "object" || Array.isArray(signer)) {
      violations.push({ code: "SIGNER_INVALID" });
      continue;
    }
    if (signer.version !== 1 || signer.algorithm !== "ed25519") {
      violations.push({ code: "SIGNER_ALGORITHM_NOT_ALLOWED", keyId: signer.keyId });
    }
    if (!HASH_PATTERN.test(signer.keyId ?? "") || !HASH_PATTERN.test(signer.fingerprint ?? "")) {
      violations.push({ code: "SIGNER_KEY_INVALID", keyId: signer.keyId });
    }
    if (signer.keyId !== signer.fingerprint) {
      violations.push({ code: "SIGNER_KEY_MISMATCH", keyId: signer.keyId });
    }
    if (typeof signer.publicKey !== "string" || signer.publicKey.length === 0) {
      violations.push({ code: "SIGNER_PUBLIC_KEY_INVALID", keyId: signer.keyId });
    } else if (fingerprintOrNull(signer) !== signer.fingerprint) {
      violations.push({ code: "SIGNER_FINGERPRINT_INVALID", keyId: signer.keyId });
    }
    if (typeof signer.registeredAt !== "string" || Number.isNaN(Date.parse(signer.registeredAt))) {
      violations.push({ code: "SIGNER_TIMESTAMP_INVALID", keyId: signer.keyId });
    }
    if (signer.active !== true && signer.active !== false) {
      violations.push({ code: "SIGNER_ACTIVE_INVALID", keyId: signer.keyId });
    }
    if (keyIds.has(signer.keyId)) {
      violations.push({ code: "DUPLICATE_SIGNER", keyId: signer.keyId });
    }
    keyIds.add(signer.keyId);
  }

  return uniqueViolations(violations);
}

export async function loadVerifiedSignerRegistry(repoRoot) {
  const [registry, signature, registrationPublicKey] = await Promise.all([
    readSigners(repoRoot),
    readSignersSignature(repoRoot),
    readRegistrationPublicKey(repoRoot)
  ]);

  const violations = validateSignerRegistry(registry);
  if (violations.length > 0) {
    throw createCodedError(violations[0].code, "Signer registry shape is invalid", { violations });
  }

  const validSignature = await verifyPayloadSignature({
    payload: canonicalizeJson(registry),
    signature,
    publicKey: registrationPublicKey
  });
  if (!validSignature) {
    throw createCodedError("SIGNERS_SIGNATURE_INVALID", "Signer registry signature is invalid");
  }

  return { registry, signature, registrationPublicKey };
}

export async function signAndWriteSignerRegistry({ repoRoot, registry, privateKey, keyId, now }) {
  const signature = await signPayload({
    payload: canonicalizeJson(registry),
    privateKey,
    keyId,
    now
  });

  await writeSigners(repoRoot, registry);
  await writeSignersSignature(repoRoot, signature);

  return signature;
}

export async function unlockRegistrationSigner({ repoRoot, masterPassword }) {
  const encrypted = await readRegistrationKey(repoRoot).catch((error) => {
    if (error.code === "ENOENT") {
      throw createCodedError("REGISTRATION_KEY_MISSING", "Encrypted registration key is missing");
    }
    throw error;
  });
  const privateKey = await decryptPrivateKey({ encrypted, password: masterPassword });
  const registrationPublicKey = await readRegistrationPublicKey(repoRoot);
  const publicKey = await exportPublicKey({ publicKey: createPublicKey(privateKey) });

  if (encrypted.publicKeyFingerprint !== registrationPublicKey.fingerprint ||
    publicKey.fingerprint !== registrationPublicKey.fingerprint) {
    throw createCodedError("REGISTRATION_KEY_MISMATCH", "Registration key does not match public verifier");
  }

  return {
    privateKey,
    publicKey: registrationPublicKey,
    keyId: registrationPublicKey.keyId
  };
}

export function findActiveSigner(registry, keyIdOrFingerprint) {
  return registry.signers.find((signer) => {
    return signer.active === true &&
      (signer.keyId === keyIdOrFingerprint || signer.fingerprint === keyIdOrFingerprint);
  });
}

export function publicKeyFromSigner(signer) {
  return {
    version: signer.version,
    algorithm: signer.algorithm,
    keyId: signer.keyId,
    fingerprint: signer.fingerprint,
    publicKey: signer.publicKey
  };
}

export function sortSigners(signers) {
  return [...signers].sort((left, right) => left.keyId.localeCompare(right.keyId));
}

function fingerprintOrNull(publicKey) {
  try {
    return fingerprintPublicKey(publicKey);
  } catch {
    return null;
  }
}

function uniqueViolations(violations) {
  const seen = new Set();
  const unique = [];

  for (const violation of violations) {
    const key = `${violation.code}:${violation.keyId ?? ""}`;
    if (!seen.has(key)) {
      seen.add(key);
      unique.push(violation);
    }
  }

  return unique;
}
