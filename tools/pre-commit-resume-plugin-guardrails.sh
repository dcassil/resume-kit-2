#!/usr/bin/env sh
set -eu

changed_files="$(git diff --cached --name-only --diff-filter=ACMR || true)"

case "$changed_files" in
  *resume-plugin/*|*tools/resume_plugin_guardrails.py*|*tools/pre-commit-resume-plugin-guardrails.sh*|*tests/contract/test_resume_plugin*|*tests/boundary/test_resume_plugin*)
    python3 tools/resume_plugin_guardrails.py --root .
    ;;
esac
