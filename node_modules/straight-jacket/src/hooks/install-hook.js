import { spawnSync } from "node:child_process";
import { chmod, mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { HOOKS_PATH, getHookStatus, preCommitHookPath } from "./status.js";

const START_MARKER = "# straight-jacket:start";
const END_MARKER = "# straight-jacket:end";
const HOOK_BODY = `if [ -f ".straight-jacket/manifest.json" ]; then
  if ! straight-jacket setup --check >/dev/null 2>&1; then
    echo "Straight Jacket local setup is missing or incomplete."
    echo "Run: straight-jacket setup"
    exit 1
  fi
fi
branch="$(git branch --show-current 2>/dev/null || true)"
verify_mode=""
if [ "$branch" != "main" ] && [ "$branch" != "master" ]; then
  verify_mode="--warn"
fi
straight-jacket verify $verify_mode && straight-jacket verify --staged $verify_mode`;

export async function installPreCommitHook({ repoRoot }) {
  const hookPath = await preCommitHookPath(repoRoot);
  const existingHook = await readHookIfPresent(hookPath);
  const nextHook = upsertHookBlock(existingHook);

  await mkdir(path.dirname(hookPath), { recursive: true });
  await writeFile(hookPath, nextHook, "utf8");
  await chmod(hookPath, 0o755);
  configureHooksPath(repoRoot);

  return {
    ok: true,
    hook: await getHookStatus({ repoRoot })
  };
}

function upsertHookBlock(existingHook) {
  const hookBlock = `${START_MARKER}\n${HOOK_BODY}\n${END_MARKER}`;
  const withoutDuplicateBlock = existingHook.replace(
    new RegExp(`${escapeRegExp(START_MARKER)}[\\s\\S]*?${escapeRegExp(END_MARKER)}\\n?`, "g"),
    ""
  );

  const prefix = withoutDuplicateBlock.length > 0
    ? trimTrailingNewlines(withoutDuplicateBlock)
    : "#!/bin/sh";

  return `${prefix}\n\n${hookBlock}\n`;
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

function trimTrailingNewlines(value) {
  return value.replace(/\n+$/g, "");
}

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function configureHooksPath(repoRoot) {
  const result = spawnSync("git", ["-C", repoRoot, "config", "core.hooksPath", HOOKS_PATH], {
    encoding: "utf8"
  });
  if (result.status !== 0) {
    throw new Error(`HOOKS_PATH_CONFIG_FAILED: ${result.stderr.trim()}`);
  }
}
