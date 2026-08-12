#!/usr/bin/env sh
set -eu

changed_files="$(git diff --cached --name-only --diff-filter=ACMR || true)"

case "$changed_files" in
  *resume-agent/*|*tools/resume_agent_guardrails.py*|*tools/pre-commit-resume-agent-guardrails.sh*|*tests/contract/test_resume_agent*|*tests/boundary/test_resume_agent*)
    python3 tools/resume_agent_guardrails.py --root .
    ;;
esac
