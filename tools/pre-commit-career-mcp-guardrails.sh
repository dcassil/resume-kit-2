#!/usr/bin/env sh
set -eu

changed_files="$(git diff --cached --name-only --diff-filter=ACMR || true)"

case "$changed_files" in
  *career-mcp/*|*tools/career_mcp_guardrails.py*|*tools/pre-commit-career-mcp-guardrails.sh*|*tests/contract/test_career_mcp*|*tests/boundary/test_career_mcp*)
    python3 tools/career_mcp_guardrails.py --root .
    ;;
esac
