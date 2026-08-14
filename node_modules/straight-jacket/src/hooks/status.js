import { readFile } from "node:fs/promises";
import { spawnSync } from "node:child_process";
import path from "node:path";

export const HOOKS_PATH = ".githooks";
export const PRE_COMMIT_COMMAND = "straight-jacket setup --check && straight-jacket verify [--warn on non-main branches] && straight-jacket verify --staged [--warn on non-main branches]";

export async function getHookStatus({ repoRoot }) {
  const hookPath = await preCommitHookPath(repoRoot);
  const hook = await readHookIfPresent(hookPath);
  const configuredHooksPath = getConfiguredHooksPath(repoRoot);

  return {
    installed: hook.includes("straight-jacket setup --check") &&
      hook.includes("straight-jacket verify") &&
      hook.includes("straight-jacket verify --staged") &&
      hook.includes("verify_mode=\"--warn\"") &&
      configuredHooksPath === HOOKS_PATH,
    path: hookPath,
    command: PRE_COMMIT_COMMAND,
    hooksPath: HOOKS_PATH,
    configuredHooksPath,
    localHookAdvisory: true
  };
}

export async function preCommitHookPath(repoRoot) {
  return path.join(repoRoot, HOOKS_PATH, "pre-commit");
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

function getConfiguredHooksPath(repoRoot) {
  const result = spawnSync("git", ["-C", repoRoot, "config", "--get", "core.hooksPath"], {
    encoding: "utf8"
  });
  if (result.status !== 0) {
    return null;
  }
  return result.stdout.trim() || null;
}
