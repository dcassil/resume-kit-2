import { readdir } from "node:fs/promises";
import path from "node:path";
import { normalizeRepoPath } from "./paths.js";

const GLOB_MAGIC = /[*?\[]/;

export async function expandRepoPatterns(repoRoot, candidates) {
  const expanded = [];

  for (const candidate of candidates) {
    if (!hasGlobMagic(candidate)) {
      expanded.push(normalizeRepoPath(candidate));
      continue;
    }

    const pattern = normalizeGlobPattern(candidate);
    const matches = await matchRepoPattern(repoRoot, pattern);
    if (matches.length === 0) {
      throw new Error(`PATTERN_NO_MATCH: ${candidate}`);
    }
    expanded.push(...matches);
  }

  return uniqueSorted(expanded);
}

export function expandListedPatterns(candidates, availablePaths) {
  const expanded = [];

  for (const candidate of candidates) {
    if (!hasGlobMagic(candidate)) {
      expanded.push(normalizeRepoPath(candidate));
      continue;
    }

    const pattern = normalizeGlobPattern(candidate);
    const regex = globToRegExp(pattern);
    const matches = uniqueSorted(availablePaths.filter((availablePath) => regex.test(availablePath)));
    if (matches.length === 0) {
      throw new Error(`PATTERN_NO_MATCH: ${candidate}`);
    }
    expanded.push(...matches);
  }

  return uniqueSorted(expanded);
}

export function hasGlobMagic(candidate) {
  return typeof candidate === "string" && GLOB_MAGIC.test(candidate);
}

async function matchRepoPattern(repoRoot, pattern) {
  const regex = globToRegExp(pattern);
  const files = await listRepoFiles(repoRoot);
  return uniqueSorted(files.filter((file) => regex.test(file)));
}

async function listRepoFiles(repoRoot, directory = repoRoot) {
  const entries = await readdir(directory, { withFileTypes: true });
  const files = [];

  for (const entry of entries) {
    if (entry.name === ".git") {
      continue;
    }

    const absolutePath = path.join(directory, entry.name);
    const relativePath = path.relative(repoRoot, absolutePath).replaceAll(path.sep, "/");
    if (entry.isDirectory()) {
      files.push(...await listRepoFiles(repoRoot, absolutePath));
      continue;
    }
    if (entry.isFile()) {
      files.push(relativePath);
    }
  }

  return files;
}

function normalizeGlobPattern(pattern) {
  const slashPattern = pattern.replaceAll("\\", "/");
  if (path.isAbsolute(slashPattern) || slashPattern.split("/").includes("..")) {
    throw new Error("INVALID_PATH_ESCAPE");
  }
  return path.posix.normalize(slashPattern);
}

function globToRegExp(pattern) {
  let source = "^";

  for (let index = 0; index < pattern.length; index += 1) {
    const character = pattern[index];
    const next = pattern[index + 1];

    if (character === "*" && next === "*") {
      source += ".*";
      index += 1;
      continue;
    }
    if (character === "*") {
      source += "[^/]*";
      continue;
    }
    if (character === "?") {
      source += "[^/]";
      continue;
    }
    if (character === "[") {
      const end = pattern.indexOf("]", index + 1);
      if (end !== -1) {
        source += pattern.slice(index, end + 1);
        index = end;
        continue;
      }
    }

    source += escapeRegExp(character);
  }

  return new RegExp(`${source}$`);
}

function uniqueSorted(paths) {
  return [...new Set(paths)].sort((left, right) => left.localeCompare(right));
}

function escapeRegExp(value) {
  return value.replace(/[|\\{}()[\]^$+?.]/g, "\\$&");
}
