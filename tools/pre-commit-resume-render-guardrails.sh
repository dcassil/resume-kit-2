#!/usr/bin/env sh
set -eu

changed_files="$(git diff --cached --name-only --diff-filter=ACMR || true)"

case "$changed_files" in
  *resume-render/*|*tools/resume_render_guardrails.py*|*tools/pre-commit-resume-render-guardrails.sh*|*tests/contract/test_resume_render*|*tests/boundary/test_resume_render*)
    python3 tools/resume_render_guardrails.py --root .
    ;;
esac
