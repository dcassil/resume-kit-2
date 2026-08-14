const COMMAND_HELP = {
  init: {
    usage: "straight-jacket init [--json]",
    summary: "Initialize Straight Jacket metadata in the current Git repository.",
    details: [
      "Creates the protected-file manifest, signer registry, registration public key, encrypted registration key, and first local signer.",
      "Prompts for a master password and a local password. The master password registers users; the local password authorizes protected-file changes.",
      "Run this from the project root before adding protected files."
    ],
    examples: [
      "straight-jacket init",
      "straight-jacket init --json"
    ]
  },
  setup: {
    usage: "straight-jacket setup [--check] [--json]",
    summary: "Register this checkout's local signer or initialize a clean repository.",
    details: [
      "In a clean repository, prompts for a master password and a local password and initializes Straight Jacket.",
      "In a legacy repository with public-key metadata, verifies protected files first, then upgrades to the signer registry and CI proof format.",
      "In an initialized clone, verifies protected files first, then prompts for the master password and a new local password.",
      "The master password cannot authorize add, update, remove, or rename.",
      "--check is read-only and exits non-zero when local signer setup is missing or incomplete."
    ],
    examples: [
      "straight-jacket setup",
      "straight-jacket setup --check --json"
    ]
  },
  add: {
    usage: "straight-jacket add <path-or-pattern>... [--reason <text>] [--json]",
    summary: "Register one or more file paths and content checksums as human-protected.",
    details: [
      "Requires an initialized project and prompts for the local password.",
      "Accepts multiple paths and quoted glob patterns such as 'scripts/guardrails/*.mjs'.",
      "Rejects absolute paths, parent-directory escapes, symlinks, duplicates, and case-only path collisions.",
      "Directory checksums are not supported yet; protect files inside a directory with a pattern."
    ],
    examples: [
      "straight-jacket add docs/policy.md --reason \"Human-owned policy file\"",
      "straight-jacket add 'scripts/guardrails/*.mjs' --reason \"Guardrail scripts\"",
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
    usage: "straight-jacket verify [--staged] [--ci-key <sjci_v1_...>] [--json]",
    summary: "Verify signed metadata and protected file integrity.",
    details: [
      "Read-only. Exits 0 when verification passes and 1 when violations are found.",
      "--staged verifies staged Git content for pre-commit and CI-style checks.",
      "--ci-key verifies the committed CI proof against the GitHub Actions secret."
    ],
    examples: [
      "straight-jacket verify",
      "straight-jacket verify --staged --json",
      "straight-jacket verify --ci-key \"$STRAIGHT_JACKET_CI_KEY\""
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
    usage: "straight-jacket update <path>... [--json]",
    summary: "Accept the current content of one or more protected files as the new authorized checksums.",
    details: [
      "Requires an initialized project and prompts for the local password.",
      "Accepts multiple registered paths and re-signs the manifest once.",
      "Use only after the human approves the protected file content change."
    ],
    examples: [
      "straight-jacket update docs/policy.md",
      "straight-jacket update docs/policy.md prompts/system.md"
    ]
  },
  remove: {
    usage: "straight-jacket remove <path-or-pattern>... [--json]",
    summary: "Remove one or more protected entries from the signed manifest.",
    details: [
      "Requires an initialized project and prompts for the local password.",
      "Accepts multiple paths and quoted glob patterns matched against registered protected paths.",
      "Does not delete files; it removes Straight Jacket protection for matching paths."
    ],
    examples: [
      "straight-jacket remove docs/policy.md",
      "straight-jacket remove 'tools/pre-commit-*'"
    ]
  },
  rename: {
    usage: "straight-jacket rename <old-path> <new-path> [--json]",
    summary: "Authorize a protected path change.",
    details: [
      "Requires an initialized project and prompts for the local password.",
      "Moving or renaming a protected file without this command is reported as a verification violation."
    ],
    examples: [
      "straight-jacket rename docs/policy.md docs/policies/security.md"
    ]
  },
  "install-hook": {
    usage: "straight-jacket install-hook [--json]",
    summary: "Install the committed advisory pre-commit hook path.",
    details: [
      "Writes .githooks/pre-commit and configures Git core.hooksPath to .githooks.",
      "The hook checks local signer setup before running straight-jacket verify and straight-jacket verify --staged.",
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
      "The generated workflow verifies the committed CI proof with the STRAIGHT_JACKET_CI_KEY GitHub Actions secret."
    ],
    examples: [
      "straight-jacket install-ci",
      "straight-jacket install-ci --provider github-actions"
    ]
  }
};

const COMMAND_ORDER = [
  "init",
  "setup",
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
    "  straight-jacket setup",
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
    "  Master passwords register new local users; local passwords authorize protected-file changes.",
    "  Mutating protected-file commands prompt for the local password in the terminal.",
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
