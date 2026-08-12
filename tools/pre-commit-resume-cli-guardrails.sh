#!/usr/bin/env sh
set -eu

changed_files="$(git diff --cached --name-only --diff-filter=ACMR || true)"

case "$changed_files" in
  *resume-cli/*|*tools/resume_cli_guardrails.py*|*tools/pre-commit-resume-cli-guardrails.sh*|*tests/contract/test_resume_cli*|*tests/boundary/test_resume_cli*)
    python3 tools/resume_cli_guardrails.py --root .
    ;;
esac
