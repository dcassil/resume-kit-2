# Core Implementation Spec

## Purpose

`src/core/` owns domain orchestration. It coordinates manifest validation, signing authorization, Git state, hooks, and filesystem checks.

Core functions must not prompt, print, parse CLI flags, or expose MCP protocol details.

## Expected Files

```text
src/core/errors.js
src/core/violations.js
src/core/verification-result.js
src/core/init-repository.js
src/core/protected-files.js
src/core/verify-repository.js
src/core/status.js
src/core/install-ci.js
```

`src/index.js` should re-export public functions from these modules.

## Required Exports

From `src/core/errors.js`:

- `createCodedError(code, message, details)`

From `src/core/violations.js`:

- `createViolation(code, fields)`

From `src/core/verification-result.js`:

- `buildVerificationResult({ checked, violations })`

Public orchestration exports:

- `initRepository(input)`
- `addProtectedFile(input)`
- `removeProtectedFile(input)`
- `updateProtectedFile(input)`
- `updateProtectedFiles(input)`
- `renameProtectedFile(input)`
- `verifyRepository(input)`
- `listProtectedFiles(input)`
- `getRepositoryStatus(input)`
- `installHook(input)`
- `installCi(input)`

## Implementation Notes

- Validate `repoRoot` first for every public function.
- Verify the current manifest signature before every manifest mutation.
- Mutating functions throw coded errors for authorization/path problems.
- `verifyRepository` returns violation objects instead of throwing for tamper state.
- Return every useful violation instead of stopping at the first one.
- Keep output JSON-serializable.

## Violation Messages

`createViolation` should create stable messages for known codes. Minimum required messages:

- `CHECKSUM_MISMATCH`: `<path> checksum changed`
- `PROTECTED_FILE_MISSING`: `<path> is missing`
- `LIKELY_RENAME_OR_MOVE`: `<path> appears to contain a protected file moved from another path`
- `MANIFEST_MISSING`: `Straight Jacket manifest is missing`
- `MANIFEST_SIGNATURE_MISSING`: `Straight Jacket manifest signature is missing`
- `REGISTRATION_PUBLIC_KEY_MISSING`: `Straight Jacket registration public key is missing`

Unknown codes may use the code as a message, but should still preserve all fields.

## Test Targets

Primary:

```text
test/unit/core.test.mjs
test/contract/core-api.contract.test.mjs
test/security/tamper-vectors.contract.test.mjs
```
