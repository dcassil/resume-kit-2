import { normalizeRepoPath } from "../git/paths.js";
import { createProtectedEntry, sortEntries } from "../manifest/entries.js";
import { validateEntrySet } from "../manifest/validation.js";
import { assertAuthorizedSigner } from "../signing/authorization.js";
import { createCodedError } from "./errors.js";
import { loadVerifiedManifest, signAndWriteManifest } from "./manifest-state.js";

export async function addProtectedFile({ repoRoot, path, password, reason, now } = {}) {
  const protectedPath = normalizeRepoPath(path);
  const { manifest } = await loadVerifiedManifest(repoRoot);
  const entrySetViolations = validateEntrySet([...manifest.entries, { path: protectedPath }]);
  if (entrySetViolations.length > 0) {
    throw createCodedError(entrySetViolations[0].code, "Protected path is already registered", {
      violations: entrySetViolations
    });
  }

  const signer = await assertAuthorizedSigner({ repoRoot, password });
  const entry = await createProtectedEntry({
    repoRoot,
    path: protectedPath,
    reason,
    now
  });
  const nextManifest = {
    ...manifest,
    entries: sortEntries([...manifest.entries, entry])
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
    entry
  };
}

export async function removeProtectedFile({ repoRoot, path, password, now } = {}) {
  const protectedPath = normalizeRepoPath(path);
  const { manifest } = await loadVerifiedManifest(repoRoot);
  const existingEntry = manifest.entries.find((entry) => entry.path === protectedPath);
  if (!existingEntry) {
    throw createCodedError("PROTECTED_PATH_NOT_REGISTERED", "Protected path is not registered");
  }

  const signer = await assertAuthorizedSigner({ repoRoot, password });
  const nextManifest = {
    ...manifest,
    entries: manifest.entries.filter((entry) => entry.path !== protectedPath)
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
    removedPath: protectedPath
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
