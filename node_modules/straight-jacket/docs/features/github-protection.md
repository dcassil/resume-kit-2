# GitHub Protection Setup

Straight Jacket is strongest when GitHub refuses to merge unverified protected-file changes. Local hooks help, but `git commit --no-verify` can bypass them. GitHub branch protection or repository rulesets must be the merge gate.

## Target State

Recommended GitHub setup:

- `main` requires pull requests before merging.
- `main` requires the `verify` status check.
- `main` requires branches to be up to date before merging.
- admins are included in enforcement.
- force pushes and branch deletion are disabled.
- `develop` exists as the integration branch, if the project uses one.
- `STRAIGHT_JACKET_CI_KEY` is stored as a GitHub Actions secret.

With this setup, a bad commit can still be pushed to an ordinary feature branch, but it cannot merge into `main`.

## Prerequisites

Run these from the repository root:

```sh
command -v gh
gh auth status
straight-jacket verify --json
```

If the GitHub CLI is missing, install it and authenticate before continuing. The token needs `repo` and `workflow` access for private repositories.

Install the verifier workflow if it does not exist:

```sh
straight-jacket install-ci
git add .github/workflows/straight-jacket.yml
git commit -m "Add Straight Jacket verifier workflow"
git push
```

## Store The CI Key

After `straight-jacket setup`, the CLI prints a CI key derived from the master password. This is not the master password and cannot unlock signing keys. Store only that generated value in GitHub Actions secrets.

```sh
gh secret set STRAIGHT_JACKET_CI_KEY
```

Paste the generated `sjci_v1_...` value when prompted. Never paste the master password into GitHub, and never ask an AI agent to handle the master password or CI key.

Check that the secret exists:

```sh
gh secret list
```

## Create `develop`

Create `develop` from the current remote `main` if it does not already exist:

```sh
git fetch origin main
git push origin origin/main:refs/heads/develop
```

## Protect `main`

Set `OWNER_REPO` to the GitHub repository in `owner/name` form:

```sh
OWNER_REPO="$(gh repo view --json nameWithOwner --jq .nameWithOwner)"
```

Apply branch protection:

```sh
gh api --method PUT "repos/$OWNER_REPO/branches/main/protection" --input - <<'JSON'
{
  "required_status_checks": {
    "strict": true,
    "contexts": [
      "verify"
    ]
  },
  "enforce_admins": true,
  "required_pull_request_reviews": {
    "dismiss_stale_reviews": false,
    "require_code_owner_reviews": false,
    "required_approving_review_count": 0,
    "require_last_push_approval": false
  },
  "restrictions": null,
  "required_linear_history": false,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "block_creations": false,
  "required_conversation_resolution": false,
  "lock_branch": false,
  "allow_fork_syncing": false
}
JSON
```

This requires PRs without requiring a reviewer. If the repository should also require human approval, change `required_approving_review_count` to `1`.

## Verify Protection

Confirm the important fields:

```sh
gh api "repos/$OWNER_REPO/branches/main/protection" --jq '{
  required_status_checks,
  required_pull_request_reviews,
  enforce_admins,
  allow_force_pushes,
  allow_deletions
}'
```

Expected:

- `required_status_checks.strict` is `true`.
- `required_status_checks.contexts` contains `verify`, or `checks` contains a `verify` check.
- `required_pull_request_reviews` is not `null`.
- `enforce_admins.enabled` is `true`.
- `allow_force_pushes.enabled` is `false`.
- `allow_deletions.enabled` is `false`.

## Optional: Protect `develop`

If `develop` is also a shared branch, apply a similar rule to `develop`. Many projects allow direct pushes to `develop` but keep `main` PR-only. Choose explicitly; do not assume local hooks protect shared branches.

## Agent Rules

Agents configuring GitHub protection must:

- verify Straight Jacket locally before making claims about protected state.
- use `gh api` or the GitHub UI/API to verify branch protection after changing it.
- never claim `main` is protected unless the remote protection readback confirms required PRs and required `verify`.
- never use `--no-verify`, remove hooks, or edit `.straight-jacket` metadata to make a protected-file change pass.
