import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

const WORKFLOW_PATH = ".github/workflows/straight-jacket.yml";

export async function installCi({ repoRoot, provider = "github-actions" } = {}) {
  if (provider !== "github-actions") {
    throw new Error("UNSUPPORTED_CI_PROVIDER");
  }

  await mkdir(path.join(repoRoot, ".github", "workflows"), { recursive: true });
  await writeFile(path.join(repoRoot, WORKFLOW_PATH), githubActionsWorkflow(), "utf8");

  return {
    ok: true,
    provider,
    path: WORKFLOW_PATH
  };
}

function githubActionsWorkflow() {
  return `name: Straight Jacket

on:
  pull_request:
  push:
    branches: [main]

jobs:
  verify:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 20
      - run: npm install -g straight-jacket
      - run: straight-jacket verify --ci-key "$STRAIGHT_JACKET_CI_KEY"
        env:
          STRAIGHT_JACKET_CI_KEY: \${{ secrets.STRAIGHT_JACKET_CI_KEY }}
`;
}
