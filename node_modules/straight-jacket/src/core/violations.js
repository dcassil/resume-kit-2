const VIOLATION_MESSAGES = {
  CHECKSUM_MISMATCH: ({ path }) => `${path} checksum changed`,
  CI_KEY_INVALID: () => "Straight Jacket CI key is invalid",
  CI_PROOF_INVALID: () => "Straight Jacket CI proof is invalid",
  CI_PROOF_MISSING: () => "Straight Jacket CI proof is missing",
  PROTECTED_FILE_MISSING: ({ path }) => `${path} is missing`,
  LIKELY_RENAME_OR_MOVE: ({ path }) => `${path} appears to contain a protected file moved from another path`,
  MANIFEST_INVALID: () => "Straight Jacket manifest is invalid",
  MANIFEST_MISSING: () => "Straight Jacket manifest is missing",
  MANIFEST_SIGNATURE_INVALID: () => "Straight Jacket manifest signature is invalid",
  MANIFEST_SIGNATURE_MISSING: () => "Straight Jacket manifest signature is missing",
  MANIFEST_SIGNER_NOT_REGISTERED: () => "Straight Jacket manifest signer is not registered",
  PUBLIC_KEY_INVALID: () => "Straight Jacket public key is invalid",
  PUBLIC_KEY_MISSING: () => "Straight Jacket public key is missing",
  REGISTRATION_PUBLIC_KEY_INVALID: () => "Straight Jacket registration public key is invalid",
  REGISTRATION_PUBLIC_KEY_MISSING: () => "Straight Jacket registration public key is missing",
  SIGNERS_INVALID: () => "Straight Jacket signer registry is invalid",
  SIGNERS_MISSING: () => "Straight Jacket signer registry is missing",
  SIGNERS_SIGNATURE_INVALID: () => "Straight Jacket signer registry signature is invalid",
  SIGNERS_SIGNATURE_MISSING: () => "Straight Jacket signer registry signature is missing",
  SIGNERS_VERSION_UNSUPPORTED: () => "Straight Jacket signer registry version is unsupported",
  SIGNERS_REPO_ID_INVALID: () => "Straight Jacket signer registry repository id is invalid",
  SIGNERS_REGISTRATION_KEY_INVALID: () => "Straight Jacket signer registry registration key is invalid",
  SIGNERS_LIST_INVALID: () => "Straight Jacket signer registry list is invalid",
  SIGNER_INVALID: () => "Straight Jacket signer record is invalid",
  SIGNER_ALGORITHM_NOT_ALLOWED: () => "Straight Jacket signer algorithm is not allowed",
  SIGNER_KEY_INVALID: () => "Straight Jacket signer key is invalid",
  SIGNER_KEY_MISMATCH: () => "Straight Jacket signer key does not match its fingerprint",
  SIGNER_PUBLIC_KEY_INVALID: () => "Straight Jacket signer public key is invalid",
  SIGNER_FINGERPRINT_INVALID: () => "Straight Jacket signer fingerprint is invalid",
  SIGNER_TIMESTAMP_INVALID: () => "Straight Jacket signer timestamp is invalid",
  SIGNER_ACTIVE_INVALID: () => "Straight Jacket signer active flag is invalid",
  DUPLICATE_SIGNER: () => "Straight Jacket signer registry contains a duplicate signer",
  STAGED_MANIFEST_SIGNATURE_INVALID: () => "Staged Straight Jacket metadata signature is invalid",
  STAGED_PROTECTED_FILE_DELETED: ({ path }) => `${path} is staged for deletion`
};

export function createViolation(code, fields = {}) {
  const messageFactory = VIOLATION_MESSAGES[code];
  return {
    code,
    ...fields,
    message: messageFactory ? messageFactory(fields) : code
  };
}
