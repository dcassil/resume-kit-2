import { createHash, randomBytes } from "node:crypto";
import { access, mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { assertGitRepoRoot } from "../git/repo.js";
import { canonicalizeJson } from "../manifest/canonical-json.js";
import {
  manifestPath,
  publicKeyPath,
  signaturePath,
  writeManifest,
  writePublicKey,
  writeSignature
} from "../manifest/read-write.js";
import { createSigningKey, exportPublicKey } from "../signing/keys.js";
import { encryptPrivateKey, writeEncryptedPrivateKey } from "../signing/private-key-store.js";
import { signPayload } from "../signing/signatures.js";
import { createCodedError } from "./errors.js";

export async function initRepository({ repoRoot, password, now } = {}) {
  await assertGitRepoRoot(repoRoot);
  await assertNotInitialized(repoRoot);
  const keyPair = await createSigningKey();
  const publicKey = await exportPublicKey(keyPair);
  const manifest = createEmptyManifest({
    repoId: createRepoId(),
    keyId: publicKey.keyId
  });
  const signature = await signPayload({
    payload: canonicalizeJson(manifest),
    privateKey: keyPair.privateKey,
    keyId: publicKey.keyId,
    now
  });
  const encryptedPrivateKey = await encryptPrivateKey({
    privateKey: keyPair.privateKey,
    password,
    publicKeyFingerprint: publicKey.fingerprint
  });

  await mkdir(path.join(repoRoot, ".straight-jacket", "local"), { recursive: true });
  await writeManifest(repoRoot, manifest);
  await writeSignature(repoRoot, signature);
  await writePublicKey(repoRoot, publicKey);
  await writeEncryptedPrivateKey(repoRoot, encryptedPrivateKey);
  await writeFile(path.join(repoRoot, ".straight-jacket", "local", ".gitignore"), "*\n", "utf8");

  return {
    ok: true,
    manifestPath: manifestPath(repoRoot),
    signaturePath: signaturePath(repoRoot),
    publicKeyPath: publicKeyPath(repoRoot),
    fingerprint: publicKey.fingerprint
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
