import { readFile } from "node:fs/promises";
import path from "node:path";
import { getGitDir } from "../git/repo.js";

export const PRE_COMMIT_COMMAND = "straight-jacket verify && straight-jacket verify --staged";

export async function getHookStatus({ repoRoot }) {
  const hookPath = await preCommitHookPath(repoRoot);
  const hook = await readHookIfPresent(hookPath);

  return {
    installed: hook.includes(PRE_COMMIT_COMMAND),
    path: hookPath,
    command: PRE_COMMIT_COMMAND,
    localHookAdvisory: true
  };
}

export async function preCommitHookPath(repoRoot) {
  return path.join(await getGitDir(repoRoot), "hooks", "pre-commit");
}

async function readHookIfPresent(hookPath) {
  try {
    return await readFile(hookPath, "utf8");
  } catch (error) {
    if (error.code === "ENOENT") {
      return "";
    }
    throw error;
  }
}
