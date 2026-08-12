import { normalizeRepoPath } from "../git/paths.js";
import { expandListedPatterns, expandRepoPatterns } from "../git/glob.js";
import { createProtectedEntry, sortEntries } from "../manifest/entries.js";
import { validateEntrySet } from "../manifest/validation.js";
import { assertAuthorizedSigner } from "../signing/authorization.js";
import { createCodedError } from "./errors.js";
import { loadVerifiedManifest, signAndWriteManifest } from "./manifest-state.js";

export async function addProtectedFile({ repoRoot, path, password, reason, now } = {}) {
  const result = await addProtectedFiles({
    repoRoot,
    paths: [path],
    password,
    reason,
    now
  });

  return {
    ok: true,
    entry: result.entries[0]
  };
}

export async function addProtectedFiles({ repoRoot, paths, password, reason, now } = {}) {
  if (!Array.isArray(paths) || paths.length === 0) {
    throw createCodedError("USAGE_ERROR", "add requires at least one path or pattern");
  }

  const protectedPaths = await expandRepoPatterns(repoRoot, paths);
  const { manifest } = await loadVerifiedManifest(repoRoot);
  const entrySetViolations = validateEntrySet([
    ...manifest.entries,
    ...protectedPaths.map((protectedPath) => ({ path: protectedPath }))
  ]);
  if (entrySetViolations.length > 0) {
    throw createCodedError(entrySetViolations[0].code, "Protected path is already registered", {
      violations: entrySetViolations
    });
  }

  const signer = await assertAuthorizedSigner({ repoRoot, password });
  const entries = [];
  for (const protectedPath of protectedPaths) {
    entries.push(await createProtectedEntry({
      repoRoot,
      path: protectedPath,
      reason,
      now
    }));
  }

  const nextManifest = {
    ...manifest,
    entries: sortEntries([...manifest.entries, ...entries])
  };

  await signAndWriteManifest({
    repoRoot,
    manifest: nextManifest,
    privateKey: signer.privateKey,
    keyId: signer.keyId,
    now
  });

  return {
    ok: true,
    entries
  };
}

export async function removeProtectedFile({ repoRoot, path, password, now } = {}) {
  const result = await removeProtectedFiles({
    repoRoot,
    paths: [path],
    password,
    now
  });

  return {
    ok: true,
    removedPath: result.removedPaths[0]
  };
}

export async function removeProtectedFiles({ repoRoot, paths, password, now } = {}) {
  if (!Array.isArray(paths) || paths.length === 0) {
    throw createCodedError("USAGE_ERROR", "remove requires at least one path or pattern");
  }

  const { manifest } = await loadVerifiedManifest(repoRoot);
  const protectedPaths = expandListedPatterns(paths, manifest.entries.map((entry) => entry.path));
  const registeredPaths = new Set(manifest.entries.map((entry) => entry.path));
  const missingPath = protectedPaths.find((protectedPath) => !registeredPaths.has(protectedPath));
  if (missingPath) {
    throw createCodedError("PROTECTED_PATH_NOT_REGISTERED", "Protected path is not registered");
  }

  const signer = await assertAuthorizedSigner({ repoRoot, password });
  const removedPathSet = new Set(protectedPaths);
  const nextManifest = {
    ...manifest,
    entries: manifest.entries.filter((entry) => !removedPathSet.has(entry.path))
  };

  await signAndWriteManifest({
    repoRoot,
    manifest: nextManifest,
    privateKey: signer.privateKey,
    keyId: signer.keyId,
    now
  });

  return {
    ok: true,
    removedPaths: protectedPaths
  };
}

export async function updateProtectedFile({ repoRoot, path, password, now } = {}) {
  const protectedPath = normalizeRepoPath(path);
  const { manifest } = await loadVerifiedManifest(repoRoot);
  const existingEntry = manifest.entries.find((entry) => entry.path === protectedPath);
  if (!existingEntry) {
    throw createCodedError("PROTECTED_PATH_NOT_REGISTERED", "Protected path is not registered");
  }

  const signer = await assertAuthorizedSigner({ repoRoot, password });
  const updatedEntry = await createProtectedEntry({
    repoRoot,
    path: protectedPath,
    reason: existingEntry.reason,
    now
  });
  const nextManifest = {
    ...manifest,
    entries: sortEntries(manifest.entries.map((entry) => entry.path === protectedPath ? updatedEntry : entry))
  };

  await signAndWriteManifest({
    repoRoot,
    manifest: nextManifest,
    privateKey: signer.privateKey,
    keyId: signer.keyId,
    now
  });

  return {
    ok: true,
    entry: updatedEntry
  };
}

export async function renameProtectedFile({ repoRoot, from, to, password, now } = {}) {
  const fromPath = normalizeRepoPath(from);
  const toPath = normalizeRepoPath(to);
  const { manifest } = await loadVerifiedManifest(repoRoot);
  const existingEntry = manifest.entries.find((entry) => entry.path === fromPath);
  if (!existingEntry) {
    throw createCodedError("PROTECTED_PATH_NOT_REGISTERED", "Protected path is not registered");
  }

  const retainedEntries = manifest.entries.filter((entry) => entry.path !== fromPath);
  const entrySetViolations = validateEntrySet([...retainedEntries, { path: toPath }]);
  if (entrySetViolations.length > 0) {
    throw createCodedError(entrySetViolations[0].code, "Protected path conflicts with an existing entry", {
      violations: entrySetViolations
    });
  }

  const signer = await assertAuthorizedSigner({ repoRoot, password });
  const renamedEntry = await createProtectedEntry({
    repoRoot,
    path: toPath,
    reason: existingEntry.reason,
    now
  });
  const nextManifest = {
    ...manifest,
    entries: sortEntries([...retainedEntries, renamedEntry])
  };

  await signAndWriteManifest({
    repoRoot,
    manifest: nextManifest,
    privateKey: signer.privateKey,
    keyId: signer.keyId,
    now
  });

  return {
    ok: true,
    from: fromPath,
    to: toPath,
    entry: renamedEntry
  };
}
