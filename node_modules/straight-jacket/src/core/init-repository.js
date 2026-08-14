import { createHash, randomBytes } from "node:crypto";
import { access, mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { assertGitRepoRoot } from "../git/repo.js";
import { canonicalizeJson } from "../manifest/canonical-json.js";
import {
  registrationKeyPath,
  registrationPublicKeyPath,
  ciProofPath,
  manifestPath,
  publicKeyPath,
  signersPath,
  signersSignaturePath,
  signaturePath,
  writeManifest,
  writeRegistrationKey,
  writeRegistrationPublicKey,
  writeCiProof,
  writeSigners,
  writeSignersSignature,
  writeSignature
} from "../manifest/read-write.js";
import { createSigningKey, exportPublicKey } from "../signing/keys.js";
import { ciSecretInstructions, createCiProof, deriveCiKey } from "../signing/ci-proof.js";
import { encryptPrivateKey, writeEncryptedPrivateKey } from "../signing/private-key-store.js";
import { createSignerRecord, createSignerRegistry } from "../signing/signer-registry.js";
import { signPayload } from "../signing/signatures.js";
import { createCodedError } from "./errors.js";

export async function initRepository({ repoRoot, password, masterPassword, localPassword, now } = {}) {
  await assertGitRepoRoot(repoRoot);
  await assertNotInitialized(repoRoot);
  const registrationPassword = masterPassword ?? password;
  const signerPassword = localPassword ?? password;
  const registrationKeyPair = await createSigningKey();
  const localKeyPair = await createSigningKey();
  const registrationPublicKey = await exportPublicKey(registrationKeyPair);
  const localPublicKey = await exportPublicKey(localKeyPair);
  const manifest = createEmptyManifest({
    repoId: createRepoId(),
    keyId: localPublicKey.keyId
  });
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
  const signature = await signPayload({
    payload: canonicalizeJson(manifest),
    privateKey: localKeyPair.privateKey,
    keyId: localPublicKey.keyId,
    now
  });
  const signersSignature = await signPayload({
    payload: canonicalizeJson(signerRegistry),
    privateKey: registrationKeyPair.privateKey,
    keyId: registrationPublicKey.keyId,
    now
  });
  const encryptedPrivateKey = await encryptPrivateKey({
    privateKey: localKeyPair.privateKey,
    password: signerPassword,
    publicKeyFingerprint: localPublicKey.fingerprint
  });
  const encryptedRegistrationKey = await encryptPrivateKey({
    privateKey: registrationKeyPair.privateKey,
    password: registrationPassword,
    publicKeyFingerprint: registrationPublicKey.fingerprint
  });
  const ciKey = await deriveCiKey({ masterPassword: registrationPassword });
  const ciProof = createCiProof({
    ciKey,
    registrationPublicKey,
    registrationKey: encryptedRegistrationKey,
    signerRegistry,
    signerRegistrySignature: signersSignature
  });

  await mkdir(path.join(repoRoot, ".straight-jacket", "local"), { recursive: true });
  await writeManifest(repoRoot, manifest);
  await writeSignature(repoRoot, signature);
  await writeSigners(repoRoot, signerRegistry);
  await writeSignersSignature(repoRoot, signersSignature);
  await writeRegistrationPublicKey(repoRoot, registrationPublicKey);
  await writeRegistrationKey(repoRoot, encryptedRegistrationKey);
  await writeCiProof(repoRoot, ciProof);
  await writeEncryptedPrivateKey(repoRoot, encryptedPrivateKey);
  await writeFile(path.join(repoRoot, ".straight-jacket", "local", ".gitignore"), "*\n", "utf8");

  return {
    ok: true,
    manifestPath: manifestPath(repoRoot),
    signaturePath: signaturePath(repoRoot),
    signersPath: signersPath(repoRoot),
    signersSignaturePath: signersSignaturePath(repoRoot),
    registrationPublicKeyPath: registrationPublicKeyPath(repoRoot),
    registrationKeyPath: registrationKeyPath(repoRoot),
    ciProofPath: ciProofPath(repoRoot),
    publicKeyPath: registrationPublicKeyPath(repoRoot),
    fingerprint: registrationPublicKey.fingerprint,
    localSignerKeyId: localPublicKey.keyId,
    ci: ciSecretInstructions(ciKey)
  };
}

function createEmptyManifest({ repoId, keyId }) {
  return {
    version: 1,
    repoId,
    hashAlgorithm: "sha256",
    signatureAlgorithm: "ed25519",
    keyId,
    policy: {
      allowSymlinks: false,
      requireHumanAuthorization: true,
      failClosed: true
    },
    entries: []
  };
}

function createRepoId() {
  return `sha256:${createHash("sha256").update(randomBytes(32)).digest("hex")}`;
}

async function assertNotInitialized(repoRoot) {
  const existingPaths = [
    manifestPath(repoRoot),
    signaturePath(repoRoot),
    publicKeyPath(repoRoot),
    signersPath(repoRoot),
    signersSignaturePath(repoRoot),
    registrationPublicKeyPath(repoRoot),
    registrationKeyPath(repoRoot),
    ciProofPath(repoRoot),
    path.join(repoRoot, ".straight-jacket", "local", "private-key.json")
  ];

  for (const filePath of existingPaths) {
    if (await pathExists(filePath)) {
      throw createCodedError("REPOSITORY_ALREADY_INITIALIZED", "Straight Jacket metadata already exists");
    }
  }
}

async function pathExists(filePath) {
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
