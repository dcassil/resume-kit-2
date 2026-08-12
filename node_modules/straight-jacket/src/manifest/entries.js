import { createHash } from "node:crypto";
import { lstat, readFile } from "node:fs/promises";
import nodePath from "node:path";

export function sortEntries(entries) {
  return [...entries].sort((left, right) => compareEntryPaths(left.path, right.path));
}

export async function createProtectedEntry({ repoRoot, path: protectedPath, reason, now }) {
  const normalizedPath = normalizeManifestPath(protectedPath);
  const absolutePath = nodePath.join(repoRoot, normalizedPath);
  const stats = await lstat(absolutePath);

  if (stats.isSymbolicLink()) {
    throw new Error("SYMLINK_NOT_ALLOWED");
  }

  const content = await readFile(absolutePath);
  const entry = {
    path: normalizedPath,
    name: nodePath.posix.basename(normalizedPath),
    checksum: `sha256:${createHash("sha256").update(content).digest("hex")}`,
    size: stats.size,
    registeredAt: timestampFrom(now)
  };

  if (reason !== undefined) {
    entry.reason = reason;
  }

  return entry;
}

export function normalizeManifestPath(protectedPath) {
  if (typeof protectedPath !== "string" || protectedPath.length === 0) {
    throw new Error("INVALID_PROTECTED_PATH");
  }

  const slashPath = protectedPath.replaceAll("\\", "/");
  if (nodePath.isAbsolute(slashPath) || slashPath.split("/").includes("..")) {
    throw new Error("INVALID_PROTECTED_PATH");
  }

  const normalized = nodePath.posix.normalize(slashPath);
  if (normalized === "." || normalized.startsWith("../")) {
    throw new Error("INVALID_PROTECTED_PATH");
  }

  return normalized;
}

function compareEntryPaths(leftPath, rightPath) {
  const leftNormalized = leftPath.toLowerCase();
  const rightNormalized = rightPath.toLowerCase();
  if (leftNormalized < rightNormalized) {
    return -1;
  }
  if (leftNormalized > rightNormalized) {
    return 1;
  }
  return leftPath.localeCompare(rightPath);
}

function timestampFrom(now) {
  if (now instanceof Date) {
    return now.toISOString();
  }
  if (typeof now === "string") {
    return new Date(now).toISOString();
  }
  return new Date().toISOString();
}
