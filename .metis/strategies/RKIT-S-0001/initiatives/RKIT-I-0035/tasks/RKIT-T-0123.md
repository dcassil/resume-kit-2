---
id: real-resume-terminal-client-result
level: task
title: "Real resume terminal client: result envelope, entrypoint, stdout/stderr presentation, TerminalIO seam"
short_code: "RKIT-T-0123"
created_at: 2026-08-18T23:47:13.716402+00:00
updated_at: 2026-08-18T23:48:28.150201+00:00
parent: resume-cli-runtime-and-workspace
blocked_by: []
archived: false

tags:
  - "#task"
  - "#phase/active"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0035
---

# Real resume terminal client: result envelope, entrypoint, stdout/stderr presentation, TerminalIO seam

## Parent Initiative

[[RKIT-I-0035]]

## Objective

Ship the actual developer-facing `resume` terminal client (initiative plan steps 1–3): a shared result envelope + typed error taxonomy + exit-code mapping across existing commands; a `[project.scripts]` console entrypoint and `resume_cli/__main__.py` with human-readable stdout reports, typed stderr errors, and `--json` machine mode; and the `TerminalIO` interaction seam (interactive + deterministic scripted mode) that I-0037/I-0040 will consume. The library `main()` stays callable — one dispatch path.

## Acceptance Criteria

## Acceptance Criteria

- [ ] Result envelope: every existing command returns `{status, exit_code, artifacts, report, errors[]}` with `errors[]` entries carrying stable code, message, offending-input reference. Presentation renders the envelope — it never re-derives domain content. Exit codes: 0 success, 1 domain/validation failure, 2 usage/config error.
- [ ] Entrypoint: `[project.scripts] resume = "resume_cli.cli:main"` in resume-cli/pyproject.toml + `resume_cli/__main__.py` delegating to the same function; new `resume_cli/cli.py` presentation layer (argv parsing → existing dispatch → sectioned human-readable stdout report; `--json` emits the machine envelope; typed error records to stderr). The stdout/stderr discard at resume_cli/__init__.py:32 (verify current line) is REMOVED. The declared cli_surface.json entrypoint becomes true.
- [ ] Subprocess contract test: spawn the installed `resume` entrypoint (and `python -m resume_cli`) for `init` and `status`: assert stdout report content, stderr typed errors on a failure case, and all three exit codes. Timeout-guarded, hermetic (temp workspace). This closes the TEST_SPEC hole where "asks interactive terminal questions"/"shows reports" had no exercising case.
- [ ] TerminalIO seam: protocol `ask(question) -> answer`, `confirm(summary) -> bool`; interactive mode binds the TTY; scripted mode consumes a supplied answer stream (deterministic — scripted-mode determinism test). Injected into command dispatch; semantics for resolve stay I-0037 (seam + wiring only).
- [ ] resume-cli/TEST_SPEC.md strengthened: entrypoint subprocess cases named; terminal-IO seam described; strengthen-only. CHECK tools/resume_cli_guardrails.py + cli_surface.json pinning FIRST — if adding cli.py/__main__.py or the envelope trips a pinned surface, STOP that sub-change and defer verbatim (the entrypoint is already DECLARED in cli_surface.json, so making it real should align, not drift).
- [ ] Smoke/plugin compatibility: resume-plugin and smoke consume main() — the envelope change must keep them green (additive keys or coordinated updates to non-protected callers; run --smoke early).
- [ ] Gates green: `--pr`, `--smoke`, `--future-contract`. New tests bridged (state where). No protected edits.

## Implementation Notes

### Technical Approach
Keep cli.py purely presentational. The subprocess test should follow the career-mcp server test pattern (env/PYTHONPATH handling). Beware: pip-installed entrypoint may not exist in the repo checkout — the subprocess test can drive `python3 -m resume_cli` in-repo and assert the [project.scripts] declaration exists in pyproject; the installed-venv smoke exercises the real console script if feasible.

### Dependencies
None (first in the CLI chain).

### Risk Considerations
resume_cli/__init__.py is large and heavily contract-tested — envelope changes must be additive where existing tests pin shapes (strengthen-only realignment where they must move, RKIT-A-0006).

Recommended Agent: opus + high

## Status Updates

### 2026-08-18 implementation session
- Checked `tools/resume_cli_guardrails.py` and `resume-cli/cli_surface.json` before edits; pinned surface already declared `resume`, and the resume-cli guardrail passed.
- Ran `python3 tools/run_gate.py --smoke --root .` before edits and again after implementation; both passed.
- Implemented additive result envelope keys in `resume_cli.main()` results while preserving existing top-level DTO fields for current callers.
- Added `TerminalIO`, `InteractiveTerminalIO`, and deterministic `ScriptedTerminalIO`; `resolve` now consumes answers through the injected seam.
- Added `resume_cli.cli` and `resume_cli.__main__`; wired `[project.scripts] resume = "resume_cli.cli:main"` in root package metadata and package-local metadata.
- Strengthened `tests/contract/test_resume_cli_contract.py` with subprocess coverage for `python -m resume_cli`, JSON mode, typed stderr errors, exit codes 0/1/2, pyproject entrypoint declarations, and scripted terminal determinism.
- Strengthened `resume-cli/TEST_SPEC.md` with named entrypoint/envelope and TerminalIO cases.
- Gates run so far: focused unittest passed; smoke passed; PR passed; future-contract passed; installed `resume --json init` smoke passed.