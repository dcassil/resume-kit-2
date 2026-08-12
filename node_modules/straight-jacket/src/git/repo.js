import { realpath } from "node:fs/promises";
import { spawnSync } from "node:child_process";
import path from "node:path";
import { createCodedError } from "../core/errors.js";

export async function assertGitRepoRoot(repoRoot) {
  if (typeof repoRoot !== "string" || !path.isAbsolute(repoRoot)) {
    throw createCodedError("GIT_REPO_REQUIRED", "repoRoot must be an absolute Git repository root");
  }

  const result = runGit(repoRoot, ["rev-parse", "--show-toplevel"]);
  if (result.status !== 0) {
    throw createCodedError("GIT_REPO_REQUIRED", "repoRoot must be a Git repository root");
  }

  const actualRoot = result.stdout.trim();
  const [expectedRealPath, actualRealPath] = await Promise.all([
    realpath(repoRoot),
    realpath(actualRoot)
  ]);

  if (expectedRealPath !== actualRealPath) {
    throw createCodedError("GIT_REPO_REQUIRED", "repoRoot must be the exact Git repository root");
  }

  return repoRoot;
}

export async function getGitDir(repoRoot) {
  await assertGitRepoRoot(repoRoot);
  const result = runGit(repoRoot, ["rev-parse", "--git-dir"]);
  if (result.status !== 0) {
    throw createCodedError("GIT_REPO_REQUIRED", "Could not read Git directory");
  }

  const gitDir = result.stdout.trim();
  return path.isAbsolute(gitDir) ? gitDir : path.join(repoRoot, gitDir);
}

function runGit(repoRoot, args) {
  return spawnSync("git", ["-C", repoRoot, ...args], {
    encoding: "utf8"
  });
}
