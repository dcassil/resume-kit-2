#!/usr/bin/env sh
set -eu

changed_files="$(git diff --cached --name-only --diff-filter=ACMR || true)"

case "$changed_files" in
  *career-store/*|*tools/career_store_guardrails.py*|*tools/pre-commit-career-store-guardrails.sh*|*tests/contract/test_career_store*|*tests/boundary/test_career_store*)
    python3 tools/career_store_guardrails.py --root .
    ;;
esac
