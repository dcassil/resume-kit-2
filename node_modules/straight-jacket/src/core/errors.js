export function createCodedError(code, message, details = {}) {
  const error = new Error(`${code}: ${message}`);
  error.code = code;

  for (const [key, value] of Object.entries(details)) {
    error[key] = value;
  }

  return error;
}
