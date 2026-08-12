import { createHash } from "node:crypto";
import { lstat, readdir, readFile } from "node:fs/promises";
import path from "node:path";

const DEFAULT_IGNORED_DIRECTORIES = new Set([".git", "node_modules"]);

export async function scanForChecksum(repoRoot, checksum, options = {}) {
  const ignoredDirectories = new Set([
    ...DEFAULT_IGNORED_DIRECTORIES,
    ...(options.ignoredDirectories ?? [])
  ]);
  const matches = [];

  await scanDirectory({
    repoRoot,
    directory: repoRoot,
    checksum,
    ignoredDirectories,
    matches
  });

  return matches;
}

async function scanDirectory({ repoRoot, directory, checksum, ignoredDirectories, matches }) {
  const entries = await readdir(directory, { withFileTypes: true });

  for (const entry of entries) {
    const absolutePath = path.join(directory, entry.name);
    const relativePath = path.relative(repoRoot, absolutePath).replaceAll(path.sep, "/");

    if (entry.isDirectory()) {
      if (ignoredDirectories.has(entry.name) || relativePath === ".straight-jacket/local") {
        continue;
      }
      await scanDirectory({ repoRoot, directory: absolutePath, checksum, ignoredDirectories, matches });
      continue;
    }

    const stats = await lstat(absolutePath);
    if (!stats.isFile()) {
      continue;
    }

    const content = await readFile(absolutePath);
    const actual = `sha256:${createHash("sha256").update(content).digest("hex")}`;
    if (actual === checksum) {
      matches.push({ path: relativePath, checksum: actual });
    }
  }
}
