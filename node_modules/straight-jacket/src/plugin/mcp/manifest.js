export function buildPluginMcpManifest() {
  return {
    tools: [
      {
        name: "straight_jacket_list_protected_files",
        access: "read-only"
      },
      {
        name: "straight_jacket_verify",
        access: "read-only"
      },
      {
        name: "straight_jacket_explain_violation",
        access: "read-only"
      }
    ]
  };
}
