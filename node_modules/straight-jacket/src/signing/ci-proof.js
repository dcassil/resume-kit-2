import { createHmac, scrypt } from "node:crypto";
import { promisify } from "node:util";
import { canonicalizeJson } from "../manifest/canonical-json.js";

const scryptAsync = promisify(scrypt);
const CI_KEY_PREFIX = "sjci_v1_";
const CI_KEY_KDF = {
  name: "scrypt",
  salt: "straight-jacket-ci-v1",
  cost: 16384,
  blockSize: 8,
  parallelization: 1,
  keyLength: 32
};

export async function deriveCiKey({ masterPassword }) {
  const key = await deriveKeyBytes(masterPassword);
  const value = `${CI_KEY_PREFIX}${key.toString("base64url")}`;
  key.fill(0);
  return value;
}

export function createCiProof({ ciKey, registrationPublicKey, registrationKey, signerRegistry, signerRegistrySignature }) {
  return {
    version: 1,
    algorithm: "hmac-sha256",
    keyDerivation: {
      ...CI_KEY_KDF
    },
    covered: [
      "registration-public-key",
      "registration-key",
      "signers",
      "signers-signature"
    ],
    proof: hmacProof({
      ciKey,
      payload: proofPayload({
        registrationPublicKey,
        registrationKey,
        signerRegistry,
        signerRegistrySignature
      })
    })
  };
}

export function verifyCiProof({ ciKey, proof, registrationPublicKey, registrationKey, signerRegistry, signerRegistrySignature }) {
  if (!proof || proof.version !== 1 || proof.algorithm !== "hmac-sha256") {
    return false;
  }

  const expected = createCiProof({
    ciKey,
    registrationPublicKey,
    registrationKey,
    signerRegistry,
    signerRegistrySignature
  });

  return proof.proof === expected.proof;
}

export function ciSecretInstructions(ciKey) {
  return {
    secretName: "STRAIGHT_JACKET_CI_KEY",
    ciKey,
    warning: "Never give an AI agent your master password. Never paste the master password into GitHub. Only store this CI key as a GitHub Actions secret."
  };
}

function proofPayload({ registrationPublicKey, registrationKey, signerRegistry, signerRegistrySignature }) {
  return {
    registrationPublicKey,
    registrationKey,
    signerRegistry,
    signerRegistrySignature
  };
}

function hmacProof({ ciKey, payload }) {
  const key = ciKeyBytes(ciKey);
  try {
    return `sha256:${createHmac("sha256", key).update(canonicalizeJson(payload)).digest("hex")}`;
  } finally {
    key.fill(0);
  }
}

function ciKeyBytes(ciKey) {
  if (typeof ciKey !== "string" || !ciKey.startsWith(CI_KEY_PREFIX)) {
    throw new Error("CI_KEY_INVALID");
  }
  return Buffer.from(ciKey.slice(CI_KEY_PREFIX.length), "base64url");
}

async function deriveKeyBytes(masterPassword) {
  return scryptAsync(masterPassword, CI_KEY_KDF.salt, CI_KEY_KDF.keyLength, {
    N: CI_KEY_KDF.cost,
    r: CI_KEY_KDF.blockSize,
    p: CI_KEY_KDF.parallelization
  });
}
