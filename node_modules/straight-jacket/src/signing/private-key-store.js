import { createCipheriv, createDecipheriv, createPrivateKey, randomBytes, scrypt } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { promisify } from "node:util";

const scryptAsync = promisify(scrypt);
const KDF = {
  name: "scrypt",
  cost: 16384,
  blockSize: 8,
  parallelization: 1,
  keyLength: 32
};

export async function encryptPrivateKey({ privateKey, password, publicKeyFingerprint }) {
  const salt = randomBytes(16);
  const iv = randomBytes(12);
  const key = await deriveEncryptionKey({ password, salt });
  const cipher = createCipheriv("aes-256-gcm", key, iv);
  const privateKeyBytes = privateKey.export({ format: "der", type: "pkcs8" });
  const encryptedPrivateKey = Buffer.concat([cipher.update(privateKeyBytes), cipher.final()]);
  const tag = cipher.getAuthTag();

  privateKeyBytes.fill(0);
  key.fill(0);

  return {
    version: 1,
    algorithm: "ed25519",
    kdf: {
      ...KDF,
      salt: salt.toString("base64url")
    },
    cipher: {
      name: "aes-256-gcm",
      iv: iv.toString("base64url"),
      tag: tag.toString("base64url")
    },
    encryptedPrivateKey: encryptedPrivateKey.toString("base64url"),
    publicKeyFingerprint
  };
}

export async function decryptPrivateKey({ encrypted, password }) {
  try {
    const salt = Buffer.from(encrypted.kdf.salt, "base64url");
    const key = await deriveEncryptionKey({ password, salt, kdf: encrypted.kdf });
    const decipher = createDecipheriv("aes-256-gcm", key, Buffer.from(encrypted.cipher.iv, "base64url"));
    decipher.setAuthTag(Buffer.from(encrypted.cipher.tag, "base64url"));
    const privateKeyBytes = Buffer.concat([
      decipher.update(Buffer.from(encrypted.encryptedPrivateKey, "base64url")),
      decipher.final()
    ]);
    const privateKey = createPrivateKey({ key: privateKeyBytes, format: "der", type: "pkcs8" });

    privateKeyBytes.fill(0);
    key.fill(0);

    return privateKey;
  } catch (error) {
    const invalidPassword = new Error("INVALID_PASSWORD: Could not unlock signing key");
    invalidPassword.code = "INVALID_PASSWORD";
    invalidPassword.cause = error;
    throw invalidPassword;
  }
}

export async function readEncryptedPrivateKey(repoRoot) {
  return JSON.parse(await readFile(privateKeyPath(repoRoot), "utf8"));
}

export async function writeEncryptedPrivateKey(repoRoot, encrypted) {
  const filePath = privateKeyPath(repoRoot);
  await mkdir(path.dirname(filePath), { recursive: true });
  await writeFile(filePath, `${JSON.stringify(encrypted, null, 2)}\n`, { mode: 0o600 });
}

function privateKeyPath(repoRoot) {
  return path.join(repoRoot, ".straight-jacket", "local", "private-key.json");
}

async function deriveEncryptionKey({ password, salt, kdf = KDF }) {
  return scryptAsync(password, salt, kdf.keyLength, {
    N: kdf.cost,
    r: kdf.blockSize,
    p: kdf.parallelization
  });
}
