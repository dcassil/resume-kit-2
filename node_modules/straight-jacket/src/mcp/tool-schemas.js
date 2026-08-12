export const toolSchemas = {
  listProtectedFiles: {
    name: "straight_jacket_list_protected_files",
    description: "Read-only list of Straight Jacket protected file metadata.",
    inputSchema: {
      type: "object",
      properties: {
        repoRoot: { type: "string" }
      },
      required: ["repoRoot"],
      additionalProperties: false
    }
  },
  verify: {
    name: "straight_jacket_verify",
    description: "Read-only verification of protected files and signed manifest state.",
    inputSchema: {
      type: "object",
      properties: {
        repoRoot: { type: "string" },
        scope: { type: "string", enum: ["working-tree", "staged"] }
      },
      required: ["repoRoot"],
      additionalProperties: false
    }
  },
  explainViolation: {
    name: "straight_jacket_explain_violation",
    description: "Explain a Straight Jacket violation with human-safe remediation instructions.",
    inputSchema: {
      type: "object",
      properties: {
        violation: {
          type: "object",
          properties: {
            code: { type: "string" },
            path: { type: "string" },
            expected: { type: "string" },
            actual: { type: "string" }
          },
          required: ["code"],
          additionalProperties: true
        }
      },
      required: ["violation"],
      additionalProperties: false
    }
  }
};
