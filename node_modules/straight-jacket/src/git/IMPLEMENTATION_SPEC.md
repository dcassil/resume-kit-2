# Git Implementation Spec

## Purpose

`src/git/` reads Git repository and index state. It does not enforce security by itself and does not mutate signed manifests.

## Expected Files

```text
src/git/paths.js
src/git/repo.js
src/git/staged.js
src/git/scan.js
```

## Required Exports

From `paths.js`:

- `normalizeRepoPath(path)`
- `resolveRepoPath(repoRoot, relativePath)`
- `assertRepoRelativePath(path)`

From `repo.js`:

- `assertGitRepoRoot(repoRoot)`
- `getGitDir(repoRoot)`

From `staged.js`:

- `getStagedChanges(repoRoot)`
- `readStagedFile(repoRoot, relativePath)`

From `scan.js`:

- `scanForChecksum(repoRoot, checksum, options)`

## Path Rules

- Convert backslashes to `/`.
- Reject absolute paths with `INVALID_PATH_ABSOLUTE`.
- Reject `..` escapes with `INVALID_PATH_ESCAPE`.
- Resolve final paths under repo root.
- Preserve exact manifest casing after validation.

## Staged Change Shape

`getStagedChanges` should return:

```js
[
  { status: "modified", path: ".straight-jacket/manifest.json" },
  { status: "deleted", path: "docs/policy.md" },
  { status: "renamed", path: "docs/new.md", oldPath: "docs/old.md" }
]
```

Use stable lowercase status names for the rest of the implementation.

## Shelling Out

Use `child_process.spawn`/`spawnSync` with argument arrays. Do not build shell command strings from user paths.

## Test Targets

Primary:

```text
test/unit/git.test.mjs
test/security/tamper-vectors.contract.test.mjs
```
