# Hooks Implementation Spec

## Purpose

`src/hooks/` installs and inspects advisory local Git hooks.

Local hooks are convenience checks, not the strong enforcement boundary.

## Expected Files

```text
src/hooks/install-hook.js
src/hooks/status.js
```

## Required Exports

From `install-hook.js`:

- `installPreCommitHook({ repoRoot })`

From `status.js`:

- `getHookStatus({ repoRoot })`

Core may wrap these as:

- `installHook(input)`
- `getRepositoryStatus(input)`

## Hook Content

Required command:

```text
straight-jacket verify && straight-jacket verify --staged
```

Required markers:

```text
# straight-jacket:start
# straight-jacket:end
```

Installer must be idempotent. Running it repeatedly should not duplicate the marked block.

## Status Shape

`getHookStatus` should return:

```js
{
  installed: false,
  path: "/repo/.git/hooks/pre-commit",
  command: "straight-jacket verify --staged",
  localHookAdvisory: true
}
```

## Test Targets

Primary:

```text
test/unit/hooks.test.mjs
test/contract/cli.contract.test.mjs
```
