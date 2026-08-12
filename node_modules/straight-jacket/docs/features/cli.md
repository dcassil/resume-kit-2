# CLI Spec

## Purpose

The CLI is the human-facing command surface and the authoritative local write path.

Entrypoints:

```text
src/cli.js
bin/straight-jacket
src/cli/
```

## Commands

Help:

```text
straight-jacket
straight-jacket --help
straight-jacket -h
straight-jacket help <command>
straight-jacket <command> --help
```

Read-only:

```text
straight-jacket list --json
straight-jacket status --json
straight-jacket verify --json
straight-jacket verify --staged --json
```

Mutating:

```text
straight-jacket init
straight-jacket add <path-or-pattern>... --reason "..."
straight-jacket remove <path-or-pattern>...
straight-jacket update <path>
straight-jacket rename <old-path> <new-path>
straight-jacket install-hook
straight-jacket install-ci
```

## JSON Output

JSON mode must emit only JSON to stdout.

Success shape:

```json
{
  "ok": true
}
```

Verification failure shape:

```json
{
  "ok": false,
  "checked": 1,
  "violations": []
}
```

Human text, progress, warnings, and prompts go to stderr when needed.

## Exit Codes

Suggested exit codes:

- `0`: success
- `1`: verification violations
- `2`: usage error
- `3`: authorization failure
- `4`: repo/config missing or invalid
- `5`: unexpected internal error

Contract tests currently assert only zero vs non-zero. Keep exact numeric codes stable once implemented.

## Prompt Handling

Mutating commands requiring signing authority should prompt on stdin/tty:

- `init`: prompt for password and confirmation
- `add`: prompt for password
- `remove`: prompt for password
- `update`: prompt for password
- `rename`: prompt for password

Interactive terminal prompts should be visible before waiting for input. Password values should not be accepted through flags, files, environment variables, or chat.

Forbidden:

- `--password`
- `--password-file`
- reading passwords from repo-local files
- default password environment variables

If a forbidden password source is provided, fail before touching repo state:

```json
{
  "ok": false,
  "error": {
    "code": "PASSWORD_SOURCE_NOT_ALLOWED",
    "message": "Passwords must be entered interactively."
  }
}
```

## Command Details

### `init`

Inputs:

- `--json`
- `--help`

Behavior:

- prompt for password twice
- call `initRepository`
- print fingerprint and paths

Help behavior:

- `straight-jacket init --help` exits 0
- prints usage, password prompt expectations, and setup context
- does not prompt or touch repo state

### `add`

Inputs:

- one or more path or glob-pattern arguments
- optional `--reason`
- `--json`

Behavior:

- prompt for password once
- call `addProtectedFiles`
- print registered entries
- accept shell-expanded path lists such as `tools/pre-commit-alpha tools/pre-commit-beta`
- expand quoted patterns such as `tools/pre-commit-*` repo-relative

### `remove`

Inputs:

- one or more path or glob-pattern arguments
- `--json`

Behavior:

- prompt for password once
- call `removeProtectedFiles`
- match quoted patterns against registered protected paths
- remove matching manifest entries without deleting files
- print `removedPath` for one removed entry and `removedPaths` for multiple removed entries

### `list`

Behavior:

- call `listProtectedFiles`
- never prompt
- never require private key

### `verify`

Inputs:

- `--staged`
- `--json`
- future `--trusted-public-key-fingerprint`

Behavior:

- call `verifyRepository`
- exit `0` on ok
- exit non-zero on violations

### `status`

Behavior:

- show manifest health
- show hook health
- show strong-mode reminder
- never imply local hooks are unbypassable

### `install-hook`

Behavior:

- call `installHook`
- write pre-commit hook template
- run full verification before staged verification in the hook
- mark executable
- do not require password

### `install-ci`

Inputs:

- `--provider github-actions`
- `--json`

Behavior:

- call `installCi`
- write `.github/workflows/straight-jacket.yml`
- include external fingerprint pinning guidance
- do not require password
- do not claim branch protection was configured

## Implementation Notes

Keep CLI thin:

- parser in `src/cli/parse-args.js`
- prompt helpers in `src/cli/prompts.js`
- output helpers in `src/cli/output.js`
- command dispatch in `src/cli/commands.js`
- executable wrapper in `src/cli.js`

Avoid large CLI frameworks for MVP unless argument parsing becomes painful.

## Test Mapping

Primary tests:

- `test/contract/cli.contract.test.mjs`
- guardrail check for forbidden password flags/sources
