---
id: inspect-from-persisted-artifacts
level: task
title: "Inspect from persisted artifacts with typed no_data; topic delegation to getUnresolvedRequirements"
short_code: "RKIT-T-0132"
created_at: 2026-08-19T19:01:07.671685+00:00
updated_at: 2026-08-20T20:32:52.159917+00:00
parent: deterministic-match-resolve-and
blocked_by: [RKIT-T-0131]
archived: false

tags:
  - "#task"
  - "#phase/active"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0037
---

# Inspect from persisted artifacts with typed no_data; topic delegation to getUnresolvedRequirements

## Parent Initiative **[CONDITIONAL: Assigned Task]**

[[RKIT-I-0037]]

## Objective **[REQUIRED]**

`inspect requirement <id>` must report only persisted, code-owned state. Today `_inspect_requirement` (`resume-cli/resume_cli/__init__.py:867-872`) fabricates `resolution_state: "exact_match" if requirement_id == "req_react" else "unknown"` — verified to return exact_match with no match ever run. Delete the fabrication; read persisted artifacts only. Also complete topic-selection delegation: `_resolution_context` must take its selected requirement from `resume_core.getUnresolvedRequirements` instead of the CLI's local ordering (`_resolution_priority`/`_topic_for_requirement` remnants — T-0130 de-fixture-ized them but they still re-implement selection the responsibility matrix assigns to core).

## Acceptance Criteria

## Acceptance Criteria **[REQUIRED]**

- [ ] `_inspect_requirement` returns: the persisted ResolutionState + supporting evidence refs from `reports/match.json` / resolution records / store facts by id when they exist; `{status: "no_data", exit_code: 0-or-documented}` typed result when absent. The `req_react` conditional is deleted. No code path can emit a resolution state core never computed — inspect-honesty test: fresh workspace, `inspect requirement req_react` → no_data.
- [ ] Subset assertion test: every state inspect ever outputs for a populated workspace is a member of the persisted core output's states (drives `cli_surface.json` must_not `invent_requirement_resolution` to testable).
- [ ] `_resolution_priority` and `_topic_for_requirement` are deleted; `_resolution_context` consumes `getUnresolvedRequirements(match_result, config)`'s ranked `selected_requirement` (and its topic/concept fields) verbatim. No CLI ordering/tie-breaking remains.
- [ ] Behavior parity check for smoke: the core-selected requirement for the smoke fixtures must drive the same AWS→GraphQL resolution order smoke expects, or smoke expectations are updated deliberately with the reasoning recorded in the status update.
- [ ] Other inspect subcommands (fact/checkpoint/etc. if present) audited for the same fabrication pattern; any found are converted to persisted-artifact reads (report what was found).
- [ ] Gates green: `--pr`, `--smoke`; new tests bridged per `test_tests_contract` pattern.

## Implementation Notes **[CONDITIONAL: Technical Task]**

### Technical Approach
- T-0131 lands full 4.3 persistence in match.json — inspect reads that artifact, never calls scoreMatch.
- `getUnresolvedRequirements` returns `unresolved_requirements` (ranked), `can_continue`; policy arg = section-13 config. Selection authority is core's — if its ranking differs from smoke's historical AWS-first order, that is core-owned behavior; adjust smoke fixtures/expectations, don't re-rank in the CLI.
- Store fact lookups by id go through existing public store surfaces (`searchFacts`/get) — no direct DB.

### Dependencies
RKIT-T-0131 (persisted full MatchResult to read).

### Risk Considerations
Smoke's resolve step depends on which requirement is selected first; if core ranking reorders, the scripted answers may mismatch. Verify the smoke sequence end-to-end before committing to expectation changes.

### Execution profile
Recommended Agent: opus + medium

## Status Updates **[REQUIRED]**

- 2026-08-20: Implemented persisted-only requirement inspect through `resume_cli._inspect`, returning `status: no_data`/`exit_code: 0` when `reports/match.json` has no persisted state. Removed CLI resolution priority/topic helpers and delegated `_resolution_context` to `resume_core.getUnresolvedRequirements`; empty core selection returns `status: no_unresolved`. Added bridged integration/unit tests and updated CLI TEST_SPEC/cli_surface metadata. Focused tests pass: `tests.integration.test_cli_inspect_requirement_integration`, `tests.unit.test_resume_cli_resolution_context_unit`, `tests.contract.test_resume_cli_contract`, `tests.contract.test_tests_contract`.
- 2026-08-20: Verification complete: `python3 tools/run_gate.py --pr --root .` passed 662 tests; `python3 tools/run_gate.py --smoke --root .` passed installed smoke. Snapshot regeneration run twice with zero diff between passes and no `fixtures/expected` baseline changes. Fresh-workspace probe for `inspect requirement req_react` returned `status: no_data`, `exit_code: 0`. Straight Jacket final verify still reports only the known pending `tools/resume_cli_guardrails.py` and `tools/resume_core_guardrails.py` checksum mismatches called out in the task.
