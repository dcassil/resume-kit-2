---
id: req-010c-redefine-future-contract
level: task
title: "REQ-010c: Redefine future-contract as distinct package-contract gate"
short_code: "RKIT-T-0018"
created_at: 2026-08-14T03:14:05.713153+00:00
updated_at: 2026-08-14T17:59:10.758768+00:00
parent: executable-release-gate-e2e
blocked_by: []
archived: false

tags:
  - "#task"
  - "#task"
  - "#phase/completed"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0051
---

# REQ-010c: Redefine future-contract as distinct package-contract gate

## Parent Initiative

[[RKIT-I-0051]]

## Objective

Resolve the orphaned `--future-contract` flag by redefining it as a genuinely distinct forward-looking package-contract gate rather than a vestigial alias of `--pr`. This task makes `--future-contract` run the extra package contracts that the current gate omits and pins its single canonical role in the docs, so the release path has a clear, non-overlapping distinction between the current gate and the full-package-contract gate.

## Acceptance Criteria

## Acceptance Criteria

## Acceptance Criteria

- [ ] `FUTURE_CONTRACT_TEST_MODULES` is no longer byte-identical to `CURRENT_TEST_MODULES` — it adds the package-contract targets that `--pr` omits (or, if retirement is chosen per the decision, `--future-contract` is removed from `run_gate.py`, `run_tests.py`, `suite_manifest.json`, and both docs).
- [ ] `python3 tools/run_gate.py --future-contract --root .` runs a demonstrably larger/different module set than `--pr` (captured in output).
- [ ] Docs state exactly one canonical current command (`--pr`) and describe `--future-contract`'s distinct role; no document names a conflicting canonical command.
- [ ] Protected files re-registered; verify passes; both `--pr` and `--future-contract` gates green.

## Implementation Notes

### Execution Profile

Recommended Agent: opus + medium

Codex-exec autonomously implementable: no — touches PROTECTED strengthen-only surfaces (`run_tests.py`, `run_gate.py`) with re-registration and cross-package contract blast radius, which requires reasoning judgment codex-exec should not exercise unsupervised.

### Technical Approach

APPROVED DECISION: redefine, do not retire. `--future-contract` becomes the distinct FULL package-contract gate. Concretely:

- Differentiate `FUTURE_CONTRACT_TEST_MODULES` from `CURRENT_TEST_MODULES` in `tools/run_tests.py`. They are currently identical lists — that byte-identical-ness is precisely the vestigial-ness the design flagged. Make `FUTURE_CONTRACT_TEST_MODULES` a genuine superset of `CURRENT_TEST_MODULES`, adding the package-contract targets that plain `--pr` omits, so `--future-contract` genuinely runs the extra package contracts. The `run_tests.py --future-contract` path already appends the package-contract targets; the fix is to make the module list reflect that so the two gates diverge.
- Keep `run_gate.py`'s `--future-contract` wiring; confirm/adjust its label so it reads as the forward-looking full-package-contract gate.
- Document in `tests/TEST_SPEC.md` and `PROJECT_STRUCTURE_AND_TEST_STRATEGY.md` that `--pr` is the canonical current gate and `--future-contract` is the forward-looking full-package-contract gate — one canonical current command, no conflicting canonical named elsewhere.

Binding constraint on PROTECTED files: `run_tests.py` and `run_gate.py` are strengthen-only. Any edit must widen/strengthen the gate (adding package contracts qualifies), never weaken it, and the touched protected files MUST be re-registered in `.straight-jacket/manifest.json`. The retirement alternative (removing `--future-contract` from `run_gate.py`/`run_tests.py`/`suite_manifest`/docs) is NOT the chosen path — see decisionsForHuman only if the team later reverses this.

### Files

- `tools/run_tests.py` (PROTECTED) — make `FUTURE_CONTRACT_TEST_MODULES` a genuine superset of `CURRENT_TEST_MODULES`; re-register.
- `tools/run_gate.py` (PROTECTED) — confirm/adjust `--future-contract` label; re-register if edited.
- `tests/TEST_SPEC.md` — clarify `--pr` canonical vs `--future-contract` full-package-contract role.
- `PROJECT_STRUCTURE_AND_TEST_STRATEGY.md` (NON-protected) — same clarification.
- `.straight-jacket/manifest.json` — re-register touched protected files.

### Dependencies

No task dependencies — startable once the initiative is active. Semantically, the package-contract targets added here belong to their owning package initiatives (any xfail'd package contracts should be owned there, not disabled in this gate wiring), and the gate role clarified here feeds the downstream executable release-gate work in RKIT-I-0004; keep this task's changes confined to `--future-contract` definition and docs so those consumers inherit a clean distinction.

### Risk Considerations

- Protected-surface / straight-jacket straight-jacket: `run_tests.py` and `run_gate.py` are strengthen-only. A weakening edit or a missed re-registration in `.straight-jacket/manifest.json` fails `straight-jacket verify`; every touched protected file must be re-registered.
- Cross-package blast radius: promoting `--future-contract` to run the full package contracts pulls additional package test modules into the gate; a not-yet-green or xfail'd package contract could turn the forward-looking gate red. Keep such failures owned by the package initiative rather than silencing them in the wiring.
- Determinism: the superset must be a stable, explicit module list so `--future-contract` produces a reproducible, demonstrably larger set than `--pr` on every run.
- Scope-boundary bleed: limit changes to the `--future-contract` definition, its `run_gate.py` label, and the two docs. Do not alter `--pr`'s current-gate contents or other suite definitions.

## Verification Steps

1. `python3 tools/run_gate.py --pr --root . 2>&1 | tee /tmp/pr.log; python3 tools/run_gate.py --future-contract --root . 2>&1 | tee /tmp/fc.log; diff <(grep -o 'tests\.[a-z_.]*' /tmp/pr.log|sort -u) <(grep -o 'tests\.[a-z_.]*' /tmp/fc.log|sort -u)` (must show fc superset).
2. `straight-jacket verify`
3. `python3 tools/run_gate.py --pr --root . && python3 tools/run_gate.py --future-contract --root .`

## Status Updates

*To be added during implementation*

- 2026-08-14: Implemented the redefine path. `tools/run_tests.py` now defines `FUTURE_CONTRACT_TEST_MODULES` as `CURRENT_TEST_MODULES` plus `tests.smoke.test_smoke_harness` and `tests.e2e.test_grounded_tailoring_final_validation`; `tools/run_gate.py` labels `--future-contract` as the forward-looking full package-contract superset. Updated `tests/TEST_SPEC.md`, `PROJECT_STRUCTURE_AND_TEST_STRATEGY.md`, and `tests/suite_manifest.json` to keep `--pr` as the only canonical current gate and describe `--future-contract` as distinct. Verification: `--pr` passed 257 tests, `--future-contract` passed 264 tests, and the import-time superset check reported `superset: True` with the two extra modules. Straight Jacket verify remains red because checksum updates were forbidden.