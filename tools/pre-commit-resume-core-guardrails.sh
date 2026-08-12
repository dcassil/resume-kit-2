#!/usr/bin/env sh
set -eu

changed_files="$(git diff --cached --name-only --diff-filter=ACMR || true)"

case "$changed_files" in
  *resume-core/*|*tools/resume_core_guardrails.py*|*tools/pre-commit-resume-core-guardrails.sh*|*tests/contract/test_resume_core*|*tests/boundary/test_resume_core*)
    python3 tools/resume_core_guardrails.py --root .
    ;;
esac
