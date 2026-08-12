import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";

export const MANIFEST_PATH = ".straight-jacket/manifest.json";
export const SIGNATURE_PATH = ".straight-jacket/manifest.sig";
export const PUBLIC_KEY_PATH = ".straight-jacket/public-key.json";

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

export function manifestPath(repoRoot) {
  return path.join(repoRoot, MANIFEST_PATH);
}

export function signaturePath(repoRoot) {
  return path.join(repoRoot, SIGNATURE_PATH);
}

export function publicKeyPath(repoRoot) {
  return path.join(repoRoot, PUBLIC_KEY_PATH);
}

async function writeJsonFile(filePath, payload) {
  await mkdir(path.dirname(filePath), { recursive: true });
  await writeFile(filePath, `${JSON.stringify(payload, null, 2)}\n`, "utf8");
}
