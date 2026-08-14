---
id: operation-lifecycle-enforcement
level: task
title: "Operation lifecycle enforcement: mandatory fields, verb semantics, status machine"
short_code: "RKIT-T-0034"
created_at: 2026-08-14T22:54:23.763323+00:00
updated_at: 2026-08-14T23:08:16.622828+00:00
parent: resume-core-grounded-change
blocked_by: []
archived: false

tags:
  - "#task"
  - "#phase/completed"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0004
---

# Operation lifecycle enforcement: mandatory fields, verb semantics, status machine

## Parent Initiative

[[RKIT-I-0004]]

## Objective

Enforce the section 4.5 operation lifecycle in `resume-core`: `validateChange` rejects operations missing `reason`, `linked_requirement_ids`, `linked_fact_ids`, or `provenance`; the full status machine (proposed → validated → applied → accepted/modified, validated → rejected, invalid transitions are typed errors) is implemented; all five verbs (replace/rewrite/insert/remove/move) have defined, tested apply semantics; and `applyChange` refuses operations missing mandatory fields (RKIT-I-0004 Requirement 6, RKIT-A-0006 item 3).

## Acceptance Criteria

## Acceptance Criteria

## Acceptance Criteria

- [ ] `validateChange` rejects an operation missing any of `reason`, `linked_requirement_ids`, `linked_fact_ids`, `provenance` with a typed, per-field error code (not a generic failure); a fully populated grounded operation still validates.
- [ ] A status machine is enforced: legal transitions are exactly proposed→validated, validated→applied, validated→rejected, applied→accepted, applied→modified. Every illegal transition (e.g. proposed→applied, applied→rejected, rejected→anything, accepted→anything) raises/returns a typed invalid-transition error naming the from/to states.
- [ ] `applyChange` refuses non-`validated` operations (existing behavior preserved) AND refuses operations missing the mandatory fields above, even if their status claims `validated`.
- [ ] All five verbs — replace, rewrite, insert, remove, move — have apply semantics implemented and covered by unit tests, including path handling for each verb and idempotence/immutability properties already established in the lifecycle code.
- [ ] Chunk-1 residual (b) resolved: `validateFinalResume` filters/validates the status of the `applied_operations` it receives — only `applied` (or later accepted/modified) operations may contribute grounding; a `proposed` op in the list must not ground a claim. Behavior is documented and tested.
- [ ] New unit tests live in `tests/unit/` (resume-core tier); PR gate (`python3 tools/run_gate.py --pr --root .`) and smoke gate (`--smoke`) both green.
- [ ] No weakening of any existing assertion; protected files untouched, or edited strengthen-only under RKIT-A-0006 with the edit reported for Daniel's approve/update-locks commit.

## Implementation Notes

### Technical Approach

The operation DTO fields (`reason`, `linked_requirement_ids`, `linked_fact_ids`, `provenance`, six statuses, five verbs) were restored by RKIT-I-0001 (schemas.py) and structural `validateChange` exists (domain.py:435-519 at re-baseline). This task turns declared shape into enforced semantics: add the mandatory-field checks into `validateChange`, introduce an explicit transition table for the status machine (module-level constant, typed error on violation), thread the same checks into `applyChange`, and give each verb a deterministic apply implementation with tests. Then extend `validateFinalResume` to check operation status before grounding (residual (b) from chunk 1 — the trust-model decision is: final validation filters to applied/accepted/modified and raises a typed error on others).

### Dependencies

RKIT-I-0001 (DTO fields — done), RKIT-I-0002 (requirement/fact linkage the ops reference — done). No sibling-task blockers; this is the first task of the I-0004 serial chain.

### Risk Considerations

Downstream producers (resume-cli shims from I-0001 tech-debt, workflow) emit operations — tightening `validateChange` may break `--smoke` even when `--pr` is green. Run BOTH gates; if smoke breaks, fix the producer shims minimally (they already emit reason/provenance per HANDOFF §5) rather than weakening the check.

### Execution profile

Recommended Agent: opus + high

Rationale: status-machine and enforcement semantics are load-bearing for every later chunk (claim-level grounding consumes op status; the honesty gate consumes op fields); wrong choices here compound.

## Status Updates

- 2026-08-14: Task activated in continuous mode (session resuming from HANDOFF). Codex agent launched with binding decisions from the initiative's Detailed Design (transition table constant; final-validation filters to applied/accepted/modified with typed error otherwise; per-field error codes). Prompt at scratchpad t0034-prompt.md. Awaiting report; driver will review diff, independently probe the status machine, and run both gates before commit.
- 2026-08-14: Implementation complete in working tree. Added internal `resume_core.change_operations` lifecycle helper module with explicit transition table, mandatory-field validation, verb-specific apply semantics, and final-validation applied-operation status filtering. `domain.py` delegates lifecycle mechanics to keep resume-core guardrails green. Added `tests/unit/test_operation_lifecycle_enforcement.py`; strengthened existing unit/contract move fixtures for `from_path`; regenerated `fixtures/expected/rejected-operations.json` for the new mandatory-field errors. Verification green: PR gate 307 tests OK, smoke gate OK, unit discovery 94 tests OK, snapshot regeneration stable by repeated diff checksum. Straight Jacket still reports pre-existing checksum mismatches in protected `tools/pre-commit-resume-cli-guardrails.sh` and `tools/run_tests.py`; neither was edited in this task.