import path from "node:path";
import { createCodedError } from "../core/errors.js";

export function normalizeRepoPath(candidatePath) {
  if (typeof candidatePath !== "string" || candidatePath.length === 0) {
    throw createCodedError("INVALID_PATH", "Path must be a non-empty string");
  }

  const slashPath = candidatePath.replaceAll("\\", "/");
  if (path.isAbsolute(slashPath)) {
    throw createCodedError("INVALID_PATH_ABSOLUTE", "Protected paths must be repository-relative");
  }

  const segments = slashPath.split("/");
  if (segments.includes("..")) {
    throw createCodedError("INVALID_PATH_ESCAPE", "Protected paths must not escape the repository root");
  }

  const normalized = path.posix.normalize(slashPath);
  if (normalized === "." || normalized.startsWith("../")) {
    throw createCodedError("INVALID_PATH_ESCAPE", "Protected paths must not escape the repository root");
  }

  return normalized;
}

export function resolveRepoPath(repoRoot, relativePath) {
  const normalizedPath = assertRepoRelativePath(relativePath);
  const resolved = path.resolve(repoRoot, normalizedPath);
  const rootWithSeparator = repoRoot.endsWith(path.sep) ? repoRoot : `${repoRoot}${path.sep}`;

  if (resolved !== repoRoot && !resolved.startsWith(rootWithSeparator)) {
    throw createCodedError("INVALID_PATH_ESCAPE", "Resolved path must stay under repository root");
  }

  return resolved;
}

export function assertRepoRelativePath(candidatePath) {
  return normalizeRepoPath(candidatePath);
}
