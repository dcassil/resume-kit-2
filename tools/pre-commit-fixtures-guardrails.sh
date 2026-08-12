#!/usr/bin/env sh
set -eu

changed_files="$(git diff --cached --name-only --diff-filter=ACMR || true)"

case "$changed_files" in
  *fixtures/*|*tools/fixtures_guardrails.py*|*tools/pre-commit-fixtures-guardrails.sh*|*tests/contract/test_fixtures*|*tests/boundary/test_fixtures*)
    python3 tools/fixtures_guardrails.py --root .
    ;;
esac
