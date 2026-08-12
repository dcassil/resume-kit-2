# CLI Implementation Spec

## Purpose

`src/cli/` owns command-line parsing, prompts, output formatting, and exit-code mapping.

It should stay thin. Domain behavior belongs in `src/core/`.

## Expected Files

```text
src/cli/parse-args.js
src/cli/output.js
src/cli/exit-codes.js
src/cli/prompts.js
src/cli/commands.js
src/cli.js
bin/straight-jacket
```

## Required Exports

From `parse-args.js`:

- `parseArgs(argv)`

From `output.js`:

- `formatOutput({ json, result })`
- `formatError({ json, error })`

From `exit-codes.js`:

- `exitCodeForResult(result)`
- `exitCodeForError(error)`

From `commands.js`:

- `runCommand({ argv, cwd, stdin, stdout, stderr })`

## Parser Rules

- Return `{ command, positional, flags }`.
- Support boolean flags: `--json`, `--staged`.
- Support value flags: `--reason`, `--provider`.
- Reject `--password` and `--password-file` with `PASSWORD_SOURCE_NOT_ALLOWED`.
- Do not read files or environment variables during parse.

## Prompt Rules

Prompt only for manifest-mutating commands:

- `init`
- `add`
- `remove`
- `update`
- `rename`

Do not prompt for:

- `list`
- `status`
- `verify`
- `install-hook`
- `install-ci`

## Output Rules

In JSON mode:

- stdout contains JSON only plus a trailing newline
- stderr is empty except prompts/errors before JSON mode is chosen

In human mode:

- keep messages concise
- violations must include stable codes

## Test Targets

Primary:

```text
test/unit/cli.test.mjs
test/contract/cli.contract.test.mjs
```
