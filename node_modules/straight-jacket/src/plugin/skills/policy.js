export function buildSkillPolicy() {
  return {
    requiredFirstChecks: [
      "straight-jacket list --json",
      "straight-jacket verify --json"
    ],
    setupGuidance: {
      cliMissing: "npm install -g github:dcassil/straight-jacket",
      projectNotInitialized: "straight-jacket setup",
      mcpNotConnected: "[mcp_servers.straight-jacket]",
      githubProtectionGuide: "docs/features/github-protection.md"
    },
    githubProtectionChecks: {
      requiredStatusCheck: "verify",
      requirePullRequestBeforeMerging: true,
      requireBranchesUpToDate: true,
      enforceAdmins: true,
      disableForcePushes: true,
      disableDeletions: true
    },
    forbiddenActions: [
      "edit .straight-jacket/manifest.json",
      "edit .straight-jacket/manifest.sig",
      "edit .straight-jacket/signers.json",
      "edit .straight-jacket/signers.sig",
      "edit .straight-jacket/registration-public-key.json",
      "edit .straight-jacket/registration-key.enc.json",
      "ask user for CI key in chat",
      "ask user for password in chat",
      "commit with --no-verify to bypass checks"
    ]
  };
}
