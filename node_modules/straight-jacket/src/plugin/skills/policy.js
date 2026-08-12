export function buildSkillPolicy() {
  return {
    requiredFirstChecks: [
      "straight-jacket list --json",
      "straight-jacket verify --json"
    ],
    setupGuidance: {
      cliMissing: "npm install -g github:dcassil/straight-jacket",
      projectNotInitialized: "straight-jacket init",
      mcpNotConnected: "[mcp_servers.straight-jacket]"
    },
    forbiddenActions: [
      "edit .straight-jacket/manifest.json",
      "edit .straight-jacket/manifest.sig",
      "edit .straight-jacket/public-key.json",
      "ask user for password in chat",
      "commit with --no-verify to bypass checks"
    ]
  };
}
