import { installPreCommitHook } from "../hooks/install-hook.js";

export async function installHook({ repoRoot } = {}) {
  return installPreCommitHook({ repoRoot });
}
