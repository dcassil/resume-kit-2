import {
  addProtectedFile,
  addProtectedFiles,
  getRepositoryStatus,
  initRepository,
  installCi,
  installHook,
  listProtectedFiles,
  removeProtectedFiles,
  renameProtectedFile,
  updateProtectedFile,
  verifyRepository
} from "../index.js";
import { createCodedError } from "../core/errors.js";
import { buildHelp } from "./help.js";
import { parseArgs } from "./parse-args.js";
import { readPassword, readPasswordConfirmation } from "./prompts.js";

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
    const { password, confirmation } = await readPasswordConfirmation(stdin, stderr);
    if (password !== confirmation) {
      throw createCodedError("INVALID_PASSWORD_CONFIRMATION", "Password confirmation did not match");
    }
    return initRepository({ repoRoot, password });
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
      trustedPublicKeyFingerprint: parsed.flags.trustedPublicKeyFingerprint
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
    return updateProtectedFile({
      repoRoot,
      path: requiredPosition(parsed, 0, "update requires a path"),
      password: await readPassword(stdin, stderr)
    });
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
