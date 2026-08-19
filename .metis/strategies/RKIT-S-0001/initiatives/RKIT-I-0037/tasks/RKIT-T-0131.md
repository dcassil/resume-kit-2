---
id: match-passthrough-and-decision
level: task
title: "Match passthrough and decision enforcement: full 4.3 MatchResult persistence, verbatim states, blocked/resolve_gaps mapping"
short_code: "RKIT-T-0131"
created_at: 2026-08-19T19:01:07.600274+00:00
updated_at: 2026-08-19T19:02:48.039698+00:00
parent: deterministic-match-resolve-and
blocked_by: []
archived: false

tags:
  - "#task"
  - "#phase/active"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0037
---

# Match passthrough and decision enforcement: full 4.3 MatchResult persistence, verbatim states, blocked/resolve_gaps mapping

## Parent Initiative **[CONDITIONAL: Assigned Task]**

[[RKIT-I-0037]]

## Objective **[REQUIRED]**

`resume match` must present and persist core's MatchResult verbatim and enforce its tri-state `decision`. Today `_match` (`resume-cli/resume_cli/__init__.py:606`) downgrades `related_match`/`possible_match` to `unknown`, rewrites per-requirement `status`, never consults `decision`/`hardRequirementsResolved`, and returns ok/0.0 even on an empty workspace. Delete the downgrade block; map `decision` to CLI behavior; honor `matching.requireHardRequirementsResolved`.

## Acceptance Criteria

## Acceptance Criteria **[REQUIRED]**

- [ ] The downgrade/rewrite block (`:616-619`) is deleted: persisted `reports/match.json` and stdout report carry byte-identical `resolution_state` values from `scoreMatch` output, including `related_match`, `possible_match`, and `not_applicable` (RKIT-A-0006 item 2 vocabulary). A report-fidelity test feeds a match result containing each state and asserts verbatim passthrough.
- [ ] Persisted match.json carries the full section-4.3 MatchResult fields: `score`, `threshold`, `hardRequirementsResolved`, `dimensions`, `requirement_results` (with per-requirement ResolutionState), tri-state `decision` — no renamed or synthesized fields (`requirements`/`unresolved` aliases may remain only as documented lossless additions if smoke depends on them; report which).
- [ ] Decision mapping enforced: `continue` → ok/0; `resolve_gaps` → ok/0 with a routing hint naming the core-selected unresolved requirement (from `getUnresolvedRequirements(match_result, config).selected_requirement` — do NOT re-implement selection); `blocked` → domain-failure exit (nonzero, I-0035 envelope error listing blocking requirement ids).
- [ ] With `matching.requireHardRequirementsResolved: true` and an unresolved required requirement, `resume match` exits nonzero with the blocked outcome — a test proves the policy is honored (TEST_SPEC match: "Blocks or routes to resolve when hard requirement policy demands it").
- [ ] Empty-workspace match (no ingested resume/job) is a typed failure (usage/domain error naming the missing artifact), not ok/0.0 — test included.
- [ ] Existing smoke/E2E stay green; expected match snapshots reviewed deliberately if churn occurs (regenerate ×2 no-drift). Note: smoke flows read `match.json` and downstream steps consume `unresolved` — verify what they need before removing aliases.
- [ ] Gates green: `--pr`, `--smoke`; new tests bridged per `test_tests_contract` pattern.

## Implementation Notes **[CONDITIONAL: Technical Task]**

### Technical Approach
- `scoreMatch` result already carries the 4.3 fields; `decide_match` (`resume_core/match_decision.py`) computes `decision` from score/threshold/hard_resolved/config — the CLI only maps, never recomputes.
- `getUnresolvedRequirements(match_result, policy)` (`resume_core/domain.py:473`) returns `unresolved_requirements`, `can_continue`, and ranked selection — use it for the resolve_gaps routing hint; full topic delegation for resolve is T-0132's, but the match-side hint should use the same call.
- Exit-code vocabulary from I-0035: 0 ok, 1 domain failure, 2 usage. Blocked → 1.
- `_record_latest_run_snapshot(workspace, "MATCH_BASE", ...)` must keep receiving the shape workflow expects — check its consumers before changing the persisted key set.

### Dependencies
None within the initiative (root task). I-0036/I-0002 landed surfaces.

### Risk Considerations
Snapshot churn in `fixtures/expected/*-match.json` is likely if persisted shape changes — prefer additive persistence (full 4.3 fields added; existing keys preserved) and review diffs semantically. The `status` rewrite deletion may break report renderers/tests that read `status` — migrate readers to `resolution_state`/`blocking`.

### Execution profile
Recommended Agent: opus + high

## Status Updates **[REQUIRED]**

*To be added during implementation*