export function formatOutput({ json, result }) {
  if (json) {
    return {
      stdout: `${JSON.stringify(result)}\n`,
      stderr: ""
    };
  }

  return {
    stdout: humanOutput(result),
    stderr: ""
  };
}

export function formatError({ json, error }) {
  const payload = {
    ok: false,
    error: {
      code: error.code ?? "INTERNAL_ERROR",
      message: error.message
    }
  };

  if (json) {
    return {
      stdout: `${JSON.stringify(payload)}\n`,
      stderr: ""
    };
  }

  return {
    stdout: "",
    stderr: `${payload.error.message}\n`
  };
}

function humanOutput(result) {
  if (typeof result.help === "string") {
    return result.help;
  }

  if (result.ok === false && Array.isArray(result.violations)) {
    return humanVerificationFailure(result.violations, { warn: result.warn === true });
  }

  if (result.ok === true && result.ci?.ciKey) {
    return humanCiSetupOutput(result);
  }

  return `${result.ok === false ? "failed" : "ok"}\n`;
}

function humanCiSetupOutput(result) {
  return [
    "ok",
    "",
    "GitHub Actions CI setup:",
    `Create a repository secret named ${result.ci.secretName} with this value:`,
    result.ci.ciKey,
    "",
    result.ci.warning
  ].join("\n") + "\n";
}

function humanVerificationFailure(violations, { warn = false } = {}) {
  const lockedPaths = uniqueSorted(violations.flatMap(lockedPathsForViolation));
  const lines = [
    "Straight Jacket verification failed.",
    ""
  ];

  if (lockedPaths.length > 0) {
    lines.push("Locked files:");
    for (const lockedPath of lockedPaths) {
      lines.push(`- ${lockedPath}`);
    }
    lines.push("");
  }

  lines.push("Violations:");
  for (const violation of violations) {
    lines.push(`- ${violation.code}${violation.path ? ` ${violation.path}` : ""}: ${violation.message ?? violation.code}`);
  }

  const updatePaths = uniqueSorted(violations.flatMap(updatePathsForViolation));
  const removePaths = uniqueSorted(violations.flatMap(removePathsForViolation));
  const renameCommands = uniqueSorted(violations.flatMap(renameCommandsForViolation));
  if (updatePaths.length > 0 || removePaths.length > 0 || renameCommands.length > 0) {
    lines.push("");
    lines.push("Human authorization required:");
    if (updatePaths.length > 0) {
      lines.push("If the protected content changes are approved, a human needs to run:");
      lines.push(`  straight-jacket update ${updatePaths.map(shellQuote).join(" ")}`);
    }
    if (removePaths.length > 0) {
      lines.push("If the protected files were intentionally removed, a human needs to run:");
      for (const protectedPath of removePaths) {
        lines.push(`  straight-jacket remove ${shellQuote(protectedPath)}`);
      }
    }
    if (renameCommands.length > 0) {
      lines.push("If the protected files were intentionally moved, a human needs to run:");
      for (const command of renameCommands) {
        lines.push(`  ${command}`);
      }
    }
  }

  if (warn) {
    lines.push("");
    lines.push("Warning mode: this command did not fail, but before a PR to a protected branch will pass the locked changes must be approved.");
  }

  return `${lines.join("\n")}\n`;
}

function lockedPathsForViolation(violation) {
  if (violation.expectedPath) {
    return [violation.expectedPath];
  }
  if (violation.path) {
    return [violation.path];
  }
  return [];
}

function updatePathsForViolation(violation) {
  if (violation.code === "CHECKSUM_MISMATCH") {
    return [violation.path];
  }
  return [];
}

function removePathsForViolation(violation) {
  if (violation.code === "PROTECTED_FILE_MISSING" || violation.code === "STAGED_PROTECTED_FILE_DELETED") {
    return [violation.path];
  }
  return [];
}

function renameCommandsForViolation(violation) {
  if (violation.code === "LIKELY_RENAME_OR_MOVE" && violation.expectedPath && violation.path) {
    return [`straight-jacket rename ${shellQuote(violation.expectedPath)} ${shellQuote(violation.path)}`];
  }
  return [];
}

function uniqueSorted(values) {
  return [...new Set(values.filter(Boolean))].sort((left, right) => left.localeCompare(right));
}

function shellQuote(value) {
  if (/^[A-Za-z0-9_./:@%+=,-]+$/.test(value)) {
    return value;
  }
  return `'${value.replaceAll("'", "'\\''")}'`;
}
