import { access, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import { assertGitRepoRoot } from "../git/repo.js";
import { canonicalizeJson } from "../manifest/canonical-json.js";
import {
  manifestPath,
  publicKeyPath,
  readManifest,
  readPublicKey,
  readRegistrationKey,
  readSignature,
  writeCiProof,
  writeManifest,
  writeRegistrationKey,
  writeRegistrationPublicKey,
  writeSignature,
  writeSigners,
  writeSignersSignature
} from "../manifest/read-write.js";
import { validateManifestShape } from "../manifest/validation.js";
import { ciSecretInstructions, createCiProof, deriveCiKey } from "../signing/ci-proof.js";
import { createSigningKey, exportPublicKey } from "../signing/keys.js";
import { encryptPrivateKey, writeEncryptedPrivateKey } from "../signing/private-key-store.js";
import {
  createSignerRegistry,
  createSignerRecord,
  findActiveSigner,
  loadVerifiedSignerRegistry,
  signAndWriteSignerRegistry,
  sortSigners,
  unlockRegistrationSigner
} from "../signing/signer-registry.js";
import { signPayload, verifyPayloadSignature } from "../signing/signatures.js";
import { checkLocalSigner } from "../signing/authorization.js";
import { initRepository } from "./init-repository.js";
import { verifyRepository, verifyWorkingTreeEntries } from "./verify-repository.js";
import { createViolation } from "./violations.js";
import { buildVerificationResult } from "./verification-result.js";

export async function setupRepository({ repoRoot, password, masterPassword, localPassword, now } = {}) {
  await assertGitRepoRoot(repoRoot);
  const registrationPassword = masterPassword ?? password;
  const signerPassword = localPassword ?? password;

  if (!await isRepositoryInitialized(repoRoot)) {
    return initRepository({
      repoRoot,
      masterPassword: registrationPassword,
      localPassword: signerPassword,
      now
    });
  }

  if (await isLegacyRepository(repoRoot)) {
    return upgradeLegacyRepository({
      repoRoot,
      registrationPassword,
      signerPassword,
      now
    });
  }

  const verification = await verifyRepository({ repoRoot, scope: "working-tree" });
  if (!verification.ok) {
    return {
      ...verification,
      setupRequired: true
    };
  }

  try {
    const local = await checkLocalSigner({ repoRoot });
    return {
      ok: true,
      alreadyRegistered: true,
      signerKeyId: local.signerKeyId
    };
  } catch (error) {
    if (error.code !== "LOCAL_SIGNER_MISSING" && error.code !== "LOCAL_SIGNER_NOT_REGISTERED") {
      throw error;
    }
  }

  const registrationSigner = await unlockRegistrationSigner({
    repoRoot,
    masterPassword: registrationPassword
  });
  const { registry, registrationPublicKey } = await loadVerifiedSignerRegistry(repoRoot);
  const localKeyPair = await createSigningKey();
  const localPublicKey = await exportPublicKey(localKeyPair);
  const existingSigner = findActiveSigner(registry, localPublicKey.keyId);
  if (existingSigner) {
    return {
      ok: true,
      alreadyRegistered: true,
      signerKeyId: existingSigner.keyId
    };
  }

  const encryptedPrivateKey = await encryptPrivateKey({
    privateKey: localKeyPair.privateKey,
    password: signerPassword,
    publicKeyFingerprint: localPublicKey.fingerprint
  });
  const nextRegistry = {
    ...registry,
    signers: sortSigners([
      ...registry.signers,
      createSignerRecord({
        publicKey: localPublicKey,
        registeredAt: now
      })
    ])
  };

  const signerRegistrySignature = await signAndWriteSignerRegistry({
    repoRoot,
    registry: nextRegistry,
    privateKey: registrationSigner.privateKey,
    keyId: registrationSigner.keyId,
    now
  });
  const registrationKey = await readRegistrationKey(repoRoot);
  const ciKey = await deriveCiKey({ masterPassword: registrationPassword });
  await writeCiProof(repoRoot, createCiProof({
    ciKey,
    registrationPublicKey,
    registrationKey,
    signerRegistry: nextRegistry,
    signerRegistrySignature
  }));
  await writeEncryptedPrivateKey(repoRoot, encryptedPrivateKey);

  return {
    ok: true,
    registered: true,
    signerKeyId: localPublicKey.keyId,
    ci: ciSecretInstructions(ciKey)
  };
}

export async function checkRepositorySetup({ repoRoot } = {}) {
  await assertGitRepoRoot(repoRoot);
  const local = await checkLocalSigner({ repoRoot });
  return {
    ok: true,
    signerKeyId: local.signerKeyId
  };
}

export async function isRepositoryInitialized(repoRoot) {
  try {
    await access(manifestPath(repoRoot));
    return true;
  } catch (error) {
    if (error.code === "ENOENT") {
      return false;
    }
    throw error;
  }
}

async function isLegacyRepository(repoRoot) {
  const [legacyPublicKeyExists, signersExist] = await Promise.all([
    fileExists(publicKeyPath(repoRoot)),
    fileExists(path.join(repoRoot, ".straight-jacket", "signers.json"))
  ]);
  return legacyPublicKeyExists && !signersExist;
}

async function upgradeLegacyRepository({ repoRoot, registrationPassword, signerPassword, now }) {
  const legacyVerification = await verifyLegacyRepository({ repoRoot });
  if (!legacyVerification.ok) {
    return {
      ...legacyVerification,
      setupRequired: true
    };
  }

  const registrationKeyPair = await createSigningKey();
  const registrationPublicKey = await exportPublicKey(registrationKeyPair);
  const localKeyPair = await createSigningKey();
  const localPublicKey = await exportPublicKey(localKeyPair);
  const manifest = await readManifest(repoRoot);
  const nextManifest = {
    ...manifest,
    keyId: localPublicKey.keyId
  };
  const signerRegistry = createSignerRegistry({
    repoId: manifest.repoId,
    registrationKeyId: registrationPublicKey.keyId,
    signers: [
      createSignerRecord({
        publicKey: localPublicKey,
        registeredAt: now
      })
    ]
  });
  const encryptedRegistrationKey = await encryptPrivateKey({
    privateKey: registrationKeyPair.privateKey,
    password: registrationPassword,
    publicKeyFingerprint: registrationPublicKey.fingerprint
  });
  const encryptedPrivateKey = await encryptPrivateKey({
    privateKey: localKeyPair.privateKey,
    password: signerPassword,
    publicKeyFingerprint: localPublicKey.fingerprint
  });
  const signerRegistrySignature = await signPayload({
    payload: canonicalizeJson(signerRegistry),
    privateKey: registrationKeyPair.privateKey,
    keyId: registrationPublicKey.keyId,
    now
  });
  const manifestSignature = await signPayload({
    payload: canonicalizeJson(nextManifest),
    privateKey: localKeyPair.privateKey,
    keyId: localPublicKey.keyId,
    now
  });
  const ciKey = await deriveCiKey({ masterPassword: registrationPassword });
  const ciProof = createCiProof({
    ciKey,
    registrationPublicKey,
    registrationKey: encryptedRegistrationKey,
    signerRegistry,
    signerRegistrySignature
  });

  await writeManifest(repoRoot, nextManifest);
  await writeSignature(repoRoot, manifestSignature);
  await writeRegistrationPublicKey(repoRoot, registrationPublicKey);
  await writeRegistrationKey(repoRoot, encryptedRegistrationKey);
  await writeSigners(repoRoot, signerRegistry);
  await writeSignersSignature(repoRoot, signerRegistrySignature);
  await writeCiProof(repoRoot, ciProof);
  await rm(publicKeyPath(repoRoot), { force: true });
  await writeEncryptedPrivateKey(repoRoot, encryptedPrivateKey);
  await writeFile(path.join(repoRoot, ".straight-jacket", "local", ".gitignore"), "*\n", "utf8");

  return {
    ok: true,
    upgraded: true,
    registered: true,
    signerKeyId: localPublicKey.keyId,
    ci: ciSecretInstructions(ciKey)
  };
}

async function verifyLegacyRepository({ repoRoot }) {
  try {
    const [manifest, signature, publicKey] = await Promise.all([
      readManifest(repoRoot),
      readSignature(repoRoot),
      readPublicKey(repoRoot)
    ]);
    const violations = validateManifestShape(manifest).map((violation) => createViolation(violation.code, violation));
    if (violations.length === 0) {
      const signatureValid = await verifyPayloadSignature({
        payload: canonicalizeJson(manifest),
        signature,
        publicKey
      });
      if (!signatureValid) {
        violations.push(createViolation("MANIFEST_SIGNATURE_INVALID"));
      }
    }
    if (violations.length === 0) {
      violations.push(...await verifyWorkingTreeEntries({ repoRoot, entries: manifest.entries }));
    }
    return buildVerificationResult({
      checked: Array.isArray(manifest.entries) ? manifest.entries.length : 0,
      violations
    });
  } catch {
    return buildVerificationResult({
      checked: 0,
      violations: [createViolation("MANIFEST_SIGNATURE_INVALID")]
    });
  }
}

async function fileExists(filePath) {
  try {
    await access(filePath);
    return true;
  } catch (error) {
    if (error.code === "ENOENT") {
      return false;
    }
    throw error;
  }
}
