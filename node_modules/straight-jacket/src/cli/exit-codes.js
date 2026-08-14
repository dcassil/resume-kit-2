const AUTHORIZATION_ERROR_CODES = new Set(["INVALID_PASSWORD", "REGISTRATION_KEY_MISSING", "REGISTRATION_KEY_MISMATCH", "SIGNING_KEY_MISSING", "SIGNING_KEY_MISMATCH", "SIGNER_NOT_REGISTERED"]);
const CONFIG_ERROR_CODES = new Set(["GIT_REPO_REQUIRED", "LOCAL_SIGNER_MISSING", "LOCAL_SIGNER_NOT_REGISTERED", "MANIFEST_MISSING", "PUBLIC_KEY_MISSING", "REGISTRATION_PUBLIC_KEY_MISSING", "REPOSITORY_ALREADY_INITIALIZED", "SIGNERS_MISSING"]);

export function exitCodeForResult(result) {
  return result.ok ? 0 : 1;
}

export function exitCodeForError(error) {
  if (error.code === "USAGE_ERROR" || error.code === "PASSWORD_SOURCE_NOT_ALLOWED") {
    return 2;
  }

  if (AUTHORIZATION_ERROR_CODES.has(error.code)) {
    return 3;
  }

  if (CONFIG_ERROR_CODES.has(error.code)) {
    return 4;
  }

  return 5;
}
