import { getHookStatus } from "../hooks/status.js";
import { verifyRepository } from "./verify-repository.js";

export async function getRepositoryStatus({ repoRoot } = {}) {
  return {
    ok: true,
    verification: await verifyRepository({ repoRoot, scope: "working-tree" }),
    hook: await getHookStatus({ repoRoot }),
    enforcement: {
      localHookAdvisory: true,
      requiresExternalVerifierForStrongMode: true
    }
  };
}
