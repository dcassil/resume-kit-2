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
    return result.violations.map((violation) => `${violation.code}: ${violation.message ?? ""}`.trim()).join("\n") + "\n";
  }

  return `${result.ok === false ? "failed" : "ok"}\n`;
}
