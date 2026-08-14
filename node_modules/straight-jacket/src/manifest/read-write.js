import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";

export const MANIFEST_PATH = ".straight-jacket/manifest.json";
export const SIGNATURE_PATH = ".straight-jacket/manifest.sig";
export const PUBLIC_KEY_PATH = ".straight-jacket/public-key.json";
export const SIGNERS_PATH = ".straight-jacket/signers.json";
export const SIGNERS_SIGNATURE_PATH = ".straight-jacket/signers.sig";
export const REGISTRATION_PUBLIC_KEY_PATH = ".straight-jacket/registration-public-key.json";
export const REGISTRATION_KEY_PATH = ".straight-jacket/registration-key.enc.json";
export const CI_PROOF_PATH = ".straight-jacket/ci-proof.json";

export async function readManifest(repoRoot) {
  return JSON.parse(await readFile(manifestPath(repoRoot), "utf8"));
}

export async function writeManifest(repoRoot, manifest) {
  await writeJsonFile(manifestPath(repoRoot), manifest);
}

export async function readSignature(repoRoot) {
  return JSON.parse(await readFile(signaturePath(repoRoot), "utf8"));
}

export async function writeSignature(repoRoot, signature) {
  await writeJsonFile(signaturePath(repoRoot), signature);
}

export async function readPublicKey(repoRoot) {
  return JSON.parse(await readFile(publicKeyPath(repoRoot), "utf8"));
}

export async function writePublicKey(repoRoot, publicKey) {
  await writeJsonFile(publicKeyPath(repoRoot), publicKey);
}

export async function readSigners(repoRoot) {
  return JSON.parse(await readFile(signersPath(repoRoot), "utf8"));
}

export async function writeSigners(repoRoot, signers) {
  await writeJsonFile(signersPath(repoRoot), signers);
}

export async function readSignersSignature(repoRoot) {
  return JSON.parse(await readFile(signersSignaturePath(repoRoot), "utf8"));
}

export async function writeSignersSignature(repoRoot, signature) {
  await writeJsonFile(signersSignaturePath(repoRoot), signature);
}

export async function readRegistrationPublicKey(repoRoot) {
  return JSON.parse(await readFile(registrationPublicKeyPath(repoRoot), "utf8"));
}

export async function writeRegistrationPublicKey(repoRoot, publicKey) {
  await writeJsonFile(registrationPublicKeyPath(repoRoot), publicKey);
}

export async function readRegistrationKey(repoRoot) {
  return JSON.parse(await readFile(registrationKeyPath(repoRoot), "utf8"));
}

export async function writeRegistrationKey(repoRoot, encrypted) {
  await writeJsonFile(registrationKeyPath(repoRoot), encrypted);
}

export async function readCiProof(repoRoot) {
  return JSON.parse(await readFile(ciProofPath(repoRoot), "utf8"));
}

export async function writeCiProof(repoRoot, proof) {
  await writeJsonFile(ciProofPath(repoRoot), proof);
}

export function manifestPath(repoRoot) {
  return path.join(repoRoot, MANIFEST_PATH);
}

export function signaturePath(repoRoot) {
  return path.join(repoRoot, SIGNATURE_PATH);
}

export function publicKeyPath(repoRoot) {
  return path.join(repoRoot, PUBLIC_KEY_PATH);
}

export function signersPath(repoRoot) {
  return path.join(repoRoot, SIGNERS_PATH);
}

export function signersSignaturePath(repoRoot) {
  return path.join(repoRoot, SIGNERS_SIGNATURE_PATH);
}

export function registrationPublicKeyPath(repoRoot) {
  return path.join(repoRoot, REGISTRATION_PUBLIC_KEY_PATH);
}

export function registrationKeyPath(repoRoot) {
  return path.join(repoRoot, REGISTRATION_KEY_PATH);
}

export function ciProofPath(repoRoot) {
  return path.join(repoRoot, CI_PROOF_PATH);
}

async function writeJsonFile(filePath, payload) {
  await mkdir(path.dirname(filePath), { recursive: true });
  await writeFile(filePath, `${JSON.stringify(payload, null, 2)}\n`, "utf8");
}
