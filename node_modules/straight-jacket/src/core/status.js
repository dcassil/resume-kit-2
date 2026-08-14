import { getHookStatus } from "../hooks/status.js";
import { checkRepositorySetup } from "./setup-repository.js";
import { verifyRepository } from "./verify-repository.js";

export async function getRepositoryStatus({ repoRoot } = {}) {
  const verification = await verifyRepository({ repoRoot, scope: "working-tree" });
  return {
    ok: true,
    verification,
    hook: await getHookStatus({ repoRoot }),
    setup: await setupStatus({ repoRoot, verification }),
    enforcement: {
      localHookAdvisory: true,
      requiresExternalVerifierForStrongMode: true
    }
  };
}

async function setupStatus({ repoRoot, verification }) {
  if (!verification.ok) {
    return {
      localSignerRegistered: false,
      blockedByVerification: true
    };
  }

  try {
    const setup = await checkRepositorySetup({ repoRoot });
    return {
      localSignerRegistered: true,
      signerKeyId: setup.signerKeyId
    };
  } catch (error) {
    return {
      localSignerRegistered: false,
      error: {
        code: error.code ?? "SETUP_STATUS_FAILED",
        message: error.message
      }
    };
  }
}
