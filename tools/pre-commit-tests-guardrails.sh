#!/usr/bin/env sh
set -eu

changed_files="$(git diff --cached --name-only --diff-filter=ACMR || true)"

case "$changed_files" in
  *tests/*|*tools/tests_guardrails.py*|*tools/pre-commit-tests-guardrails.sh*)
    python3 tools/tests_guardrails.py --root .
    ;;
esac
