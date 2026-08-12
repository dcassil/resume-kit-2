import { spawnSync } from "node:child_process";
import { normalizeRepoPath } from "./paths.js";

export async function getStagedChanges(repoRoot) {
  const result = runGit(repoRoot, ["diff", "--cached", "--name-status", "--find-renames"]);
  if (result.status !== 0) {
    throw new Error(`GIT_STAGED_READ_FAILED: ${result.stderr.trim()}`);
  }

  return result.stdout
    .split("\n")
    .filter(Boolean)
    .map(parseNameStatusLine);
}

export async function readStagedFile(repoRoot, relativePath) {
  const normalizedPath = normalizeRepoPath(relativePath);
  const result = runGit(repoRoot, ["show", `:${normalizedPath}`]);
  if (result.status !== 0) {
    return null;
  }

  return result.stdout;
}

function parseNameStatusLine(line) {
  const [statusCode, firstPath, secondPath] = line.split("\t");
  const statusType = statusCode.slice(0, 1);

  if (statusType === "R") {
    return {
      status: "renamed",
      oldPath: firstPath,
      path: secondPath
    };
  }

  return {
    status: statusFromCode(statusType),
    path: firstPath
  };
}

function statusFromCode(statusCode) {
  if (statusCode === "A") {
    return "added";
  }
  if (statusCode === "D") {
    return "deleted";
  }
  if (statusCode === "M") {
    return "modified";
  }
  return "changed";
}

function runGit(repoRoot, args) {
  return spawnSync("git", ["-C", repoRoot, ...args], {
    encoding: "utf8",
    maxBuffer: 10 * 1024 * 1024
  });
}
