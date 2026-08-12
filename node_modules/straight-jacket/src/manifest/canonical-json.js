const UNSUPPORTED_VALUE_CODE = "CANONICAL_JSON_UNSUPPORTED_VALUE";

export function canonicalizeJson(value) {
  return JSON.stringify(normalizeForCanonicalJson(value));
}

function normalizeForCanonicalJson(value) {
  if (value === null) {
    return null;
  }

  if (Array.isArray(value)) {
    return value.map((item) => normalizeForCanonicalJson(item));
  }

  const valueType = typeof value;
  if (valueType === "string" || valueType === "boolean") {
    return value;
  }

  if (valueType === "number") {
    if (!Number.isFinite(value)) {
      throwUnsupportedValue();
    }
    return value;
  }

  if (valueType === "object") {
    const normalized = {};
    for (const key of Object.keys(value).sort()) {
      normalized[key] = normalizeForCanonicalJson(value[key]);
    }
    return normalized;
  }

  throwUnsupportedValue();
}

function throwUnsupportedValue() {
  throw new Error(UNSUPPORTED_VALUE_CODE);
}
