export function explainViolation(violation) {
  return {
    ok: true,
    message: messageForViolation(violation)
  };
}

function messageForViolation(violation) {
  if (violation.code === "CHECKSUM_MISMATCH") {
    return `${violation.path} changed. Ask the human to run: straight-jacket update ${violation.path}`;
  }

  if (violation.code === "PROTECTED_FILE_MISSING") {
    return `${violation.path} is missing. Ask the human to restore it or run: straight-jacket remove ${violation.path}`;
  }

  if (violation.code === "LIKELY_RENAME_OR_MOVE") {
    return `${violation.path} appears moved. Ask the human to run: straight-jacket rename <old-path> <new-path>`;
  }

  return `${violation.code} requires human review before changing protected file state.`;
}
