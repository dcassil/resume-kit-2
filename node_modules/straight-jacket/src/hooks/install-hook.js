import { chmod, mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { PRE_COMMIT_COMMAND, getHookStatus, preCommitHookPath } from "./status.js";

const START_MARKER = "# straight-jacket:start";
const END_MARKER = "# straight-jacket:end";

export async function installPreCommitHook({ repoRoot }) {
  const hookPath = await preCommitHookPath(repoRoot);
  const existingHook = await readHookIfPresent(hookPath);
  const nextHook = upsertHookBlock(existingHook);

  await mkdir(path.dirname(hookPath), { recursive: true });
  await writeFile(hookPath, nextHook, "utf8");
  await chmod(hookPath, 0o755);

  return {
    ok: true,
    hook: await getHookStatus({ repoRoot })
  };
}

function upsertHookBlock(existingHook) {
  const hookBlock = `${START_MARKER}\n${PRE_COMMIT_COMMAND}\n${END_MARKER}`;
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
