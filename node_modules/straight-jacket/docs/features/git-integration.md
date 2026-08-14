# Git Integration Spec

## Purpose

Git integration reads repository state without becoming the security boundary.

Implementation folder:

```text
src/git/
```

## Responsibilities

Git helpers should:

- verify `repoRoot` is a Git repository root
- detect staged file status
- read staged blobs for protected paths
- detect staged deletions
- detect staged manifest, signature, signer registry, and registration public-key changes
- report hook installation status
- provide stable repo-root path handling

Git helpers should not:

- mutate protected manifests
- sign data
- prompt for passwords
- assume local hooks cannot be bypassed

## Repo Root Detection

Internal function:

```js
assertGitRepoRoot(repoRoot)
```

Rules:

- `repoRoot` must be absolute.
- `git -C <repoRoot> rev-parse --show-toplevel` must equal `repoRoot` after realpath normalization.
- If the folder is not a Git repo, return a clear `GIT_REPO_REQUIRED` error.

Current test helpers create temp Git repos, so implementation should support local temporary repos cleanly.

## Working Tree State

For `scope: "working-tree"`:

- use filesystem reads for protected files
- use `lstat` before reading to reject symlinks
- use recursive scan only for likely move/rename diagnostics

Likely rename detection:

- when a protected path is missing, scan tracked and untracked files under repo root
- skip `.git/`, `node_modules/`, and `.straight-jacket/local/`
- compute checksums looking for the missing entry checksum
- return `LIKELY_RENAME_OR_MOVE` for matching content at a different path

## Staged State

For `scope: "staged"`:

- use `git diff --cached --name-status --find-renames`
- detect deleted protected paths
- detect renamed protected paths
- inspect staged shared Straight Jacket metadata
- verify staged signer registry and manifest payloads when those files are staged

Useful commands:

```text
git diff --cached --name-status --find-renames
git show :docs/policy.md
git show :.straight-jacket/manifest.json
git show :.straight-jacket/manifest.sig
git show :.straight-jacket/signers.json
git show :.straight-jacket/signers.sig
git show :.straight-jacket/registration-public-key.json
```

If a protected file is staged as deleted:

```js
{
  code: "STAGED_PROTECTED_FILE_DELETED",
  path: "docs/policy.md"
}
```

If manifest is staged without a matching valid staged signature:

```js
{
  code: "STAGED_MANIFEST_SIGNATURE_INVALID",
  path: ".straight-jacket/manifest.json"
}
```

## Path Handling

All Git paths should be repo-relative and use `/`.

Rules:

- normalize Windows separators to `/`
- reject absolute paths
- reject `..` segments
- resolve candidate realpath under repo root
- reject path case collisions
- preserve exact casing in manifest output

## Hook Health

Internal function:

```js
getHookStatus(repoRoot)
```

Expected status shape:

```js
{
  installed: false,
  path: "/repo/.githooks/pre-commit",
  command: "straight-jacket setup --check && straight-jacket verify && straight-jacket verify --staged",
  hooksPath: ".githooks",
  configuredHooksPath: null
}
```

`status` must include:

```js
{
  enforcement: {
    localHookAdvisory: true,
    requiresExternalVerifierForStrongMode: true
  }
}
```

This prevents the CLI from overclaiming local hook strength.

## Internal API

Suggested functions:

- `assertGitRepoRoot(repoRoot)`
- `toRepoRelativePath(repoRoot, candidatePath)`
- `resolveRepoPath(repoRoot, relativePath)`
- `isRegularFileNoSymlink(repoRoot, relativePath)`
- `readWorkingTreeFile(repoRoot, relativePath)`
- `readStagedFile(repoRoot, relativePath)`
- `getStagedChanges(repoRoot)`
- `getHookStatus(repoRoot)`
- `scanForChecksum(repoRoot, checksum, ignoredDirectories)`

## Test Mapping

Primary tests:

- staged protected-file deletion
- staged manifest tampering
- move/rename detection
- symlink detection
- CLI hook health status
