import {
  addProtectedFile,
  addProtectedFiles,
  checkRepositorySetup,
  getRepositoryStatus,
  initRepository,
  installCi,
  installHook,
  isRepositoryInitialized,
  listProtectedFiles,
  removeProtectedFiles,
  renameProtectedFile,
  setupRepository,
  updateProtectedFiles,
  verifyRepository
} from "../index.js";
import { createCodedError } from "../core/errors.js";
import { buildHelp } from "./help.js";
import { parseArgs } from "./parse-args.js";
import { readMasterAndLocalPasswordConfirmation, readPassword, readSetupPasswords } from "./prompts.js";

export async function runCommand({ argv, cwd, stdin, stderr }) {
  const parsed = parseArgs(argv);
  const repoRoot = cwd;

  if (parsed.command === "help" || parsed.flags.help) {
    return {
      ok: true,
      help: buildHelp(parsed.command === "help" ? parsed.positional[0] : parsed.command)
    };
  }

  if (parsed.command === "init") {
    const { masterPassword, masterConfirmation, localPassword, localConfirmation } = await readMasterAndLocalPasswordConfirmation(stdin, stderr);
    if (masterPassword !== masterConfirmation) {
      throw createCodedError("INVALID_PASSWORD_CONFIRMATION", "Master password confirmation did not match");
    }
    if (localPassword !== localConfirmation) {
      throw createCodedError("INVALID_PASSWORD_CONFIRMATION", "Local password confirmation did not match");
    }
    return initRepository({ repoRoot, masterPassword, localPassword });
  }

  if (parsed.command === "setup") {
    if (parsed.flags.check) {
      return checkRepositorySetup({ repoRoot });
    }
    if (!await isRepositoryInitialized(repoRoot)) {
      const { masterPassword, masterConfirmation, localPassword, localConfirmation } = await readMasterAndLocalPasswordConfirmation(stdin, stderr);
      if (masterPassword !== masterConfirmation) {
        throw createCodedError("INVALID_PASSWORD_CONFIRMATION", "Master password confirmation did not match");
      }
      if (localPassword !== localConfirmation) {
        throw createCodedError("INVALID_PASSWORD_CONFIRMATION", "Local password confirmation did not match");
      }
      return setupRepository({ repoRoot, masterPassword, localPassword });
    }
    const { masterPassword, localPassword, localConfirmation } = await readSetupPasswords(stdin, stderr);
    if (localPassword !== localConfirmation) {
      throw createCodedError("INVALID_PASSWORD_CONFIRMATION", "Local password confirmation did not match");
    }
    return setupRepository({ repoRoot, masterPassword, localPassword });
  }

  if (parsed.command === "add") {
    const paths = allPositions(parsed, "add requires at least one path or pattern");
    const result = await addProtectedFiles({
      repoRoot,
      paths,
      password: await readPassword(stdin, stderr),
      reason: parsed.flags.reason
    });

    if (result.entries.length === 1) {
      return {
        ok: true,
        entry: result.entries[0],
        entries: result.entries
      };
    }

    return result;
  }

  if (parsed.command === "list") {
    return listProtectedFiles({ repoRoot });
  }

  if (parsed.command === "verify") {
    return verifyRepository({
      repoRoot,
      scope: parsed.flags.staged ? "staged" : "working-tree",
      ciKey: parsed.flags.ciKey
    });
  }

  if (parsed.command === "status") {
    return getRepositoryStatus({ repoRoot });
  }

  if (parsed.command === "install-hook") {
    return installHook({ repoRoot });
  }

  if (parsed.command === "install-ci") {
    return installCi({
      repoRoot,
      provider: parsed.flags.provider ?? "github-actions"
    });
  }

  if (parsed.command === "update") {
    const paths = allPositions(parsed, "update requires at least one path");
    const result = await updateProtectedFiles({
      repoRoot,
      paths,
      password: await readPassword(stdin, stderr)
    });

    if (result.entries.length === 1) {
      return {
        ok: true,
        entry: result.entries[0]
      };
    }

    return result;
  }

  if (parsed.command === "remove") {
    const paths = allPositions(parsed, "remove requires at least one path or pattern");
    const result = await removeProtectedFiles({
      repoRoot,
      paths,
      password: await readPassword(stdin, stderr)
    });

    if (result.removedPaths.length === 1) {
      return {
        ok: true,
        removedPath: result.removedPaths[0]
      };
    }

    return result;
  }

  if (parsed.command === "rename") {
    return renameProtectedFile({
      repoRoot,
      from: requiredPosition(parsed, 0, "rename requires an old path"),
      to: requiredPosition(parsed, 1, "rename requires a new path"),
      password: await readPassword(stdin, stderr)
    });
  }

  throw createCodedError("USAGE_ERROR", `Unknown command ${parsed.command}`);
}

function requiredPosition(parsed, index, message) {
  const value = parsed.positional[index];
  if (!value) {
    throw createCodedError("USAGE_ERROR", message);
  }
  return value;
}

function allPositions(parsed, message) {
  if (parsed.positional.length === 0) {
    throw createCodedError("USAGE_ERROR", message);
  }
  return parsed.positional;
}
