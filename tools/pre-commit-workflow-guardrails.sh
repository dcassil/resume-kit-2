#!/usr/bin/env sh
set -eu

changed_files="$(git diff --cached --name-only --diff-filter=ACMR || true)"

case "$changed_files" in
  *workflow/*|*tools/workflow_guardrails.py*|*tools/pre-commit-workflow-guardrails.sh*|*tests/contract/test_workflow*|*tests/boundary/test_workflow*)
    python3 tools/workflow_guardrails.py --root .
    ;;
esac
