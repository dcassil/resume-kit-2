const COMMAND_HELP = {
  init: {
    usage: "straight-jacket init [--json]",
    summary: "Initialize Straight Jacket metadata in the current Git repository.",
    details: [
      "Creates .straight-jacket/manifest.json, .straight-jacket/manifest.sig, and .straight-jacket/public-key.json.",
      "Prompts for a human password twice. The password unlocks local signing material and is never stored in repo files.",
      "Run this from the project root before adding protected files."
    ],
    examples: [
      "straight-jacket init",
      "straight-jacket init --json"
    ]
  },
  add: {
    usage: "straight-jacket add <path> [--reason <text>] [--json]",
    summary: "Register a file path and content checksum as human-protected.",
    details: [
      "Requires an initialized project and prompts for the human password.",
      "Rejects absolute paths, parent-directory escapes, symlinks, duplicates, and case-only path collisions."
    ],
    examples: [
      "straight-jacket add docs/policy.md --reason \"Human-owned policy file\"",
      "straight-jacket add prompts/system.md --json"
    ]
  },
  list: {
    usage: "straight-jacket list [--json]",
    summary: "List protected files without requiring signing authority.",
    details: [
      "Read-only. Does not prompt for a password and never exposes private signing material."
    ],
    examples: [
      "straight-jacket list",
      "straight-jacket list --json"
    ]
  },
  verify: {
    usage: "straight-jacket verify [--staged] [--trusted-public-key-fingerprint <sha256:...>] [--json]",
    summary: "Verify signed metadata and protected file integrity.",
    details: [
      "Read-only. Exits 0 when verification passes and 1 when violations are found.",
      "--staged verifies staged Git content for pre-commit and CI-style checks.",
      "--trusted-public-key-fingerprint pins the expected public verifier fingerprint from external config."
    ],
    examples: [
      "straight-jacket verify",
      "straight-jacket verify --staged --json"
    ]
  },
  status: {
    usage: "straight-jacket status [--json]",
    summary: "Show verification health, hook status, and enforcement posture.",
    details: [
      "Read-only. Reports local hook status as advisory and reminds that strong mode needs an external verifier."
    ],
    examples: [
      "straight-jacket status",
      "straight-jacket status --json"
    ]
  },
  update: {
    usage: "straight-jacket update <path> [--json]",
    summary: "Accept the current content of a protected file as the new authorized checksum.",
    details: [
      "Requires an initialized project and prompts for the human password.",
      "Use only after the human approves the protected file content change."
    ],
    examples: [
      "straight-jacket update docs/policy.md"
    ]
  },
  remove: {
    usage: "straight-jacket remove <path> [--json]",
    summary: "Remove a protected entry from the signed manifest.",
    details: [
      "Requires an initialized project and prompts for the human password.",
      "Does not delete the file itself; it removes Straight Jacket protection for that path."
    ],
    examples: [
      "straight-jacket remove docs/policy.md"
    ]
  },
  rename: {
    usage: "straight-jacket rename <old-path> <new-path> [--json]",
    summary: "Authorize a protected path change.",
    details: [
      "Requires an initialized project and prompts for the human password.",
      "Moving or renaming a protected file without this command is reported as a verification violation."
    ],
    examples: [
      "straight-jacket rename docs/policy.md docs/policies/security.md"
    ]
  },
  "install-hook": {
    usage: "straight-jacket install-hook [--json]",
    summary: "Install the advisory local pre-commit hook.",
    details: [
      "Writes a hook that runs straight-jacket verify and straight-jacket verify --staged.",
      "Local hooks are useful friction, not the strong security boundary."
    ],
    examples: [
      "straight-jacket install-hook"
    ]
  },
  "install-ci": {
    usage: "straight-jacket install-ci [--provider github-actions] [--json]",
    summary: "Write a CI verifier template.",
    details: [
      "Currently supports --provider github-actions.",
      "The generated workflow includes guidance for externally pinned public-key fingerprints."
    ],
    examples: [
      "straight-jacket install-ci",
      "straight-jacket install-ci --provider github-actions"
    ]
  }
};

const COMMAND_ORDER = [
  "init",
  "add",
  "list",
  "verify",
  "status",
  "update",
  "remove",
  "rename",
  "install-hook",
  "install-ci"
];

export function buildHelp(topic) {
  if (topic) {
    return buildCommandHelp(topic);
  }

  return [
    "Straight Jacket protects human-owned repository files with signed metadata.",
    "",
    "Usage:",
    "  straight-jacket <command> [options]",
    "  straight-jacket --help",
    "  straight-jacket <command> --help",
    "",
    "Setup:",
    "  straight-jacket init",
    "  straight-jacket add <path> --reason \"Human-owned file\"",
    "  straight-jacket verify",
    "",
    "Commands:",
    ...COMMAND_ORDER.map((name) => `  ${name.padEnd(14)} ${COMMAND_HELP[name].summary}`),
    "",
    "Global options:",
    "  --json           Emit machine-readable JSON on stdout where supported.",
    "  -h, --help       Show help.",
    "",
    "Security notes:",
    "  Mutating commands prompt for the human password in the terminal.",
    "  Passwords are never accepted through --password, --password-file, env vars, or repo files.",
    "  Local hooks are advisory; strong enforcement requires CI or a server-side verifier.",
    "",
    "Run 'straight-jacket <command> --help' for command details."
  ].join("\n") + "\n";
}

function buildCommandHelp(topic) {
  const command = COMMAND_HELP[topic];
  if (!command) {
    return [
      `Unknown help topic: ${topic}`,
      "",
      "Run 'straight-jacket --help' to list commands."
    ].join("\n") + "\n";
  }

  return [
    command.summary,
    "",
    "Usage:",
    `  ${command.usage}`,
    "",
    "Details:",
    ...command.details.map((detail) => `  - ${detail}`),
    "",
    "Examples:",
    ...command.examples.map((example) => `  ${example}`)
  ].join("\n") + "\n";
}
