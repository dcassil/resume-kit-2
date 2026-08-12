#!/usr/bin/env sh
set -eu

changed_files="$(git diff --cached --name-only --diff-filter=ACMR || true)"

case "$changed_files" in
  *tools/*|*tests/contract/test_tools*|*tests/boundary/test_tools*)
    python3 tools/tools_guardrails.py --root .
    ;;
esac
