export function buildVerificationResult({ checked, violations }) {
  return {
    ok: violations.length === 0,
    checked,
    violations
  };
}
